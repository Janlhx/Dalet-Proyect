import discord
from discord.ext import commands
import os
import asyncio
import logging
import traceback
from datetime import datetime, timezone
from discord.utils import format_dt
from ui.osu_ui import AnalysisPaginator, DescriptionPaginator
from handlers.modules.dalet_osuanalyzer import OsuAnalyzer
import google.generativeai as genai

logger = logging.getLogger("dalet.handlers.osu")

class OsuHandler(commands.Cog, name="osu!"):
    """Comandos dedicados a osu! y análisis con IA."""

    def __init__(self, bot):
        self.bot = bot
        self.osu_service = bot.osu_service
        self.repo = bot.osu_repo

    @commands.command(name="link")
    async def link(self, ctx, osu_username: str):
         """Vincula tu cuenta de Discord con tu perfil de osu! y guarda tus stats."""
         async with ctx.typing():
             try:
                 user_data = await self.osu_service.get_user(osu_username)
                 if not user_data or 'statistics' not in user_data:
                     return await ctx.send(f"❌ No se encontró un jugador con el nombre '{osu_username}'.")

                 stats = user_data.get('statistics', {})
                 await self.repo.link_account(
                     ctx.author.id, user_data["username"], user_data["id"],
                     user_data.get('playmode', 'osu'), stats.get('pp', 0.0),
                     stats.get('global_rank', None), stats.get('country_rank', None),
                     stats.get('hit_accuracy', 0.0)
                 )
                 await ctx.send(f"✅ ¡Tu cuenta ha sido vinculada con **{user_data['username']}**!")
             except Exception as e:
                 logger.error(f"Error in link: {e}")
                 await ctx.send("❌ Hubo un error al procesar la vinculación.")

    @commands.command(name="unlink")
    async def unlink(self, ctx):
        """Desvincula tu cuenta de osu!."""
        try:
             await self.repo.unlink_account(ctx.author.id)
             await ctx.send("✅ Vinculación con osu! eliminada.")
        except Exception as e:
             logger.error(f"Error in unlink: {e}")
             await ctx.send("❌ Hubo un error al desvincular la cuenta.")

    @commands.command(name="op", aliases=["osuProfile"])
    async def osu_profile(self, ctx, *, args: str = None):
        """Muestra un perfil detallado de osu!."""
        username, mode = None, "osu"
        if args:
            parts = args.split()
            for part in parts:
                if part.startswith("-") and part[1:].lower() in ["osu", "taiko", "fruits", "mania"]:
                    mode = part[1:].lower()
                else:
                    username = part # Simplifying for core refactor
        
        if not username:
            username = await self.repo.get_linked_username(ctx.author.id)
            if not username:
                return await ctx.send("❌ No tienes cuenta vinculada. Usa `d.link <usuario>`.")

        async with ctx.typing():
            try:
                user = await self.osu_service.get_user(username, mode)
                stats = user.get("statistics", {})
                embed = discord.Embed(
                    title=f"Perfil de {user['username']}",
                    url=f"https://osu.ppy.sh/users/{user['id']}/{mode}",
                    color=0xFF66AA
                )
                embed.set_thumbnail(url=user.get("avatar_url", ""))
                embed.add_field(name="PP", value=f"{stats.get('pp', 0):,.2f}")
                embed.add_field(name="Rank", value=f"#{stats.get('global_rank', 0):,}")
                await ctx.send(embed=embed)
            except Exception as e:
                logger.error(f"Error in osuProfile: {e}")
                await ctx.send(f"⚠️ Error al obtener el perfil de '{username}'.")

async def setup(bot):
    await bot.add_cog(OsuHandler(bot))