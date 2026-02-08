import discord
from discord.ext import commands
import asyncio
import time
import random
import logging
import traceback

logger = logging.getLogger("dalet.handlers.nlp")

# --- Configuración de Comportamiento ---
BASE_RESPONSE_RATE = 0.25  # 25% de probabilidad
COOLDOWN_TIME = 45  # Espera 45 segundos
MIN_MESSAGES_BETWEEN_REPLIES = 10  # Mínimo 10 mensajes
MAX_MESSAGES_WINDOW = 20  # Si pasan 20 mensajes sin responder, resetear contador

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

    async def generate_response(self, message, is_direct_mention: bool):
        if self.is_responding: return
        
        self.is_responding = True
        async with message.channel.typing():
            try:
                context = await self.bot.memory_service.get_relevant_context(
                    message.channel.id, message.author.id, message.content
                )
                
                reply = await self.bot.nlp_service.generate_reply(
                    message.content, context, message.author.name
                )

                if reply:
                    # --- Extracción de Memoria Automática ---
                    import re
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

            except Exception as e:
                logger.error(f"Error generating response: {e}")
                traceback.print_exc()
            finally:
                self.is_responding = False

    async def _execute_action(self, message, action_name, params):
        """Mapea y ejecuta comandos de Discord basados en la intención de la IA."""
        try:
            ctx = await self.bot.get_context(message)
            
            if action_name == "osu_analyze":
                target = params.get("user")
                if target:
                    command = self.bot.get_command("oa")
                    if command: await ctx.invoke(command, args=target)
            
            elif action_name == "userinfo":
                target = params.get("target")
                # Intentar convertir mención o ID a miembro
                member = None
                if target:
                    if target.startswith("<@") and target.endswith(">"):
                        user_id = int(re.sub(r"\D", "", target))
                        member = message.guild.get_member(user_id)
                
                command = self.bot.get_command("userinfo")
                if command: await ctx.invoke(command, member=member or message.author)

            elif action_name == "serverinfo":
                command = self.bot.get_command("serverinfo")
                if command: await ctx.invoke(command)

            elif action_name == "ping":
                command = self.bot.get_command("ms")
                if command: await ctx.invoke(command)

            elif action_name == "say":
                text = params.get("text")
                if text:
                    command = self.bot.get_command("say")
                    if command: await ctx.invoke(command, mensaje=text)

        except Exception as e:
            logger.error(f"Error executing action {action_name}: {e}")


async def setup(bot):
    await bot.add_cog(DaletNLPChat(bot))