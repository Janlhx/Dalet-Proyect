import time
import logging
import asyncio

import discord
from discord.ext import commands

from ui.atoms import DaletAtoms
from ui.locales import t
from services.osu_service import OsuService, OsuUserNotFoundError
from handlers.modules.dalet_osuanalyzer import OsuAnalyzer
from handlers.dalet_osu_presenter import OsuPresenter

logger = logging.getLogger("dalet.handlers.osu")

# Modos de juego válidos
VALID_MODES = {"osu", "taiko", "fruits", "mania"}

MODE_FLAG_ALIASES = {
    "osu": "osu", "std": "osu", "standard": "osu", "o": "osu",
    "taiko": "taiko", "tko": "taiko", "t": "taiko",
    "fruits": "fruits", "ctb": "fruits", "catch": "fruits", "c": "fruits",
    "mania": "mania", "mna": "mania", "m": "mania",
}

SERVER_FLAG_ALIASES = {
    "bancho": "bancho", "official": "bancho",
    "akatsuki": "akatsuki", "aka": "akatsuki", "vn": "akatsuki",
    "rx": "akatsuki_rx", "relax": "akatsuki_rx", "akatsuki_rx": "akatsuki_rx", "akarx": "akatsuki_rx", "aka-rx": "akatsuki_rx",
    "ap": "akatsuki_ap", "autopilot": "akatsuki_ap", "akatsuki_ap": "akatsuki_ap", "akaap": "akatsuki_ap", "aka-ap": "akatsuki_ap",
    "gatari": "gatari", "gat": "gatari",
}

SERVER_PRIMARY_FLAG = {
    "bancho": "",
    "akatsuki": " -aka",
    "akatsuki_rx": " -rx",
    "akatsuki_ap": " -ap",
    "gatari": " -gatari",
}

FILTER_FLAG_ALIASES = {
    "best": "best", "-b": "best", "-best": "best",
    "recent": "recent", "-r": "recent", "-recent": "recent", "rb": "recent",
    "pass": "pass", "passes": "pass", "-p": "pass", "-pass": "pass",
    "acc": "acc", "accuracy": "acc", "-a": "acc", "-acc": "acc",
    "pp": "pp", "-pp": "pp",
    "last": "last",
}


