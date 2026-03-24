import discord
from discord.ext import commands
import asyncio
import time
import random
import logging
import traceback
import re

logger = logging.getLogger("dalet.handlers.nlp")

# --- Configuración de Comportamiento ---
BASE_RESPONSE_RATE = 0.25  # 25% de probabilidad
COOLDOWN_TIME = 45  # Espera 45 segundos
MIN_MESSAGES_BETWEEN_REPLIES = 10  # Mínimo 10 mensajes
MAX_MESSAGES_WINDOW = 10  # Si pasan 10 mensajes sin responder, resetear contador

class DaletNLPChat(commands.Cog):
    """Maneja el listener 'on_message' para las respuestas de la IA."""
    
    def __init__(self, bot):
        self.bot = bot
        self.last_reply_time = 0
        self.message_counter = 0
        self.is_responding = False # Flag para evitar doble respuesta
        self.error_cooldown = 0 # Cooldown dinámico ante errores 429
        self.consecutive_429s = 0

    async def _handle_429(self, exception, source="unknown"):
        """Centraliza la lógica de manejo de errores 429 (Rate Limit)."""
        self.bot.global_consecutive_429s += 1
        self.consecutive_429s = self.bot.global_consecutive_429s
        
        # Si es un error 1015 de Cloudflare, ser mucho más agresivos con el cooldown
        is_cloudflare_1015 = "1015" in str(exception) or "Cloudflare" in str(exception)
        
        if is_cloudflare_1015:
            # Cloudflare 1015 es un bloqueo duro. Cooldown largo de base.
            wait_secs = 180 * (2 ** (self.consecutive_429s - 1)) # Empieza en 3 min
            logger.error(f"HARD Rate Limit (Cloudflare 1015) in {source}. Throttling for {wait_secs}s")
        else:
            # Rate limit normal de Discord
            wait_secs = 30 * (2 ** (self.consecutive_429s - 1)) # Empieza en 30s
            logger.error(f"Discord 429 Rate Limit in {source}. Throttling for {wait_secs}s")

        self.error_cooldown = time.time() + wait_secs
        self.bot.global_error_cooldown = self.error_cooldown
        
        # Persistir error en BD
        try:
            await self.bot.analytics_repo.log_error(
                "discord_429_hard" if is_cloudflare_1015 else "discord_429",
                f"Source: {source}. Throttle: {wait_secs}s. Consecutive: {self.consecutive_429s}",
                f"dalet_nlpchat.{source}",
                None # Guild ID a veces no está disponible aquí
            )
        except Exception:
            pass
        
        return wait_secs

    def _should_respond(self):
        if self.is_responding: return False # Ignorar si ya está procesando
        
        # Incrementar contador de mensajes
        self.message_counter += 1
        
        # Lógica de Reinicio de Ventana (Si superamos el límite sin haber respondido)
        if self.message_counter > MAX_MESSAGES_WINDOW:
            logger.info(f"Proactive window reset: {self.message_counter} messages reached without response.")
            self.message_counter = 0
            return False

        now = time.time()
        if now - self.last_reply_time < COOLDOWN_TIME:
            return False
        
        # Verificar si cumplimos el mínimo y la probabilidad
        if self.message_counter >= MIN_MESSAGES_BETWEEN_REPLIES and random.random() < BASE_RESPONSE_RATE:
            return True
            
        return False


    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        
        # Ignorar si el mensaje es un comando del bot o de otros bots comunes
        bot_prefixes = ("d.", "D.", "!", "/", ".", "?", "$", ">", "-", "+")
        if message.content.startswith(bot_prefixes): return


        # 0. Registro en historial local (Emergencia/Resiliencia)
        self.bot.memory_service.add_to_local_history(message.channel.id, message.author.name, message.content)

        content_lower = message.content.lower().strip()

        # --- DALET ON: Respuesta instantánea sin IA ---
        if content_lower in ("dalet on", "dalet, on", "dale on"):
            try:
                await message.channel.send("estoy on")
            except discord.HTTPException:
                pass
            return
        
        # Throttling global ante errores 429 registrados
        if time.time() < self.error_cooldown:
            return


        # 2. Guardado de Memoria
        if "recuerda que" in content_lower or "mi nombre es" in content_lower:
            try:
                await self.bot.memory_service.add_memory(
                    message.author.id, str(message.author.name), message.content
                )
                try:
                    await message.add_reaction("✅")
                except discord.HTTPException as e:
                    if e.status == 429:
                        await self._handle_429(e, "reaction")
            except Exception as e:
                logger.error(f"Error saving memory: {e}")

        # 3. Lógica de Decisión
        try:
            is_reactive = await self.bot.user_repo.is_server_reactive(message.guild.id)
            if is_reactive and (self.bot.user.mentioned_in(message) or "dalet" in content_lower):
                trigger_type = "mention" if self.bot.user.mentioned_in(message) else "name_trigger"
                return await self.generate_response(message, is_direct_mention=True, trigger_type=trigger_type)

            is_proactive = await self.bot.user_repo.is_channel_proactive(message.channel.id)
            if is_proactive and self._should_respond():
                await self.generate_response(message, is_direct_mention=False, trigger_type="proactive")
        except Exception as e:
            logger.error(f"Error in decision logic: {e}")
            self.is_responding = False # Emergency reset if something fails early

    async def generate_response(self, message, is_direct_mention: bool, trigger_type: str = "mention"):
        if self.is_responding: return
        
        # Throttling ante rate limits previos
        if time.time() < self.error_cooldown:
            if is_direct_mention:
                logger.warning("Throttling activo por erores 429 previos. Ignorando respuesta.")
            return

        self.is_responding = True
        try:
            # --- Deteccion de Imágenes ---
            image_urls = []
            if message.attachments:
                for attachment in message.attachments:
                    if attachment.content_type and attachment.content_type.startswith('image/'):
                        image_urls.append(attachment.url)
                    elif any(attachment.filename.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                        image_urls.append(attachment.url)

            if message.embeds:
                for embed in message.embeds:
                    if embed.image and embed.image.url:
                        image_urls.append(embed.image.url)

            if not image_urls and message.reference and message.reference.resolved:
                ref_msg = message.reference.resolved
                if isinstance(ref_msg, discord.Message):
                    for attachment in ref_msg.attachments:
                        if any(attachment.filename.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                            image_urls.append(attachment.url)

            if image_urls:
                image_urls = list(dict.fromkeys(image_urls))[:1]  # Solo 1 imagen para ahorrar cuota

            # --- Limpieza de Contenido ---
            clean_content = re.sub(r"<@!?\d+>", "", message.content)
            clean_content = re.compile(re.escape("dalet"), re.IGNORECASE).sub("", clean_content)
            clean_content = clean_content.strip()
            final_content = clean_content if clean_content else message.content

            context = await self.bot.memory_service.get_relevant_context(
                message.channel.id, message.author.id, final_content
            )
            
            # Contexto de sala (leve, no gastar tokens de más)
            members_list = [m.display_name for m in message.channel.members if not m.bot][:10]
            active_users = ", ".join(members_list)

            # Indicador de escritura — directo y simple, sin wrappers complejos
            try:
                async with message.channel.typing():
                    reply = await self.bot.nlp_service.generate_reply(
                        final_content, context, message.author.display_name,
                        image_urls=image_urls,
                        user_id=message.author.id,
                        channel_id=message.channel.id,
                        active_room_users=active_users
                    )
            except discord.HTTPException as e:
                if e.status == 429:
                    await self._handle_429(e, "typing")
                    return
                # Si falla el typing() por permisos, intentar sin el
                reply = await self.bot.nlp_service.generate_reply(
                    final_content, context, message.author.display_name,
                    image_urls=image_urls,
                    user_id=message.author.id,
                    channel_id=message.channel.id,
                    active_room_users=active_users
                )

            active_provider = getattr(self.bot.nlp_service, 'active_provider', 'gemini')

            if reply:
                try:
                    await message.channel.send(reply)
                    self.consecutive_429s = 0
                    self.bot.global_consecutive_429s = 0
                    
                    # Log asincrónico no-bloqueante
                    asyncio.create_task(self._log_interaction(
                        message, trigger_type, active_provider, reply
                    ))
                    
                    # Guardar en historial local
                    self.bot.memory_service.add_to_local_history(
                        message.channel.id, self.bot.user.name, reply
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
            self.is_responding = False

    async def _log_interaction(self, message, trigger_type, provider, reply):
        """Log de interacción en BD de forma asíncrona no-bloqueante."""
        try:
            await self.bot.analytics_repo.log_ai_interaction(
                message.guild.id, message.channel.id,
                trigger_type, provider, 0, True
            )
        except Exception:
            pass
        try:
            await self.bot.user_repo.log_message(
                self.bot.user.id, self.bot.user.name,
                message.guild.id, message.guild.name,
                message.channel.id, message.channel.name,
                reply
            )
        except Exception as db_err:
            logger.warning(f"No se pudo loguear la respuesta en BD: {db_err}")


    async def _execute_action(self, message, action_name, params):
        """Mapea y ejecuta comandos de Discord basados en la intención de la IA."""
        try:
            ctx = await self.bot.get_context(message)
            
            # --- Mapeo de Comandos ---
            command_map = {
                "osu_analyze": ("oa", {"args": params.get("user")}),
                "userinfo": ("userinfo", {}), # El member se maneja abajo
                "serverinfo": ("serverinfo", {}),
                "ping": ("ms", {}),
                "say": ("say", {"mensaje": params.get("text")})
            }

            if action_name in command_map:
                cmd_name, cmd_params = command_map[action_name]
                command = self.bot.get_command(cmd_name)
                
                if command:
                    # CASO ESPECIAL: Manejo de miembros en userinfo
                    if action_name == "userinfo" and params.get("target"):
                        target = params.get("target")
                        if target.startswith("<@") and target.endswith(">"):
                            user_id = int(re.sub(r"\D", "", target))
                            cmd_params["member"] = message.guild.get_member(user_id) or message.author

                    # VERIFICACIÓN DE SEGURIDAD (Respetar bot.check y bloqueos)
                    try:
                        if await command.can_run(ctx):
                             await ctx.invoke(command, **cmd_params)
                        else:
                             logger.warning(f"AI Action {action_name} blocked by security checks in #{message.channel.name}")
                    except commands.CheckFailure:
                        logger.info(f"AI Action {action_name} skipped: Channel is locked or permissions missing.")

        except Exception as e:
            logger.error(f"Error executing action {action_name}: {e}")


async def setup(bot):
    await bot.add_cog(DaletNLPChat(bot))