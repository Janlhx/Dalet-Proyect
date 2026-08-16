import discord
from discord.ext import commands
import asyncio
import time
import random
import logging
import traceback
import re

logger = logging.getLogger("dalet.handlers.nlp")

# --- Configuración de Comportamiento Proactivo ---
BASE_RESPONSE_RATE = 0.25  # 25% de probabilidad de responder
COOLDOWN_TIME = 45  # Segundos mínimos entre respuestas proactivas
MIN_MESSAGES_BETWEEN_REPLIES = 10  # Mensajes mínimos antes de considerar responder
MAX_MESSAGES_WINDOW = 30  # Ventana de reset si no respondió (más grande para dar espacio a la probabilidad)

# --- Configuración de Sesiones Reactive ---
REACTIVE_SESSION_MAX = 5       # Máx respuestas reactive por sesión/usuario
REACTIVE_SESSION_COOLDOWN = 8  # Minutos de cooldown post-sesión

# Frases de cierre cuando la sesión llega al límite
REACTIVE_CLOSING_PHRASES = [
    "ya, hasta aquí por ahora.",
    "ok ya fue, hablamos luego.",
    "me cansé un rato, vuelve después.",
    "suficiente por ahora.",
    "ya me agotaste, luego seguimos.",
    "hasta aquí llegué, vuelvo en un rato.",
]


from discord.ext import tasks


