import discord
from discord.ext import commands
import logging

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
        """Guarda mensajes de usuarios (no comandos, no bots) en el buffer de SQLite."""
        # Ignorar mensajes de bots
        if message.author.bot or not message.guild:
            return

        # Ignorar comandos del bot
        if message.content.startswith(("d.", "D.")):
            return

        try:
            await self.repo.log_message(
                message.author.id,
                str(message.author.display_name),
                message.guild.id,
                str(message.guild.name),
                message.channel.id,
                str(message.channel.name),
                message.content.strip()
            )
        except Exception as e:
            logger.error(f"Error guardando mensaje en buffer: {e}")

    @commands.command(name="chatlog")
    @commands.has_permissions(administrator=True)
    async def chatlog(self, ctx, cantidad: int = 10):
        """[ADMIN] Muestra los últimos mensajes guardados en este canal."""
        try:
            registros = await self.repo.get_channel_messages(ctx.channel.id, cantidad)

            if not registros:
                return await ctx.send("No hay mensajes registrados en este canal aún.")

            display_list = list(registros)
            display_list.reverse()  # Cronológico

            texto = "\n".join([f"**{r['username']}**: {r['content']}" for r in display_list])

            if len(texto) > 1900:
                texto = texto[:1900] + "..."

            embed = discord.Embed(
                title=f"📜 Últimos {len(registros)} mensajes en #{ctx.channel.name}",
                description=texto,
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en chatlog: {e}")
            await ctx.send("❌ Error al consultar los logs.")


async def setup(bot):
    await bot.add_cog(ChatLogger(bot))
