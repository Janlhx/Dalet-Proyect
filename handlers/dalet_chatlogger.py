import discord
from discord.ext import commands
import logging
import re

logger = logging.getLogger("dalet.handlers.chatlogger")


class ChatLogger(commands.Cog, name="Memoria Global"):
    """
    Registra mensajes en SQLite para memoria de contexto e historial.
    El on_message está centralizado aquí — dalet_nlpchat.py lee de aquí.
    """
    def __init__(self, bot):
        self.bot = bot
        self.repo = bot.user_repo

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignorar mensajes de otros bots (permitir a Dalet registrar sus propias respuestas para memoria de chat)
        if (message.author.bot and message.author != self.bot.user) or not message.guild:
            return

        # Ignorar comandos con prefijo del bot
        if message.content.startswith(("d.", "D.")):
            return

        content = message.content.strip()
        if not content:
            if message.author == self.bot.user and message.embeds:
                emb = message.embeds[0]
                details = []
                if emb.title:
                    details.append(emb.title)
                if emb.description:
                    clean_desc = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', emb.description)
                    details.append(clean_desc.replace('\n', ' │ '))
                for f in emb.fields[:3]:
                    clean_val = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', f.value)
                    details.append(f"{f.name}: {clean_val.replace('\n', ' │ ')}")
                raw_embed_str = " │ ".join(details)
                if len(raw_embed_str) > 350:
                    raw_embed_str = raw_embed_str[:347] + "..."
                content = f"[Tarjeta: {raw_embed_str or 'Embed'}]"
            else:
                return

        try:
            await self.repo.log_message(
                message.author.id,
                str(message.author.display_name),
                message.guild.id,
                str(message.guild.name),
                message.channel.id,
                str(message.channel.name),
                content
            )
        except Exception as e:
            logger.error(f"Error guardando mensaje en buffer: {e}")


async def setup(bot):
    await bot.add_cog(ChatLogger(bot))
