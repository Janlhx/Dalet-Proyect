import discord
from discord.ext import commands
import asyncio
import time
import random
import logging
import traceback

logger = logging.getLogger("dalet.handlers.nlp")

# --- Configuración de Comportamiento ---
BASE_RESPONSE_RATE = 0.35  # 35% de probabilidad de responder (antes: 10%)
COOLDOWN_TIME = 30  # Espera 30 segundos entre respuestas (antes: 60s)
MIN_MESSAGES_BETWEEN_REPLIES = 4  # Mínimo 4 mensajes antes de responder (antes: 10) 

class DaletNLPChat(commands.Cog):
    """Maneja el listener 'on_message' para las respuestas de la IA."""
    
    def __init__(self, bot):
        self.bot = bot
        self.last_reply_time = 0
        self.message_counter = 0

    def _should_respond(self):
        now = time.time()
        if now - self.last_reply_time < COOLDOWN_TIME:
            return False
        
        self.message_counter += 1
        return self.message_counter >= MIN_MESSAGES_BETWEEN_REPLIES and random.random() < BASE_RESPONSE_RATE

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        if message.content.lower().startswith(("d.", "D.")): return

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
        async with message.channel.typing():
            try:
                context = await self.bot.memory_service.get_relevant_context(
                    message.channel.id, message.author.id, message.content
                )
                
                reply = await self.bot.nlp_service.generate_reply(
                    message.content, context, message.author.name
                )

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

async def setup(bot):
    await bot.add_cog(DaletNLPChat(bot))