class OsuHandler(commands.Cog, name="osu!"):
    """Comandos de osu! — perfil, jugadas, análisis, multi-servidor y ranking."""

    def __init__(self, bot):
        self.bot = bot
        self.osu = bot.osu_service
        self.repo = bot.osu_repo
        self._snap_cooldowns: dict[int, float] = {}

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    async def _resolve_lang(self, ctx) -> str:
        """Resuelve el idioma efectivo en O(1) con cascada Usuario > Servidor > Default."""
        guild_id = ctx.guild.id if getattr(ctx, "guild", None) else None
        try:
            return await self.bot.admin_repo.resolve_language(ctx.author.id, guild_id, default="en")
        except Exception:
            return "en"

    async def _parse_args(self, ctx, args: str | None, default_mode: str = "osu"):
        """Parsea argumentos: extraer username, modo y servidor."""
        username, mode, _, _, server = await self._parse_osu_filter_args(
            ctx, args, default_filter="last", default_mode=default_mode
        )
        return username, mode, server

    @staticmethod
    def _merge_server_flag(current_server: str, candidate_server: str) -> str:
        """Evita que '-aka' degrade '-rx'/'-ap' a vanilla si se escriben en distinto orden (-rx -aka)."""
        if candidate_server == "akatsuki" and current_server in ("akatsuki_rx", "akatsuki_ap"):
            return current_server
        return candidate_server

    @staticmethod
    def _clean_username_tokens(tokens: list[str]) -> str:
        joined = " ".join(tokens).strip()
        if len(joined) >= 2 and joined[0] == joined[-1] and joined[0] in ('"', "'", "`"):
            joined = joined[1:-1].strip()
        return joined

    async def _parse_osu_filter_args(
        self,
        ctx,
        args: str | None,
        default_filter: str = "last",
        default_mode: str = "osu",
    ):
        """
        Parsea argumentos flexibles al estilo de bots de osu! (Bathbot/owo):
        - Modo: -osu/-std/-o, -taiko/-t, -mania/-m, -fruits/-ctb/-c
        - Servidor: -bancho, -akatsuki/-aka, -rx/-relax, -ap/-autopilot, -gatari/-gat
        - Filtro: best/-b, recent/-r/rb, pass/-p, acc/-a, pp
        - Mods: +dt, +hddt, +hr, +nm, etc.
        - Username: resto de argumentos (o cuenta vinculada del autor en ese servidor)
        """
        mode = default_mode or "osu"
        server = "bancho"
        filter_by = default_filter
        mods_filter = None
        user_tokens = []

        if args:
            parts = args.split()
            for part in parts:
                low = part.lower().strip()
                stripped = low.lstrip("-")
                if low.startswith("-") and stripped in SERVER_FLAG_ALIASES:
                    server = self._merge_server_flag(server, SERVER_FLAG_ALIASES[stripped])
                elif low.startswith("-") and stripped in MODE_FLAG_ALIASES:
                    mode = MODE_FLAG_ALIASES[stripped]
                elif low in FILTER_FLAG_ALIASES:
                    filter_by = FILTER_FLAG_ALIASES[low]
                elif low.startswith("+") and len(low) >= 3:
                    mods_filter = low[1:].upper()
                else:
                    user_tokens.append(part)

        username = self._clean_username_tokens(user_tokens) if user_tokens else None
        if not username:
            username = await self.repo.get_linked_username(ctx.author.id, server=server)
            if not username:
                lang = await self._resolve_lang(ctx)
                srv_title = OsuPresenter.server_title(server)
                srv_flag = SERVER_PRIMARY_FLAG.get(server, "")
                hint = ""
                try:
                    if hasattr(self.repo, "get_linked_accounts"):
                        other = await self.repo.get_linked_accounts(ctx.author.id)
                        if isinstance(other, dict) and other:
                            labels = ", ".join(OsuPresenter.server_title(k) for k in other.keys())
                            hint = f"\n{DaletAtoms.GLYPH_SUB} Vinculados: {labels}" if lang.startswith("es") else f"\n{DaletAtoms.GLYPH_SUB} Linked: {labels}"
                except Exception:
                    pass
                if lang.startswith("es"):
                    await ctx.send(
                        f"{DaletAtoms.GLYPH_POINTER} no tienes cuenta vinculada para **{srv_title}**. usa `d.link <usuario>{srv_flag}` primero.{hint}"
                    )
                else:
                    await ctx.send(
                        f"{DaletAtoms.GLYPH_POINTER} you don't have a linked account for **{srv_title}**. use `d.link <username>{srv_flag}` first.{hint}"
                    )
                return None, None, None, None, None
        return username, mode, filter_by, mods_filter, server

    async def _maybe_snapshot(self, discord_id: int, queried_username: str, user_data: dict, mode: str = "osu", server: str = "bancho"):
        """Actualiza estadísticas cacheadas y snapshot diario si el usuario consultó su propia cuenta en Bancho."""
        if server != "bancho":
            return
        try:
            linked = await self.repo.get_linked_username(discord_id, server="bancho")
            if not linked or linked.lower() != queried_username.lower():
                return

            stats = user_data.get("statistics", {}) or {}
            pp           = float(stats.get("pp", 0.0) or 0.0)
            global_rank  = stats.get("global_rank")
            country_rank = stats.get("country_rank")
            accuracy     = float(stats.get("hit_accuracy", 0.0) or 0.0)
            queried_mode = (mode or user_data.get("playmode", "osu") or "osu").lower().strip()

            await self.repo.update_cached_stats(
                discord_id, user_data["username"], pp, global_rank, country_rank, accuracy, mode=queried_mode
            )

            now = time.time()
            if now - self._snap_cooldowns.get(discord_id, 0) >= 180:
                await self.bot.analytics_repo.record_osu_snapshot(
                    discord_id, pp, global_rank, country_rank, accuracy, queried_mode
                )
                self._snap_cooldowns[discord_id] = now

        except Exception as e:
            logger.debug(f"[OsuSnapshot] Error no crítico: {e}")

    # ------------------------------------------------------------------
    # d.lang / d.language — Preferencia de idioma personal o de servidor
    # ------------------------------------------------------------------

    @commands.command(name="lang", aliases=["language", "idioma"])
    async def set_language_cmd(self, ctx, *, args: str = None):
        """Configura tu idioma personal (es/en/auto) o el del servidor (d.lang server es)."""
        lang = await self._resolve_lang(ctx)
        is_es = lang.startswith("es")
        if not args:
            msg = (
                f"{DaletAtoms.GLYPH_POINTER} Idioma actual: **{lang.upper()}**. Usa `d.lang es`, `d.lang en` o `d.lang auto`."
                if is_es else
                f"{DaletAtoms.GLYPH_POINTER} Current language: **{lang.upper()}**. Use `d.lang es`, `d.lang en`, or `d.lang auto`."
            )
            return await ctx.send(msg)

        tokens = [t_part.lower().strip() for t_part in args.split() if t_part.strip()]
        scope = "user"
        target_lang = tokens[0]
        if len(tokens) >= 2 and tokens[0] in ("server", "srv", "guild", "sv"):
            scope = "server"
            target_lang = tokens[1]

        lang_map = {
            "es": "es", "esp": "es", "spanish": "es", "español": "es", "espanol": "es",
            "en": "en", "eng": "en", "english": "en", "ingles": "en", "inglés": "en",
            "auto": "auto", "reset": "auto", "default": "auto", "none": "auto",
        }
        norm_lang = lang_map.get(target_lang)
        if not norm_lang:
            return await ctx.send(
                f"{DaletAtoms.GLYPH_CROSS} Usa `d.lang es`, `d.lang en` o `d.lang auto`."
                if is_es else
                f"{DaletAtoms.GLYPH_CROSS} Use `d.lang es`, `d.lang en`, or `d.lang auto`."
            )

        if scope == "server":
            if not ctx.guild or not ctx.author.guild_permissions.administrator:
                return await ctx.send(
                    f"{DaletAtoms.GLYPH_CROSS} Necesitas permisos de Administrador para cambiar el idioma del servidor."
                    if is_es else
                    f"{DaletAtoms.GLYPH_CROSS} You need Administrator permissions to change the server language."
                )
            srv_code = "en" if norm_lang == "auto" else norm_lang
            await self.bot.admin_repo.set_server_language(ctx.guild.id, srv_code, ctx.guild.name)
            return await ctx.send(f"{DaletAtoms.GLYPH_CHECK} {t('lang.updated', srv_code)}")

        await self.bot.admin_repo.set_user_language(
            ctx.author.id, None if norm_lang == "auto" else norm_lang, str(ctx.author)
        )
        eff = await self._resolve_lang(ctx)
        if norm_lang == "auto":
            confirm = (
                f"{DaletAtoms.GLYPH_CHECK} Tu idioma personal ahora sigue el del servidor (**{eff.upper()}**)."
                if eff.startswith("es") else
                f"{DaletAtoms.GLYPH_CHECK} Your personal language now follows the server default (**{eff.upper()}**)."
            )
        else:
            confirm = (
                f"{DaletAtoms.GLYPH_CHECK} Tu idioma personal se ha actualizado a **Español**."
                if norm_lang == "es" else
                f"{DaletAtoms.GLYPH_CHECK} Your personal language has been set to **English**."
            )
        await ctx.send(confirm)

    # ------------------------------------------------------------------
    # d.link / d.unlink (Multi-servidor)
    # ------------------------------------------------------------------

    @commands.command(name="link")
    async def link(self, ctx, *, args: str = None):
        """Vincula tu cuenta de Discord con tu perfil de osu! (soporta -aka, -rx, -ap, -gatari, -modo)."""
        lang = await self._resolve_lang(ctx)
        is_es = lang.startswith("es")
        if not args or not args.strip():
            linked_summary = ""
            try:
                if hasattr(self.repo, "get_linked_accounts"):
                    accounts = await self.repo.get_linked_accounts(ctx.author.id)
                    if isinstance(accounts, dict) and accounts:
                        rows_txt = "\n".join(
                            f"{DaletAtoms.GLYPH_SUB} **{OsuPresenter.server_title(srv)}**: `{uname}`"
                            for srv, uname in accounts.items()
                        )
                        hdr = "Cuentas vinculadas actualmente:" if is_es else "Currently linked accounts:"
                        linked_summary = f"\n\n{hdr}\n{rows_txt}"
            except Exception:
                pass
            msg = (
                f"{DaletAtoms.GLYPH_POINTER} Uso: `d.link <usuario> [-aka|-rx|-ap|-gatari] [-std|-mania|-taiko|-ctb]`{linked_summary}"
                if is_es else
                f"{DaletAtoms.GLYPH_POINTER} Usage: `d.link <username> [-aka|-rx|-ap|-gatari] [-std|-mania|-taiko|-ctb]`{linked_summary}"
            )
            return await ctx.send(msg)

        server = "bancho"
        mode = None
        user_tokens = []
        for part in args.split():
            low = part.lower().strip()
            stripped = low.lstrip("-")
            if low.startswith("-") and stripped in SERVER_FLAG_ALIASES:
                server = self._merge_server_flag(server, SERVER_FLAG_ALIASES[stripped])
            elif low.startswith("-") and stripped in MODE_FLAG_ALIASES:
                mode = MODE_FLAG_ALIASES[stripped]
            else:
                user_tokens.append(part)

        osu_username = self._clean_username_tokens(user_tokens)
        if not osu_username:
            return await ctx.send(
                f"{DaletAtoms.GLYPH_CROSS} Especifica tu nombre de usuario de osu! (ej: `d.link tu_nombre -gatari`)."
                if is_es else
                f"{DaletAtoms.GLYPH_CROSS} Specify your osu! username (e.g. `d.link your_name -gatari`)."
            )
        if osu_username.startswith("<@") and osu_username.endswith(">"):
            return await ctx.send(
                f"{DaletAtoms.GLYPH_CROSS} Escribe tu nombre de usuario de osu!, no una mención de Discord."
                if is_es else
                f"{DaletAtoms.GLYPH_CROSS} Enter your osu! username, not a Discord mention."
            )

        srv_label = OsuPresenter.server_title(server)
        try:
            async with ctx.typing():
                user_data = await self.osu.get_user(osu_username, mode=mode or "osu", server=server)

            if not user_data or "statistics" not in user_data:
                return await ctx.send(
                    f"{DaletAtoms.GLYPH_CROSS} no encontré a `{osu_username}` en **{srv_label}**."
                    if is_es else
                    f"{DaletAtoms.GLYPH_CROSS} couldn't find `{osu_username}` on **{srv_label}**."
                )

            stats = user_data.get("statistics", {}) or {}
            pp = float(stats.get("pp", 0.0) or 0.0)
            gr = stats.get("global_rank")
            cr = stats.get("country_rank")
            acc = float(stats.get("hit_accuracy", 0.0) or 0.0)
            resolved_mode = (mode or user_data.get("playmode") or "osu").lower().strip()

            await self.repo.link_account(
                ctx.author.id,
                user_data["username"],
                user_data["id"],
                resolved_mode,
                pp,
                gr,
                cr,
                acc,
                server=server,
            )

            if server == "bancho":
                try:
                    await self.bot.analytics_repo.record_osu_snapshot(
                        ctx.author.id, pp, gr, cr, acc, resolved_mode
                    )
                except Exception:
                    pass

            mode_label = OsuPresenter.mode_title(resolved_mode)
            msg = (
                f"{DaletAtoms.GLYPH_CHECK} cuenta vinculada con éxito a **{user_data['username']}** (`{srv_label}` · `{mode_label}`)."
                if is_es else
                f"{DaletAtoms.GLYPH_CHECK} account linked to **{user_data['username']}** (`{srv_label}` · `{mode_label}`)."
            )
            await ctx.send(msg)

        except OsuUserNotFoundError:
            await ctx.send(
                f"{DaletAtoms.GLYPH_CROSS} no encontré a `{osu_username}` en **{srv_label}**."
                if is_es else
                f"{DaletAtoms.GLYPH_CROSS} couldn't find `{osu_username}` on **{srv_label}**."
            )
        except Exception as e:
            logger.error(f"Error en d.link ({server} / {osu_username}): {e}", exc_info=True)
            await ctx.send(
                f"{DaletAtoms.GLYPH_CROSS} error al vincular la cuenta en **{srv_label}**."
                if is_es else
                f"{DaletAtoms.GLYPH_CROSS} failed to link account on **{srv_label}**."
            )

    @commands.command(name="unlink")
    async def unlink(self, ctx, *, args: str = None):
        """Desvincula tu cuenta de osu! (general o de un servidor específico con -aka/-rx/-gatari)."""
        lang = await self._resolve_lang(ctx)
        is_es = lang.startswith("es")
        server = None
        if args:
            for part in args.split():
                low = part.lower().strip()
                stripped = low.lstrip("-")
                if stripped in SERVER_FLAG_ALIASES:
                    cand = SERVER_FLAG_ALIASES[stripped]
                    server = self._merge_server_flag(server or "bancho", cand)
                elif stripped == "all":
                    server = None

        try:
            await self.repo.unlink_account(ctx.author.id, server=server)
            if server:
                srv_label = OsuPresenter.server_title(server)
                msg = (
                    f"{DaletAtoms.GLYPH_CHECK} vinculación con **{srv_label}** eliminada."
                    if is_es else
                    f"{DaletAtoms.GLYPH_CHECK} unlinked your **{srv_label}** account."
                )
            else:
                msg = (
                    f"{DaletAtoms.GLYPH_CHECK} vinculación con osu! eliminada."
                    if is_es else
                    f"{DaletAtoms.GLYPH_CHECK} osu! account unlinked."
                )
            await ctx.send(msg)
        except Exception as e:
            logger.error(f"Error en unlink: {e}")
            await ctx.send(f"{DaletAtoms.GLYPH_CROSS} error al desvincular.")

    # ------------------------------------------------------------------
    # d.op — Perfil (con atajos Bathbot/owo: d.opm, d.opt, d.opc)
    # ------------------------------------------------------------------

    async def _run_profile(self, ctx, args: str | None, default_mode: str = "osu"):
        username, mode, server = await self._parse_args(ctx, args, default_mode=default_mode)
        if not username:
            return

        server_lang = await self._resolve_lang(ctx)
        try:
            async with ctx.typing():
                user = await self.osu.get_user(username, mode, server=server)

            embed = OsuPresenter.build_profile_card(user, mode, lang=server_lang)
            await ctx.send(embed=embed)
            await self._maybe_snapshot(ctx.author.id, username, user, mode=mode, server=server)

        except Exception as e:
            logger.error(f"Error en op para {username} ({server}): {e}")
            srv_label = OsuPresenter.server_title(server)
            await ctx.send(f"{DaletAtoms.GLYPH_CROSS} no pude obtener el perfil de '{username}' en {srv_label}.")

    @commands.command(name="op", aliases=["osuProfile", "profile", "o"])
    async def osu_profile(self, ctx, *, args: str = None):
        """Muestra el perfil completo de osu! de un jugador."""
        await self._run_profile(ctx, args, default_mode="osu")

    @commands.command(name="opm", aliases=["opmania", "mania"])
    async def osu_profile_mania(self, ctx, *, args: str = None):
        """Atajo directo de perfil para osu!mania (d.opm)."""
        await self._run_profile(ctx, args, default_mode="mania")

    @commands.command(name="opt", aliases=["optaiko", "taiko"])
    async def osu_profile_taiko(self, ctx, *, args: str = None):
        """Atajo directo de perfil para osu!taiko (d.opt)."""
        await self._run_profile(ctx, args, default_mode="taiko")

    @commands.command(name="opc", aliases=["opctb", "ctb", "catch"])
    async def osu_profile_ctb(self, ctx, *, args: str = None):
        """Atajo directo de perfil para osu!catch (d.opc)."""
        await self._run_profile(ctx, args, default_mode="fruits")

    # ------------------------------------------------------------------
    # d.orecent / d.or / d.rs / d.rp — Jugadas recientes con filtros y atajos de modo
    # ------------------------------------------------------------------

    async def _run_recent(self, ctx, args: str | None, default_mode: str = "osu", default_filter: str = "last"):
        username, mode, filter_by, mods_filter, server = await self._parse_osu_filter_args(
            ctx, args, default_filter=default_filter, default_mode=default_mode
        )
        if not username:
            return
        if filter_by not in ("last", "best", "pass"):
            filter_by = default_filter

        server_lang = await self._resolve_lang(ctx)
        try:
            fetch_limit = 50 if (filter_by != "last" or mods_filter) else 1
            include_fails = 0 if filter_by == "pass" else 1
            async with ctx.typing():
                user = await self.osu.get_user(username, mode, server=server)
                recent = await self.osu.get_user_recent_scores(
                    user["id"], mode, limit=fetch_limit, include_fails=include_fails, server=server
                )

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
            if hasattr(self.osu, "enrich_scores_with_pp"):
                await self.osu.enrich_scores_with_pp(target_list, mode=mode, max_maps=1)

            bm0 = (target_list[0].get("beatmap") or {}) if target_list else {}
            if bm0.get("id") and hasattr(self.osu, "remember_channel_map"):
                self.osu.remember_channel_map(ctx.channel.id, int(bm0["id"]), mode)

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
            logger.error(f"Error en orecent ({server}): {e}")
            await ctx.send(f"{DaletAtoms.GLYPH_POINTER} error obteniendo jugada reciente de '{username}'.")

    @commands.command(name="orecent", aliases=["or", "rs", "recent", "r"])
    async def osu_recent(self, ctx, *, args: str = None):
        """Muestra tu última jugada de osu! (soporta filtros: best, pass, +mods, -modo, -aka/-rx/-gatari)."""
        await self._run_recent(ctx, args, default_mode="osu", default_filter="last")

    @commands.command(name="rsm", aliases=["rsmania", "recentmania", "rm"])
    async def osu_recent_mania(self, ctx, *, args: str = None):
        """Atajo directo de jugada reciente en osu!mania (d.rsm)."""
        await self._run_recent(ctx, args, default_mode="mania", default_filter="last")

    @commands.command(name="rst", aliases=["rstaiko", "recenttaiko", "rt"])
    async def osu_recent_taiko(self, ctx, *, args: str = None):
        """Atajo directo de jugada reciente en osu!taiko (d.rst)."""
        await self._run_recent(ctx, args, default_mode="taiko", default_filter="last")

    @commands.command(name="rsc", aliases=["rsctb", "recentctb", "rc"])
    async def osu_recent_ctb(self, ctx, *, args: str = None):
        """Atajo directo de jugada reciente en osu!catch (d.rsc)."""
        await self._run_recent(ctx, args, default_mode="fruits", default_filter="last")

    @commands.command(name="recentpass", aliases=["rp"])
    async def osu_recent_pass(self, ctx, *, args: str = None):
        """Atajo directo para mostrar el último pass reciente sin fallos (d.rp)."""
        await self._run_recent(ctx, args, default_mode="osu", default_filter="pass")

    # ------------------------------------------------------------------
    # d.otop / d.top / d.rb — Top plays con filtros y atajos de modo
    # ------------------------------------------------------------------

    async def _run_top(self, ctx, args: str | None, default_mode: str = "osu", default_sort: str = "pp"):
        username, mode, sort_by, mods_filter, server = await self._parse_osu_filter_args(
            ctx, args, default_filter=default_sort, default_mode=default_mode
        )
        if not username:
            return
        if sort_by == "best":
            sort_by = "pp"
        elif sort_by not in ("pp", "recent", "acc"):
            sort_by = default_sort

        server_lang = await self._resolve_lang(ctx)
        try:
            async with ctx.typing():
                user = await self.osu.get_user(username, mode, server=server)
                best = await self.osu.get_user_best_scores(user["id"], mode, limit=100, server=server)

            if not best:
                return await ctx.send(f"{DaletAtoms.GLYPH_POINTER} **{username}** no tiene plays en {mode}.")

            filtered_best = OsuPresenter.filter_and_sort_top_scores(best, sort_by=sort_by, mods_filter=mods_filter)
            if not filtered_best:
                return await ctx.send(
                    f"{DaletAtoms.GLYPH_POINTER} {t('osu.top_none_filtered', server_lang, username=username, mode=mode)}"
                )

            await self.osu.enrich_scores_with_attributes(filtered_best[:5], mode=mode)
            if hasattr(self.osu, "enrich_scores_with_pp"):
                await self.osu.enrich_scores_with_pp(filtered_best[:5], mode=mode, max_maps=5)

            embed = OsuPresenter.build_top_card(
                user,
                filtered_best,
                mode=mode,
                lang=server_lang,
                sort_by=sort_by,
                mods_filter=mods_filter,
            )

            chart_file = OsuPresenter.generate_pp_chart(username, filtered_best, lang=server_lang)
            if chart_file:
                embed.set_image(url="attachment://pp_distribution.png")
                await ctx.send(embed=embed, file=chart_file)
            else:
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en otop ({server}): {e}")
            await ctx.send(f"{DaletAtoms.GLYPH_POINTER} error obteniendo top plays de '{username}'.")

    @commands.command(name="otop", aliases=["top", "osutop", "topplays"])
    async def osu_top(self, ctx, *, args: str = None):
        """Muestra tus mejores plays (soporta filtros: recent/rb/-r, acc/-a, +mods, -modo, -aka/-rx/-gatari)."""
        await self._run_top(ctx, args, default_mode="osu", default_sort="pp")

    @commands.command(name="topm", aliases=["topmania", "otopm"])
    async def osu_top_mania(self, ctx, *, args: str = None):
        """Atajo directo de top plays en osu!mania (d.topm)."""
        await self._run_top(ctx, args, default_mode="mania", default_sort="pp")

    @commands.command(name="topt", aliases=["toptaiko", "otopt"])
    async def osu_top_taiko(self, ctx, *, args: str = None):
        """Atajo directo de top plays en osu!taiko (d.topt)."""
        await self._run_top(ctx, args, default_mode="taiko", default_sort="pp")

    @commands.command(name="topc", aliases=["topctb", "otopc"])
    async def osu_top_ctb(self, ctx, *, args: str = None):
        """Atajo directo de top plays en osu!catch (d.topc)."""
        await self._run_top(ctx, args, default_mode="fruits", default_sort="pp")

    @commands.command(name="recentbest", aliases=["rb"])
    async def osu_recent_best(self, ctx, *, args: str = None):
        """Atajo directo para mostrar los mejores plays recientes del Top 100 (d.rb)."""
        await self._run_top(ctx, args, default_mode="osu", default_sort="recent")

    # ------------------------------------------------------------------
    # d.compare — Comparar dos jugadores
    # ------------------------------------------------------------------

    @commands.command(name="compare", aliases=["vs", "ocmp"])
    async def osu_compare(self, ctx, *args):
        """Compara perfiles de osu! frente a frente. Uso: d.compare [user1] <user2> [-modo] [-aka|-rx|-gatari]"""
        mode = "osu"
        server = "bancho"
        players = []
        for part in args:
            low = part.lower().strip()
            stripped = low.lstrip("-")
            if low.startswith("-") and stripped in SERVER_FLAG_ALIASES:
                server = self._merge_server_flag(server, SERVER_FLAG_ALIASES[stripped])
            elif low.startswith("-") and stripped in MODE_FLAG_ALIASES:
                mode = MODE_FLAG_ALIASES[stripped]
            else:
                players.append(part)

        server_lang = await self._resolve_lang(ctx)

        if len(players) >= 2:
            u1_name = players[0]
            u2_name = players[1]
        elif len(players) == 1:
            linked_name = await self.repo.get_linked_username(ctx.author.id, server=server)
            if not linked_name:
                return await ctx.send(f"{DaletAtoms.GLYPH_POINTER} {t('osu.compare_need_link', server_lang)}")
            u1_name = linked_name
            u2_name = players[0]
        else:
            return await ctx.send(f"{DaletAtoms.GLYPH_POINTER} Uso: `d.compare [usuario1] <usuario2> [-modo] [-aka|-rx|-gatari]`")

        try:
            async with ctx.typing():
                u1_data, u2_data = await asyncio.gather(
                    self.osu.get_user(u1_name, mode, server=server),
                    self.osu.get_user(u2_name, mode, server=server),
                )

                b1, b2 = await asyncio.gather(
                    self.osu.get_user_best_scores(u1_data["id"], mode=mode, limit=100, server=server),
                    self.osu.get_user_best_scores(u2_data["id"], mode=mode, limit=100, server=server),
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

    @commands.command(name="rank", aliases=["osurank", "lb"])
    async def osu_server_rank(self, ctx, *, args: str = None):
        """Muestra el ranking osu! entre los jugadores vinculados en este servidor."""
        mode = "osu"
        if args:
            for part in args.split():
                low = part.lower().strip()
                if low.startswith("-") and low[1:] in MODE_FLAG_ALIASES:
                    mode = MODE_FLAG_ALIASES[low[1:]]
                elif low in MODE_FLAG_ALIASES:
                    mode = MODE_FLAG_ALIASES[low]

        server_lang = await self._resolve_lang(ctx)

        if not ctx.guild:
            return await ctx.send(f"{DaletAtoms.GLYPH_POINTER} Este comando solo funciona dentro de un servidor.")

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

            mode_label = OsuPresenter.mode_title(mode)
            title_txt = (
                f"✦ Ranking osu! del Servidor — {mode_label}"
                if server_lang.startswith("es") else
                f"✦ Server osu! Leaderboard — {mode_label}"
            )
            embed = discord.Embed(
                title=title_txt,
                color=DaletAtoms.COLOR_PRIMARY
            )

            lines = []
            medals = ["✦", "◈", "◇"]
            for i, row in enumerate(server_rows):
                medal = medals[i] if i < 3 else f"`#{i+1}`"
                osu_name = _get_val(row, "OsuUsername", "osuusername", "UserName", "username", 1, default="??")
                pp   = float(_get_val(row, "PP", "pp", 5, default=0) or 0)
                acc  = float(_get_val(row, "Accuracy", "accuracy", 8, default=0) or 0)
                gr   = _get_val(row, "GlobalRank", "globalrank", 6, default=None)
                gr_str = f" │ `#{int(gr):,}`" if gr else ""
                lines.append(f"{medal} **{osu_name}** — **{pp:,.0f}pp** │ `{acc:.2f}%`{gr_str}")

            embed.description = "\n\n".join(lines)
            footer_txt = (
                f"{len(server_rows)} jugadores vinculados en este servidor"
                if server_lang.startswith("es") else
                f"{len(server_rows)} linked players in this server"
            )
            DaletMolecules_footer = f"{footer_txt} {DaletAtoms.GLYPH_PIPE} osu! {mode_label}"
            embed.set_footer(text=DaletMolecules_footer)
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
        server_lang = await self._resolve_lang(ctx)

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

    @commands.command(name="op1s", aliases=["firsts", "1s"])
    async def osu_firsts(self, ctx, *, args: str = None):
        """Muestra los #1 globales del jugador en osu!."""
        username, mode, server = await self._parse_args(ctx, args)
        if not username:
            return

        server_lang = await self._resolve_lang(ctx)

        try:
            async with ctx.typing():
                user   = await self.osu.get_user(username, mode, server=server)
                firsts = await self.osu.get_user_firsts(user["id"], mode, limit=10, server=server)

            if not firsts:
                return await ctx.send(
                    f"{DaletAtoms.GLYPH_POINTER} {t('osu.firsts_none', server_lang, username=username, mode=OsuPresenter.mode_title(mode))}"
                )

            await self.osu.enrich_scores_with_attributes(firsts[:10], mode=mode)
            if hasattr(self.osu, "enrich_scores_with_pp"):
                await self.osu.enrich_scores_with_pp(firsts[:10], mode=mode, max_maps=10)
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
        """Desglose de habilidades (Aim, Speed, Acc, Stamina, Reading) con veredicto consciente de nivel."""
        username, mode, _, mods_filter, server = await self._parse_osu_filter_args(ctx, args, default_filter="pp")
        if not username:
            return

        server_lang = await self._resolve_lang(ctx)

        try:
            async with ctx.typing():
                user = await self.osu.get_user(username, mode, server=server)
                best = await self.osu.get_user_best_scores(user["id"], mode, limit=100, server=server)

            if not best:
                return await ctx.send(f"{DaletAtoms.GLYPH_POINTER} **{username}** no tiene mejores jugadas registradas en {mode}.")

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

            # 2. Construir prompt y fallback consciente de arquetipo y rango (APEX_TITAN, ALL_ROUNDER, SPECIALIST, RISING_GRINDER)
            verdict_ctx = OsuAnalyzer.build_skill_verdict_context(
                user.get("username", username),
                user,
                skills_data,
                mode=mode,
                lang=server_lang,
                server=server,
            )

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
                    verdict_ctx["micro_prompt"],
                    "Skill Verdict",
                    user.get("username", username),
                    max_tokens_override=350,
                    system_prompt_override=verdict_ctx["system_override"],
                    language=server_lang,
                )
            except Exception as nlp_err:
                logger.warning(f"No se pudo generar veredicto para skills ({username}): {nlp_err}")

            if not _is_valid_roast(roast_text):
                roast_text = verdict_ctx["fallback_text"]

            embed = OsuPresenter.build_skills_card(
                user, skills_data, roast_text=roast_text, mode=mode, lang=server_lang, mods_filter=mods_filter
            )
            await ctx.send(embed=embed)
            await self._maybe_snapshot(ctx.author.id, username, user, mode=mode, server=server)

        except Exception as e:
            logger.error(f"Error en d.skills para {username}: {e}", exc_info=True)
            await ctx.send(f"{DaletAtoms.GLYPH_POINTER} error calculando el desglose de habilidades.")

    # ------------------------------------------------------------------
    # d.m / d.map — Ficha técnica de beatmap + simulación PP (bajo invocación)
    # ------------------------------------------------------------------

    @commands.command(name="m", aliases=["map", "beatmap", "bm"])
    async def osu_map(self, ctx, *, args: str = None):
        """Muestra info detallada de un beatmap y tabla de PP (+mods, -modo, link/ID o búsqueda)."""
        server_lang = await self._resolve_lang(ctx)
        query_text, mods_list, mode_override = OsuService.parse_map_args(args)

        preferred_id = None
        fallback_mode = "osu"
        if not query_text:
            recent_ctx = self.osu.get_channel_map(ctx.channel.id) if hasattr(self.osu, "get_channel_map") else None
            if not recent_ctx:
                return await ctx.send(t("osu.map_no_recent", server_lang))
            preferred_id, fallback_mode = recent_ctx

        mode_hint = mode_override or fallback_mode

        try:
            async with ctx.typing():
                resolved = await self.osu.resolve_beatmap(
                    query=query_text or None,
                    preferred_id=preferred_id,
                    mode_hint=mode_hint,
                )
                if not resolved or not resolved.get("beatmap"):
                    return await ctx.send(t("osu.map_not_found", server_lang))

                bm = resolved["beatmap"]
                eff_mode = mode_override or resolved.get("mode") or bm.get("mode") or "osu"
                bm_id = int(bm.get("id") or 0)
                pp_table = await self.osu.simulate_map_pp_table(bm_id, mode=eff_mode, mods=mods_list) if bm_id else {}

                if bm_id and hasattr(self.osu, "remember_channel_map"):
                    self.osu.remember_channel_map(ctx.channel.id, bm_id, eff_mode)

            embed = OsuPresenter.build_map_card(
                bm,
                pp_table=pp_table,
                mode=eff_mode,
                mods=mods_list,
                lang=server_lang,
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en d.m ({args}): {e}", exc_info=True)
            await ctx.send(f"{DaletAtoms.GLYPH_CROSS} error consultando el beatmap.")


async def setup(bot):
    await bot.add_cog(OsuHandler(bot))
