import discord
from discord.ext import commands
import os
import json


class CommandsHandler(commands.Cog, name="Comandos Generales"):
    """Comandos básicos de Dalet (utilidades, info y herramientas generales)."""

    def __init__(self, bot):
        self.bot = bot

    # --- 💬 UTILIDADES ---
    @commands.command()
    async def ms(self, ctx):
        """Muestra la latencia del bot."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(embed=discord.Embed(
            title="🏓 Ping",
            description=f"`{latency}ms`",
            color=discord.Color.green()
        ))

    @commands.command()
    async def userinfo(self, ctx, member: discord.Member = None):
        """Muestra información de un usuario."""
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
        """Muestra información del servidor."""
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


async def setup(bot):
    await bot.add_cog(CommandsHandler(bot))
