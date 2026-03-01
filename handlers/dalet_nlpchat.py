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

        content_lower = message.content.lower()
        
        # Throttling global ante errores 429 registrados
        if time.time() < self.error_cooldown:
            return

        # 1. Respuestas Rápidas
        quick_responses = {"dalet test": "si sirvo", "dalet on": "estoy on"}
        for trigger, response in quick_responses.items():
            if trigger in content_lower:
                return await message.channel.send(response)

        # 2. Guardado de Memoria
        if "recuerda que" in content_lower or "mi nombre es" in content_lower:
            try:
                await self.bot.memory_service.add_memory(
                    message.author.id, str(message.author.name), message.content
                )
                await message.add_reaction("✅")
            except Exception as e:
                logger.error(f"Error saving memory: {e}")

        # 3. Lógica de Decisión
        try:
            is_reactive = await self.bot.user_repo.is_server_reactive(message.guild.id)
            if is_reactive and (self.bot.user.mentioned_in(message) or "dalet" in content_lower):
                return await self.generate_response(message, is_direct_mention=True)

            is_proactive = await self.bot.user_repo.is_channel_proactive(message.channel.id)
            if is_proactive and self._should_respond():
                await self.generate_response(message, is_direct_mention=False)
        except Exception as e:
            logger.error(f"Error in decision logic: {e}")
            self.is_responding = False # Emergency reset if something fails early

    async def generate_response(self, message, is_direct_mention: bool):
        if self.is_responding: return
        
        # Throttling ante rate limits previos
        if time.time() < self.error_cooldown:
            if is_direct_mention:
                logger.warning("Throttling active due to recent 429 errors. Skipping response.")
            return

        self.is_responding = True
        try:
            # Usar typing() como context manager correcto para evitar errores con __aenter__/__aexit__ manual
            try:
                typing_ctx = message.channel.typing()
            except Exception:
                typing_ctx = None

            async def _do_respond():
                """Lógica interna de respuesta, envuelta para poder usar typing correctamente."""
                # --- Detección de Imágenes ---
                image_urls = []
                
                # 1. Archivos adjuntos (Attachments)
                if message.attachments:
                    logger.info(f"Checking attachments: {len(message.attachments)}")
                    for attachment in message.attachments:
                        if attachment.content_type and attachment.content_type.startswith('image/'):
                            image_urls.append(attachment.url)
                        elif any(attachment.filename.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                            image_urls.append(attachment.url)

                # 2. Enlaces incrustados (Embeds - tipo imagen o miniatura)
                if message.embeds:
                    logger.info(f"Checking embeds: {len(message.embeds)}")
                    for embed in message.embeds:
                        if embed.image and embed.image.url:
                            image_urls.append(embed.image.url)
                        elif embed.thumbnail and embed.thumbnail.url:
                            image_urls.append(embed.thumbnail.url)

                # 3. Respuesta a un mensaje con imagen (Reference/Reply)
                if not image_urls and message.reference and message.reference.resolved:
                    ref_msg = message.reference.resolved
                    if isinstance(ref_msg, discord.Message):
                        logger.info(f"Checking referenced message (reply) for images")
                        for attachment in ref_msg.attachments:
                            if any(attachment.filename.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                                image_urls.append(attachment.url)
                        for embed in ref_msg.embeds:
                            if embed.image and embed.image.url:
                                image_urls.append(embed.image.url)

                if image_urls:
                    image_urls = list(dict.fromkeys(image_urls))
                    logger.info(f"Final valid images to analyze: {image_urls}")
                elif message.attachments or message.embeds or message.reference:
                    logger.info("Potential visual content detected but no valid image URLs extracted.")

                # --- Limpieza de Contenido ---
                clean_content = re.sub(r"<@!?\d+>", "", message.content)
                clean_content = re.compile(re.escape("dalet"), re.IGNORECASE).sub("", clean_content)
                clean_content = clean_content.strip()
                final_content = clean_content if clean_content else message.content

                context = await self.bot.memory_service.get_relevant_context(
                    message.channel.id, message.author.id, final_content
                )
                
                reply = await self.bot.nlp_service.generate_reply(
                    final_content, context, message.author.name, image_urls=image_urls
                )

                if reply:
                    # --- Extracción de Memoria Automática ---
                    memory_match = re.search(r"\[SAVE_MEMORY:\s*(.*?)\]", reply)
                    if memory_match:
                        memory_content = memory_match.group(1).strip()
                        try:
                            logger.info(f"Auto-Memory detected: {memory_content} for {message.author.name}")
                            await self.bot.memory_service.add_memory(
                                message.author.id, str(message.author.name), memory_content
                            )
                            reply = re.sub(r"\[SAVE_MEMORY:.*?\]", "", reply).strip()
                        except Exception as e:
                            logger.error(f"Error saving auto-memory: {e}")

                    # --- Ejecución de Acciones por Intención ---
                    action_match = re.search(r"(\[ACTION:\s*(\w+)(?:,\s*.*?)?\])", reply)
                    if action_match:
                        full_tag = action_match.group(1)
                        action_name = action_match.group(2).lower()
                        params = {}
                        param_matches = re.findall(r"(\w+):\s*([^,\]]+)", full_tag)
                        for k, v in param_matches:
                            params[k.strip()] = v.strip()
                        reply = re.sub(r"\[ACTION:.*?\]", "", reply).strip()
                        await self._execute_action(message, action_name, params)

                    if reply:
                        try:
                            await message.channel.send(reply)
                            self.consecutive_429s = 0
                            try:
                                await self.bot.user_repo.log_message(
                                    self.bot.user.id, self.bot.user.name,
                                    message.guild.id, message.guild.name,
                                    message.channel.id, message.channel.name,
                                    reply
                                )
                            except Exception as db_err:
                                logger.warning(f"Failed to log reply to DB: {db_err}")
                        except discord.HTTPException as e:
                            if e.status == 429:
                                self.consecutive_429s += 1
                                wait_secs = 30 * (2 ** (self.consecutive_429s - 1))
                                self.error_cooldown = time.time() + wait_secs
                                logger.error(f"429 Rate Limit on send. Throttling for {wait_secs}s")
                            else:
                                logger.error(f"Discord HTTP error sending message: {e}")

                if not is_direct_mention:
                    self.last_reply_time = time.time()
                    self.message_counter = 0

            # Ejecutar con typing si está disponible; si typing falla con 429, continuar igual
            if typing_ctx:
                try:
                    async with typing_ctx:
                        await _do_respond()
                except discord.HTTPException as e:
                    if e.status == 429:
                        logger.warning(f"429 on typing indicator, responding without typing indicator.")
                        await _do_respond()
                    else:
                        raise
                except discord.Forbidden:
                    logger.warning(f"Missing permissions for typing in #{message.channel.name}, responding anyway.")
                    await _do_respond()
            else:
                await _do_respond()

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            traceback.print_exc()
        finally:
            self.is_responding = False

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