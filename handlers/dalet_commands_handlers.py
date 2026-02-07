import discord
from discord.ext import commands
import logging
from discord.utils import format_dt

logger = logging.getLogger("dalet.handlers.general")

class CommandsHandler(commands.Cog, name="Comandos Generales"):
    """Comandos básicos de Dalet (utilidades, info y herramientas generales)."""

    def __init__(self, bot):
        self.bot = bot
        self.repo = bot.user_repo

    # --- 💬 UTILIDADES ---
    @commands.command()
    async def ms(self, ctx):
        """🏓 Muestra la latencia del bot en milisegundos."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(embed=discord.Embed(
            title="🏓 Ping",
            description=f"`{latency}ms`",
            color=discord.Color.green()
        ))

    @commands.command()
    async def userinfo(self, ctx, member: discord.Member = None):
        """👤 Muestra información detallada de un usuario del servidor."""
        member = member or ctx.author
        embed = discord.Embed(
            title=f"👤 {member}",
            color=discord.Color.random()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else "")
        embed.add_field(name="ID", value=member.id)
        embed.add_field(name="Creado", value=member.created_at.strftime("%d/%m/%Y"))
        embed.add_field(name="Unido", value=member.joined_at.strftime("%d/%m/%Y"))
        await ctx.send(embed=embed)

    @commands.command()
    async def serverinfo(self, ctx):
        """🌐 Muestra información detallada del servidor actual."""
        g = ctx.guild
        embed = discord.Embed(
            title=f"🌐 {g.name}",
            color=discord.Color.random()
        )
        embed.set_thumbnail(url=g.icon.url if g.icon else "")
        embed.add_field(name="Miembros", value=g.member_count)
        embed.add_field(name="Dueño", value=g.owner.mention)
        embed.add_field(name="Creado", value=g.created_at.strftime("%d/%m/%Y"))
        await ctx.send(embed=embed)

    @commands.command()
    async def say(self, ctx, *, mensaje):
        """💬 Hace que Dalet repita tu mensaje."""
        await ctx.send(mensaje)

    @commands.command(name="mystats")
    async def mystats(self, ctx):
        """📊 Muestra tus estadísticas de actividad: mensajes enviados, scores de osu! guardados, y más."""
        try:
            query = "SELECT * FROM fn_GetUserStats($1)"
            stats = await self.repo.fetch_one(query, ctx.author.id)

            if not stats:
                return await ctx.send("No tengo datos sobre ti.")

            # fn_GetUserStats returns: (msg_count, score_count, last_msg_timestamp)
            msg_count = stats[0]
            score_count = stats[1]
            last_msg = stats[2]

            embed = discord.Embed(
                title=f"📊 Estadísticas de {ctx.author.name}",
                color=discord.Color.random()
            )
            embed.add_field(name="Mensajes Enviados", value=f"`{msg_count:,}`", inline=True)
            embed.add_field(name="Scores de osu! Guardados", value=f"`{score_count:,}`", inline=True)
            if last_msg:
                embed.add_field(name="Último Mensaje", value=format_dt(last_msg, 'R'), inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in mystats command: {e}")
            await ctx.send(f"❌ Error al obtener tus estadísticas.")

async def setup(bot):
    await bot.add_cog(CommandsHandler(bot))
