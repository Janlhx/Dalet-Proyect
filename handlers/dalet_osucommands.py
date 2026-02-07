import discord
from discord.ext import commands
import os
import asyncio
import logging
import traceback
from datetime import datetime, timezone
from discord.utils import format_dt
from ui.osu_ui import UniversalPaginator
from handlers.modules.dalet_osuanalyzer import OsuAnalyzer
import google.generativeai as genai
import re

logger = logging.getLogger("dalet.handlers.osu")

class OsuHandler(commands.Cog, name="osu!"):
    """Comandos dedicados a osu! y análisis Pro con IA."""

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
                
                # Color basado en el rango
                color = self._get_rank_color(stats.get('global_rank', 999999))
                
                # Crear embed principal
                embed = discord.Embed(
                    title=f"🎮 {user['username']}",
                    url=f"https://osu.ppy.sh/users/{user['id']}/{mode}",
                    color=color,
                    description=f"**{user.get('country', {}).get('name', '??')}** {user.get('country', {}).get('code', '??')} | Modo: **{mode.upper()}**"
                )
                
                # Avatar y cover
                embed.set_thumbnail(url=user.get("avatar_url", ""))
                if user.get("cover_url"):
                    embed.set_image(url=user.get("cover_url"))
                
                # === SECCIÓN 1: RENDIMIENTO ===
                pp = stats.get('pp', 0)
                global_rank = stats.get('global_rank', 0)
                country_rank = stats.get('country_rank', 0)
                
                embed.add_field(
                    name="💎 Performance",
                    value=f"**{pp:,.0f}pp**\n"
                          f"🌍 Global: **#{global_rank:,}**\n"
                          f"🏳️ País: **#{country_rank:,}**",
                    inline=True
                )
                
                # === SECCIÓN 2: PRECISIÓN Y NIVEL ===
                accuracy = stats.get('hit_accuracy', 0)
                level = stats.get('level', {})
                current_level = level.get('current', 0)
                level_progress = level.get('progress', 0)
                
                # Barra de progreso visual
                progress_bar = self._create_progress_bar(level_progress)
                
                embed.add_field(
                    name="🎯 Precisión & Nivel",
                    value=f"**{accuracy:.2f}%**\n"
                          f"📊 Nivel **{current_level}**\n"
                          f"{progress_bar} {level_progress}%",
                    inline=True
                )
                
                # === SECCIÓN 3: ACTIVIDAD ===
                play_count = stats.get('play_count', 0)
                play_time = stats.get('play_time', 0)
                hours = play_time // 3600
                total_hits = stats.get('total_hits', 0)
                
                embed.add_field(
                    name="⏱️ Actividad",
                    value=f"🎵 **{play_count:,}** jugadas\n"
                          f"⏰ **{hours:,}h** jugadas\n"
                          f"🎯 **{total_hits:,}** hits totales",
                    inline=True
                )
                
                # === SECCIÓN 4: RANGOS ===
                grades = stats.get('grade_counts', {})
                ssh = grades.get('ssh', 0)
                ss = grades.get('ss', 0)
                sh = grades.get('sh', 0)
                s = grades.get('s', 0)
                a = grades.get('a', 0)
                
                embed.add_field(
                    name="🏅 Rangos Obtenidos",
                    value=f"🌟 **SS+**: {ssh:,} | **SS**: {ss:,}\n"
                          f"⭐ **S+**: {sh:,} | **S**: {s:,}\n"
                          f"✨ **A**: {a:,}",
                    inline=True
                )
                
                # === SECCIÓN 5: ESTADÍSTICAS AVANZADAS ===
                ranked_score = stats.get('ranked_score', 0)
                total_score = stats.get('total_score', 0)
                max_combo = stats.get('maximum_combo', 0)
                replays_watched = stats.get('replays_watched_by_others', 0)
                
                embed.add_field(
                    name="📈 Estadísticas Avanzadas",
                    value=f"🎖️ Score Ranked: **{ranked_score:,}**\n"
                          f"💯 Score Total: **{total_score:,}**\n"
                          f"🔗 Combo Máximo: **{max_combo:,}x**",
                    inline=True
                )
                
                # === SECCIÓN 6: POPULARIDAD ===
                followers = user.get('follower_count', 0)
                medals = len(user.get('user_achievements', []))
                
                embed.add_field(
                    name="🌟 Popularidad",
                    value=f"👥 **{followers:,}** seguidores\n"
                          f"🎖️ **{replays_watched:,}** replays vistos\n"
                          f"🏆 **{medals}** medallas",
                    inline=True
                )
                
                # Footer con información adicional
                join_date = user.get('join_date', '')
                if join_date:
                    from datetime import datetime
                    join_dt = datetime.fromisoformat(join_date.replace('Z', '+00:00'))
                    embed.set_footer(
                        text=f"Jugador desde {join_dt.strftime('%d/%m/%Y')} • ID: {user['id']}",
                        icon_url=user.get('country', {}).get('flag_url', '')
                    )
                
                await ctx.send(embed=embed)
            except Exception as e:
                logger.error(f"Error in osuProfile: {e}")
                await ctx.send(f"⚠️ Error al obtener el perfil de '{username}'.")

    def _create_progress_bar(self, percentage, length=10):
        """Crea una barra de progreso visual."""
        filled = int(length * percentage / 100)
        empty = length - filled
        return f"[{'█' * filled}{'░' * empty}]"

    @commands.command(name="oa", aliases=["osuAnalyze", "oc", "osuCoach"])
    async def osu_analyze(self, ctx, *, args: str = None):
        """[SUPER ANALYZE PRO] Análisis profundo + Coaching personalizado en un solo reporte."""
        username, mode = await self._parse_args(ctx, args)
        if not username: return

        async with ctx.typing():
            try:
                # 1. Recolección de Datos (Enriquecida)
                user = await self.osu_service.get_user(username, mode)
                recent = await self.osu_service.get_user_recent_scores(user["id"], mode, limit=50)
                best = await self.osu_service.get_user_best_scores(user["id"], mode, limit=50)
                stats = user.get("statistics", {})
                
                # Crear embed inicial (Skeleton)
                color = self._get_rank_color(stats.get('global_rank', 999999))
                embed = discord.Embed(
                    title=f"📊 Reporte Dalet: {username}",
                    url=f"https://osu.ppy.sh/users/{user['id']}/{mode}",
                    color=color,
                    description="🚀 Generando análisis total y plan de coaching..."
                )
                embed.set_thumbnail(url=user.get("avatar_url", ""))
                
                # Stats rápidas en Pagina 1
                embed.add_field(name="PP", value=f"`{stats.get('pp', 0):,.0f}`", inline=True)
                embed.add_field(name="Rank", value=f"`#{stats.get('global_rank', 0):,}`", inline=True)
                embed.add_field(name="Acc", value=f"`{stats.get('hit_accuracy', 0):.2f}%`", inline=True)
                
                msg = await ctx.send(embed=embed)
                
                # 2. Generar Análisis con IA
                analyzer = OsuAnalyzer(self.osu_service, user, recent, best)
                prompt = await analyzer.generate_super_prompt()
                
                response = await self.bot.nlp_service.generate_reply(prompt, "Súper Análisis de osu!", username)
                
                if response:
                    # 3. Parsing del Response (Separadores [PAGE1_INTRO], etc)
                    pages = self._parse_ai_response(response)
                    
                    # Actualizar embed con la primera página (Intro)
                    embed.description = pages[0]
                    embed.set_footer(text=f"{pages[3]} | Página 1/3")
                    
                    # 4. Lanzar Paginador
                    view = UniversalPaginator(pages, embed)
                    await msg.edit(embed=embed, view=view)
                else:
                    embed.description = "❌ Dalet se quedó dormida. No pude obtener el análisis."
                    await msg.edit(embed=embed)
                    
            except Exception as e:
                logger.error(f"Error in Super Analyze for {username}: {e}")
                traceback.print_exc()
                await ctx.send(f"⚠️ Error técnico en el Súper Análisis. Dile a Litxe que revise los logs.")

    def _get_rank_color(self, rank):
        if rank <= 1000: return 0xFFD700
        if rank <= 10000: return 0xC0C0C0
        if rank <= 100000: return 0xCD7F32
        return 0xFF66AA

    def _parse_ai_response(self, text):
        """Divide la respuesta de la IA en secciones basadas en los delimitadores."""
        # Secciones esperadas: [PAGE1_INTRO], [PAGE2_ANALYSIS], [PAGE3_COACHING], [FOOTER]
        
        intro = self._extract_section(text, "PAGE1_INTRO")
        analysis = self._extract_section(text, "PAGE2_ANALYSIS")
        coaching = self._extract_section(text, "PAGE3_COACHING")
        footer = self._extract_section(text, "FOOTER")
        
        # Fallbacks si la IA falla en los tags
        if not intro and not analysis:
            return [text[:1500], "Análisis no disponible", "Coaching no disponible", "Fin."]
            
        return [intro, analysis, coaching, footer]

    def _extract_section(self, text, tag):
        pattern = rf"\[{tag}\](.*?)(?=\[|$)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    # ... (parse_args y setup se mantienen)


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