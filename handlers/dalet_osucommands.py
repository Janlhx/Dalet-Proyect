import discord
from discord.ext import commands
import asyncio
import logging
import traceback
import re
import io
from datetime import datetime, timezone

logger = logging.getLogger("dalet.handlers.osu")

from ui.organisms import DaletOrganisms
from ui.atoms import DaletAtoms
from handlers.modules.dalet_osuanalyzer import OsuAnalyzer
from handlers.dalet_osu_presenter import OsuPresenter

# Modos de juego válidos
VALID_MODES = {"osu", "taiko", "fruits", "mania"}

# Emojis de grado para embeds
GRADE_EMOJIS = {
    "XH": "🌟", "X": "⭐", "SH": "🥈", "S": "🏅", "A": "🎯",
    "B": "🔵", "C": "🟡", "D": "🔴", "F": "💀"
}

# Emojis de modos
MODE_EMOJIS = {"osu": "🎵", "taiko": "🥁", "fruits": "🍎", "mania": "🎹"}


def _mods_str(mods: list) -> str:
    """Convierte lista de mods a string legible (ej. +HDDT)."""
    if not mods:
        return "+NM"
    return "+" + "".join(mods)


def _acc_str(accuracy: float) -> str:
    return f"{accuracy * 100:.2f}%"


def _rank_color(rank: int | None) -> int:
    if not rank:
        return 0x7289DA
    if rank <= 1000:    return 0xFFD700
    if rank <= 10000:   return 0xC0C0C0
    if rank <= 100000:  return 0xCD7F32
    return 0x7289DA


