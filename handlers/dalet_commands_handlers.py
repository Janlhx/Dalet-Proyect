"""
Handler (Cog) para Comandos Generales y de Utilidad.

Este Cog agrupa comandos básicos que proporcionan información
sobre el bot, el servidor o los usuarios (ej. ping, userinfo).
No están ligados a una lógica de negocio compleja (como IA o osu!).
"""
import discord
from discord.ext import commands
import os
import json
import db_connector # Importado para el comando mystats
from discord.utils import format_dt # Para formatear la fecha

class CommandsHandler(commands.Cog, name="Comandos Generales"):
    """Comandos básicos de Dalet (utilidades, info y herramientas generales)."""

    def __init__(self, bot):
        self.bot = bot

    # --- 💬 UTILIDADES ---
    @commands.command()
    async def ms(self, ctx):
        """Muestra la latencia del bot (ping)."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(embed=discord.Embed(
            title="🏓 Ping",
            description=f"`{latency}ms`",
            color=discord.Color.green()
        ))

    @commands.command()
    async def userinfo(self, ctx, member: discord.Member = None):
        """Muestra información de un usuario (o de quien usa el comando)."""
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
        """Muestra información del servidor actual."""
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
        """Hace que el bot repita tu mensaje."""
        await ctx.send(mensaje)

    @commands.command()
    async def mystats(self, ctx):
        """Muestra tus estadísticas de actividad en el bot."""
        try:
            
            query = "SELECT * FROM fn_GetUserStats(%s)"
            stats = db_connector.fetch_one(query, (ctx.author.id,))

            if not stats:
                return await ctx.send("No tengo datos sobre ti.")

            # La función SQL devuelve: (MsgCount, LastMsgTimestamp, ScoreCount, LastScoreTimestamp)
            msg_count = stats[0]
            last_msg = stats[1]
            score_count = stats[2]

            embed = discord.Embed(
                title=f"📊 Estadísticas de {ctx.author.name}",
                color=discord.Color.random()
            )
            embed.add_field(name="Mensajes Enviados", value=f"`{msg_count:,}`", inline=True)
            embed.add_field(name="Scores de osu! Guardados", value=f"`{score_count:,}`", inline=True)
            if last_msg:
                # format_dt(last_msg, 'R') crea un timestamp relativo (ej: "hace 2 horas")
                embed.add_field(name="Último Mensaje", value=format_dt(last_msg, 'R'), inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error al obtener tus estadísticas: {e}")
            print(f"!!!!!! [CommandsHandler] Error en mystats: {e}")


async def setup(bot):
    """Función 'setup' para cargar el Cog."""
    await bot.add_cog(CommandsHandler(bot))