class DaletNLPChat(commands.Cog):
    """Maneja el listener 'on_message' para las respuestas de IA."""

    def __init__(self, bot):
        self.bot = bot
        self.last_reply_time = 0
        self.message_counter = 0
        self.active_user_responses = set()
        self.error_cooldown = 0
        self.consecutive_429s = 0

        # --- Rate Limiter (Token Bucket) ---
        self.guild_ratelimits = {}
        self.channel_ratelimits = {}
        self.user_ratelimits = {}

        # --- Sesiones Reactive (por usuario/servidor) ---
        self.reactive_sessions = {}

        # Iniciar tarea de limpieza de memoria en RAM (TTL)
        self.cleanup_task.start()

    def cog_unload(self):
        self.cleanup_task.cancel()

    @tasks.loop(hours=1)
    async def cleanup_task(self):
        """Limpia periódicamente dicts en RAM con más de 2 horas de inactividad."""
        now = time.time()
        ttl = 7200  # 2 horas

        # Limpiar ratelimits
        for g_id, (_, last) in list(self.guild_ratelimits.items()):
            if now - last > ttl:
                self.guild_ratelimits.pop(g_id, None)

        for c_id, (_, last) in list(self.channel_ratelimits.items()):
            if now - last > ttl:
                self.channel_ratelimits.pop(c_id, None)

        for u_id, (_, last) in list(self.user_ratelimits.items()):
            if now - last > ttl:
                self.user_ratelimits.pop(u_id, None)

        # Limpiar sesiones reactivas expiradas
        for key, data in list(self.reactive_sessions.items()):
            cooldown_until = data.get("cooldown_until", 0)
            if cooldown_until > 0 and now > cooldown_until + ttl:
                self.reactive_sessions.pop(key, None)

    def _check_rate_limit(self, guild_id: int, channel_id: int, user_id: int, priority: str = "mention") -> bool:
        """
        Aplica un rate limiter usando Token Bucket en 3 niveles (Guild -> Canal -> Usuario).
        - Level 1 Guild: máx 8 tokens, 1 token / 7.5s (8 por min).
        - Level 2 Canal: máx 5 tokens, 1 token / 12s (5 por min).
        - Level 3 Usuario: máx 3 tokens, 1 token / 20s.
        Triggers proactivos se rechazan si a la guild le quedan menos de 3 tokens.
        """
        now = time.time()

        # 1. Límite de Guild (Servidor)
        g_tokens, g_last = self.guild_ratelimits.get(guild_id, (8.0, now))
        g_elapsed = now - g_last
        g_tokens = min(8.0, g_tokens + g_elapsed * (1.0 / 7.5))
        self.guild_ratelimits[guild_id] = (g_tokens, now)

        if priority == "proactive" and g_tokens < 3.0:
            logger.debug(f"Proactividad omitida para proteger cuota de guild {guild_id}")
            return False

        if g_tokens < 1.0:
            logger.warning(f"Rate limit de Servidor excedido para {guild_id} (Tokens: {g_tokens:.2f})")
            return False

        # 2. Límite de Canal
        c_tokens, c_last = self.channel_ratelimits.get(channel_id, (5.0, now))
        c_elapsed = now - c_last
        c_tokens = min(5.0, c_tokens + c_elapsed * (1.0 / 12.0))
        self.channel_ratelimits[channel_id] = (c_tokens, now)

        if c_tokens < 1.0:
            logger.warning(
                f"Rate limit excedido para canal {channel_id} (Tokens: {c_tokens:.2f})"
            )
            return False

        # 3. Límite de Usuario
        u_tokens, u_last = self.user_ratelimits.get(user_id, (3.0, now))
        u_elapsed = now - u_last
        u_tokens = min(3.0, u_tokens + u_elapsed * (1.0 / 20.0))
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
        Retorna:
          'ok'      → responder normalmente
          'last'    → último mensaje permitido, enviar frase de cierre e iniciar cooldown
          'blocked' → usuario en cooldown, ignorar
        """
        now = time.time()
        key = (guild_id, user_id)
        session = self.reactive_sessions.get(key)

        if session is not None:
            cooldown_until = session.get("cooldown_until", 0)

            if cooldown_until > now:
                # En cooldown activo
                return "blocked"

            if cooldown_until > 0:
                # Cooldown expirado → resetear sesión
                self.reactive_sessions[key] = {"count": 1, "cooldown_until": 0}
                return "ok"

            # Sesión activa sin cooldown — incrementar contador
            session["count"] += 1
            if session["count"] >= REACTIVE_SESSION_MAX:
                session["cooldown_until"] = now + REACTIVE_SESSION_COOLDOWN * 60
                return "last"
            return "ok"

        # Sesión nueva
        self.reactive_sessions[key] = {"count": 1, "cooldown_until": 0}
        if REACTIVE_SESSION_MAX <= 1:
            self.reactive_sessions[key]["cooldown_until"] = now + REACTIVE_SESSION_COOLDOWN * 60
            return "last"
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

    def _should_respond(self) -> bool:
        """Decide si el bot debe responder proactivamente en este mensaje."""
        self.message_counter += 1

        now = time.time()
        if now - self.last_reply_time < COOLDOWN_TIME:
            return False

        # Si ya pasamos la ventana de reset, reiniciamos el contador de mensajes
        if self.message_counter > MAX_MESSAGES_WINDOW:
            self.message_counter = 1

        if (
            self.message_counter >= MIN_MESSAGES_BETWEEN_REPLIES
            and random.random() < BASE_RESPONSE_RATE
        ):
            return True

        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        content_lower = message.content.lower().strip()

        # --- Respuesta prioritaria a "dalet on" / "dalet, on" ---
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

        # --- Guardado de Memoria Explícita ---
        if "recuerda que" in content_lower or "mi nombre es" in content_lower:
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

            # ¿Mencionaron al bot o dijeron su nombre?
            name_mentioned = (
                self.bot.user.mentioned_in(message)
                or "dalet" in content_lower
                or custom_name.lower() in content_lower
            )

            if name_mentioned:
                # Verificar si tiene activada la reactividad en el servidor
                is_reactive = False
                try:
                    is_reactive = await self.bot.user_repo.is_server_reactive(
                        message.guild.id
                    )
                except Exception:
                    pass

                if not is_reactive:
                    # Si no es reactivo el servidor, ignoramos la mención silenciosamente
                    return

                # Verificar sesión reactive del usuario
                session_status = self._check_reactive_session(
                    message.guild.id, message.author.id
                )
                if session_status == "blocked":
                    return
                if session_status == "last":
                    # Último mensaje permitido — cerrar con frase ácida
                    phrase = random.choice(REACTIVE_CLOSING_PHRASES)
                    try:
                        await message.reply(phrase)
                    except discord.HTTPException as e:
                        if e.status == 429:
                            await self._handle_429(e, "session_closing")
                    return

                # Aplicar Rate Limit a menciones
                if not self._check_rate_limit(message.guild.id, message.channel.id, message.author.id, priority="mention"):
                    return

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

            if is_proactive and self._should_respond():
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
            # Recopilar imágenes adjuntas o en embeds
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

            # También revisar imagen del mensaje al que se responde (reply)
            if not image_urls and message.reference and message.reference.resolved:
                ref = message.reference.resolved
                if isinstance(ref, discord.Message):
                    for att in ref.attachments:
                        if any(
                            att.filename.lower().endswith(ext)
                            for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")
                        ):
                            image_urls.append(att.url)

            image_urls = list(dict.fromkeys(image_urls))[:1]  # Solo 1 imagen

            # Limpiar menciones y nombre del bot del contenido
            clean_content = re.sub(r"<@!?\d+>", "", message.content)
            clean_content = re.compile(re.escape("dalet"), re.IGNORECASE).sub(
                "", clean_content
            )
            if custom_name := bot_name if bot_name.lower() != "dalet" else None:
                clean_content = re.compile(re.escape(custom_name), re.IGNORECASE).sub(
                    "", clean_content
                )
            clean_content = clean_content.strip() or message.content

            # Obtener contexto de conversación del canal
            context = await self.bot.memory_service.get_relevant_context(
                message.channel.id, message.author.id, clean_content
            )

            # Lista ligera de miembros activos en el canal
            members_list = [
                m.display_name for m in message.channel.members if not m.bot
            ][:8]
            active_users = ", ".join(members_list)

            # Generar respuesta (máx 2 en paralelo en todo el bot)
            async with self.bot.discord_semaphore:
                try:
                    async with message.channel.typing():
                        reply = await self.bot.nlp_service.generate_reply(
                            clean_content,
                            context,
                            message.author.display_name,
                            bot_name=bot_name,
                            image_urls=image_urls,
                            user_id=message.author.id,
                            channel_id=message.channel.id,
                            active_room_users=active_users,
                            is_reactive=is_reactive,
                        )
                except discord.HTTPException as e:
                    if e.status == 429:
                        await self._handle_429(e, "typing")
                        return
                    # Si falla el typing (permisos), intentar sin él
                    try:
                        reply = await self.bot.nlp_service.generate_reply(
                            clean_content,
                            context,
                            message.author.display_name,
                            bot_name=bot_name,
                            image_urls=image_urls,
                            user_id=message.author.id,
                            channel_id=message.channel.id,
                            active_room_users=active_users,
                            is_reactive=is_reactive,
                        )
                    except Exception as e:
                        logger.error(f"Error llamando nlp_service (sin typing): {e}")
                        reply = None
                except Exception as e:
                    logger.error(f"Error llamando nlp_service: {e}")
                    reply = None

            if reply:
                try:
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

                except discord.HTTPException as e:
                    if e.status == 429:
                        await self._handle_429(e, "send_message")
                    else:
                        logger.error(f"Error HTTP enviando mensaje: {e}")

            if not is_direct_mention:
                self.last_reply_time = time.time()
                self.message_counter = 0

        except Exception as e:
            logger.error(f"Error generando respuesta: {e}")
            traceback.print_exc()
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
