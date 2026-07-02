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

            embed = DaletOrganisms.create_osu_card(user, mode)

            # Añadir fecha de registro
            join_date = user.get("join_date", "")
            if join_date:
                join_dt = datetime.fromisoformat(join_date.replace("Z", "+00:00"))
                footer_text = embed.footer.text if embed.footer else ""
                embed.set_footer(text=f"{footer_text} • desde {join_dt.strftime('%d/%m/%Y')}")

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

            score_data = recent[0]
            bmap  = score_data.get("beatmap", {})
            bset  = score_data.get("beatmapset", {})
            stats_score = score_data.get("statistics", {})

            grade = score_data.get("rank", "?")
            grade_emoji = GRADE_EMOJIS.get(grade, "❓")
            mods  = _mods_str(score_data.get("mods", []))
            acc   = _acc_str(score_data.get("accuracy", 0))
            pp    = score_data.get("pp")
            pp_str = f"**{pp:.2f}pp**" if pp else "*(sin pp)*"
            
            combo = score_data.get("max_combo", 0)
            max_combo = bmap.get("max_combo") or "?"
            total_score = score_data.get("score", 0)

            title_name  = bset.get("title", "??")
            artist_name = bset.get("artist", "??")
            version     = bmap.get("version", "??")
            stars       = bmap.get("difficulty_rating", 0)
            bmap_url    = f"https://osu.ppy.sh/b/{bmap.get('id', 0)}"
            mapper      = bset.get("creator", "Desconocido")
            map_status  = bset.get("status", "unknown").upper()

            # Atributos técnicos del mapa
            bpm = bmap.get("bpm", 0)
            cs = bmap.get("cs", 0.0)
            ar = bmap.get("ar", 0.0)
            od = bmap.get("accuracy", 0.0) # OD en osu v2 se llama accuracy en beatmaps
            hp = bmap.get("drain", 0.0)    # HP en osu v2 se llama drain
            
            # Hits detallados
            n300 = stats_score.get("count_300", 0)
            n100 = stats_score.get("count_100", 0)
            n50  = stats_score.get("count_50", 0)
            nmiss = stats_score.get("count_miss", 0)
            ngeki = stats_score.get("count_geki", 0) # MAX en mania / 300g
            nkatu = stats_score.get("count_katu", 0) # 200 en mania/taiko

            embed = discord.Embed(
                title=f"{title_name} [{version}]",
                url=bmap_url,
                description=f"**{artist_name}** • {stars:.2f}★ • {mods}",
                color=_rank_color(user.get("statistics", {}).get("global_rank"))
            )
            embed.set_author(name=f"Jugada Reciente · {user.get('username')} ({mode.upper()})", icon_url=user.get("avatar_url", ""))
            
            # Usar la imagen de portada del mapa como thumbnail lateral
            cover_url = bset.get("covers", {}).get("list") or bset.get("covers", {}).get("cover")
            if cover_url:
                embed.set_thumbnail(url=cover_url)
            else:
                embed.set_thumbnail(url=user.get("avatar_url", ""))

            # Formatear Hits según el modo para más precisión técnica
            if mode == "mania":
                hits_str = f"MAX: `{ngeki}` • 300: `{n300}` • 200: `{nkatu}`\n100: `{n100}` • 50: `{n50}` • Miss: `{nmiss}`"
            elif mode == "taiko":
                hits_str = f"GREAT: `{n300}` • GOOD: `{n100}` • Miss: `{nmiss}`"
            else: # Standard / Catch
                hits_str = f"300: `{n300}` • 100: `{n100}` • 50: `{n50}` • Miss: `{nmiss}`"

            embed.add_field(
                name="Resultado",
                value=(
                    f"Rango: **{grade_emoji} {grade}**\n"
                    f"Precisión: **{acc}**\n"
                    f"PP: {pp_str}"
                ),
                inline=True
            )
            embed.add_field(
                name="Puntuación & Combo",
                value=(
                    f"Puntaje: `{total_score:,}`\n"
                    f"Combo: **{combo}x** / {max_combo}x\n"
                    f"Estado: `{map_status}`"
                ),
                inline=True
            )
            embed.add_field(
                name="Hits",
                value=hits_str,
                inline=False
            )
            embed.add_field(
                name="Información del Mapa",
                value=f"• BPM: `{bpm}` • CS: `{cs:.1f}` • AR: `{ar:.1f}` • OD: `{od:.1f}` • HP: `{hp:.1f}`",
                inline=False
            )

            # Tiempo relativo y Mapper en footer
            played_at = score_data.get("created_at", "")
            if played_at:
                played_dt = datetime.fromisoformat(played_at.replace("Z", "+00:00"))
                embed.set_footer(text=f"Mapeado por {mapper} · Jugado por {username}")
                embed.timestamp = played_dt
            else:
                embed.set_footer(text=f"Mapeado por {mapper}")

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

            # Top 5 para mostrar en texto
            top5 = best[:5]
            lines = []
            for i, s in enumerate(top5, 1):
                bmap  = s.get("beatmap", {})
                bset  = s.get("beatmapset", {})
                pp    = s.get("pp", 0)
                acc   = _acc_str(s.get("accuracy", 0))
                mods  = _mods_str(s.get("mods", []))
                grade = GRADE_EMOJIS.get(s.get("rank", "?"), "❓")
                title = bset.get("title", "??")[:30]
                stars = bmap.get("difficulty_rating", 0)
                lines.append(
                    f"`{i}.` {grade} **{pp:.0f}pp** • {acc} • {mods}\n"
                    f"   [{title} {s.get('beatmap', {}).get('version', '')}] {stars:.1f}★"
                )

            # Weighted PP total estimado
            weighted_pp = sum(s.get("pp", 0) * (0.95 ** i) for i, s in enumerate(best))

            embed = discord.Embed(
                title=f"🏆 Top Plays — {username}",
                url=f"https://osu.ppy.sh/users/{user['id']}/{mode}",
                description="\n".join(lines),
                color=_rank_color(user.get("statistics", {}).get("global_rank"))
            )
            embed.set_thumbnail(url=user.get("avatar_url", ""))
            embed.add_field(
                name="📊 Stats generales",
                value=(
                    f"PP real: **{user['statistics'].get('pp', 0):,.0f}pp**\n"
                    f"PP ponderado top 100: **{weighted_pp:,.0f}pp**\n"
                    f"Plays analizados: **{len(best)}**"
                ),
                inline=False
            )

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
        """Genera un gráfico de barras de distribución de PP con matplotlib."""
        try:
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
            fig.patch.set_facecolor("#1a1a2e")
            ax.set_facecolor("#16213e")

            bars = ax.bar(indices, pp_values, color=colors, width=0.8, zorder=3)

            # Línea de tendencia
            if len(pp_values) > 3:
                z = np.polyfit(indices, pp_values, 2)
                p = np.poly1d(z)
                x_smooth = np.linspace(1, len(pp_values), 200)
                ax.plot(x_smooth, p(x_smooth), color="#e94560", linewidth=1.5,
                        linestyle="--", alpha=0.7, zorder=4)

            ax.set_xlabel("Rank del play", color="#ccc", fontsize=9)
            ax.set_ylabel("PP", color="#ccc", fontsize=9)
            ax.set_title(f"Distribución de PP — {username}", color="white", fontsize=12, pad=10)
            ax.tick_params(colors="#999", labelsize=8)
            ax.spines[:].set_color("#333")
            ax.grid(axis="y", color="#333", alpha=0.5, zorder=1)

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
                title=f"🏆 Ranking osu! del Servidor — {MODE_EMOJIS.get(mode, '')} {mode.upper()}",
                color=0xFFD700
            )

            lines = []
            medals = ["🥇", "🥈", "🥉"]
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

            chart_file = await self._generate_progress_chart(
                member.display_name, history
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

    async def _generate_progress_chart(self, username: str, history: list) -> discord.File | None:
        """Gráfico de línea de PP a lo largo del tiempo."""
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
    # d.oa — Análisis IA completo
    # ------------------------------------------------------------------

    @commands.command(name="oa", aliases=["osuAnalyze", "oc"])
    async def osu_analyze(self, ctx, *, args: str = None):
        """Análisis profundo con IA de tu perfil de osu! — coaching incluido."""
        username, mode = await self._parse_args(ctx, args)
        if not username:
            return

        try:
            async with ctx.typing():
                user   = await self.osu.get_user(username, mode)
                recent = await self.osu.get_user_recent_scores(user["id"], mode, limit=50)
                best   = await self.osu.get_user_best_scores(user["id"], mode, limit=50)

            stats = user.get("statistics", {})
            embed = discord.Embed(
                title=f"📊 Análisis Dalet: {username}",
                url=f"https://osu.ppy.sh/users/{user['id']}/{mode}",
                color=_rank_color(stats.get("global_rank")),
                description="🔍 Generando análisis con IA..."
            )
            embed.set_thumbnail(url=user.get("avatar_url", ""))
            embed.add_field(name="PP",   value=f"`{stats.get('pp', 0):,.0f}`", inline=True)
            embed.add_field(name="Rank", value=f"`#{stats.get('global_rank', '?'):,}`", inline=True)
            embed.add_field(name="Acc",  value=f"`{stats.get('hit_accuracy', 0):.2f}%`", inline=True)
            msg = await ctx.send(embed=embed)

            # Generar análisis IA — con más tokens que una respuesta normal
            analyzer = OsuAnalyzer(self.osu, user, recent, best)
            prompt   = await analyzer.generate_super_prompt()
            response = await self.bot.nlp_service.generate_reply(
                prompt, "Análisis osu!", username,
                max_tokens_override=1200  # El análisis necesita más espacio
            )

            if response:
                # Dividir el reporte por secciones de Markdown (usualmente empiezan con '###')
                # O por bloques de 1900 caracteres como fallback
                sections = []
                current_section = ""
                
                for line in response.split("\n"):
                    if line.startswith("###") and current_section:
                        sections.append(current_section.strip())
                        current_section = line + "\n"
                    else:
                        current_section += line + "\n"
                if current_section:
                    sections.append(current_section.strip())

                # Si no se dividió bien en secciones, dividimos por caracteres
                if len(sections) <= 1 and len(response) > 1900:
                    sections = [response[i:i+1900] for i in range(0, len(response), 1900)]

                # Primer bloque va en el embed original
                embed.description = sections[0] if sections else "Error al procesar el análisis."
                embed.set_footer(text=f"Análisis generado por Dalet · Página 1/{len(sections)}")
                await msg.edit(embed=embed)

                # Los bloques siguientes se envían como nuevos embeds en el orden correcto
                for idx, sec in enumerate(sections[1:], start=2):
                    next_embed = discord.Embed(
                        description=sec,
                        color=embed.color
                    )
                    next_embed.set_footer(text=f"Análisis generado por Dalet · Página {idx}/{len(sections)}")
                    await ctx.send(embed=next_embed)
            else:
                embed.description = "no pude generar el análisis esta vez — inténtalo de nuevo."
                await msg.edit(embed=embed)

            await self._maybe_snapshot(ctx.author.id, username, user)

        except Exception as e:
            logger.error(f"Error en oa para {username}: {e}")
            traceback.print_exc()
            await ctx.send("⚠️ error técnico en el análisis.")

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
                lines.append(f"🥇 **{title}** {stars:.1f}★ {mods} — **{pp:.0f}pp**")

            embed = discord.Embed(
                title=f"🥇 #1s Globales — {username}",
                description="\n".join(lines),
                color=0xFFD700
            )
            embed.set_thumbnail(url=user.get("avatar_url", ""))
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en op1s: {e}")
            await ctx.send(f"⚠️ error obteniendo los #1s de '{username}'.")


async def setup(bot):
    await bot.add_cog(OsuHandler(bot))