class OsuHandler(commands.Cog, name="osu!"):
    """Comandos de osu! — perfil, jugadas, análisis y ranking."""

    def __init__(self, bot):
        self.bot = bot
        self.osu = bot.osu_service
        self.repo = bot.osu_repo
        self._snap_cooldowns: dict[int, float] = {}

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    async def _parse_args(self, ctx, args: str | None):
        """Parsea argumentos: extraer username y modo (-osu/-taiko/-mania/-fruits)."""
        username, mode = None, "osu"
        if args:
            parts = args.split()
            for part in parts:
                if part.startswith("-") and part[1:].lower() in VALID_MODES:
                    mode = part[1:].lower()
                else:
                    username = part

        if not username:
            username = await self.repo.get_linked_username(ctx.author.id)
            if not username:
                await ctx.send(
                    "❌ no tienes cuenta vinculada. usa `d.link <usuario>` primero."
                )
                return None, None
        return username, mode

    async def _maybe_snapshot(self, discord_id: int, queried_username: str, user_data: dict):
        """Actualiza estadísticas y snapshot diario si el usuario consultó su propia cuenta."""
        import time
        try:
            linked = await self.repo.get_linked_username(discord_id)
            if not linked or linked.lower() != queried_username.lower():
                return

            stats = user_data.get("statistics", {})
            pp           = stats.get("pp", 0.0)
            global_rank  = stats.get("global_rank")
            country_rank = stats.get("country_rank")
            accuracy     = stats.get("hit_accuracy", 0.0)
            play_mode    = user_data.get("playmode", "osu")

            # Actualizar cuenta vinculada
            await self.repo.link_account(
                discord_id, user_data["username"], user_data["id"],
                play_mode, pp, global_rank, country_rank, accuracy
            )

            # Snapshot con cooldown de 5 min
            now = time.time()
            if now - self._snap_cooldowns.get(discord_id, 0) >= 300:
                await self.bot.analytics_repo.record_osu_snapshot(
                    discord_id, pp, global_rank, country_rank, accuracy, play_mode
                )
                self._snap_cooldowns[discord_id] = now

        except Exception as e:
            logger.debug(f"[OsuSnapshot] Error no crítico: {e}")

    # ------------------------------------------------------------------
    # d.link / d.unlink
    # ------------------------------------------------------------------

    @commands.command(name="link")
    async def link(self, ctx, osu_username: str):
        """Vincula tu cuenta de Discord con tu perfil de osu!."""
        try:
            async with ctx.typing():
                user_data = await self.osu.get_user(osu_username)

            if not user_data or "statistics" not in user_data:
                return await ctx.send(f"❌ no encontré a '{osu_username}' en osu!.")

            stats = user_data.get("statistics", {})
            await self.repo.link_account(
                ctx.author.id,
                user_data["username"],
                user_data["id"],
                user_data.get("playmode", "osu"),
                stats.get("pp", 0.0),
                stats.get("global_rank"),
                stats.get("country_rank"),
                stats.get("hit_accuracy", 0.0),
            )

            # Primer snapshot
            try:
                await self.bot.analytics_repo.record_osu_snapshot(
                    ctx.author.id,
                    stats.get("pp", 0.0),
                    stats.get("global_rank"),
                    stats.get("country_rank"),
                    stats.get("hit_accuracy", 0.0),
                    user_data.get("playmode", "osu"),
                )
            except Exception:
                pass

            await ctx.send(f"✅ vinculado con **{user_data['username']}**.")

        except Exception as e:
            logger.error(f"Error en link: {e}")
            await ctx.send("❌ error al vincular la cuenta.")

    @commands.command(name="unlink")
    async def unlink(self, ctx):
        """Desvincula tu cuenta de osu!."""
        try:
            await self.repo.unlink_account(ctx.author.id)
            await ctx.send("✅ vinculación con osu! eliminada.")
        except Exception as e:
            logger.error(f"Error en unlink: {e}")
            await ctx.send("❌ error al desvincular.")

    # ------------------------------------------------------------------
    # d.op — Perfil
    # ------------------------------------------------------------------

    @commands.command(name="op", aliases=["osuProfile"])
    async def osu_profile(self, ctx, *, args: str = None):
        """Muestra el perfil completo de osu! de un jugador."""
        username, mode = await self._parse_args(ctx, args)
        if not username:
            return

        try:
            async with ctx.typing():
                user = await self.osu.get_user(username, mode)

            server_lang = "en"
            if ctx.guild:
                server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)

            embed = OsuPresenter.build_profile_card(user, mode, lang=server_lang)
            await ctx.send(embed=embed)
            await self._maybe_snapshot(ctx.author.id, username, user)

        except Exception as e:
            logger.error(f"Error en op para {username}: {e}")
            await ctx.send(f"⚠️ no pude obtener el perfil de '{username}'.")

    # ------------------------------------------------------------------
    # d.orecent / d.or — Última jugada
    # ------------------------------------------------------------------

    @commands.command(name="orecent", aliases=["or", "rs"])
    async def osu_recent(self, ctx, *, args: str = None):
        """Muestra tu última jugada de osu! con todos los detalles."""
        username, mode = await self._parse_args(ctx, args)
        if not username:
            return

        try:
            async with ctx.typing():
                user = await self.osu.get_user(username, mode)
                recent = await self.osu.get_user_recent_scores(
                    user["id"], mode, limit=1, include_fails=1
                )

            if not recent:
                return await ctx.send(f"**{username}** no tiene jugadas recientes en {mode}.")

            server_lang = "en"
            if ctx.guild:
                server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)

            embed = OsuPresenter.build_recent_card(
                user.get("username", username), mode, recent[0], user_data=user, lang=server_lang
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en orecent: {e}")
            await ctx.send(f"⚠️ error obteniendo jugada reciente de '{username}'.")

    # ------------------------------------------------------------------
    # d.otop — Top plays con distribución de PP
    # ------------------------------------------------------------------

    @commands.command(name="otop", aliases=["top"])
    async def osu_top(self, ctx, *, args: str = None):
        """Muestra tus mejores plays y una gráfica de distribución de PP."""
        username, mode = await self._parse_args(ctx, args)
        if not username:
            return

        try:
            async with ctx.typing():
                user = await self.osu.get_user(username, mode)
                best = await self.osu.get_user_best_scores(user["id"], mode, limit=100)

            if not best:
                return await ctx.send(f"**{username}** no tiene plays en {mode}.")

            server_lang = "en"
            if ctx.guild:
                try:
                    server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)
                except Exception:
                    server_lang = "en"

            embed = OsuPresenter.build_top_card(user, best, mode=mode, lang=server_lang)

            # Gráfico de distribución de PP
            chart_file = await self._generate_pp_chart(username, best)
            if chart_file:
                embed.set_image(url="attachment://pp_distribution.png")
                await ctx.send(embed=embed, file=chart_file)
            else:
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en otop: {e}")
            await ctx.send(f"⚠️ error obteniendo top plays de '{username}'.")

    async def _generate_pp_chart(self, username: str, scores: list) -> discord.File | None:
        """Genera un gráfico de barras de distribución de PP con matplotlib ajustado dinámicamente."""
        try:
            import io
            import matplotlib
            matplotlib.use("Agg")  # Backend sin GUI — obligatorio en servidores
            import matplotlib.pyplot as plt
            import numpy as np

            pp_values = [s.get("pp", 0) for s in scores if s.get("pp")]
            if not pp_values:
                return None

            indices = list(range(1, len(pp_values) + 1))

            # Colores degradados por PP
            colors = plt.cm.plasma(np.linspace(0.9, 0.3, len(pp_values)))

            fig, ax = plt.subplots(figsize=(10, 4))
            fig.patch.set_facecolor("#18181b")  # Zinc Dark estética Dalet
            ax.set_facecolor("#111113")

            bars = ax.bar(indices, pp_values, color=colors, width=0.8, zorder=3)

            # Línea de tendencia polinómica
            if len(pp_values) > 3:
                z = np.polyfit(indices, pp_values, 2)
                p = np.poly1d(z)
                x_smooth = np.linspace(1, len(pp_values), 200)
                ax.plot(x_smooth, p(x_smooth), color="#ff69b4", linewidth=1.8,
                        linestyle="--", alpha=0.85, zorder=4)

            # Ajuste dinámico del mínimo vertical para acentuar caídas y perfil individual (feedback Delis)
            min_pp = min(pp_values)
            max_pp = max(pp_values)
            if len(pp_values) >= 5 and min_pp > 20:
                y_min = max(0, min_pp * 0.80)
                y_max = max_pp * 1.05
                ax.set_ylim(bottom=y_min, top=y_max)
            else:
                ax.set_ylim(bottom=0, top=max_pp * 1.05)

            ax.set_xlabel("Rank del play", color="#a1a1aa", fontsize=9)
            ax.set_ylabel("PP", color="#a1a1aa", fontsize=9)
            ax.set_title(f"Distribución de PP — {username}", color="white", fontsize=12, pad=10, fontweight="bold")
            ax.tick_params(colors="#71717a", labelsize=8)
            ax.spines[:].set_color("#27272a")
            ax.grid(axis="y", color="#27272a", alpha=0.6, zorder=1)

            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            return discord.File(buf, filename="pp_distribution.png")

        except Exception as e:
            logger.warning(f"No se pudo generar gráfico PP: {e}")
            return None

    # ------------------------------------------------------------------
    # d.compare — Comparar dos jugadores
    # ------------------------------------------------------------------

    @commands.command(name="compare", aliases=["vs"])
    async def osu_compare(self, ctx, user2: str, *, args: str = None):
        """Compara tu perfil de osu! contra otro jugador. Uso: d.compare usuario [-modo]"""
        mode = "osu"
        if args:
            for part in args.split():
                if part.startswith("-") and part[1:].lower() in VALID_MODES:
                    mode = part[1:].lower()

        # Usuario 1 = el autor del comando
        user1_name = await self.repo.get_linked_username(ctx.author.id)
        if not user1_name:
            return await ctx.send(
                "❌ vincula tu cuenta primero con `d.link <usuario>`."
            )

        try:
            async with ctx.typing():
                u1_data, u2_data = await asyncio.gather(
                    self.osu.get_user(user1_name, mode),
                    self.osu.get_user(user2, mode),
                )

            s1 = u1_data.get("statistics", {})
            s2 = u2_data.get("statistics", {})

            def delta(v1, v2, higher_better=True):
                """Devuelve flecha indicando quién gana."""
                if v1 == v2: return "🟰"
                return ("⬆️" if (v1 > v2) == higher_better else "⬇️")

            pp1, pp2   = s1.get("pp", 0), s2.get("pp", 0)
            rk1, rk2   = s1.get("global_rank", 0) or 0, s2.get("global_rank", 0) or 0
            acc1, acc2 = s1.get("hit_accuracy", 0), s2.get("hit_accuracy", 0)
            pc1, pc2   = s1.get("play_count", 0), s2.get("play_count", 0)
            h1, h2     = (s1.get("play_time", 0) or 0) // 3600, (s2.get("play_time", 0) or 0) // 3600

            n1, n2 = u1_data.get("username", user1_name), u2_data.get("username", user2)

            embed = discord.Embed(
                title=f"⚔️ {n1}  vs  {n2}",
                description=f"Modo: **{MODE_EMOJIS.get(mode, '')} {mode.upper()}**",
                color=0xE94560
            )
            embed.set_thumbnail(url=u1_data.get("avatar_url", ""))

            rows = [
                ("💎 PP",        f"{pp1:,.0f}", f"{pp2:,.0f}", delta(pp1, pp2)),
                ("🌍 Rank Global", f"#{rk1:,}" if rk1 else "?", f"#{rk2:,}" if rk2 else "?",
                 delta(rk1, rk2, higher_better=False)),
                ("🎯 Precisión",  f"{acc1:.2f}%", f"{acc2:.2f}%", delta(acc1, acc2)),
                ("🎵 Plays",      f"{pc1:,}", f"{pc2:,}", delta(pc1, pc2)),
                ("⏰ Horas",      f"{h1:,}h", f"{h2:,}h", delta(h1, h2)),
            ]

            table = f"{'Stat':<14} {n1[:10]:<12} {'vs':^5} {n2[:10]:<12}\n" + "─" * 46 + "\n"
            for stat, v1, v2, arrow in rows:
                table += f"{stat:<14} {v1:<12} {arrow:^5} {v2:<12}\n"

            embed.add_field(name="📊 Comparativa", value=f"```\n{table}```", inline=False)
            embed.set_footer(text=f"generado con ✨ por Dalet")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en compare: {e}")
            await ctx.send(f"⚠️ error comparando perfiles.")

    # ------------------------------------------------------------------
    # d.rank — Ranking del servidor
    # ------------------------------------------------------------------

    @commands.command(name="rank", aliases=["osurank"])
    async def osu_server_rank(self, ctx, *, args: str = None):
        """Muestra el ranking osu! entre los jugadores vinculados en este servidor."""
        mode = "osu"
        if args:
            for part in args.split():
                if part.startswith("-") and part[1:].lower() in VALID_MODES:
                    mode = part[1:].lower()

        try:
            async with ctx.typing():
                # Obtener todos los IDs de Discord de los miembros del servidor
                guild_member_ids = [str(m.id) for m in ctx.guild.members if not m.bot]

                # Obtener ranking solo de los miembros del servidor
                # Filtramos en Python desde el ranking global (evita query compleja)
                all_rows = await self.repo.get_ranking(limit=200)  # Traer más para filtrar
                server_rows = [
                    row for row in all_rows
                    if str(row.get("UserID") or row.get("userid") or "") in guild_member_ids
                ][:15]  # Limitar a top 15 del servidor

            if not server_rows:
                return await ctx.send(
                    "nadie en este servidor tiene cuenta vinculada todavía. "
                    "usa `d.link <usuario>` para entrar al ranking."
                )

            embed = discord.Embed(
                title=f"{DaletAtoms.EMOJI_DALET} Ranking osu! del Servidor — {mode.upper()}",
                color=DaletAtoms.COLOR_PRIMARY
            )

            lines = []
            medals = ["✦", "◈", "◇"]
            for i, row in enumerate(server_rows):
                medal = medals[i] if i < 3 else f"`{i+1}.`"
                name  = row.get("UserName") or row.get("username") or row.get("osuusername") or "??"
                pp    = float(row.get("PP") or row.get("pp") or 0)
                acc   = float(row.get("Accuracy") or row.get("accuracy") or 0)
                lines.append(f"{medal} **{name}** — {pp:,.0f}pp • {acc:.2f}%")

            embed.description = "\n".join(lines)
            embed.set_footer(text=f"{len(server_rows)} jugadores vinculados en este servidor")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en rank: {e}")
            await ctx.send("⚠️ error obteniendo el ranking.")

    # ------------------------------------------------------------------
    # d.progress — Gráfico de progreso de PP
    # ------------------------------------------------------------------

    @commands.command(name="progress", aliases=["prog"])
    async def osu_progress(self, ctx, member: discord.Member = None):
        """Muestra tu gráfico de progreso de PP a lo largo del tiempo."""
        member = member or ctx.author

        try:
            async with ctx.typing():
                history = await self.bot.analytics_repo.get_osu_progress(member.id, limit=30)

            if not history or len(history) < 2:
                return await ctx.send(
                    "necesito al menos 2 snapshots para hacer el gráfico. "
                    "usa `d.op` regularmente para que vaya registrando tu progreso."
                )

            loop = asyncio.get_running_loop()
            chart_file = await loop.run_in_executor(
                None, _create_progress_chart_sync, member.display_name, history
            )

            username = await self.repo.get_linked_username(member.id)
            embed = discord.Embed(
                title=f"📈 Progreso de PP — {username or member.display_name}",
                color=0x40C074
            )

            # Delta de PP
            first_pp = history[-1]["pp"]
            last_pp  = history[0]["pp"]
            delta    = last_pp - first_pp
            delta_str = f"+{delta:.0f}pp" if delta >= 0 else f"{delta:.0f}pp"
            color_delta = 0x40C074 if delta >= 0 else 0xE94560

            embed.color = color_delta
            embed.add_field(
                name="Resumen",
                value=(
                    f"PP actual: **{last_pp:,.0f}pp**\n"
                    f"Cambio total: **{delta_str}**\n"
                    f"Snapshots: **{len(history)}**"
                ),
                inline=False
            )

            if chart_file:
                embed.set_image(url="attachment://progress.png")
                await ctx.send(embed=embed, file=chart_file)
            else:
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en progress: {e}")
            await ctx.send("⚠️ error generando el gráfico de progreso.")


