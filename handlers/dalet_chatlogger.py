import discord
from discord.ext import commands
from collections import deque
import json
import os
from datetime import datetime

class ChatLogger(commands.Cog, name="Memoria Global"):
    def __init__(self, bot):
        self.bot = bot
        self.LOG_FILE = "chat_history.json"
        self.MAX_MESSAGES = 100
        if os.path.exists(self.LOG_FILE):
            with open(self.LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.chat_log = deque(data[-self.MAX_MESSAGES:], maxlen=self.MAX_MESSAGES)
        else:
            self.chat_log = deque(maxlen=self.MAX_MESSAGES)
        self.allowed_channels = []

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if self.allowed_channels and message.channel.id not in self.allowed_channels:
            return
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(), "author_id": message.author.id,
            "author_name": str(message.author), "guild_id": message.guild.id if message.guild else None,
            "guild_name": str(message.guild) if message.guild else "DM", "channel_id": message.channel.id,
            "channel_name": str(message.channel), "content": message.content.strip()
        }
        self.chat_log.append(log_entry)
        with open(self.LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(list(self.chat_log), f, indent=4, ensure_ascii=False)

    @commands.command(name="chatlog")
    @commands.is_owner()
    async def chatlog(self, ctx, cantidad: int = 10):
        """[ADMIN] Muestra los últimos mensajes guardados.
        
        Uso: d.chatlog [cantidad]
        Ejemplo: d.chatlog 25
        
        Muestra los últimos mensajes que el bot ha registrado
        globalmente en todos los servidores. Por defecto muestra 10.
        """
        registros = list(self.chat_log)[-cantidad:]
        texto = "\n".join([f"**{r['author_name']}**: {r['content']}" for r in registros if r['content']]) or "No hay mensajes recientes."
        if len(texto) > 2000:
            texto = texto[-1900:]
        await ctx.send(f"🗒️ Últimos {cantidad} mensajes globales:\n{texto}")

async def setup(bot):
    await bot.add_cog(ChatLogger(bot))