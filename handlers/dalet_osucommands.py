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
        username, mode = await self._parse_args(ctx, args)
        if not username: return

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
                embed.add_field(name="Accuracy", value=f"{stats.get('hit_accuracy', 0):.2f}%")
                await ctx.send(embed=embed)
            except Exception as e:
                logger.error(f"Error in osuProfile: {e}")
                await ctx.send(f"⚠️ Error al obtener el perfil de '{username}'.")

    @commands.command(name="oa", aliases=["osuAnalyze"])
    async def osu_analyze(self, ctx, *, args: str = None):
        """Analiza tu perfil de osu! y hábitos recientes con IA."""
        username, mode = await self._parse_args(ctx, args)
        if not username: return

        async with ctx.typing():
            try:
                user = await self.osu_service.get_user(username, mode)
                recent = await self.osu_service.get_user_recent_scores(user["id"], mode, limit=50)
                best = await self.osu_service.get_user_best_scores(user["id"], mode, limit=50)
                
                # OsuAnalyzer usa self.osu_service para búsquedas asíncronas
                analyzer = OsuAnalyzer(self.osu_service, user, recent, best)
                prompt = analyzer.generate_ai_analysis()
                
                response = await self.bot.nlp_service.generate_reply(prompt, "Análisis de osu!", username)
                
                if response:
                    pages = [response[i:i+1900] for i in range(0, len(response), 1900)]
                    if len(pages) > 1:
                        view = AnalysisPaginator(pages)
                        embed = discord.Embed(title=f"Análisis IA: {username}", description=pages[0], color=0xFF66AA)
                        await ctx.send(embed=embed, view=view)
                    else:
                        await ctx.send(f"### 🧠 Análisis IA: {username}\n{response}")
                else:
                    await ctx.send("❌ No pude generar el análisis en este momento.")
            except Exception as e:
                logger.error(f"Error in osuAnalyze: {e}")
                await ctx.send(f"⚠️ Error al analizar a '{username}'.")

    @commands.command(name="oc", aliases=["osuCoach"])
    async def osu_coach(self, ctx, *, args: str = None):
        """Plan de entrenamiento personalizado basado en tus debilidades."""
        username, mode = await self._parse_args(ctx, args)
        if not username: return

        async with ctx.typing():
            try:
                user = await self.osu_service.get_user(username, mode)
                recent = await self.osu_service.get_user_recent_scores(user["id"], mode, limit=50)
                best = await self.osu_service.get_user_best_scores(user["id"], mode, limit=50)
                
                analyzer = OsuAnalyzer(self.osu_service, user, recent, best)
                prompt = await analyzer.generate_coaching_prompt()
                
                response = await self.bot.nlp_service.generate_reply(prompt, "Coaching de osu!", username)
                
                if response:
                    await ctx.send(f"### 🎯 Plan de Coaching: {username}\n{response}")
                else:
                    await ctx.send("❌ No pude generar el plan de coaching.")
            except Exception as e:
                logger.error(f"Error in osuCoach: {e}")
                await ctx.send(f"⚠️ Error al generar coaching para '{username}'.")

    async def _parse_args(self, ctx, args):
        username, mode = None, "osu"
        if args:
            parts = args.split()
            for part in parts:
                if part.startswith("-") and part[1:].lower() in ["osu", "taiko", "fruits", "mania"]:
                    mode = part[1:].lower()
                else:
                    username = part
        
        if not username:
            username = await self.repo.get_linked_username(ctx.author.id)
            if not username:
                await ctx.send("❌ No tienes cuenta vinculada. Usa `d.link <usuario>`.")
                return None, None
        return username, mode

async def setup(bot):
    await bot.add_cog(OsuHandler(bot))