def _create_progress_chart_sync(username: str, history: list) -> discord.File | None:
    """Gráfico de línea de PP a lo largo del tiempo (ejecución síncrona fuera del loop)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        import numpy as np
        from datetime import datetime

        # History viene de más reciente a más antiguo — invertimos
        history_chron = list(reversed(history))

        dates, pp_vals = [], []
        for h in history_chron:
            ts = h.get("recorded_at", "")
            pp = h.get("pp", 0)
            if ts:
                try:
                    if hasattr(ts, "year"):
                        dates.append(ts)
                    else:
                        dates.append(datetime.fromisoformat(str(ts)[:19]))
                    pp_vals.append(pp)
                except Exception:
                    continue

        if len(dates) < 2:
            return None

        fig, ax = plt.subplots(figsize=(10, 4))
        fig.patch.set_facecolor("#1a1a2e")
        ax.set_facecolor("#16213e")

        # Área bajo la curva
        ax.fill_between(dates, pp_vals, alpha=0.2, color="#7f5af0")
        ax.plot(dates, pp_vals, color="#7f5af0", linewidth=2.5, zorder=5)
        ax.scatter(dates, pp_vals, color="#e94560", s=30, zorder=6)

        # Línea de tendencia
        if len(dates) >= 3:
            x_num = mdates.date2num(dates)
            z = np.polyfit(x_num, pp_vals, 1)
            p = np.poly1d(z)
            x_smooth = np.linspace(x_num[0], x_num[-1], 200)
            ax.plot(
                mdates.num2date(x_smooth), p(x_smooth),
                color="#2cb67d", linewidth=1.2, linestyle="--", alpha=0.6
            )

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=30, fontsize=8)

        ax.set_ylabel("PP", color="#ccc", fontsize=9)
        ax.set_title(f"Progreso PP — {username}", color="white", fontsize=12, pad=10)
        ax.tick_params(colors="#999", labelsize=8)
        ax.spines[:].set_color("#333")
        ax.grid(color="#333", alpha=0.4, zorder=1)

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return discord.File(buf, filename="progress.png")

    except Exception as e:
        logger.warning(f"No se pudo generar gráfico progress: {e}")
        return None




    # ------------------------------------------------------------------
    # d.op1s — #1s del usuario (bonus)
    # ------------------------------------------------------------------

    @commands.command(name="op1s", aliases=["firsts"])
    async def osu_firsts(self, ctx, *, args: str = None):
        """Muestra los #1 globales del jugador en osu!."""
        username, mode = await self._parse_args(ctx, args)
        if not username:
            return

        try:
            async with ctx.typing():
                user   = await self.osu.get_user(username, mode)
                firsts = await self.osu.get_user_firsts(user["id"], mode, limit=10)

            if not firsts:
                return await ctx.send(f"**{username}** no tiene #1 globales en {mode}.")

            lines = []
            for s in firsts[:10]:
                bmap  = s.get("beatmap", {})
                bset  = s.get("beatmapset", {})
                pp    = s.get("pp", 0)
                mods  = _mods_str(s.get("mods", []))
                title = bset.get("title", "??")[:35]
                stars = bmap.get("difficulty_rating", 0)
                lines.append(f"{DaletAtoms.EMOJI_DALET} **{title}** {stars:.1f}★ {mods} — **{pp:.0f}pp**")

            embed = discord.Embed(
                title=f"{DaletAtoms.EMOJI_DALET} #1s Globales — {username}",
                description="\n".join(lines),
                color=DaletAtoms.COLOR_PRIMARY
            )
            embed.set_thumbnail(url=user.get("avatar_url", ""))
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en op1s: {e}")
            await ctx.send(f"⚠️ error obteniendo los #1s de '{username}'.")

    # ------------------------------------------------------------------
    # d.skills / d.skill — Desglose de habilidades osu! (Skill Breakdown)
    # ------------------------------------------------------------------

    @commands.command(name="skills", aliases=["skill", "osk", "oa", "oc", "osuAnalyze"])
    async def osu_skills(self, ctx, *, args: str = None):
        """Desglose de habilidades (Aim, Speed, Acc, Stamina, Reading) con veredicto de Dalet."""
        username, mode = await self._parse_args(ctx, args)
        if not username:
            return

        try:
            async with ctx.typing():
                user = await self.osu.get_user(username, mode)
                best = await self.osu.get_user_best_scores(user["id"], mode, limit=100)

            if not best:
                return await ctx.send(f"**{username}** no tiene mejores jugadas registradas en {mode}.")

            server_lang = "en"
            if ctx.guild:
                try:
                    server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)
                except Exception:
                    server_lang = "en"

            # 1. Calcular habilidades ponderadas según el modo
            skills_data = OsuAnalyzer.calculate_skills(best, mode=mode, lang=server_lang)

            # 2. Generar roast/veredicto ultra conciso con Dalet (micro-prompt)
            dominant = skills_data.get("dominant_skill", "Aim")
            weakest = skills_data.get("weakest_skill", "Stamina")
            overall = skills_data.get("overall_skill_stars", 0.0)
            overall_pts = skills_data.get("overall_skill_points", 0.0)
            overall_tier = skills_data.get("overall_tier_name", "Master")
            dom_pts = skills_data.get(dominant, {}).get("points", 0.0)
            dom_tier = skills_data.get(dominant, {}).get("tier_name", "")
            weak_pts = skills_data.get(weakest, {}).get("points", 0.0)
            weak_tier = skills_data.get(weakest, {}).get("tier_name", "")
            stats = user.get("statistics", {})
            gr = stats.get("global_rank") or "N/A"

            is_es = server_lang == "es"
            if is_es:
                micro_prompt = (
                    f"ROL: Eres Dalet, una bot cínica, técnica y experta en osu! ({mode}).\n"
                    f"TAREA: Haz un roast o veredicto técnico contundente (MÁXIMO 2 ORACIONES, 25-35 palabras) sobre el perfil de {username}:\n"
                    f"- Modo: {mode}\n"
                    f"- Habilidad dominante: {dominant} ({dom_pts} pts [{dom_tier}])\n"
                    f"- Habilidad más débil: {weakest} ({weak_pts} pts [{weak_tier}])\n"
                    f"- Puntuación de Maestría General: {overall_pts} pts [{overall_tier}]\n"
                    f"- Rank global: #{gr}\n"
                    f"REGLAS: Búrlate con sarcasmo de su debilidad en {weakest} comparado con su {dominant}. Ve directo al grano sin introducciones. Cero rodeos. IDIOMA: Español."
                )
                system_override = "Eres Dalet, una IA sarcástica y experta en osu!. Da un veredicto técnico contundente en 1 o 2 oraciones cortas. Ve directo al grano, sin explicaciones previas ni rodeos."
                fallback_roasts = {
                    "Speed": "Mucho DT farmeado en mapas cortos, pero ponle una ráfaga rápida y se te traba el cerebro.",
                    "Stamina": "Aguantas maratones eternos de relleno, lástima que ante una ráfaga veloz te derritas.",
                    "Aim": "Metes buen acc en ritmos planos, pero te mueven los círculos dos milímetros y ya estás tirando miss.",
                    "Accuracy": "Mucho combo y estrellitas infladas, pero ese acc parece que tocas con guantes de boxeo.",
                    "Reading": "Buen reading en mapas lentos, pero te suben el scroll y ni te enteras de qué nota fallaste.",
                    "Patterning": "Te sabes el ritmo de memoria, pero te cambian dos colores de tambor seguidos y te da un colapso mental.",
                    "Agility": "Muy rápido corriendo en línea recta, pero te piden un cambio brusco de dirección y el plato vuela al vacío.",
                    "Precision": "Cazas frutas gigantes como si nada, pero achican el plato medio pixel y las gotas caen como lluvia.",
                    "Chordjack": "Mucho spam de teclas sueltas, pero te tiran tres acordes densos simultáneos y se te apagan los dedos.",
                    "LN": "Mucha pose apretando notas largas estáticas, pero te sueltan un fideo con inverse y tus dedos entran en cortocircuito.",
                    "Stream": "Muy cómodo con acordes estáticos, pero te meten una escalera fluida a 200 BPM y pareces una lavadora rota.",
                    "Tech": "Mucho spam de acordes planos, pero te meten dos bursts técnicos o un minijack veloz y se te cruzan los dedos."
                }
            else:
                micro_prompt = (
                    f"ROLE: You are Dalet, a cynical, witty, and sharp osu! expert ({mode}).\n"
                    f"TASK: Write a biting technical roast (MAX 2 SHORT SENTENCES, 25-35 words) about {username}'s profile in English:\n"
                    f"- Mode: {mode}\n"
                    f"- Dominant skill: {dominant} ({dom_pts} pts [{dom_tier}])\n"
                    f"- Weakest skill: {weakest} ({weak_pts} pts [{weak_tier}])\n"
                    f"- Overall Mastery Score: {overall_pts} pts [{overall_tier}]\n"
                    f"- Global rank: #{gr}\n"
                    f"RULES: Mock their weak {weakest} compared to their {dominant} with dry sarcasm. Be direct with no intro. No filler. LANGUAGE: English."
                )
                system_override = "You are Dalet, a sarcastic and witty osu! expert. Give a sharp, punchy technical verdict in 1-2 short sentences. Be direct, no fluff or preliminary reasoning."
                fallback_roasts = {
                    "Speed": "Lots of DT farmed on short maps, but throw you a fast burst and your hands fall apart.",
                    "Stamina": "You can endure endless marathon filler, too bad you melt the second any speed burst hits.",
                    "Aim": "Decent accuracy on flat rhythms, but move the circles two millimeters and you're already dropping misses.",
                    "Accuracy": "Inflated star rating and combo, but with that accuracy you might as well be tapping with boxing gloves.",
                    "Reading": "Decent reading on slow maps, but bump the scroll speed and you won't even know which note you choked.",
                    "Patterning": "You memorize the beat fine, but throw two alternating drum colors your way and your brain short-circuits.",
                    "Agility": "Fast sprinting in a straight line, but ask for a sharp direction snap and your plate flies into the void.",
                    "Precision": "Catching giant fruits is easy, but shrink the plate half a pixel and droplets pour past you like rain.",
                    "Chordjack": "Plenty of single-key spam, but throw dense chords at you and your fingers freeze instantly.",
                    "LN": "Holding down static long notes is easy, but throw in inverse noodles and your release timing completely vanishes.",
                    "Stream": "Comfortable with static chords, but throw a fluid 200 BPM stream at you and you sound like a broken washing machine.",
                    "Tech": "Fine tapping flat patterns, but throw two technical bursts or a quick minijack and your fingers cross instantly."
                }

            def _is_valid_roast(txt: str) -> bool:
                if not txt or not isinstance(txt, str):
                    return False
                t_str = txt.strip()
                words = t_str.split()
                if len(words) < 5:
                    return False
                if t_str[-1] not in ('.', '!', '?', '"', '”', '*'):
                    return False
                dangling = (
                    ' de', ' que', ' con', ' en', ' por', ' para', ' a', ' del', ' al',
                    ' of', ' to', ' the', ' with', ' and', ' or', ' but', ' in', ' on', ' at'
                )
                clean_no_punct = t_str.rstrip('.!?*"” ').lower()
                for d in dangling:
                    if clean_no_punct.endswith(d):
                        return False
                return True

            roast_text = None
            try:
                roast_text = await self.bot.nlp_service.generate_reply(
                    micro_prompt, "Skill Roast", username,
                    max_tokens_override=350,
                    system_prompt_override=system_override,
                    language=server_lang
                )
            except Exception as nlp_err:
                logger.warning(f"No se pudo generar roast para skills ({username}): {nlp_err}")

            if not _is_valid_roast(roast_text):
                fallback_default = f"Mucho número inflado en {dominant}, pero en {weakest} das pena ajena." if is_es else f"Over-inflated numbers in {dominant}, but your {weakest} is embarrassing."
                roast_text = fallback_roasts.get(weakest, fallback_default)

            embed = OsuPresenter.build_skills_card(user, skills_data, roast_text=roast_text, mode=mode, lang=server_lang)
            await ctx.send(embed=embed)
            await self._maybe_snapshot(ctx.author.id, username, user)

        except Exception as e:
            logger.error(f"Error en d.skills para {username}: {e}")
            traceback.print_exc()
            await ctx.send("⚠️ error calculando el desglose de habilidades.")


async def setup(bot):
    await bot.add_cog(OsuHandler(bot))