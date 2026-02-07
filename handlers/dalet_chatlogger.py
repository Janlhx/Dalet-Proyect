import discord
from discord.ext import commands
import logging
import traceback

logger = logging.getLogger("dalet.handlers.chatlogger")

class ChatLogger(commands.Cog, name="Memoria Global"):
    """Maneja el registro de todos los mensajes en la base de datos de forma asíncrona."""
    def __init__(self, bot):
        self.bot = bot
        self.repo = bot.user_repo

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listener que guarda el contenido de los mensajes en la BD."""
        if message.author.bot or not message.guild:
            return
        
        if message.content.lower().startswith(("d.", "D.")):
            return

        try:
            await self.repo.log_message(
                message.author.id,
                str(message.author),
                message.guild.id,
                str(message.guild.name),
                message.channel.id,
                str(message.channel.name),
                message.content.strip()
            )
        except Exception as e:
            logger.error(f"Error saving message to DB: {e}")

    @commands.command(name="chatlog")
    @commands.has_permissions(administrator=True)
    async def chatlog(self, ctx, cantidad: int = 10):
        """[ADMIN] Muestra los últimos mensajes guardados desde la BD."""
        try:
            registros = await self.repo.get_channel_messages(ctx.channel.id, cantidad)
            
            if not registros:
                return await ctx.send("No hay mensajes registrados en este canal.")

            # Formatear registros (UserName, Content)
            # registers are already in descending order, we want chronological for display
            display_list = list(registros)
            display_list.reverse()
            
            texto = "\n".join([f"**{r['username']}**: {r['content']}" for r in display_list])
            
            if len(texto) > 1900:
                texto = texto[:1900] + "..."

            embed = discord.Embed(
                title=f"📜 Últimos {len(registros)} Mensajes en #{ctx.channel.name}",
                description=texto,
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in chatlog command: {e}")
            await ctx.send("❌ Error al consultar los logs de la base de datos.")

async def setup(bot):
    await bot.add_cog(ChatLogger(bot))
