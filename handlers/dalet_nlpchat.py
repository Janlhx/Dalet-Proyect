import logging
import random
import re
import time
import asyncio

try:
    from cachetools import TTLCache
except ImportError:
    class TTLCache(dict):  # Fallback ligero para entornos de CI/tests sin cachetools
        def __init__(self, maxsize=1000, ttl=3600, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.maxsize = maxsize
            self.ttl = ttl

import discord
from discord.ext import commands

logger = logging.getLogger("dalet.handlers.nlp")

# Configuración de comportamiento proactivo y reactivo
BASE_RESPONSE_RATE = 0.30  # Probabilidad base de intervenir proactivamente al cumplir umbral
COOLDOWN_TIME = 45         # Segundos mínimos entre intervenciones proactivas por canal
MIN_MESSAGES_BETWEEN_REPLIES = 6
MAX_MESSAGES_WINDOW = 20
REACTIVE_SESSION_MAX = 12
REACTIVE_SESSION_COOLDOWN = 2


class DaletNLPChat(commands.Cog):
    """Maneja el procesamiento de lenguaje natural y respuestas conversacionales en Discord."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_reply_time = 0.0
        self.message_counter = 0
        self.active_user_responses: set[int] = set()
        self.error_cooldown = 0.0
        self.consecutive_429s = 0

        # Rate Limiting & Sesiones gestionadas con TTLCache (O(1), thread-safe, auto-expiración)
        self.guild_ratelimits: TTLCache = TTLCache(maxsize=1000, ttl=7200)
        self.channel_ratelimits: TTLCache = TTLCache(maxsize=2000, ttl=7200)
        self.user_ratelimits: TTLCache = TTLCache(maxsize=5000, ttl=7200)
        self.reactive_sessions: TTLCache = TTLCache(maxsize=2000, ttl=7200)
        self.recent_user_messages: TTLCache = TTLCache(maxsize=5000, ttl=300)
        self.proactive_channels: TTLCache = TTLCache(maxsize=2000, ttl=7200)

    async def cog_load(self):
        try:
            if hasattr(self.bot, "user_repo") and self.bot.user_repo:
                await self.bot.user_repo.ensure_memories_schema()
        except Exception as e:
            logger.debug(f"Error asegurando esquema de memorias: {e}")

    def _check_rate_limit(self, guild_id: int, channel_id: int, user_id: int, priority: str = "mention") -> bool:
        """
        Aplica un rate limiter usando Token Bucket en 3 niveles (Guild -> Canal -> Usuario).
        Límites calibrados para proteger contra abusos y ráfagas de spam:
        - Level 1 Guild: máx 25 tokens, 1 token / 2.0s (~30 por min).
        - Level 2 Canal: máx 15 tokens, 1 token / 3.0s (~20 por min).
        - Level 3 Usuario: máx 3 tokens de ráfaga, 1 token / 5.0s (~12 por min).
        """
        now = time.time()

        # 1. Límite de Guild (Servidor)
        g_tokens, g_last = self.guild_ratelimits.get(guild_id, (25.0, now))
        g_elapsed = now - g_last
        g_tokens = min(25.0, g_tokens + g_elapsed * (1.0 / 2.0))
        self.guild_ratelimits[guild_id] = (g_tokens, now)

        if priority == "proactive" and g_tokens < 5.0:
            logger.debug(f"Proactividad omitida para proteger cuota de guild {guild_id}")
            return False

        if g_tokens < 1.0:
            logger.warning(f"Rate limit de Servidor excedido para {guild_id} (Tokens: {g_tokens:.2f})")
            return False

        # 2. Límite de Canal
        c_tokens, c_last = self.channel_ratelimits.get(channel_id, (15.0, now))
        c_elapsed = now - c_last
        c_tokens = min(15.0, c_tokens + c_elapsed * (1.0 / 3.0))
        self.channel_ratelimits[channel_id] = (c_tokens, now)

        if c_tokens < 1.0:
            logger.warning(
                f"Rate limit excedido para canal {channel_id} (Tokens: {c_tokens:.2f})"
            )
            return False

        # 3. Límite de Usuario (máx 3 tokens de ráfaga, recarga 1 token / 5s)
        u_tokens, u_last = self.user_ratelimits.get(user_id, (3.0, now))
        u_elapsed = now - u_last
        u_tokens = min(3.0, u_tokens + u_elapsed * (1.0 / 5.0))
        self.user_ratelimits[user_id] = (u_tokens, now)

        if u_tokens < 1.0:
            logger.warning(
                f"Rate limit excedido para usuario {user_id} (Tokens: {u_tokens:.2f})"
            )
            return False

        # Consumir un token de cada nivel
        self.guild_ratelimits[guild_id] = (g_tokens - 1.0, now)
        self.channel_ratelimits[channel_id] = (c_tokens - 1.0, now)
        self.user_ratelimits[user_id] = (u_tokens - 1.0, now)
        return True

    def _check_reactive_session(self, guild_id: int, user_id: int) -> str:
        """
        Controla las sesiones reactive por usuario/servidor.
        Conversación continua y natural sin interrupciones arbitrarias.
        """
        now = time.time()
        key = (guild_id, user_id)
        session = self.reactive_sessions.get(key)

        if session is not None:
            cooldown_until = session.get("cooldown_until", 0)
            if cooldown_until > now:
                return "blocked"

            if cooldown_until > 0:
                self.reactive_sessions[key] = {"count": 1, "cooldown_until": 0}
                return "ok"

            session["count"] += 1
            if session["count"] >= REACTIVE_SESSION_MAX:
                session["cooldown_until"] = now + REACTIVE_SESSION_COOLDOWN * 60
                return "blocked"
            return "ok"

        self.reactive_sessions[key] = {"count": 1, "cooldown_until": 0}
        return "ok"

    async def _handle_429(self, exception, source="unknown"):
        """Centraliza el manejo de errores 429 con backoff exponencial."""
        self.bot.global_consecutive_429s += 1
        self.consecutive_429s = self.bot.global_consecutive_429s

        is_hard_limit = "1015" in str(exception) or "Cloudflare" in str(exception)

        if is_hard_limit:
            wait_secs = min(180 * (2 ** (self.consecutive_429s - 1)), 1800)
            logger.error(
                f"HARD Rate Limit (Cloudflare 1015) en {source}. Throttle: {wait_secs}s"
            )
        else:
            wait_secs = min(30 * (2 ** (self.consecutive_429s - 1)), 600)
            logger.warning(f"Discord 429 en {source}. Throttle: {wait_secs}s")

        self.error_cooldown = time.time() + wait_secs
        self.bot.global_error_cooldown = self.error_cooldown

        try:
            await self.bot.analytics_repo.log_error(
                "discord_429_hard" if is_hard_limit else "discord_429",
                f"Source: {source}. Throttle: {wait_secs}s. Consecutivos: {self.consecutive_429s}",
                f"dalet_nlpchat.{source}",
                None,
            )
        except Exception:
            pass

        return wait_secs

    @staticmethod
    def _is_meaningful_proactive_message(content: str) -> bool:
        """
        Verifica si un mensaje tiene suficiente sustancia conversacional para que valga
        la pena evaluarlo en modo proactivo (descarta monosílabos, risas sueltas o links puros).
        """
        if not content:
            return False

        # Limpiar menciones, emojis custom y URLs
        cleaned = re.sub(r"<@!?\d+>|<a?:[a-zA-Z0-9_]+:\d+>|https?://\S+", "", content).strip()
        if len(cleaned) < 12:
            return False

        words = [w for w in cleaned.split() if len(w) > 1]
        if len(words) < 3:
            return False

        # Descartar si es únicamente risa repetida (ej. "jajajaja xd lol")
        filler_pattern = r"^(?:(?:ja)+|(?:je)+|xd+|lol+|lmao+|ok+|si+|sí+|no+|wtf+|\?+|!+|\s+)+$"
        if re.match(filler_pattern, cleaned, flags=re.IGNORECASE):
            return False

        return True

    def _should_respond(self, channel_id: int = 0, content: str = "") -> bool:
        """
        Decide si el bot debe evaluar una intervención proactiva en este canal.
        Mantiene estado aislado por canal (O(1) en TTLCache) y exige que el mensaje
        tenga sustancia conversacional antes de invocar al LLM.
        """
        now = time.time()
        state = self.proactive_channels.get(channel_id)
        if state is None:
            state = {"count": 0, "last_reply_time": self.last_reply_time}

        state["count"] += 1
        self.message_counter = state["count"]
        self.proactive_channels[channel_id] = state

        if now - state["last_reply_time"] < COOLDOWN_TIME:
            return False

        if state["count"] < MIN_MESSAGES_BETWEEN_REPLIES:
            return False

        # Si se pasó el texto del mensaje y es trivial/corto, mantener el contador alto
        # para evaluar el siguiente mensaje con contenido real en el canal.
        if content and not self._is_meaningful_proactive_message(content):
            return False

        # Si ya alcanzamos el tope de la ventana, disparo garantizado sobre este mensaje con sustancia
        if state["count"] >= MAX_MESSAGES_WINDOW:
            return True

        # Probabilidad progresiva: sube desde BASE_RESPONSE_RATE hacia 1.0 a medida que avanza la ventana
        progress = (state["count"] - MIN_MESSAGES_BETWEEN_REPLIES) / max(
            1, MAX_MESSAGES_WINDOW - MIN_MESSAGES_BETWEEN_REPLIES
        )
        dynamic_prob = BASE_RESPONSE_RATE + (1.0 - BASE_RESPONSE_RATE) * (progress * 0.5)
        return random.random() < dynamic_prob

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        content_lower = message.content.lower().strip()

        # Respuesta prioritaria de estado de conexión
        if content_lower in ("dalet on", "dalet, on", "dale on"):
            logger.info(f"Trigger 'dalet on' en #{message.channel.name}")
            try:
                await message.channel.send("estoy on")
            except discord.HTTPException as e:
                logger.error(f"Error respondiendo 'dalet on': {e}")
            return

        # Ignorar comandos del bot y prefijos comunes de otros bots
        if message.content.startswith(
            ("d.", "D.", "!", "/", ".", "?", "$", ">", "-", "+")
        ):
            return

        # Throttling por rate limits previos
        if time.time() < self.error_cooldown:
            return

        # Guardado de memoria explícita (soporte multilenguaje ES y EN)
        memory_triggers = ("recuerda que", "remember that", "mi nombre es", "my name is")
        if any(trig in content_lower for trig in memory_triggers):
            try:
                await self.bot.memory_service.add_memory(
                    message.author.id, str(message.author.display_name), message.content
                )
                try:
                    await message.add_reaction("✅")
                except discord.HTTPException as e:
                    if e.status == 429:
                        await self._handle_429(e, "reaction")
            except Exception as e:
                logger.error(f"Error guardando memoria: {e}")

        # --- Lógica de Decisión de Respuesta ---
        try:
            # Nombre personalizado del servidor (con fallback seguro)
            custom_name = "Dalet"
            try:
                custom_name = await self.bot.admin_repo.get_server_custom_name(
                    message.guild.id
                )
            except Exception:
                pass

            if custom_name == "Dalet" and message.guild and message.guild.me and message.guild.me.nick:
                custom_name = message.guild.me.nick

            # ¿Mencionaron al bot o dijeron su nombre?
            name_mentioned = (
                self.bot.user.mentioned_in(message)
                or "dalet" in content_lower
                or custom_name.lower() in content_lower
            )

            if name_mentioned:
                # Verificar si tiene activada la reactividad en el servidor
                is_reactive = True  # fallback: si la DB falla, responder igualmente
                try:
                    is_reactive = await self.bot.user_repo.is_server_reactive(
                        message.guild.id
                    )
                except Exception:
                    pass  # DB no disponible → asumir reactivo para no silenciar al bot

                if not is_reactive:
                    # El servidor tiene la reactividad explícitamente desactivada
                    return

                # Verificar sesión reactive (anti-spam básico)
                if self._check_reactive_session(message.guild.id, message.author.id) == "blocked":
                    return

                # Aplicar Rate Limit a menciones
                if not self._check_rate_limit(message.guild.id, message.channel.id, message.author.id, priority="mention"):
                    return

                # Anti-Spam Debounce: Evitar llamadas idénticas consecutivas del mismo usuario en <10s
                now = time.time()
                last_msg, last_time = self.recent_user_messages.get(message.author.id, ("", 0.0))
                clean_probe = content_lower.strip()
                if last_msg and clean_probe == last_msg and (now - last_time) < 10.0:
                    try:
                        canned = random.choice([
                            "ya te leí, no hace falta que me repitas lo mismo.",
                            "no soy sorda, con una vez que lo digas es suficiente.",
                            "¿crees que por repetirlo te voy a contestar más rápido? paciencia.",
                        ])
                        await message.channel.send(canned)
                    except Exception:
                        pass
                    return

                self.recent_user_messages[message.author.id] = (clean_probe, now)

                trigger_type = (
                    "mention" if self.bot.user.mentioned_in(message) else "name_trigger"
                )
                return await self.generate_response(
                    message,
                    is_direct_mention=True,
                    trigger_type=trigger_type,
                    bot_name=custom_name,
                    is_reactive=True,
                )

            # ¿El canal tiene modo proactivo activo?
            is_proactive = False
            try:
                is_proactive = await self.bot.user_repo.is_channel_proactive(
                    message.channel.id
                )
            except Exception as e:
                logger.debug(f"Error consultando proactividad (usando False): {e}")

            # Si el mensaje menciona a OTRO bot (ej. Sengo, Mudae), no meterse en modo proactivo
            mentions_other_bot = any(
                getattr(m, "bot", False) and (not self.bot.user or m.id != self.bot.user.id)
                for m in getattr(message, "mentions", [])
            )
            if mentions_other_bot:
                return

            if is_proactive and self._should_respond(message.channel.id, message.content):
                # Aplicar Rate Limit también a proactividad por seguridad
                if not self._check_rate_limit(message.guild.id, message.channel.id, self.bot.user.id, priority="proactive"):
                    return

                await self.generate_response(
                    message,
                    is_direct_mention=False,
                    trigger_type="proactive",
                    bot_name=custom_name,
                )
        except Exception as e:
            logger.error(f"Error procesando on_message en DaletNLPChat: {e}")

    async def generate_response(
        self,
        message: discord.Message,
        is_direct_mention: bool,
        trigger_type: str = "mention",
        bot_name: str = "Dalet",
        is_reactive: bool = False,
    ):
        user_id = message.author.id
        if user_id in self.active_user_responses:
            return

        if time.time() < self.error_cooldown:
            if is_direct_mention:
                logger.warning(
                    "Throttling activo por 429 previos. Ignorando respuesta."
                )
            return

        self.active_user_responses.add(user_id)
        try:
            # Recopilar imágenes adjuntas o en embeds del propio mensaje actual
            image_urls = []
            if message.attachments:
                for att in message.attachments:
                    if att.content_type and att.content_type.startswith("image/"):
                        image_urls.append(att.url)
                    elif any(
                        att.filename.lower().endswith(ext)
                        for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")
                    ):
                        image_urls.append(att.url)

            if message.embeds:
                for embed in message.embeds:
                    if embed.image and embed.image.url:
                        image_urls.append(embed.image.url)

            # También revisar imagen y contenido del mensaje al que se responde (reply)
            ref_summary = ""
            if message.reference:
                ref = message.reference.resolved
                if not isinstance(ref, discord.Message) and message.reference.message_id:
                    try:
                        ref = await message.channel.fetch_message(message.reference.message_id)
                    except Exception as e:
                        logger.debug(f"No se pudo resolver mensaje de referencia: {e}")

                if isinstance(ref, discord.Message):
                    # En modo proactivo, si el usuario le está haciendo Reply a OTRO bot (ej. Sengo), no meterse
                    if not is_direct_mention and getattr(ref.author, "bot", False) and ref.author != self.bot.user:
                        return

                    # Solo heredar imágenes del mensaje referenciado cuando el usuario menciona/habla con Dalet directamente
                    if is_direct_mention and not image_urls:
                        for att in ref.attachments:
                            if any(
                                att.filename.lower().endswith(ext)
                                for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")
                            ):
                                image_urls.append(att.url)

                    # Extraer texto y/o contenido de Embeds del mensaje al que se responde
                    if ref.author == self.bot.user:
                        if ref.embeds:
                            emb = ref.embeds[0]
                            parts = []
                            if emb.title:
                                parts.append(f"Título: {emb.title}")
                            if emb.description:
                                parts.append(f"Descripción: {emb.description}")
                            for f in emb.fields[:5]:
                                parts.append(f"{f.name}: {f.value}")
                            ref_summary = f"[El usuario te está respondiendo directamente a este Embed que enviaste tú ({bot_name}): {' | '.join(parts)}]"
                        elif ref.content:
                            ref_summary = f"[El usuario te está respondiendo directamente a tu mensaje anterior: \"{ref.content}\"]"
                    elif is_direct_mention:
                        if ref.embeds:
                            emb = ref.embeds[0]
                            parts = []
                            if emb.title: parts.append(f"Título: {emb.title}")
                            if emb.description: parts.append(f"Descripción: {emb.description}")
                            for f in emb.fields[:3]: parts.append(f"{f.name}: {f.value}")
                            ref_summary = f"[El usuario te responde en referencia a este Embed de {ref.author.display_name}: {' | '.join(parts)}]"
                        elif ref.content:
                            ref_summary = f"[El usuario está respondiendo al mensaje de {ref.author.display_name}: \"{ref.content}\"]"
                    else:
                        if ref.content:
                            ref_summary = (
                                f"[Contexto del hilo: {message.author.display_name} le está respondiendo al mensaje de "
                                f"{ref.author.display_name} (\"{ref.content}\"), NO a ti]"
                            )

            # Si el usuario mencionó a Dalet sin usar Reply explícito pero pregunta por 'mi top', 'mis skills', etc.,
            # recuperar el Embed más reciente enviado por Dalet en el canal (solo en mención directa)
            if is_direct_mention and not ref_summary:
                trigger_probes = (
                    "opina", "opinas", "qué tal", "que tal", "mi top", "este top",
                    "mi play", "mi jugada", "mis skills", "mi perfil", "eso", "esto",
                    "mira mi", "cómo ves", "como ves", "qué te parece", "que te parece",
                    "cómo juego", "como juego", "mi rendimiento", "califica mi", "critica mi",
                    "qué opinas de mi", "que opinas de mi", "cómo me ves", "como me ves"
                )
                if any(p in message.content.lower() for p in trigger_probes):
                    try:
                        async for prev_msg in message.channel.history(limit=6, before=message):
                            if prev_msg.author == self.bot.user and prev_msg.embeds:
                                emb = prev_msg.embeds[0]
                                parts = []
                                if emb.title: parts.append(f"Título: {emb.title}")
                                if emb.description: parts.append(f"Descripción: {emb.description}")
                                for f in emb.fields[:5]: parts.append(f"{f.name}: {f.value}")
                                ref_summary = f"[Contexto visual reciente en este canal: Hace un momento enviaste tú ({bot_name}) este Embed: {' | '.join(parts)}]"
                                break
                    except Exception as e:
                        logger.debug(f"Error consultando historial reciente de embeds: {e}")

            image_urls = list(dict.fromkeys(image_urls))[:1]  # Solo 1 imagen

            # Normalizar menciones numéricas de Discord a nombres reales para que la IA entienda a quién se refieren
            clean_content = message.content
            if self.bot.user:
                clean_content = re.sub(rf"<@!?{self.bot.user.id}>", f"@{bot_name}", clean_content)
            for mentioned_user in getattr(message, "mentions", []):
                if self.bot.user and mentioned_user.id == self.bot.user.id:
                    continue
                m_label = f"@{mentioned_user.display_name} [BOT]" if getattr(mentioned_user, "bot", False) else f"@{mentioned_user.display_name}"
                clean_content = re.sub(rf"<@!?{mentioned_user.id}>", m_label, clean_content)
            # Reemplazar menciones restantes sin resolver por '@usuario'
            clean_content = re.sub(r"<@!?\d+>", "@usuario", clean_content)
            clean_content = clean_content.strip() or message.content
            # Truncado de seguridad para evitar muros de texto abusivos (máx 400 caracteres)
            if len(clean_content) > 400:
                clean_content = clean_content[:400] + "..."

            # Obtener contexto de conversación del canal (con autoría de bot normalizada y memorias reflexivas)
            context = await self.bot.memory_service.get_relevant_context(
                message.channel.id,
                message.author.id,
                clean_content,
                bot_id=self.bot.user.id if self.bot.user else None,
                bot_name=bot_name,
                user_name=message.author.display_name,
            )

            if ref_summary:
                context = f"{ref_summary}\n\n{context}" if context else ref_summary

            # Inyectar miembros activos solo si es contextualmente relevante
            active_users = ""
            content_lower_probe = clean_content.lower()
            if any(k in content_lower_probe for k in ("quién", "quien", "gente", "todos", "alguien", "sala", "canal")):
                members_list = [
                    m.display_name for m in message.channel.members if not m.bot
                ][:6]
                active_users = ", ".join(members_list)

            # Obtener idioma configurado del servidor (default: 'en')
            server_lang = "en"
            if message.guild:
                try:
                    server_lang = await self.bot.admin_repo.get_server_language(message.guild.id)
                except Exception:
                    server_lang = "en"

            is_proactive_turn = trigger_type == "proactive"

            # Generar respuesta con protección de timeout estricto (máx 25s)
            # En modo proactivo evitamos mostrar "Dalet está escribiendo..." antes de saber
            # si el modelo eligió [PASS] o solo reaccionar con un emoji.
            async with self.bot.discord_semaphore:
                try:
                    if is_direct_mention:
                        async with message.channel.typing():
                            raw_reply = await asyncio.wait_for(
                                self.bot.nlp_service.generate_reply(
                                    clean_content,
                                    context,
                                    message.author.display_name,
                                    bot_name=bot_name,
                                    image_urls=image_urls,
                                    user_id=message.author.id,
                                    channel_id=message.channel.id,
                                    active_room_users=active_users,
                                    is_reactive=is_reactive,
                                    language=server_lang,
                                    allow_reactions=True,
                                    is_proactive=False,
                                ),
                                timeout=25.0
                            )
                    else:
                        raw_reply = await asyncio.wait_for(
                            self.bot.nlp_service.generate_reply(
                                clean_content,
                                context,
                                message.author.display_name,
                                bot_name=bot_name,
                                image_urls=image_urls,
                                user_id=message.author.id,
                                channel_id=message.channel.id,
                                active_room_users=active_users,
                                is_reactive=is_reactive,
                                language=server_lang,
                                allow_reactions=True,
                                is_proactive=is_proactive_turn,
                            ),
                            timeout=20.0
                        )
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout generando respuesta para {message.author.display_name}")
                    raw_reply = None
                except discord.HTTPException as e:
                    if e.status == 429:
                        await self._handle_429(e, "typing")
                        return
                    try:
                        raw_reply = await asyncio.wait_for(
                            self.bot.nlp_service.generate_reply(
                                clean_content,
                                context,
                                message.author.display_name,
                                bot_name=bot_name,
                                image_urls=image_urls,
                                user_id=message.author.id,
                                channel_id=message.channel.id,
                                active_room_users=active_users,
                                is_reactive=is_reactive,
                                language=server_lang,
                                allow_reactions=True,
                                is_proactive=is_proactive_turn,
                            ),
                            timeout=20.0
                        )
                    except Exception as e:
                        logger.error(f"Error llamando nlp_service (sin typing): {e}")
                        raw_reply = None
                except Exception as e:
                    logger.error(f"Error llamando nlp_service: {e}")
                    raw_reply = None

            from services.nlp_service import NLPService
            reply, reaction_emoji = NLPService.extract_reaction(raw_reply or "")

            # 1. Aplicar reacción con emoji si Dalet decidió reaccionar al mensaje
            if reaction_emoji:
                try:
                    await message.add_reaction(reaction_emoji)
                    self.consecutive_429s = 0
                    self.bot.global_consecutive_429s = 0
                except discord.HTTPException as e:
                    if e.status == 429:
                        await self._handle_429(e, "reaction")
                    else:
                        logger.debug(f"No se pudo agregar reacción '{reaction_emoji}': {e}")
                except Exception as e:
                    logger.debug(f"Error aplicando reacción '{reaction_emoji}': {e}")

            # 2. Enviar respuesta de texto si hay contenido verbal (usando Reply nativo sin @ping)
            if reply:
                try:
                    if hasattr(message, "reply"):
                        try:
                            await message.reply(reply, mention_author=False)
                        except discord.HTTPException as e_rep:
                            if e_rep.status == 429:
                                raise
                            await message.channel.send(reply)
                    else:
                        await message.channel.send(reply)
                    self.consecutive_429s = 0
                    self.bot.global_consecutive_429s = 0

                    # Guardar respuesta en SQLite/Buffer para tener el contexto cronológico perfecto
                    await self.bot.user_repo.log_message(
                        self.bot.user.id,
                        bot_name,
                        message.guild.id,
                        str(message.guild.name),
                        message.channel.id,
                        str(message.channel.name),
                        reply.strip(),
                    )

                    # Log asíncrono no-bloqueante
                    asyncio.create_task(
                        self._log_interaction(
                            message,
                            trigger_type,
                            getattr(self.bot.nlp_service, "active_provider", "gemini"),
                            reply,
                        )
                    )

                    # Iniciar análisis reflexivo de recuerdos en segundo plano (asíncrono, 0 lag al usuario)
                    if hasattr(self.bot, "memory_service") and self.bot.memory_service:
                        asyncio.create_task(
                            self.bot.memory_service.analyze_and_record_memory(
                                user_id=message.author.id,
                                user_name=message.author.display_name,
                                user_message=clean_content,
                                dalet_reply=reply.strip(),
                                nlp_service=self.bot.nlp_service,
                            )
                        )

                except discord.HTTPException as e:
                    if e.status == 429:
                        await self._handle_429(e, "send_message")
                    else:
                        logger.error(f"Error HTTP enviando mensaje: {e}")

            if not is_direct_mention:
                now_ts = time.time()
                if reply or reaction_emoji:
                    self.last_reply_time = now_ts
                    self.message_counter = 0
                    self.proactive_channels[message.channel.id] = {
                        "count": 0,
                        "last_reply_time": now_ts,
                    }
                else:
                    # Si eligió [PASS], hacer una pausa breve antes de volver a evaluar el canal
                    self.proactive_channels[message.channel.id] = {
                        "count": MIN_MESSAGES_BETWEEN_REPLIES // 2,
                        "last_reply_time": now_ts - (COOLDOWN_TIME // 2),
                    }

        except Exception as e:
            logger.error(f"Error generando respuesta: {e}", exc_info=True)
        finally:
            self.active_user_responses.discard(user_id)


    async def _log_interaction(
        self, message: discord.Message, trigger_type: str, provider: str, reply: str
    ):
        """Registra la interacción de IA en BD de forma no-bloqueante."""
        try:
            await self.bot.analytics_repo.log_ai_interaction(
                message.guild.id, message.channel.id, trigger_type, provider, 0, True
            )
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(DaletNLPChat(bot))
