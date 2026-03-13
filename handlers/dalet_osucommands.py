import discord
from discord.ext import commands
import os
import asyncio
import logging
import traceback
from datetime import datetime, timezone
from discord.utils import format_dt
from ui.osu_ui import UniversalPaginator
from ui.organisms import DaletOrganisms
from handlers.modules.dalet_osuanalyzer import OsuAnalyzer
import re

logger = logging.getLogger("dalet.handlers.osu")

class OsuHandler(commands.Cog, name="osu!"):
    """Comandos dedicados a osu! y análisis Pro con IA."""

    def __init__(self, bot):
        self.bot = bot
        self.osu_service = bot.osu_service
        self.repo = bot.osu_repo
        # Cooldown para registros en OsuHistory: 5 minutos
        # Para evitar spam de conexiones a la DB en un mismo minuto,
        # pero permitiendo que el snapshot diario se actualice si sube de nivel más tarde.
        self._snapshot_cooldowns = {}
        self._snapshot_cooldown_secs = 300  # 5 minutos

    async def _try_update_osu_snapshot(self, discord_user_id: int, osu_username_queried: str, user_data: dict):
        """
        1. Actualiza SIEMPRE OsuAccounts con los últimos datos de la API.
        2. Guarda o actualiza un snapshot en OsuHistory (con cooldown de 5 min).
        """
        import time
        try:
            # Extraer stats del user_data
            stats        = user_data.get('statistics', {})
            pp           = stats.get('pp', 0.0)
            global_rank  = stats.get('global_rank', None)
            country_rank = stats.get('country_rank', None)
            accuracy     = stats.get('hit_accuracy', 0.0)
            play_mode    = user_data.get('playmode', 'osu')

            # --- PARTE 1: Actualización de datos actuales (SIEMPRE) ---
            # Solo si el usuario consultado es el vinculado al autor del comando
            linked_username = await self.repo.get_linked_username(discord_user_id)
            
            if linked_username and linked_username.lower() == osu_username_queried.lower():
                await self.repo.link_account(
                    discord_user_id, user_data["username"], user_data["id"],
                    play_mode, pp, global_rank, country_rank, accuracy
                )
                logger.debug(f"[OsuSync] Updated current stats for {discord_user_id}")

                # --- PARTE 2: Historial diario (Cooldown de 5 min) ---
                now = time.time()
                last_snap = self._snapshot_cooldowns.get(discord_user_id, 0)
                if now - last_snap >= self._snapshot_cooldown_secs:
                    await self.bot.analytics_repo.record_osu_snapshot(
                        discord_user_id, pp, global_rank, country_rank, accuracy, play_mode
                    )
                    self._snapshot_cooldowns[discord_user_id] = now
                    logger.info(f"[OsuSnapshot] Snapshot updated in history for {discord_user_id}")
        
        except Exception as e:
            logger.warning(f"[OsuSnapshot] Non-critical error: {e}")

    @commands.command(name="link")
    async def link(self, ctx, osu_username: str):
         """Vincula tu cuenta de Discord con tu perfil de osu! y guarda tus stats."""
         async with ctx.typing():
             try:
                 user_data = await self.osu_service.get_user(osu_username)
                 if not user_data or 'statistics' not in user_data:
                     return await ctx.send(f"❌ No se encontró un jugador con el nombre '{osu_username}'.")

                 stats = user_data.get('statistics', {})
                 pp          = stats.get('pp', 0.0)
                 global_rank = stats.get('global_rank', None)
                 country_rank= stats.get('country_rank', None)
                 accuracy    = stats.get('hit_accuracy', 0.0)
                 play_mode   = user_data.get('playmode', 'osu')

                 await self.repo.link_account(
                     ctx.author.id, user_data["username"], user_data["id"],
                     play_mode, pp, global_rank, country_rank, accuracy
                 )

                 # Guardar snapshot en historial de progreso osu!
                 try:
                     await self.bot.analytics_repo.record_osu_snapshot(
                         ctx.author.id, pp, global_rank, country_rank, accuracy, play_mode
                     )
                 except Exception as snap_err:
                     logger.warning(f"Could not save osu snapshot: {snap_err}")

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
                
                # Usar el organismo Atómico para crear la tarjeta de perfil
                embed = DaletOrganisms.create_osu_card(user, mode)
                
                # Personalización adicional si es necesario
                join_date = user.get('join_date', '')
                if join_date:
                    join_dt = datetime.fromisoformat(join_date.replace('Z', '+00:00'))
                    footer_text = embed.footer.text if embed.footer else ""
                    embed.set_footer(
                        text=f"{footer_text} • Desde {join_dt.strftime('%d/%m/%Y')}",
                        icon_url=user.get('country', {}).get('flag_url', '')
                    )
                
                await ctx.send(embed=embed)

                # Actualizar snapshot si el autor está consultando su propia cuenta
                await self._try_update_osu_snapshot(ctx.author.id, username, user)

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
                color = DaletAtoms.get_rank_color(stats.get('global_rank', 999999))
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

                # Actualizar snapshot si el autor está consultando su propia cuenta
                await self._try_update_osu_snapshot(ctx.author.id, username, user)

            except Exception as e:
                logger.error(f"Error in Super Analyze for {username}: {e}")
                traceback.print_exc()
                await ctx.send(f"⚠️ Error técnico en el Súper Análisis. Dile a Litxe que revise los logs.")


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