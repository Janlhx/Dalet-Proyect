"""
Slash Commands (Application Commands) de Dalet.
Unifica y expone los comandos principales como comandos de barra / para Discord.
"""
import asyncio
import logging
import time
from typing import Literal
import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import format_dt

from ui.organisms import DaletOrganisms
from ui.atoms import DaletAtoms
from ui.molecules import DaletMolecules
from ui.locales import t
from services.feedback_service import FeedbackService
from services.osu_service import OsuService, OsuUserNotFoundError
from handlers.dalet_osu_presenter import OsuPresenter
from handlers.modules.dalet_osuanalyzer import OsuAnalyzer
from handlers.dalet_helpcommands_handlers import build_help_pages, HelpPaginator

logger = logging.getLogger("dalet.handlers.slash")

OSU_SERVER_CHOICES = [
    app_commands.Choice(name="Bancho (Official)",    value="bancho"),
    app_commands.Choice(name="Akatsuki (Vanilla)",   value="akatsuki"),
    app_commands.Choice(name="Akatsuki (Relax)",     value="akatsuki_rx"),
    app_commands.Choice(name="Akatsuki (Autopilot)", value="akatsuki_ap"),
    app_commands.Choice(name="Gatari",               value="gatari"),
]


class SlashCommands(commands.Cog, name="Slash Commands"):
    """Versiones slash (/) de los comandos principales de Dalet."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ai_slash_cooldowns: dict[str, float] = {}

    async def _resolve_lang(self, interaction: discord.Interaction) -> str:
        """Resuelve el idioma efectivo en O(1) con cascada Usuario > Servidor > Default."""
        try:
            return await self.bot.admin_repo.resolve_language(
                interaction.user.id, interaction.guild_id, default="en"
            )
        except Exception:
            return "en"

    def _check_cooldown(self, key: str, duration_sec: float) -> float | None:
        """Devuelve los segundos restantes si la acción está en cooldown, o None si puede proceder."""
        now = time.time()
        cooldown_until = self._ai_slash_cooldowns.get(key, 0.0)
        if now < cooldown_until:
            return cooldown_until - now
        self._ai_slash_cooldowns[key] = now + duration_sec
        return None

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    @app_commands.command(name="ping", description="Checks bot response latency in milliseconds.")
    async def slash_ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            f"{DaletAtoms.GLYPH_POINTER} response time: **{latency}ms**. don't rush me.", ephemeral=True
        )

    @app_commands.command(name="say", description="Repeats your message with mentions safely disabled.")
    @app_commands.describe(message="Text for Dalet to repeat")
    async def slash_say(self, interaction: discord.Interaction, message: str):
        clean_msg = message.strip()
        if not clean_msg:
            return await interaction.response.send_message(
                f"{DaletAtoms.GLYPH_CROSS} Empty message.", ephemeral=True
            )
        await interaction.response.send_message(
            clean_msg, allowed_mentions=discord.AllowedMentions.none()
        )

    @app_commands.command(name="stats", description="Displays your server social activity statistics.")
    @app_commands.describe(user="User to inspect (defaults to yourself)")
    async def slash_stats(self, interaction: discord.Interaction, user: discord.Member = None):
        member = user or interaction.user
        server_lang = await self._resolve_lang(interaction)
        await interaction.response.defer()
        try:
            stats = await self.bot.user_repo.get_user_social_stats(member.id)
            avatar = member.avatar.url if member.avatar else None
            embed = DaletOrganisms.create_user_stats_card(member.display_name, stats, avatar, lang=server_lang)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /stats: {e}")
            await interaction.followup.send(t("general.user_stats_fail", server_lang), ephemeral=True)

    @app_commands.command(name="userinfo", description="Displays detailed information about a server member.")
    @app_commands.describe(user="Member to inspect")
    async def slash_userinfo(self, interaction: discord.Interaction, user: discord.Member = None):
        member = user or interaction.user
        server_lang = await self._resolve_lang(interaction)
        desc = (
            f"• {DaletAtoms.bold(t('userinfo.id', server_lang))}: {DaletAtoms.code(member.id)}\n"
            f"• {DaletAtoms.bold(t('userinfo.created', server_lang))}: {format_dt(member.created_at, 'D')}\n"
            f"• {DaletAtoms.bold(t('userinfo.joined', server_lang))}: {format_dt(member.joined_at, 'D')}\n"
        )
        embed = DaletOrganisms.create_simple_embed(t("userinfo.title", server_lang, username=member.display_name), desc)
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Displays information about the current server.")
    async def slash_serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild
        server_lang = await self._resolve_lang(interaction)
        desc = (
            f"• {DaletAtoms.bold(t('serverinfo.members', server_lang))}: {DaletAtoms.code(g.member_count)}\n"
            f"• {DaletAtoms.bold(t('serverinfo.owner', server_lang))}: {g.owner.mention}\n"
            f"• {DaletAtoms.bold(t('serverinfo.created', server_lang))}: {format_dt(g.created_at, 'D')}\n"
        )
        embed = DaletOrganisms.create_simple_embed(t("serverinfo.title", server_lang, name=g.name), desc)
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="info", description="Displays Dalet's profile card, version, and information.")
    async def slash_info(self, interaction: discord.Interaction):
        server_lang = await self._resolve_lang(interaction)

        tagline = t("info.tagline", server_lang)
        lbl_creator = t("info.creator", server_lang)
        lbl_status = t("info.status", server_lang)
        status_desc = t("info.status_desc", server_lang)
        lbl_prefix = t("info.prefix", server_lang)
        prefix_desc = t("info.prefix_desc", server_lang)
        hint_changelog = t("info.changelog_hint", server_lang)
        hint_help = t("info.help_hint", server_lang)
        hint_feedback = t("info.feedback_hint", server_lang)

        embed = discord.Embed(
            title=f"{DaletAtoms.EMOJI_DALET} Dalet {DaletAtoms.VERSION}",
            description=(
                f'{tagline}\n\n'
                f"{DaletAtoms.GLYPH_POINTER} **{lbl_creator}**: Litxe\n"
                f"{DaletAtoms.GLYPH_POINTER} **{lbl_status}**: {status_desc}\n"
                f"{DaletAtoms.GLYPH_POINTER} **{lbl_prefix}**: {prefix_desc}\n\n"
                f"{DaletAtoms.GLYPH_SUB} {hint_feedback}\n"
                f"{DaletAtoms.GLYPH_SUB} {hint_changelog}\n"
                f"{DaletAtoms.GLYPH_SUB} {hint_help}"
            ),
            color=DaletAtoms.COLOR_PRIMARY
        )
        if self.bot.user and self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        DaletMolecules.add_standard_footer(embed, context_text=f"{DaletAtoms.VERSION} │ Litxe")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="changelog", description="Displays version release notes, major milestones, and recent commits.")
    async def slash_changelog(self, interaction: discord.Interaction):
        server_lang = await self._resolve_lang(interaction)

        custom = getattr(self.bot, "custom_changelog", None)
        from services.changelog_service import ChangelogService
        embed = ChangelogService.build_embed(server_lang=server_lang, custom_banner=custom)

        if self.bot.user and self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="Displays an interactive categorized command guide.")
    async def slash_help(self, interaction: discord.Interaction):
        server_lang = await self._resolve_lang(interaction)
        pages, category_names = build_help_pages(self.bot, interaction.user, server_lang=server_lang)
        view = HelpPaginator(pages, category_names, lang=server_lang)
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)

    @app_commands.command(name="feedback", description="Sends feedback, suggestions, or bug reports directly to the developer.")
    @app_commands.describe(message="Feedback, suggestion, or bug report to deliver")
    async def slash_feedback(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer(ephemeral=True)
        server_lang = await self._resolve_lang(interaction)

        # Anti-spam Cooldown (5 minutos)
        cooldown_remaining = await FeedbackService.check_user_cooldown(interaction.user.id)
        if cooldown_remaining > 0:
            mins = max(1, (cooldown_remaining + 59) // 60)
            warning_msg = (
                f"{DaletAtoms.GLYPH_POINTER} Has enviado una sugerencia recientemente. Para evitar saturación, por favor espera **{mins} minuto(s)** antes de enviar otra."
                if server_lang == "es"
                else f"{DaletAtoms.GLYPH_POINTER} You have submitted feedback recently. To prevent spam, please wait **{mins} minute(s)** before sending another."
            )
            await interaction.followup.send(warning_msg, ephemeral=True)
            return

        sent = await FeedbackService.send_feedback(
            bot=self.bot,
            author=interaction.user,
            content=message,
            guild=interaction.guild,
            channel=interaction.channel
        )
        if sent:
            await interaction.followup.send(t("feedback.success", server_lang), ephemeral=True)
        else:
            await interaction.followup.send(t("feedback.error", server_lang), ephemeral=True)

    # ------------------------------------------------------------------
    # osu!
    # ------------------------------------------------------------------

    async def _sync_slash_snapshot(self, discord_id: int, queried_username: str, user_data: dict, mode: str = "osu", server: str = "bancho"):
        """Sincroniza silenciosamente las estadísticas del perfil del usuario en Bancho para mantener el ranking y progreso al día."""
        if server != "bancho":
            return
        try:
            linked = await self.bot.osu_repo.get_linked_username(discord_id, server="bancho")
            if not linked or linked.lower() != queried_username.lower():
                return

            stats = user_data.get("statistics", {}) or {}
            pp = float(stats.get("pp", 0.0) or 0.0)
            gr = stats.get("global_rank")
            cr = stats.get("country_rank")
            acc = float(stats.get("hit_accuracy", 0.0) or 0.0)
            mode_clean = (mode or user_data.get("playmode", "osu") or "osu").lower().strip()

            await self.bot.osu_repo.update_cached_stats(
                discord_id, user_data["username"], pp, gr, cr, acc, mode=mode_clean
            )
            await self.bot.analytics_repo.record_osu_snapshot(
                discord_id, pp, gr, cr, acc, mode_clean
            )
        except Exception as e:
            logger.debug(f"[SlashSnapshot] Error no crítico: {e}")

    @app_commands.command(name="op", description="Displays full osu! profile, rank, and stats for a player.")
    @app_commands.describe(
        username="osu! username (or leave empty for your linked account)",
        mode="Game mode (default: osu)",
        server="osu! server (Bancho, Akatsuki, Akatsuki Relax, Gatari)"
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="osu!standard", value="osu"),
            app_commands.Choice(name="osu!taiko",    value="taiko"),
            app_commands.Choice(name="osu!catch",    value="fruits"),
            app_commands.Choice(name="osu!mania",    value="mania"),
        ],
        server=OSU_SERVER_CHOICES,
    )
    async def slash_op(
        self, interaction: discord.Interaction,
        username: str = None, mode: str = "osu", server: str = "bancho"
    ):
        await interaction.response.defer()
        try:
            uname = username
            if not uname:
                uname = await self.bot.osu_repo.get_linked_username(interaction.user.id, server=server)
            if not uname:
                return await interaction.followup.send(
                    f"{DaletAtoms.GLYPH_CROSS} no tienes cuenta vinculada. usa `/link` primero.",
                    ephemeral=True
                )
            server_lang = await self._resolve_lang(interaction)
            user = await self.bot.osu_service.get_user(uname, mode, server=server)
            embed = OsuPresenter.build_profile_card(user, mode, lang=server_lang)
            await interaction.followup.send(embed=embed)
            await self._sync_slash_snapshot(interaction.user.id, uname, user, mode=mode, server=server)
        except Exception as e:
            logger.error(f"Error en /op: {e}")
            await interaction.followup.send(f"{DaletAtoms.GLYPH_CROSS} error obteniendo el perfil.", ephemeral=True)

    @app_commands.command(name="link", description="Links your Discord account to your osu! profile (Bancho, Akatsuki, or Gatari).")
    @app_commands.describe(
        username="Your osu! username",
        server="osu! server (default: Bancho)"
    )
    @app_commands.choices(server=OSU_SERVER_CHOICES)
    async def slash_link(self, interaction: discord.Interaction, username: str, server: str = "bancho"):
        await interaction.response.defer(ephemeral=True)
        srv_label = OsuPresenter.server_title(server)
        try:
            user_data = await self.bot.osu_service.get_user(username, server=server)
            if not user_data or "statistics" not in user_data:
                return await interaction.followup.send(
                    f"{DaletAtoms.GLYPH_CROSS} no encontré a `{username}` en **{srv_label}**.", ephemeral=True
                )
            stats = user_data.get("statistics", {}) or {}
            pp = float(stats.get("pp", 0.0) or 0.0)
            gr = stats.get("global_rank")
            cr = stats.get("country_rank")
            acc = float(stats.get("hit_accuracy", 0.0) or 0.0)
            mode = (user_data.get("playmode") or "osu").lower().strip()

            await self.bot.osu_repo.link_account(
                interaction.user.id,
                user_data["username"],
                user_data["id"],
                mode,
                pp,
                gr,
                cr,
                acc,
                server=server,
            )

            if server == "bancho":
                try:
                    await self.bot.analytics_repo.record_osu_snapshot(
                        interaction.user.id,
                        pp,
                        gr,
                        cr,
                        acc,
                        mode,
                    )
                except Exception:
                    pass

            await interaction.followup.send(
                f"{DaletAtoms.GLYPH_CHECK} vinculado con éxito a **{user_data['username']}** (`{srv_label}`).", ephemeral=True
            )
        except OsuUserNotFoundError:
            await interaction.followup.send(
                f"{DaletAtoms.GLYPH_CROSS} no encontré a `{username}` en **{srv_label}**.", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /link ({server} / {username}): {e}", exc_info=True)
            await interaction.followup.send(f"{DaletAtoms.GLYPH_CROSS} error al vincular en **{srv_label}**.", ephemeral=True)

    @app_commands.command(name="unlink", description="Unlinks your osu! account from Dalet.")
    @app_commands.describe(server="Optional: unlink only a specific osu! server (leave empty to unlink all)")
    @app_commands.choices(server=OSU_SERVER_CHOICES)
    async def slash_unlink(self, interaction: discord.Interaction, server: str = None):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.osu_repo.unlink_account(interaction.user.id, server=server)
            await interaction.followup.send(
                f"{DaletAtoms.GLYPH_CHECK} vinculación con osu! eliminada.", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /unlink: {e}")
            await interaction.followup.send(f"{DaletAtoms.GLYPH_CROSS} error al desvincular.", ephemeral=True)

    @app_commands.command(name="progress", description="Displays your historical PP progress chart over time.")
    @app_commands.describe(user="Server member to view progress for (default: yourself)")
    async def slash_progress(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer()
        target_member = user or interaction.user
        server_lang = await self._resolve_lang(interaction)

        try:
            history = await self.bot.analytics_repo.get_osu_progress(target_member.id, mode="osu", limit=30)
            if not history or len(history) < 2:
                return await interaction.followup.send(
                    f"{DaletAtoms.GLYPH_POINTER} {t('osu.progress_need_snapshots', server_lang)}"
                )

            loop = asyncio.get_running_loop()
            chart_file = await loop.run_in_executor(
                None, OsuPresenter.generate_progress_chart, target_member.display_name, history, server_lang
            )

            username = await self.bot.osu_repo.get_linked_username(target_member.id)
            display_name = username or target_member.display_name
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
                await interaction.followup.send(embed=embed, file=chart_file)
            else:
                await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /progress: {e}")
            await interaction.followup.send(f"{DaletAtoms.GLYPH_CROSS} error generando el gráfico de progreso.", ephemeral=True)

    @app_commands.command(name="firsts", description="Displays global #1 scores for a player.")
    @app_commands.describe(
        username="osu! username (or leave empty for your linked account)",
        mode="Game mode (default: osu)",
        server="osu! server (default: Bancho)"
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="osu!standard", value="osu"),
            app_commands.Choice(name="osu!taiko",    value="taiko"),
            app_commands.Choice(name="osu!catch",    value="fruits"),
            app_commands.Choice(name="osu!mania",    value="mania"),
        ],
        server=OSU_SERVER_CHOICES,
    )
    async def slash_firsts(
        self, interaction: discord.Interaction,
        username: str = None, mode: str = "osu", server: str = "bancho"
    ):
        await interaction.response.defer()
        try:
            uname = username
            if not uname:
                uname = await self.bot.osu_repo.get_linked_username(interaction.user.id, server=server)
            if not uname:
                return await interaction.followup.send(
                    f"{DaletAtoms.GLYPH_CROSS} no tienes cuenta vinculada.", ephemeral=True
                )
            server_lang = await self._resolve_lang(interaction)

            user = await self.bot.osu_service.get_user(uname, mode, server=server)
            firsts = await self.bot.osu_service.get_user_firsts(user["id"], mode, limit=10, server=server)
            if not firsts:
                return await interaction.followup.send(
                    f"{DaletAtoms.GLYPH_POINTER} {t('osu.firsts_none', server_lang, username=uname, mode=OsuPresenter.mode_title(mode))}"
                )

            await self.bot.osu_service.enrich_scores_with_attributes(firsts[:10], mode=mode)
            if hasattr(self.bot.osu_service, "enrich_scores_with_pp"):
                await self.bot.osu_service.enrich_scores_with_pp(firsts[:10], mode=mode, max_maps=10)
            embed = OsuPresenter.build_firsts_card(user.get("username", uname), firsts, user_data=user, mode=mode, lang=server_lang)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /firsts: {e}")
            await interaction.followup.send(f"{DaletAtoms.GLYPH_CROSS} error obteniendo #1s globales.", ephemeral=True)

    @app_commands.command(name="recent", description="Displays your most recent osu! play with optional session-best, pass-only, or mod filters.")
    @app_commands.describe(
        username="osu! username (or leave empty for your linked account)",
        mode="Game mode",
        filter="Filter recent plays: last play, best play in last 24h, or last pass without fails",
        mods="Filter by mods (e.g. DT, HDDT, HR, NM)",
        server="osu! server (Bancho, Akatsuki, Akatsuki Relax, Gatari)"
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="osu!standard", value="osu"),
            app_commands.Choice(name="osu!taiko",    value="taiko"),
            app_commands.Choice(name="osu!catch",    value="fruits"),
            app_commands.Choice(name="osu!mania",    value="mania"),
        ],
        filter=[
            app_commands.Choice(name="Last Play (Default)",          value="last"),
            app_commands.Choice(name="Recent Best (Best in 24h)",    value="best"),
            app_commands.Choice(name="Last Pass (Ignore Fails)",     value="pass"),
        ],
        server=OSU_SERVER_CHOICES,
    )
    async def slash_recent(
        self,
        interaction: discord.Interaction,
        username: str = None,
        mode: str = "osu",
        filter: str = "last",
        mods: str = None,
        server: str = "bancho",
    ):
        await interaction.response.defer()
        uname = username
        if not uname:
            uname = await self.bot.osu_repo.get_linked_username(interaction.user.id, server=server)
        if not uname:
            return await interaction.followup.send(
                f"{DaletAtoms.GLYPH_POINTER} no tienes cuenta vinculada.", ephemeral=True
            )
        try:
            server_lang = await self._resolve_lang(interaction)
            user = await self.bot.osu_service.get_user(uname, mode, server=server)
            fetch_limit = 50 if (filter != "last" or mods) else 1
            include_fails = 0 if filter == "pass" else 1
            recent = await self.bot.osu_service.get_user_recent_scores(
                user["id"], mode, limit=fetch_limit, include_fails=include_fails, server=server
            )
            if not recent:
                return await interaction.followup.send(
                    f"{DaletAtoms.GLYPH_POINTER} {t('osu.no_recent', server_lang, username=uname, mode=mode)}"
                )

            filtered = OsuPresenter.filter_recent_scores(recent, filter_by=filter, mods_filter=mods)
            if not filtered:
                return await interaction.followup.send(
                    f"{DaletAtoms.GLYPH_POINTER} {t('osu.no_recent_filtered', server_lang, username=uname, mode=mode)}"
                )

            target_list = filtered[:1]
            await self.bot.osu_service.enrich_scores_with_attributes(target_list, mode=mode)
            if hasattr(self.bot.osu_service, "enrich_scores_with_pp"):
                await self.bot.osu_service.enrich_scores_with_pp(target_list, mode=mode, max_maps=1)

            bm0 = (target_list[0].get("beatmap") or {}) if target_list else {}
            if bm0.get("id") and interaction.channel_id and hasattr(self.bot.osu_service, "remember_channel_map"):
                self.bot.osu_service.remember_channel_map(interaction.channel_id, int(bm0["id"]), mode)

            embed = OsuPresenter.build_recent_card(
                user.get("username", uname),
                mode,
                target_list[0],
                user_data=user,
                lang=server_lang,
                filter_by=filter,
                mods_filter=mods,
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en /recent: {e}")
            await interaction.followup.send(f"{DaletAtoms.GLYPH_POINTER} error obteniendo la jugada.", ephemeral=True)

    @app_commands.command(name="top", description="Displays your top 5 osu! scores sorted by PP, Recent Best, Accuracy, or filtered by mods.")
    @app_commands.describe(
        username="osu! username (or leave empty for your linked account)",
        mode="Game mode",
        filter="Sort order: Highest PP (default), Recent Best (newest in top 100), or Highest Accuracy",
        mods="Filter top 100 plays by mods (e.g. DT, HDDT, HR, NM)",
        server="osu! server (Bancho, Akatsuki, Akatsuki Relax, Gatari)"
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="osu!standard", value="osu"),
            app_commands.Choice(name="osu!taiko",    value="taiko"),
            app_commands.Choice(name="osu!catch",    value="fruits"),
            app_commands.Choice(name="osu!mania",    value="mania"),
        ],
        filter=[
            app_commands.Choice(name="Highest PP (Default)",             value="pp"),
            app_commands.Choice(name="Recent Best (Newest in Top 100)",  value="recent"),
            app_commands.Choice(name="Highest Accuracy",                 value="acc"),
        ],
        server=OSU_SERVER_CHOICES,
    )
    async def slash_top(
        self,
        interaction: discord.Interaction,
        username: str = None,
        mode: str = "osu",
        filter: str = "pp",
        mods: str = None,
        server: str = "bancho",
    ):
        await interaction.response.defer()
        uname = username
        if not uname:
            uname = await self.bot.osu_repo.get_linked_username(interaction.user.id, server=server)
        if not uname:
            return await interaction.followup.send(
                f"{DaletAtoms.GLYPH_POINTER} no tienes cuenta vinculada.", ephemeral=True
            )
        try:
            server_lang = await self._resolve_lang(interaction)
            user = await self.bot.osu_service.get_user(uname, mode, server=server)
            best = await self.bot.osu_service.get_user_best_scores(user["id"], mode=mode, limit=100, server=server)
            if not best:
                return await interaction.followup.send(
                    f"{DaletAtoms.GLYPH_POINTER} **{uname}** no tiene top plays en {mode}."
                )

            filtered_best = OsuPresenter.filter_and_sort_top_scores(best, sort_by=filter, mods_filter=mods)
            if not filtered_best:
                return await interaction.followup.send(
                    f"{DaletAtoms.GLYPH_POINTER} {t('osu.top_none_filtered', server_lang, username=uname, mode=mode)}"
                )

            await self.bot.osu_service.enrich_scores_with_attributes(filtered_best[:5], mode=mode)
            if hasattr(self.bot.osu_service, "enrich_scores_with_pp"):
                await self.bot.osu_service.enrich_scores_with_pp(filtered_best[:5], mode=mode, max_maps=5)
            embed = OsuPresenter.build_top_card(
                user.get("username", uname),
                mode,
                filtered_best,
                user_data=user,
                lang=server_lang,
                sort_by=filter,
                mods_filter=mods,
            )
            chart_file = OsuPresenter.generate_pp_chart(user.get("username", uname), filtered_best, lang=server_lang)
            if chart_file:
                embed.set_image(url="attachment://pp_distribution.png")
                await interaction.followup.send(embed=embed, file=chart_file)
            else:
                await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /top: {e}")
            await interaction.followup.send(f"{DaletAtoms.GLYPH_POINTER} error obteniendo top plays.", ephemeral=True)

    @app_commands.command(name="map", description="Displays beatmap info, mod-adjusted difficulty stats, and PP table (95/98/99/100%).")
    @app_commands.describe(
        query="Beatmap URL, ID, or search keywords (leave empty for last beatmap shown in channel)",
        mods="Optional mods to simulate (e.g. HDDT, HR, HDHR, DT)",
        mode="Optional game mode conversion",
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Auto / Beatmap Default", value="auto"),
            app_commands.Choice(name="osu!standard", value="osu"),
            app_commands.Choice(name="osu!taiko",    value="taiko"),
            app_commands.Choice(name="osu!catch",    value="fruits"),
            app_commands.Choice(name="osu!mania",    value="mania"),
        ]
    )
    async def slash_map(
        self,
        interaction: discord.Interaction,
        query: str = None,
        mods: str = None,
        mode: str = "auto",
    ):
        await interaction.response.defer()
        server_lang = await self._resolve_lang(interaction)

        q_clean, q_mods, q_mode = OsuService.parse_map_args(query)
        mods_list = list(dict.fromkeys((OsuService._clean_rosu_mods(mods) if mods else []) + q_mods))
        mode_override = None if mode == "auto" else mode
        mode_override = q_mode or mode_override

        preferred_id = None
        fallback_mode = "osu"
        if not q_clean:
            recent_ctx = (
                self.bot.osu_service.get_channel_map(interaction.channel_id)
                if interaction.channel_id and hasattr(self.bot.osu_service, "get_channel_map")
                else None
            )
            if not recent_ctx:
                return await interaction.followup.send(t("osu.map_no_recent", server_lang), ephemeral=True)
            preferred_id, fallback_mode = recent_ctx

        mode_hint = mode_override or fallback_mode
        try:
            resolved = await self.bot.osu_service.resolve_beatmap(
                query=q_clean or None,
                preferred_id=preferred_id,
                mode_hint=mode_hint,
            )
            if not resolved or not resolved.get("beatmap"):
                return await interaction.followup.send(t("osu.map_not_found", server_lang), ephemeral=True)

            bm = resolved["beatmap"]
            eff_mode = mode_override or resolved.get("mode") or bm.get("mode") or "osu"
            bm_id = int(bm.get("id") or 0)
            pp_table = await self.bot.osu_service.simulate_map_pp_table(bm_id, mode=eff_mode, mods=mods_list) if bm_id else {}

            if bm_id and interaction.channel_id and hasattr(self.bot.osu_service, "remember_channel_map"):
                self.bot.osu_service.remember_channel_map(interaction.channel_id, bm_id, eff_mode)

            embed = OsuPresenter.build_map_card(
                bm,
                pp_table=pp_table,
                mode=eff_mode,
                mods=mods_list,
                lang=server_lang,
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /map: {e}", exc_info=True)
            await interaction.followup.send(f"{DaletAtoms.GLYPH_CROSS} error consultando el beatmap.", ephemeral=True)

    @app_commands.command(name="skills", description="5-dimension osu! skill radar (Aim, Speed, Acc, Stamina, Reading) with Dalet's verdict.")
    @app_commands.describe(
        username="osu! username (or leave empty for your linked account)",
        mode="Game mode (default: osu)",
        mods="Optional mods filter (e.g. DT, HDDT, HR, NM)",
        server="osu! server (Bancho, Akatsuki, Akatsuki Relax, Gatari)"
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="osu!standard", value="osu"),
            app_commands.Choice(name="osu!taiko",    value="taiko"),
            app_commands.Choice(name="osu!catch",    value="fruits"),
            app_commands.Choice(name="osu!mania",    value="mania"),
        ],
        server=OSU_SERVER_CHOICES,
    )
    async def slash_skills(
        self, interaction: discord.Interaction,
        username: str = None, mode: str = "osu", mods: str = None, server: str = "bancho"
    ):
        await interaction.response.defer()
        try:
            uname = username
            if not uname:
                uname = await self.bot.osu_repo.get_linked_username(interaction.user.id, server=server)
            if not uname:
                return await interaction.followup.send(
                    f"{DaletAtoms.GLYPH_POINTER} no tienes cuenta vinculada. usa `/link` primero o especifica un usuario.",
                    ephemeral=True
                )

            user = await self.bot.osu_service.get_user(uname, mode, server=server)
            best = await self.bot.osu_service.get_user_best_scores(user["id"], mode=mode, limit=100, server=server)
            if not best:
                return await interaction.followup.send(f"{DaletAtoms.GLYPH_POINTER} **{uname}** no tiene mejores jugadas registradas en {mode}.")

            server_lang = await self._resolve_lang(interaction)

            target_scores = best
            if mods and mods.strip():
                target_scores = OsuPresenter.filter_and_sort_top_scores(best, sort_by="pp", mods_filter=mods)
                if not target_scores:
                    return await interaction.followup.send(
                        f"{DaletAtoms.GLYPH_POINTER} {t('osu.top_none_filtered', server_lang, username=uname, mode=mode)}"
                    )

            await self.bot.osu_service.enrich_scores_with_attributes(target_scores[:15], mode=mode)
            skills_data = OsuAnalyzer.calculate_skills(target_scores, mode=mode, lang=server_lang)

            verdict_ctx = OsuAnalyzer.build_skill_verdict_context(
                user.get("username", uname),
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
                    user.get("username", uname),
                    max_tokens_override=350,
                    system_prompt_override=verdict_ctx["system_override"],
                    language=server_lang,
                )
            except Exception as nlp_err:
                logger.warning(f"No se pudo generar veredicto para slash skills ({uname}): {nlp_err}")

            if not _is_valid_roast(roast_text):
                roast_text = verdict_ctx["fallback_text"]

            embed = OsuPresenter.build_skills_card(
                user, skills_data, roast_text=roast_text, mode=mode, lang=server_lang, mods_filter=mods
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /skills: {e}")
            await interaction.followup.send(f"{DaletAtoms.GLYPH_POINTER} error calculando las habilidades.", ephemeral=True)

    @app_commands.command(name="rank", description="Server osu! leaderboard for linked members.")
    @app_commands.describe(mode="Game mode for leaderboard (default: osu!)")
    @app_commands.choices(mode=[
        app_commands.Choice(name="osu!standard", value="osu"),
        app_commands.Choice(name="osu!taiko",    value="taiko"),
        app_commands.Choice(name="osu!catch",    value="fruits"),
        app_commands.Choice(name="osu!mania",    value="mania"),
    ])
    async def slash_rank(self, interaction: discord.Interaction, mode: str = "osu"):
        await interaction.response.defer()
        server_lang = await self._resolve_lang(interaction)
        try:
            guild_member_ids = {str(m.id) for m in interaction.guild.members if not m.bot}
            all_rows = await self.bot.osu_repo.get_ranking(mode=mode, limit=500)

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
                return await interaction.followup.send(
                    f"{DaletAtoms.GLYPH_POINTER} {t('rank.empty', server_lang)}"
                )

            medals = ["✦", "◈", "◇"]
            lines = []
            for i, row in enumerate(server_rows):
                medal = medals[i] if i < 3 else f"`#{i+1}`"
                osu_name = _get_val(row, "OsuUsername", "osuusername", "UserName", "username", 1, default="??")
                pp   = float(_get_val(row, "PP", "pp", 5, default=0) or 0)
                acc  = float(_get_val(row, "Accuracy", "accuracy", 8, default=0) or 0)
                gr   = _get_val(row, "GlobalRank", "globalrank", 6, default=None)
                gr_str = f" │ `#{int(gr):,}`" if gr else ""
                lines.append(f"{medal} **{osu_name}** — **{pp:,.0f}pp** │ `{acc:.2f}%`{gr_str}")

            mode_label = OsuPresenter.mode_title(mode)
            embed = discord.Embed(
                title=f"✦ {t('rank.title', server_lang)} — {mode_label}",
                description="\n\n".join(lines),
                color=DaletAtoms.COLOR_PRIMARY
            )
            footer_txt = f"{len(server_rows)} jugadores vinculados en este servidor" if server_lang.startswith("es") else f"{len(server_rows)} linked players in this server"
            embed.set_footer(text=f"{footer_txt} {DaletAtoms.GLYPH_PIPE} osu! {mode_label}")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /rank: {e}")
            await interaction.followup.send(f"{DaletAtoms.GLYPH_CROSS} {t('rank.error', server_lang)}", ephemeral=True)

    @app_commands.command(name="compare", description="Compares osu! profiles head-to-head with in-depth stats and skill breakdown.")
    @app_commands.describe(
        player1="First player (or leave player2 empty to compare against your linked account)",
        player2="Second player (optional, compares against yourself if omitted)",
        mode="Game mode (default: osu!)",
        server="osu! server (Bancho, Akatsuki, Akatsuki Relax, Gatari)"
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="osu! (Standard)", value="osu"),
            app_commands.Choice(name="osu!taiko", value="taiko"),
            app_commands.Choice(name="osu!catch", value="fruits"),
            app_commands.Choice(name="osu!mania", value="mania"),
        ],
        server=OSU_SERVER_CHOICES,
    )
    async def slash_compare(
        self,
        interaction: discord.Interaction,
        player1: str,
        player2: str = None,
        mode: app_commands.Choice[str] = None,
        server: str = "bancho",
    ):
        server_lang = await self._resolve_lang(interaction)

        mode_str = mode.value if mode else "osu"
        p1 = player1.strip()
        p2 = player2.strip() if player2 else None

        if p2:
            u1_name = p1
            u2_name = p2
        else:
            linked_name = await self.bot.osu_repo.get_linked_username(interaction.user.id, server=server)
            if not linked_name:
                return await interaction.response.send_message(
                    f"{DaletAtoms.GLYPH_POINTER} {t('osu.compare_need_link', server_lang)}",
                    ephemeral=True
                )
            u1_name = linked_name
            u2_name = p1

        await interaction.response.defer()
        try:
            u1, u2 = await asyncio.gather(
                self.bot.osu_service.get_user(u1_name, mode_str, server=server),
                self.bot.osu_service.get_user(u2_name, mode_str, server=server),
            )

            b1, b2 = await asyncio.gather(
                self.bot.osu_service.get_user_best_scores(u1["id"], mode=mode_str, limit=100, server=server),
                self.bot.osu_service.get_user_best_scores(u2["id"], mode=mode_str, limit=100, server=server),
                return_exceptions=True
            )
            b1_list = b1 if isinstance(b1, list) else []
            b2_list = b2 if isinstance(b2, list) else []

            await asyncio.gather(
                self.bot.osu_service.enrich_scores_with_attributes(b1_list[:12], mode=mode_str),
                self.bot.osu_service.enrich_scores_with_attributes(b2_list[:12], mode=mode_str),
                return_exceptions=True
            )

            skills1 = OsuAnalyzer.calculate_skills(b1_list, mode=mode_str, lang=server_lang)
            skills2 = OsuAnalyzer.calculate_skills(b2_list, mode=mode_str, lang=server_lang)
            common_maps = OsuAnalyzer.find_common_top_maps(b1_list, b2_list, limit=3)

            verdict_text = None
            try:
                pp1 = float((u1.get("statistics") or {}).get("pp") or 0.0)
                pp2 = float((u2.get("statistics") or {}).get("pp") or 0.0)
                dom1 = skills1.get("dominant_skill", "Aim")
                dom2 = skills2.get("dominant_skill", "Aim")
                cw1 = common_maps.get("wins1", 0)
                cw2 = common_maps.get("wins2", 0)
                tot_c = common_maps.get("total_common", 0)
                is_es = server_lang.startswith("es")
                if is_es:
                    cmp_prompt = (
                        f"ROL: Eres Dalet, analista mordaz de osu! ({mode_str}).\n"
                        f"TAREA: Escribe un veredicto de duelo (MÁX 2 ORACIONES CORTAS, 25-35 palabras) entre {u1.get('username', u1_name)} ({pp1:.0f}pp, fuerte en {dom1}) "
                        f"y {u2.get('username', u2_name)} ({pp2:.0f}pp, fuerte en {dom2}). "
                        f"Mapas en común en su Top: {tot_c} ({cw1} a {cw2}). Di quién domina y por qué con sarcasmo ingenioso sin ser cruel."
                    )
                    sys_ov = "Eres Dalet. Da un veredicto técnico y sarcástico de 1-2 oraciones sobre este duelo de osu!."
                else:
                    cmp_prompt = (
                        f"ROLE: You are Dalet, sharp osu! analyst ({mode_str}).\n"
                        f"TASK: Write a 1-2 sentence duel verdict (25-35 words) comparing {u1.get('username', u1_name)} ({pp1:.0f}pp, best at {dom1}) "
                        f"vs {u2.get('username', u2_name)} ({pp2:.0f}pp, best at {dom2}). "
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
                u1, u2,
                skills1=skills1,
                skills2=skills2,
                mode=mode_str,
                lang=server_lang,
                common_maps_data=common_maps,
                verdict_text=verdict_text,
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /compare: {e}")
            await interaction.followup.send(f"{DaletAtoms.GLYPH_POINTER} error comparando perfiles.", ephemeral=True)


    # ------------------------------------------------------------------
    # Conversaciones / Memoria
    # ------------------------------------------------------------------

    @app_commands.command(name="lore", description="Searches server history and chat archives with cynical AI commentary.")
    @app_commands.describe(query="Topic to research in server history")
    async def slash_lore(self, interaction: discord.Interaction, query: str):
        # Cooldown anti-spam de 10s por usuario
        cd_left = self._check_cooldown(f"lore:{interaction.user.id}", 10.0)
        if cd_left:
            return await interaction.response.send_message(
                f"{DaletAtoms.GLYPH_POINTER} Calma, espera `{cd_left:.0f}s` antes de volver a investigar lore.",
                ephemeral=True
            )

        await interaction.response.defer()
        lang = await self._resolve_lang(interaction)
        try:
            # Truncar query de búsqueda abusiva (máx 150 caracteres)
            clean_query = query.strip()[:150]
            resultados = await self.bot.user_repo.search_lore(clean_query, interaction.channel_id, limit=20)
            if not resultados:
                return await interaction.followup.send(
                    f"{DaletAtoms.GLYPH_POINTER} ni idea de qué es '{clean_query}'. ese lore te lo inventaste."
                )

            bot_name = "Dalet"
            if interaction.guild_id:
                try:
                    bot_name = await self.bot.admin_repo.get_server_custom_name(interaction.guild_id)
                except Exception:
                    pass

            lineas = []
            for r in resultados:
                ts = r['Timestamp'] if isinstance(r, dict) else r[2]
                fecha = str(ts)[:10] if ts else "??/??/????"
                usr = r['UserName'] if isinstance(r, dict) else r[0]
                cnt = r['Content'] if isinstance(r, dict) else r[1]
                if usr and usr.lower() in ("dalet", (bot_name or "").lower()):
                    usr = f"Tú ({bot_name})"
                lineas.append(f"[{fecha}] {usr}: {cnt}")

            prompt = (
                f"ESTÁS INVESTIGANDO EL LORE DEL SERVIDOR sobre \"{clean_query}\":\n"
                + "\n".join(lineas)
                + "\nResponde de forma sarcástica y directa, como quien revisó los archivos."
            )
            respuesta = await self.bot.nlp_service.generate_reply(
                prompt, "", interaction.user.display_name, bot_name=bot_name, max_tokens=450, language=lang
            )
            await interaction.followup.send(
                respuesta or f"{DaletAtoms.GLYPH_POINTER} me dio pereza leer los archivos. inténtalo otra vez.",
                allowed_mentions=discord.AllowedMentions.none()
            )
        except Exception as e:
            logger.error(f"Error en /lore: {e}")
            await interaction.followup.send(f"{DaletAtoms.GLYPH_CROSS} error leyendo los archivos.", ephemeral=True)

    @app_commands.command(name="resumir", description="Genera un resumen inteligente de la conversación reciente del canal.")
    @app_commands.describe(
        limit="Cantidad de mensajes recientes a analizar (10 a 50, por defecto: 25).",
        estilo="Tono del resumen: 'dalet' (ingenioso y con personalidad) o 'neutral' (objetivo y analítico)."
    )
    async def slash_resumir(
        self,
        interaction: discord.Interaction,
        limit: int = 25,
        estilo: Literal["dalet", "neutral"] = "dalet",
    ):
        # Cooldown anti-spam de 15s por canal
        cd_left = self._check_cooldown(f"resumir:{interaction.channel_id}", 15.0)
        if cd_left:
            return await interaction.response.send_message(
                f"{DaletAtoms.GLYPH_POINTER} Este canal ya fue resumido hace poco. Espera `{cd_left:.0f}s` antes de pedir otro resumen.",
                ephemeral=True
            )

        await interaction.response.defer()
        try:
            clamped_limit = min(max(10, limit), 50)
            channel = interaction.channel
            if not channel or not hasattr(channel, "history"):
                return await interaction.followup.send(f"{DaletAtoms.GLYPH_CROSS} No se puede acceder al historial de este canal.", ephemeral=True)

            raw_messages = []
            async for msg in channel.history(limit=clamped_limit + 5):
                # Omitir invocaciones vacías o el propio mensaje actual
                if msg.id == interaction.id:
                    continue
                raw_messages.append(msg)
                if len(raw_messages) >= clamped_limit:
                    break

            if len(raw_messages) < 3:
                return await interaction.followup.send(f"{DaletAtoms.GLYPH_POINTER} No hay suficientes mensajes recientes para generar un resumen.", ephemeral=True)

            # Invertir para leer en orden cronológico (antiguo -> reciente)
            raw_messages.reverse()

            lineas = []
            for m in raw_messages:
                author_name = m.author.display_name or m.author.name
                content = (m.clean_content or "").strip()
                if not content and m.attachments:
                    content = f"[Adjuntó {len(m.attachments)} archivo(s)/imagen(es)]"
                elif not content and m.embeds:
                    content = "[Envió un embed/enlace]"
                elif m.attachments:
                    content += f" (+{len(m.attachments)} adjunto(s))"

                if len(content) > 300:
                    content = content[:300] + "…"

                lineas.append(f"{author_name}: {content}")

            historial = "\n".join(lineas)

            if estilo == "dalet":
                system_prompt = (
                    "Eres Dalet, una chica aguda, observadora, ligeramente sarcástica y muy carismática de Discord. "
                    "Tu tarea es resumir la conversación reciente de este canal sin rodeos innecesarios. "
                    "Sigue ESTRICTAMENTE esta estructura en Markdown (sin emojis coloridos):\n"
                    "### ▸ En pocas palabras (TL;DR)\n"
                    "(1 o 2 oraciones resumiendo el punto central de lo que pasó)\n\n"
                    "### ▫ Temas clave\n"
                    "▫ (Punto 1 claro)\n"
                    "▫ (Punto 2 claro)\n"
                    "▫ (Punto 3 claro si aplica)\n\n"
                    "### ✦ El veredicto de Dalet\n"
                    "(Un comentario ingenioso, con tu humor seco y personalidad sobre de qué estaban hablando)"
                )
            else:
                system_prompt = (
                    "Eres un asistente analítico y neutral especializado en síntesis de conversaciones. "
                    "Tu tarea es resumir objetivamente la conversación reciente de este canal. "
                    "Sigue ESTRICTAMENTE esta estructura en Markdown (sin emojis coloridos):\n"
                    "### ▸ En pocas palabras (TL;DR)\n"
                    "(1 o 2 oraciones con el resumen ejecutivo central)\n\n"
                    "### ▫ Temas clave\n"
                    "▫ (Punto 1 objetivo)\n"
                    "▫ (Punto 2 objetivo)\n"
                    "▫ (Punto 3 objetivo si aplica)\n\n"
                    "### ✦ Conclusión\n"
                    "(Cierre analítico y neutral del estado de la conversación)"
                )

            user_prompt = f"Analiza esta conversación reciente ({len(raw_messages)} mensajes):\n\n{historial}\n\nGenera el resumen estructurado:"

            resumen = await self.bot.nlp_service.generate_reply(
                user_prompt,
                "Resumen de Chat",
                interaction.user.display_name or interaction.user.name,
                system_prompt_override=system_prompt,
                max_tokens=550
            )

            if not resumen:
                return await interaction.followup.send(f"{DaletAtoms.GLYPH_CROSS} No pude generar el resumen esta vez.", ephemeral=True)

            color = DaletAtoms.COLOR_PRIMARY if estilo == "dalet" else DaletAtoms.COLOR_INFO
            estilo_label = "Modo Dalet" if estilo == "dalet" else "Modo Neutral"
            embed = discord.Embed(
                title=f"{DaletAtoms.EMOJI_DALET} Resumen del Canal │ {estilo_label}",
                description=resumen,
                color=color
            )
            ch_name = getattr(channel, "name", "chat")
            embed.set_author(
                name=f"#{ch_name} │ {len(raw_messages)} mensajes analizados",
                icon_url=interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None
            )
            DaletMolecules.add_standard_footer(embed, context_text="Resumen Inteligente con IA")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /resumir: {e}")
            await interaction.followup.send(f"{DaletAtoms.GLYPH_CROSS} Ocurrió un error al generar el resumen.", ephemeral=True)

    # ------------------------------------------------------------------
    # Admin: Lock / Unlock
    # ------------------------------------------------------------------

    @app_commands.command(name="lock", description="[ADMIN] Blocks Dalet interactions and commands in this channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_lock(self, interaction: discord.Interaction):
        server_lang = "en"
        if interaction.guild_id:
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)
        try:
            await self.bot.admin_repo.set_channel_lock(
                interaction.channel_id, interaction.channel.name,
                interaction.guild_id, interaction.guild.name, True
            )
            await interaction.response.send_message(
                t("admin.lock_success", server_lang, channel=interaction.channel.mention),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /lock: {e}")
            await interaction.response.send_message(t("admin.lock_error", server_lang), ephemeral=True)

    @app_commands.command(name="unlock", description="[ADMIN] Unblocks Dalet interactions and commands in this channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_unlock(self, interaction: discord.Interaction):
        server_lang = "en"
        if interaction.guild_id:
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)
        try:
            await self.bot.admin_repo.set_channel_lock(
                interaction.channel_id, interaction.channel.name,
                interaction.guild_id, interaction.guild.name, False
            )
            await interaction.response.send_message(
                t("admin.unlock_success", server_lang, channel=interaction.channel.mention),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /unlock: {e}")
            await interaction.response.send_message(t("admin.unlock_error", server_lang), ephemeral=True)

    # ------------------------------------------------------------------
    # Admin: Proactive / Reactive
    # ------------------------------------------------------------------

    @app_commands.command(name="proactive", description="[ADMIN] Enables or disables proactive AI chat in this channel.")
    @app_commands.describe(enabled="True to enable, False to disable")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_proactive(self, interaction: discord.Interaction, enabled: bool):
        server_lang = "en"
        if interaction.guild_id:
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)
        try:
            await self.bot.user_repo.set_channel_proactive(
                interaction.channel_id, interaction.channel.name,
                interaction.guild_id, enabled
            )
            status_str = t("admin.enabled", server_lang) if enabled else t("admin.disabled", server_lang)
            await interaction.response.send_message(
                t("admin.proactive_status", server_lang, status=status_str, channel=interaction.channel.mention),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /proactive: {e}")
            await interaction.response.send_message(f"{DaletAtoms.GLYPH_CROSS} Error", ephemeral=True)

    @app_commands.command(name="reactive", description="[ADMIN] Enables or disables reactive AI replies to mentions in the server.")
    @app_commands.describe(enabled="True to enable, False to disable")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_reactive(self, interaction: discord.Interaction, enabled: bool):
        server_lang = "en"
        if interaction.guild_id:
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)
        try:
            await self.bot.user_repo.set_server_reactive(
                interaction.guild_id, interaction.guild.name, enabled
            )
            status_str = t("admin.enabled", server_lang) if enabled else t("admin.disabled", server_lang)
            await interaction.response.send_message(
                t("admin.reactive_status", server_lang, status=status_str),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /reactive: {e}")
            await interaction.response.send_message(f"{DaletAtoms.GLYPH_CROSS} Error", ephemeral=True)

    @app_commands.command(name="channelstatus", description="Displays security lock and AI status for the current channel.")
    async def slash_channelstatus(self, interaction: discord.Interaction):
        lang = await self._resolve_lang(interaction)
        if not interaction.guild:
            return await interaction.response.send_message(
                f"{DaletAtoms.GLYPH_CROSS} Server only.", ephemeral=True
            )
        try:
            is_locked = await self.bot.admin_repo.is_channel_locked(interaction.channel_id)
            is_proactive = await self.bot.user_repo.is_channel_proactive(interaction.channel_id)
            is_reactive = await self.bot.user_repo.is_server_reactive(interaction.guild_id)

            embed = discord.Embed(
                title=t("admin.cs_title", lang, channel=interaction.channel.name),
                color=DaletAtoms.COLOR_ERROR if is_locked else DaletAtoms.COLOR_SUCCESS
            )
            embed.add_field(
                name=t("admin.cs_commands", lang),
                value=t("admin.cs_blocked", lang) if is_locked else t("admin.cs_active", lang),
                inline=False
            )
            embed.add_field(
                name=t("admin.cs_proactive", lang),
                value=t("admin.cs_on", lang) if is_proactive else t("admin.cs_off", lang),
                inline=True
            )
            embed.add_field(
                name=t("admin.cs_reactive", lang),
                value=t("admin.cs_on", lang) if is_reactive else t("admin.cs_off", lang),
                inline=True
            )
            DaletMolecules.add_standard_footer(embed, context_text="Dalet")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error en /channelstatus: {e}")
            await interaction.response.send_message(f"{DaletAtoms.GLYPH_CROSS} Error", ephemeral=True)


    # ------------------------------------------------------------------
    # Admin: Welcome Channel
    # ------------------------------------------------------------------

    @app_commands.command(name="setwelcome", description="[ADMIN] Sets the welcome message channel for this server.")
    @app_commands.describe(channel="Channel where Dalet will send welcome messages")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_setwelcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        server_lang = "en"
        if interaction.guild_id:
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)
        try:
            await self.bot.admin_repo.set_welcome_channel(interaction.guild_id, channel.id)
            await interaction.response.send_message(
                t("admin.setwelcome_success", server_lang, channel=channel.mention),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /setwelcome: {e}")
            await interaction.response.send_message(t("admin.setwelcome_error", server_lang), ephemeral=True)

    @app_commands.command(name="removewelcome", description="[ADMIN] Removes the welcome channel and disables welcome greetings.")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_removewelcome(self, interaction: discord.Interaction):
        server_lang = "en"
        if interaction.guild_id:
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)
        try:
            await self.bot.admin_repo.set_welcome_channel(interaction.guild_id, None)
            await interaction.response.send_message(
                t("admin.removewelcome_success", server_lang),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /removewelcome: {e}")
            await interaction.response.send_message(t("admin.removewelcome_error", server_lang), ephemeral=True)

    # ------------------------------------------------------------------
    # Admin: Nombre personalizado del bot
    # ------------------------------------------------------------------

    @app_commands.command(name="setname", description="[ADMIN] Sets a custom nickname for Dalet in this server.")
    @app_commands.describe(name="Custom nickname (max 32 characters)")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_setname(self, interaction: discord.Interaction, name: str):
        server_lang = "en"
        if interaction.guild_id:
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)
        if len(name) > 32:
            return await interaction.response.send_message(
                t("admin.name_too_long", server_lang), ephemeral=True
            )
        try:
            await self.bot.admin_repo.set_server_custom_name(interaction.guild_id, name)
            await interaction.response.send_message(
                t("admin.setname_success", server_lang, name=name),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /setname: {e}")
            await interaction.response.send_message(t("admin.setname_error", server_lang), ephemeral=True)

    # ------------------------------------------------------------------
    # Idioma (Personal por Usuario o General del Servidor)
    # ------------------------------------------------------------------

    @app_commands.command(name="language", description="Configures your personal language preference or the server default language.")
    @app_commands.describe(
        language="Choose language: English, Español, or Auto (follow server default)",
        scope="Apply to your personal profile (default) or the entire server (Admin only)"
    )
    @app_commands.choices(
        language=[
            app_commands.Choice(name="Español", value="es"),
            app_commands.Choice(name="English", value="en"),
            app_commands.Choice(name="Auto (Follow Server Default)", value="auto"),
        ],
        scope=[
            app_commands.Choice(name="Personal (Only for me)", value="user"),
            app_commands.Choice(name="Server Default (Admin only)", value="server"),
        ],
    )
    async def slash_language(
        self,
        interaction: discord.Interaction,
        language: str = None,
        scope: str = "user",
    ):
        effective_lang = await self._resolve_lang(interaction)
        if not language:
            user_pref = await self.bot.admin_repo.get_user_language(interaction.user.id)
            srv_pref = await self.bot.admin_repo.get_server_language(interaction.guild_id) if interaction.guild_id else "en"
            u_str = user_pref.upper() if user_pref else f"AUTO ({srv_pref.upper()})"
            return await interaction.response.send_message(
                f"{DaletAtoms.GLYPH_POINTER} Personal language: **{u_str}** │ Server default: **{srv_pref.upper()}**.\n"
                f"{DaletAtoms.GLYPH_SUB} Use `/language [language] [scope]` or `d.lang es|en|auto` to change it.",
                ephemeral=True
            )

        if scope == "server":
            if not interaction.guild_id or not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message(
                    f"{DaletAtoms.GLYPH_CROSS} You need Administrator permissions to change the server default language.",
                    ephemeral=True
                )
            srv_code = "en" if language == "auto" else language
            await self.bot.admin_repo.set_server_language(
                interaction.guild_id, srv_code, interaction.guild.name if interaction.guild else None
            )
            if srv_code == "es":
                return await interaction.response.send_message(
                    f"{DaletAtoms.EMOJI_DALET} Idioma del servidor actualizado a **Español**. Dalet responderá y mostrará estadísticas en español por defecto.",
                    ephemeral=False
                )
            return await interaction.response.send_message(
                f"{DaletAtoms.EMOJI_DALET} Server language updated to **English**. Dalet will now chat and format statistics in English by default.",
                ephemeral=False
            )

        # Scope = user (cualquier usuario puede elegir su idioma personal)
        await self.bot.admin_repo.set_user_language(
            interaction.user.id,
            None if language == "auto" else language,
            str(interaction.user),
        )
        new_eff = await self._resolve_lang(interaction)
        if language == "auto":
            msg = (
                f"{DaletAtoms.GLYPH_CHECK} Tu idioma personal ahora sigue el del servidor (**{new_eff.upper()}**)."
                if new_eff.startswith("es") else
                f"{DaletAtoms.GLYPH_CHECK} Your personal language now follows the server default (**{new_eff.upper()}**)."
            )
        elif language == "es":
            msg = f"{DaletAtoms.GLYPH_CHECK} Tu idioma personal ha sido actualizado a **Español**."
        else:
            msg = f"{DaletAtoms.GLYPH_CHECK} Your personal language has been set to **English**."
        await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SlashCommands(bot))

