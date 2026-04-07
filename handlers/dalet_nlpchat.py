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
BASE_RESPONSE_RATE = 0.25          # 25% de probabilidad de responder
COOLDOWN_TIME = 45                 # Segundos mínimos entre respuestas proactivas
MIN_MESSAGES_BETWEEN_REPLIES = 10  # Mensajes mínimos antes de considerar responder
MAX_MESSAGES_WINDOW = 10           # Ventana de reset si no respondió


class DaletNLPChat(commands.Cog):
    """Maneja el listener 'on_message' para las respuestas de IA."""

    def __init__(self, bot):
        self.bot = bot
        self.last_reply_time = 0
        self.message_counter = 0
        self.is_responding = False
        self.error_cooldown = 0
        self.consecutive_429s = 0

    async def _handle_429(self, exception, source="unknown"):
        """Centraliza el manejo de errores 429 con backoff exponencial."""
        self.bot.global_consecutive_429s += 1
        self.consecutive_429s = self.bot.global_consecutive_429s

        is_hard_limit = "1015" in str(exception) or "Cloudflare" in str(exception)

        if is_hard_limit:
            wait_secs = min(180 * (2 ** (self.consecutive_429s - 1)), 1800)
            logger.error(f"HARD Rate Limit (Cloudflare 1015) en {source}. Throttle: {wait_secs}s")
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
                None
            )
        except Exception:
            pass

        return wait_secs

    def _should_respond(self) -> bool:
        """Decide si el bot debe responder proactivamente en este mensaje."""
        if self.is_responding:
            return False

        self.message_counter += 1

        # Si superamos la ventana sin responder, reset silencioso
        if self.message_counter > MAX_MESSAGES_WINDOW:
            self.message_counter = 0
            return False

        now = time.time()
        if now - self.last_reply_time < COOLDOWN_TIME:
            return False

        if (self.message_counter >= MIN_MESSAGES_BETWEEN_REPLIES
                and random.random() < BASE_RESPONSE_RATE):
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
        if message.content.startswith(("d.", "D.", "!", "/", ".", "?", "$", ">", "-", "+")):
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
                custom_name = await self.bot.admin_repo.get_server_custom_name(message.guild.id)
            except Exception:
                pass

            # ¿Mencionaron al bot o dijeron su nombre?
            name_mentioned = (
                self.bot.user.mentioned_in(message)
                or "dalet" in content_lower
                or custom_name.lower() in content_lower
            )

            if name_mentioned:
                trigger_type = "mention" if self.bot.user.mentioned_in(message) else "name_trigger"
                return await self.generate_response(
                    message, is_direct_mention=True,
                    trigger_type=trigger_type, bot_name=custom_name
                )

            # ¿El canal tiene modo proactivo activo?
            is_proactive = False
            try:
                is_proactive = await self.bot.user_repo.is_channel_proactive(message.channel.id)
            except Exception as e:
                logger.debug(f"Error consultando proactividad (usando False): {e}")

            if is_proactive and self._should_respond():
                await self.generate_response(
                    message, is_direct_mention=False,
                    trigger_type="proactive", bot_name=custom_name
                )

        except Exception as e:
            logger.error(f"Error crítico en lógica de decisión: {e}")
            self.is_responding = False

    async def generate_response(
        self, message: discord.Message,
        is_direct_mention: bool, trigger_type: str = "mention", bot_name: str = "Dalet"
    ):
        if self.is_responding:
            return

        if time.time() < self.error_cooldown:
            if is_direct_mention:
                logger.warning("Throttling activo por 429 previos. Ignorando respuesta.")
            return

        self.is_responding = True
        try:
            # Recopilar imágenes adjuntas o en embeds
            image_urls = []
            if message.attachments:
                for att in message.attachments:
                    if att.content_type and att.content_type.startswith("image/"):
                        image_urls.append(att.url)
                    elif any(att.filename.lower().endswith(ext)
                             for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
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
                        if any(att.filename.lower().endswith(ext)
                               for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
                            image_urls.append(att.url)

            image_urls = list(dict.fromkeys(image_urls))[:1]  # Solo 1 imagen

            # Limpiar menciones y nombre del bot del contenido
            clean_content = re.sub(r"<@!?\d+>", "", message.content)
            clean_content = re.compile(re.escape("dalet"), re.IGNORECASE).sub("", clean_content)
            if custom_name := bot_name if bot_name.lower() != "dalet" else None:
                clean_content = re.compile(re.escape(custom_name), re.IGNORECASE).sub("", clean_content)
            clean_content = clean_content.strip() or message.content

            # Obtener contexto de conversación del canal
            context = await self.bot.memory_service.get_relevant_context(
                message.channel.id, message.author.id, clean_content
            )

            # Lista ligera de miembros activos en el canal
            members_list = [m.display_name for m in message.channel.members if not m.bot][:8]
            active_users = ", ".join(members_list)

            # Generar respuesta con typing activo
            try:
                async with message.channel.typing():
                    reply = await self.bot.nlp_service.generate_reply(
                        clean_content, context,
                        message.author.display_name,
                        bot_name=bot_name,
                        image_urls=image_urls,
                        user_id=message.author.id,
                        channel_id=message.channel.id,
                        active_room_users=active_users
                    )
            except discord.HTTPException as e:
                if e.status == 429:
                    await self._handle_429(e, "typing")
                    return
                # Si falla el typing (permisos), intentar sin él
                reply = await self.bot.nlp_service.generate_reply(
                    clean_content, context,
                    message.author.display_name,
                    bot_name=bot_name,
                    image_urls=image_urls,
                    user_id=message.author.id,
                    channel_id=message.channel.id,
                    active_room_users=active_users
                )

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
                        reply.strip()
                    )

                    # Log asíncrono no-bloqueante
                    asyncio.create_task(self._log_interaction(
                        message, trigger_type,
                        getattr(self.bot.nlp_service, "active_provider", "gemini"),
                        reply
                    ))

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
            self.is_responding = False

    async def _log_interaction(self, message: discord.Message, trigger_type: str, provider: str, reply: str):
        """Registra la interacción de IA en BD de forma no-bloqueante."""
        try:
            await self.bot.analytics_repo.log_ai_interaction(
                message.guild.id, message.channel.id,
                trigger_type, provider, 0, True
            )
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(DaletNLPChat(bot))