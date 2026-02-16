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


        content_lower = message.content.lower()

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
        
        self.is_responding = True
        try:
            # Intentar activar el typing solo si tenemos permisos
            try:
                # Usar un contexto typing manual para tener control total
                typing_ctx = message.channel.typing()
                await typing_ctx.__aenter__()
            except discord.Forbidden:
                logger.warning(f"Missing permissions to show typing in #{message.channel.name}")
                typing_ctx = None # No enviamos typing pero seguimos adelante
            except Exception as e:
                logger.error(f"Error starting typing: {e}")
                typing_ctx = None

            try:
                # --- Detección de Imágenes ---
                image_urls = []
                if message.attachments:
                    logger.info(f"Attachments detected: {len(message.attachments)}")
                    for attachment in message.attachments:
                        logger.info(f"Attachment: {attachment.filename} ({attachment.content_type})")
                        if any(attachment.filename.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                            image_urls.append(attachment.url)
                
                if image_urls:
                    logger.info(f"Valid images found: {image_urls}")
                elif message.attachments:
                    logger.info("Attachments found but no valid image extensions detected.")

                # --- Limpieza de Contenido ---
                # 1. Quitar menciones al bot (<@!ID> o <@ID>)
                clean_content = re.sub(r"<@!?\d+>", "", message.content)
                # 2. Quitar la palabra "dalet" (insensible a mayúsculas)
                clean_content = re.compile(re.escape("dalet"), re.IGNORECASE).sub("", clean_content)
                # 3. Limpiar espacios extras
                clean_content = clean_content.strip()

                # Si el contenido quedó vacío después de limpiar, usar el original como fallback 
                final_content = clean_content if clean_content else message.content

                context = await self.bot.memory_service.get_relevant_context(
                    message.channel.id, message.author.id, final_content
                )
                
                # Pasar las imágenes al servicio NLP
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
                        
                        # Extraer parámetros SOLO dentro de la etiqueta
                        params = {}
                        param_matches = re.findall(r"(\w+):\s*([^,\]]+)", full_tag)
                        for k, v in param_matches:
                            params[k.strip()] = v.strip()

                        # Limpiar el mensaje antes de enviarlo
                        reply = re.sub(r"\[ACTION:.*?\]", "", reply).strip()
                        
                        # Ejecutar la acción
                        await self._execute_action(message, action_name, params)

                    if reply:
                        await message.channel.send(reply)
                        await self.bot.user_repo.log_message(
                            self.bot.user.id, self.bot.user.name,
                            message.guild.id, message.guild.name,
                            message.channel.id, message.channel.name,
                            reply
                        )

                if not is_direct_mention:
                    self.last_reply_time = time.time()
                    self.message_counter = 0

            finally:
                # Cerrar el contexto de typing si se inició
                if typing_ctx:
                    try:
                        await typing_ctx.__aexit__(None, None, None)
                    except:
                        pass

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