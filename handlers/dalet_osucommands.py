import time
import logging
import asyncio

import discord
from discord.ext import commands

from ui.atoms import DaletAtoms
from ui.locales import t
from handlers.modules.dalet_osuanalyzer import OsuAnalyzer
from handlers.dalet_osu_presenter import OsuPresenter

logger = logging.getLogger("dalet.handlers.osu")

# Modos de juego válidos
VALID_MODES = {"osu", "taiko", "fruits", "mania"}


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
        username, mode, _, _ = await self._parse_osu_filter_args(ctx, args, default_filter="last")
        return username, mode

    async def _parse_osu_filter_args(self, ctx, args: str | None, default_filter: str = "last"):
        """
        Parsea argumentos flexibles al estilo de bots de osu! (Bathbot/owo):
        - Modo: -osu, -taiko, -mania, -fruits, -ctb, -catch
        - Filtro: best/-b, recent/-r/rb, pass/-p, acc/-a, pp
        - Mods: +dt, +hddt, +hr, +nm, etc.
        - Username: resto de argumentos (o cuenta vinculada del autor)
        """
        mode = "osu"
        filter_by = default_filter
        mods_filter = None
        user_tokens = []

        mode_aliases = {
            "osu": "osu", "std": "osu", "standard": "osu",
            "taiko": "taiko", "tko": "taiko",
            "fruits": "fruits", "ctb": "fruits", "catch": "fruits",
            "mania": "mania", "mna": "mania",
        }
        filter_aliases = {
            "best": "best", "-b": "best", "-best": "best",
            "recent": "recent", "-r": "recent", "-recent": "recent", "rb": "recent",
            "pass": "pass", "passes": "pass", "-p": "pass", "-pass": "pass",
            "acc": "acc", "accuracy": "acc", "-a": "acc", "-acc": "acc",
            "pp": "pp", "-pp": "pp",
            "last": "last",
        }

        if args:
            parts = args.split()
            for part in parts:
                low = part.lower().strip()
                if low.startswith("-") and low[1:] in mode_aliases:
                    mode = mode_aliases[low[1:]]
                elif low in filter_aliases:
                    filter_by = filter_aliases[low]
                elif low.startswith("+") and len(low) >= 3:
                    mods_filter = low[1:].upper()
                else:
                    user_tokens.append(part)

        username = " ".join(user_tokens).strip() if user_tokens else None
        if not username:
            username = await self.repo.get_linked_username(ctx.author.id)
            if not username:
                await ctx.send(
                    f"{DaletAtoms.GLYPH_POINTER} no tienes cuenta vinculada. usa `d.link <usuario>` primero."
                )
                return None, None, None, None
        return username, mode, filter_by, mods_filter

    async def _maybe_snapshot(self, discord_id: int, queried_username: str, user_data: dict, mode: str = "osu"):
        """Actualiza estadísticas cacheadas y snapshot diario si el usuario consultó su propia cuenta."""
        try:
            linked = await self.repo.get_linked_username(discord_id)
            if not linked or linked.lower() != queried_username.lower():
                return

            stats = user_data.get("statistics", {}) or {}
            pp           = float(stats.get("pp", 0.0) or 0.0)
            global_rank  = stats.get("global_rank")
            country_rank = stats.get("country_rank")
            accuracy     = float(stats.get("hit_accuracy", 0.0) or 0.0)
            queried_mode = (mode or user_data.get("playmode", "osu") or "osu").lower().strip()

            # Actualizar estadísticas cacheadas (no pisa PlayMode si consultó un modo secundario)
            await self.repo.update_cached_stats(
                discord_id, user_data["username"], pp, global_rank, country_rank, accuracy, mode=queried_mode
            )

            # Snapshot con cooldown de 3 min
            now = time.time()
            if now - self._snap_cooldowns.get(discord_id, 0) >= 180:
                await self.bot.analytics_repo.record_osu_snapshot(
                    discord_id, pp, global_rank, country_rank, accuracy, queried_mode
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
                return await ctx.send(f"{DaletAtoms.GLYPH_CROSS} no encontré a '{osu_username}' en osu!.")

            stats = user_data.get("statistics", {}) or {}
            pp = float(stats.get("pp", 0.0) or 0.0)
            gr = stats.get("global_rank")
            cr = stats.get("country_rank")
            acc = float(stats.get("hit_accuracy", 0.0) or 0.0)
            mode = (user_data.get("playmode") or "osu").lower().strip()

            await self.repo.link_account(
                ctx.author.id,
                user_data["username"],
                user_data["id"],
                mode,
                pp,
                gr,
                cr,
                acc,
            )

            # Primer snapshot inmediato en Analytics
            try:
                await self.bot.analytics_repo.record_osu_snapshot(
                    ctx.author.id,
                    pp,
                    gr,
                    cr,
                    acc,
                    mode,
                )
            except Exception:
                pass

            await ctx.send(f"{DaletAtoms.GLYPH_CHECK} cuenta vinculada con éxito a **{user_data['username']}**.")

        except Exception as e:
            logger.error(f"Error en link: {e}")
            await ctx.send(f"{DaletAtoms.GLYPH_CROSS} error al vincular la cuenta.")

    @commands.command(name="unlink")
    async def unlink(self, ctx):
        """Desvincula tu cuenta de osu!."""
        try:
            await self.repo.unlink_account(ctx.author.id)
            await ctx.send(f"{DaletAtoms.GLYPH_CHECK} vinculación con osu! eliminada.")
        except Exception as e:
            logger.error(f"Error en unlink: {e}")
            await ctx.send(f"{DaletAtoms.GLYPH_CROSS} error al desvincular.")

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
            await self._maybe_snapshot(ctx.author.id, username, user, mode=mode)

        except Exception as e:
            logger.error(f"Error en op para {username}: {e}")
            await ctx.send(f"{DaletAtoms.GLYPH_CROSS} no pude obtener el perfil de '{username}'.")

    # ------------------------------------------------------------------
    # d.orecent / d.or / d.rs / d.rp — Jugadas recientes con filtros
    # ------------------------------------------------------------------

    @commands.command(name="orecent", aliases=["or", "rs", "recent"])
    async def osu_recent(self, ctx, *, args: str = None):
        """Muestra tu última jugada de osu! (soporta filtros: best, pass, +mods, -modo)."""
        username, mode, filter_by, mods_filter = await self._parse_osu_filter_args(ctx, args, default_filter="last")
        if not username:
            return
        if filter_by not in ("last", "best", "pass"):
            filter_by = "last"

        try:
            fetch_limit = 50 if (filter_by != "last" or mods_filter) else 1
            include_fails = 0 if filter_by == "pass" else 1
            async with ctx.typing():
                user = await self.osu.get_user(username, mode)
                recent = await self.osu.get_user_recent_scores(
                    user["id"], mode, limit=fetch_limit, include_fails=include_fails
                )

            server_lang = "en"
            if ctx.guild:
                server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)

            if not recent:
                return await ctx.send(
                    f"{DaletAtoms.GLYPH_POINTER} {t('osu.no_recent', server_lang, username=username, mode=mode)}"
                )

            filtered = OsuPresenter.filter_recent_scores(recent, filter_by=filter_by, mods_filter=mods_filter)
            if not filtered:
                return await ctx.send(
                    f"{DaletAtoms.GLYPH_POINTER} {t('osu.no_recent_filtered', server_lang, username=username, mode=mode)}"
                )

            target_list = filtered[:1]
            await self.osu.enrich_scores_with_attributes(target_list, mode=mode)

            embed = OsuPresenter.build_recent_card(
                user.get("username", username),
                mode,
                target_list[0],
                user_data=user,
                lang=server_lang,
                filter_by=filter_by,
                mods_filter=mods_filter,
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en orecent: {e}")
            await ctx.send(f"{DaletAtoms.GLYPH_POINTER} error obteniendo jugada reciente de '{username}'.")

    @commands.command(name="recentpass", aliases=["rp"])
    async def osu_recent_pass(self, ctx, *, args: str = None):
        """Atajo directo para mostrar el último pass reciente sin fallos (d.rp)."""
        merged_args = f"{args} pass".strip() if args else "pass"
        await self.osu_recent(ctx, args=merged_args)

    # ------------------------------------------------------------------
    # d.otop / d.top / d.rb — Top plays con filtros (pp, recent, acc, +mods)
    # ------------------------------------------------------------------

    @commands.command(name="otop", aliases=["top"])
    async def osu_top(self, ctx, *, args: str = None):
        """Muestra tus mejores plays (soporta filtros: recent/rb/-r, acc/-a, +mods, -modo)."""
        username, mode, sort_by, mods_filter = await self._parse_osu_filter_args(ctx, args, default_filter="pp")
        if not username:
            return
        if sort_by == "best":
            sort_by = "pp"
        elif sort_by not in ("pp", "recent", "acc"):
            sort_by = "pp"

        try:
            async with ctx.typing():
                user = await self.osu.get_user(username, mode)
                best = await self.osu.get_user_best_scores(user["id"], mode, limit=100)

            server_lang = "en"
            if ctx.guild:
                try:
                    server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)
                except Exception:
                    server_lang = "en"

            if not best:
                return await ctx.send(f"{DaletAtoms.GLYPH_POINTER} **{username}** no tiene plays en {mode}.")

            filtered_best = OsuPresenter.filter_and_sort_top_scores(best, sort_by=sort_by, mods_filter=mods_filter)
            if not filtered_best:
                return await ctx.send(
                    f"{DaletAtoms.GLYPH_POINTER} {t('osu.top_none_filtered', server_lang, username=username, mode=mode)}"
                )

            await self.osu.enrich_scores_with_attributes(filtered_best[:5], mode=mode)

            embed = OsuPresenter.build_top_card(
                user,
                filtered_best,
                mode=mode,
                lang=server_lang,
                sort_by=sort_by,
                mods_filter=mods_filter,
            )

            # Gráfico de distribución de PP
            chart_file = OsuPresenter.generate_pp_chart(username, filtered_best, lang=server_lang)
            if chart_file:
                embed.set_image(url="attachment://pp_distribution.png")
                await ctx.send(embed=embed, file=chart_file)
            else:
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en otop: {e}")
            await ctx.send(f"{DaletAtoms.GLYPH_POINTER} error obteniendo top plays de '{username}'.")

    @commands.command(name="recentbest", aliases=["rb"])
    async def osu_recent_best(self, ctx, *, args: str = None):
        """Atajo directo para mostrar los mejores plays recientes del Top 100 (d.rb)."""
        merged_args = f"{args} recent".strip() if args else "recent"
        await self.osu_top(ctx, args=merged_args)

    # ------------------------------------------------------------------
    # d.compare — Comparar dos jugadores
    # ------------------------------------------------------------------

    @commands.command(name="compare", aliases=["vs"])
    async def osu_compare(self, ctx, *args):
        """Compara perfiles de osu! frente a frente. Uso: d.compare [user1] <user2> [-modo]"""
        mode = "osu"
        players = []
        for part in args:
            if part.startswith("-") and part[1:].lower() in VALID_MODES:
                mode = part[1:].lower()
            else:
                players.append(part)

        server_lang = "es"
        if ctx.guild:
            try:
                server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)
            except Exception:
                server_lang = "es"

        if len(players) >= 2:
            u1_name = players[0]
            u2_name = players[1]
        elif len(players) == 1:
            linked_name = await self.repo.get_linked_username(ctx.author.id)
            if not linked_name:
                return await ctx.send(f"{DaletAtoms.GLYPH_POINTER} {t('osu.compare_need_link', server_lang)}")
            u1_name = linked_name
            u2_name = players[0]
        else:
            return await ctx.send(f"{DaletAtoms.GLYPH_POINTER} Uso: `d.compare [usuario1] <usuario2> [-modo]`")

        try:
            async with ctx.typing():
                u1_data, u2_data = await asyncio.gather(
                    self.osu.get_user(u1_name, mode),
                    self.osu.get_user(u2_name, mode),
                )

                b1, b2 = await asyncio.gather(
                    self.osu.get_user_best_scores(u1_data["id"], mode=mode, limit=100),
                    self.osu.get_user_best_scores(u2_data["id"], mode=mode, limit=100),
                    return_exceptions=True
                )
                b1_list = b1 if isinstance(b1, list) else []
                b2_list = b2 if isinstance(b2, list) else []

                await asyncio.gather(
                    self.osu.enrich_scores_with_attributes(b1_list[:12], mode=mode),
                    self.osu.enrich_scores_with_attributes(b2_list[:12], mode=mode),
                    return_exceptions=True
                )

                skills1 = OsuAnalyzer.calculate_skills(b1_list, mode=mode, lang=server_lang)
                skills2 = OsuAnalyzer.calculate_skills(b2_list, mode=mode, lang=server_lang)
                common_maps = OsuAnalyzer.find_common_top_maps(b1_list, b2_list, limit=3)

                verdict_text = None
                try:
                    pp1 = float((u1_data.get("statistics") or {}).get("pp") or 0.0)
                    pp2 = float((u2_data.get("statistics") or {}).get("pp") or 0.0)
                    dom1 = skills1.get("dominant_skill", "Aim")
                    dom2 = skills2.get("dominant_skill", "Aim")
                    cw1 = common_maps.get("wins1", 0)
                    cw2 = common_maps.get("wins2", 0)
                    tot_c = common_maps.get("total_common", 0)
                    is_es = server_lang.startswith("es")
                    if is_es:
                        cmp_prompt = (
                            f"ROL: Eres Dalet, analista mordaz de osu! ({mode}).\n"
                            f"TAREA: Escribe un veredicto de duelo (MÁX 2 ORACIONES CORTAS, 25-35 palabras) entre {u1_data.get('username', u1_name)} ({pp1:.0f}pp, fuerte en {dom1}) "
                            f"y {u2_data.get('username', u2_name)} ({pp2:.0f}pp, fuerte en {dom2}). "
                            f"Mapas en común en su Top: {tot_c} ({cw1} a {cw2}). Di quién domina y por qué con sarcasmo ingenioso sin ser cruel."
                        )
                        sys_ov = "Eres Dalet. Da un veredicto técnico y sarcástico de 1-2 oraciones sobre este duelo de osu!."
                    else:
                        cmp_prompt = (
                            f"ROLE: You are Dalet, sharp osu! analyst ({mode}).\n"
                            f"TASK: Write a 1-2 sentence duel verdict (25-35 words) comparing {u1_data.get('username', u1_name)} ({pp1:.0f}pp, best at {dom1}) "
                            f"vs {u2_data.get('username', u2_name)} ({pp2:.0f}pp, best at {dom2}). "
                            f"Shared Top Maps: {tot_c} ({cw1}-{cw2}). Declare who takes the crown with witty dry humor."
                        )
                        sys_ov = "You are Dalet. Give a sharp 1-2 sentence technical verdict on this osu! duel."
                    verdict_text = await self.bot.nlp_service.generate_reply(
                        cmp_prompt, "Compare Verdict", u1_name,
                        max_tokens_override=280,
                        system_prompt_override=sys_ov,
                        language=server_lang,
                    )
                except Exception:
                    verdict_text = None

                embed = OsuPresenter.build_compare_card(
                    u1_data, u2_data,
                    skills1=skills1,
                    skills2=skills2,
                    mode=mode,
                    lang=server_lang,
                    common_maps_data=common_maps,
                    verdict_text=verdict_text,
                )
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en compare: {e}")
            await ctx.send(f"{DaletAtoms.GLYPH_POINTER} error comparando perfiles.")

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

        server_lang = "en"
        if ctx.guild:
            try:
                server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)
            except Exception:
                server_lang = "en"

        try:
            async with ctx.typing():
                guild_member_ids = {str(m.id) for m in ctx.guild.members if not m.bot}
                all_rows = await self.repo.get_ranking(mode=mode, limit=500)

                def _get_val(r, *keys, default=""):
                    if isinstance(r, dict):
                        for k in keys:
                            if k in r and r[k] is not None:
                                return r[k]
                        return default
                    for k in keys:
                        try:
                            v = r[k]
                            if v is not None:
                                return v
                        except Exception:
                            pass
                    return default

                server_rows = []
                for row in all_rows:
                    uid = str(_get_val(row, "UserID", "userid", 0, default=""))
                    if uid and uid in guild_member_ids:
                        server_rows.append(row)
                        if len(server_rows) >= 15:
                            break

            if not server_rows:
                return await ctx.send(
                    f"{DaletAtoms.GLYPH_POINTER} {t('rank.empty', server_lang)}"
                )

            embed = discord.Embed(
                title=f"✦ Ranking osu! del Servidor — {_mode_title(mode)}",
                color=DaletAtoms.COLOR_PRIMARY
            )

            lines = []
            medals = ["✦", "◈", "◇"]
            for i, row in enumerate(server_rows):
                medal = medals[i] if i < 3 else f"`{i+1}.`"
                osu_name = _get_val(row, "OsuUsername", "osuusername", "UserName", "username", 1, default="??")
                pp   = float(_get_val(row, "PP", "pp", 5, default=0) or 0)
                acc  = float(_get_val(row, "Accuracy", "accuracy", 8, default=0) or 0)
                gr   = _get_val(row, "GlobalRank", "globalrank", 6, default=None)
                gr_str = f" (#{int(gr):,})" if gr else ""
                lines.append(f"{medal} **{osu_name}** — `{pp:,.0f}pp` • `{acc:.2f}%`{gr_str}")

            embed.description = "\n".join(lines)
            footer_txt = f"{len(server_rows)} jugadores vinculados en este servidor" if server_lang.startswith("es") else f"{len(server_rows)} linked players in this server"
            embed.set_footer(text=footer_txt)
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en rank: {e}")
            await ctx.send(f"{DaletAtoms.GLYPH_CROSS} {t('rank.error', server_lang)}")

    # ------------------------------------------------------------------
    # d.progress — Gráfico de progreso de PP
    # ------------------------------------------------------------------

    @commands.command(name="progress", aliases=["prog"])
    async def osu_progress(self, ctx, member: discord.Member = None):
        """Muestra tu gráfico de progreso de PP a lo largo del tiempo."""
        member = member or ctx.author

        server_lang = "en"
        if ctx.guild:
            try:
                server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)
            except Exception:
                server_lang = "en"

        try:
            async with ctx.typing():
                history = await self.bot.analytics_repo.get_osu_progress(member.id, mode="osu", limit=30)

            if not history or len(history) < 2:
                return await ctx.send(
                    f"{DaletAtoms.GLYPH_POINTER} {t('osu.progress_need_snapshots', server_lang)}"
                )

            loop = asyncio.get_running_loop()
            chart_file = await loop.run_in_executor(
                None, OsuPresenter.generate_progress_chart, member.display_name, history, server_lang
            )

            username = await self.repo.get_linked_username(member.id)
            display_name = username or member.display_name
            embed = discord.Embed(
                title=f"✦ {t('osu.progress_title', server_lang, username=display_name, mode='Standard')}",
                color=DaletAtoms.COLOR_PRIMARY
            )

            # Delta de PP cronológico: history[0] es el más reciente, history[-1] el más antiguo
            first_pp = float(history[-1]["pp"] or 0.0)
            last_pp  = float(history[0]["pp"] or 0.0)
            delta    = last_pp - first_pp
            delta_str = f"+{delta:.1f}pp" if delta >= 0 else f"{delta:.1f}pp"

            embed.add_field(
                name=f"{DaletAtoms.GLYPH_POINTER} {t('osu.progress_summary', server_lang)}",
                value=(
                    f"{DaletAtoms.GLYPH_POINTER} **{t('osu.progress_current_pp', server_lang)}**: `{last_pp:,.1f}pp`\n"
                    f"{DaletAtoms.GLYPH_POINTER} **{t('osu.progress_change', server_lang)}**: `{delta_str}`\n"
                    f"{DaletAtoms.GLYPH_POINTER} **{t('osu.progress_snapshots', server_lang)}**: `{len(history)}`"
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
            await ctx.send(f"{DaletAtoms.GLYPH_CROSS} error generando el gráfico de progreso.")

    # ------------------------------------------------------------------
    # d.op1s — #1s del usuario
    # ------------------------------------------------------------------

    @commands.command(name="op1s", aliases=["firsts"])
    async def osu_firsts(self, ctx, *, args: str = None):
        """Muestra los #1 globales del jugador en osu!."""
        username, mode = await self._parse_args(ctx, args)
        if not username:
            return

        server_lang = "en"
        if ctx.guild:
            try:
                server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)
            except Exception:
                server_lang = "en"

        try:
            async with ctx.typing():
                user   = await self.osu.get_user(username, mode)
                firsts = await self.osu.get_user_firsts(user["id"], mode, limit=10)

            if not firsts:
                return await ctx.send(
                    f"{DaletAtoms.GLYPH_POINTER} {t('osu.firsts_none', server_lang, username=username, mode=_mode_title(mode))}"
                )

            await self.osu.enrich_scores_with_attributes(firsts[:10], mode=mode)
            embed = OsuPresenter.build_firsts_card(user.get("username", username), firsts, user_data=user, mode=mode, lang=server_lang)
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en op1s: {e}")
            await ctx.send(f"{DaletAtoms.GLYPH_CROSS} error obteniendo los #1s de '{username}'.")

    # ------------------------------------------------------------------
    # d.skills / d.skill — Desglose de habilidades osu! (Skill Breakdown)
    # ------------------------------------------------------------------

    @commands.command(name="skills", aliases=["skill", "osk", "oa", "oc", "osuAnalyze"])
    async def osu_skills(self, ctx, *, args: str = None):
        """Desglose de habilidades (Aim, Speed, Acc, Stamina, Reading) con veredicto de Dalet."""
        username, mode, _, mods_filter = await self._parse_osu_filter_args(ctx, args, default_filter="pp")
        if not username:
            return

        try:
            async with ctx.typing():
                user = await self.osu.get_user(username, mode)
                best = await self.osu.get_user_best_scores(user["id"], mode, limit=100)

            if not best:
                return await ctx.send(f"{DaletAtoms.GLYPH_POINTER} **{username}** no tiene mejores jugadas registradas en {mode}.")

            server_lang = "en"
            if ctx.guild:
                try:
                    server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)
                except Exception:
                    server_lang = "en"

            target_scores = best
            if mods_filter:
                target_scores = OsuPresenter.filter_and_sort_top_scores(best, sort_by="pp", mods_filter=mods_filter)
                if not target_scores:
                    return await ctx.send(
                        f"{DaletAtoms.GLYPH_POINTER} {t('osu.top_none_filtered', server_lang, username=username, mode=mode)}"
                    )

            await self.osu.enrich_scores_with_attributes(target_scores[:15], mode=mode)

            # 1. Calcular habilidades ponderadas según el modo
            skills_data = OsuAnalyzer.calculate_skills(target_scores, mode=mode, lang=server_lang)

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

            embed = OsuPresenter.build_skills_card(
                user, skills_data, roast_text=roast_text, mode=mode, lang=server_lang, mods_filter=mods_filter
            )
            await ctx.send(embed=embed)
            await self._maybe_snapshot(ctx.author.id, username, user)

        except Exception as e:
            logger.error(f"Error en d.skills para {username}: {e}", exc_info=True)
            await ctx.send(f"{DaletAtoms.GLYPH_POINTER} error calculando el desglose de habilidades.")


async def setup(bot):
    await bot.add_cog(OsuHandler(bot))