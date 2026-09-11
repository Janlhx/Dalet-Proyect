"""
Slash Commands (Application Commands) de Dalet.
Unifica y expone los comandos principales como comandos de barra / para Discord.
"""
import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import format_dt
import logging

from ui.organisms import DaletOrganisms
from ui.atoms import DaletAtoms
from ui.molecules import DaletMolecules
from ui.locales import t
from services.feedback_service import FeedbackService
from handlers.dalet_osu_presenter import OsuPresenter
from handlers.modules.dalet_osuanalyzer import OsuAnalyzer

logger = logging.getLogger("dalet.handlers.slash")


class SlashCommands(commands.Cog, name="Slash Commands"):
    """Versiones slash (/) de los comandos principales de Dalet."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    @app_commands.command(name="ping", description="Checks bot response latency in milliseconds.")
    async def slash_ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            f"🏓 response time: **{latency}ms**. don't rush me.", ephemeral=True
        )

    @app_commands.command(name="stats", description="Displays your server social activity statistics.")
    @app_commands.describe(user="User to inspect (defaults to yourself)")
    async def slash_stats(self, interaction: discord.Interaction, user: discord.Member = None):
        member = user or interaction.user
        server_lang = "en"
        if interaction.guild_id:
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)
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
        server_lang = "en"
        if interaction.guild_id:
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)
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
        server_lang = "en"
        if interaction.guild_id:
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)
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
        server_lang = "en"
        if interaction.guild_id:
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)

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

    @app_commands.command(name="help", description="Displays an interactive categorized command guide.")
    async def slash_help(self, interaction: discord.Interaction):
        from handlers.dalet_helpcommands_handlers import build_help_pages, HelpPaginator
        server_lang = "en"
        if interaction.guild_id:
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)
        pages, category_names = build_help_pages(self.bot, interaction.user, server_lang=server_lang)
        view = HelpPaginator(pages, category_names, lang=server_lang)
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)

    @app_commands.command(name="feedback", description="Sends feedback, suggestions, or bug reports directly to the developer.")
    @app_commands.describe(message="Feedback, suggestion, or bug report to deliver")
    async def slash_feedback(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer(ephemeral=True)
        server_lang = "en"
        if interaction.guild_id:
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)

        # Anti-spam Cooldown (5 minutos)
        cooldown_remaining = await FeedbackService.check_user_cooldown(interaction.user.id)
        if cooldown_remaining > 0:
            mins = max(1, (cooldown_remaining + 59) // 60)
            warning_msg = (
                f"⏳ Has enviado una sugerencia recientemente. Para evitar saturación, por favor espera **{mins} minuto(s)** antes de enviar otra."
                if server_lang == "es"
                else f"⏳ You have submitted feedback recently. To prevent spam, please wait **{mins} minute(s)** before sending another."
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

    @app_commands.command(name="op", description="Displays full osu! profile, rank, and stats for a player.")
    @app_commands.describe(
        username="osu! username (or leave empty for your linked account)",
        mode="Game mode (default: osu)"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="osu!standard", value="osu"),
        app_commands.Choice(name="osu!taiko",    value="taiko"),
        app_commands.Choice(name="osu!catch",    value="fruits"),
        app_commands.Choice(name="osu!mania",    value="mania"),
    ])
    async def slash_op(
        self, interaction: discord.Interaction,
        username: str = None, mode: str = "osu"
    ):
        await interaction.response.defer()
        try:
            uname = username
            if not uname:
                uname = await self.bot.osu_repo.get_linked_username(interaction.user.id)
            if not uname:
                return await interaction.followup.send(
                    "❌ no tienes cuenta vinculada. usa `/link` primero.",
                    ephemeral=True
                )
            server_lang = "en"
            if interaction.guild:
                server_lang = await self.bot.admin_repo.get_server_language(interaction.guild.id)
            user = await self.bot.osu_service.get_user(uname, mode)
            embed = OsuPresenter.build_profile_card(user, mode, lang=server_lang)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /op: {e}")
            await interaction.followup.send("⚠️ error obteniendo el perfil.", ephemeral=True)

    @app_commands.command(name="link", description="Links your Discord account to your osu! profile.")
    @app_commands.describe(username="Your osu! username")
    async def slash_link(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer(ephemeral=True)
        try:
            user_data = await self.bot.osu_service.get_user(username)
            if not user_data or "statistics" not in user_data:
                return await interaction.followup.send(
                    f"❌ no encontré a '{username}' en osu!.", ephemeral=True
                )
            stats = user_data.get("statistics", {})
            await self.bot.osu_repo.link_account(
                interaction.user.id,
                user_data["username"],
                user_data["id"],
                user_data.get("playmode", "osu"),
                stats.get("pp", 0.0),
                stats.get("global_rank"),
                stats.get("country_rank"),
                stats.get("hit_accuracy", 0.0),
            )
            await interaction.followup.send(
                f"✅ vinculado con **{user_data['username']}**.", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error en /link: {e}")
            await interaction.followup.send("❌ error al vincular.", ephemeral=True)

    @app_commands.command(name="recent", description="Displays your most recent osu! play with detailed stats.")
    @app_commands.describe(
        username="osu! username (or leave empty for your linked account)",
        mode="Game mode"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="osu!standard", value="osu"),
        app_commands.Choice(name="osu!taiko",    value="taiko"),
        app_commands.Choice(name="osu!catch",    value="fruits"),
        app_commands.Choice(name="osu!mania",    value="mania"),
    ])
    async def slash_recent(
        self, interaction: discord.Interaction,
        username: str = None, mode: str = "osu"
    ):
        await interaction.response.defer()
        uname = username
        if not uname:
            uname = await self.bot.osu_repo.get_linked_username(interaction.user.id)
        if not uname:
            return await interaction.followup.send(
                "❌ no tienes cuenta vinculada.", ephemeral=True
            )
        try:
            server_lang = "en"
            if interaction.guild:
                server_lang = await self.bot.admin_repo.get_server_language(interaction.guild.id)
            user = await self.bot.osu_service.get_user(uname, mode)
            recent = await self.bot.osu_service.get_user_recent_scores(
                user["id"], mode, limit=1, include_fails=1
            )
            if not recent:
                return await interaction.followup.send(
                    f"**{uname}** no tiene jugadas recientes."
                )

            embed = OsuPresenter.build_recent_card(user.get("username", uname), mode, recent[0], user_data=user, lang=server_lang)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en /recent: {e}")
            await interaction.followup.send("⚠️ error obteniendo la jugada.", ephemeral=True)

    @app_commands.command(name="top", description="Displays your top 5 best registered osu! scores.")
    @app_commands.describe(
        username="osu! username (or leave empty for your linked account)",
        mode="Game mode"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="osu!standard", value="osu"),
        app_commands.Choice(name="osu!taiko",    value="taiko"),
        app_commands.Choice(name="osu!catch",    value="fruits"),
        app_commands.Choice(name="osu!mania",    value="mania"),
    ])
    async def slash_top(self, interaction: discord.Interaction, username: str = None, mode: str = "osu"):
        await interaction.response.defer()
        uname = username
        if not uname:
            uname = await self.bot.osu_repo.get_linked_username(interaction.user.id)
        if not uname:
            return await interaction.followup.send(
                "❌ no tienes cuenta vinculada.", ephemeral=True
            )
        try:
            server_lang = "en"
            if interaction.guild:
                server_lang = await self.bot.admin_repo.get_server_language(interaction.guild.id)
            user = await self.bot.osu_service.get_user(uname, mode)
            best = await self.bot.osu_service.get_user_best_scores(user["id"], mode=mode, limit=5)
            embed = OsuPresenter.build_top_card(user.get("username", uname), mode, best, user_data=user, lang=server_lang)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /top: {e}")
            await interaction.followup.send("⚠️ error obteniendo top plays.", ephemeral=True)

    @app_commands.command(name="skills", description="5-dimension osu! skill radar (Aim, Speed, Acc, Stamina, Reading) with Dalet's verdict.")
    @app_commands.describe(
        username="osu! username (or leave empty for your linked account)",
        mode="Game mode (default: osu)"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="osu!standard", value="osu"),
        app_commands.Choice(name="osu!taiko",    value="taiko"),
        app_commands.Choice(name="osu!catch",    value="fruits"),
        app_commands.Choice(name="osu!mania",    value="mania"),
    ])
    async def slash_skills(
        self, interaction: discord.Interaction,
        username: str = None, mode: str = "osu"
    ):
        await interaction.response.defer()
        try:
            uname = username
            if not uname:
                uname = await self.bot.osu_repo.get_linked_username(interaction.user.id)
            if not uname:
                return await interaction.followup.send(
                    "❌ no tienes cuenta vinculada. usa `/link` primero o especifica un usuario.",
                    ephemeral=True
                )

            user = await self.bot.osu_service.get_user(uname, mode)
            best = await self.bot.osu_service.get_user_best_scores(user["id"], mode=mode, limit=50)
            if not best:
                return await interaction.followup.send(f"**{uname}** no tiene mejores jugadas registradas en {mode}.")

            server_lang = "en"
            if interaction.guild_id:
                try:
                    server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)
                except Exception:
                    server_lang = "en"

            skills_data = OsuAnalyzer.calculate_skills(best, mode=mode, lang=server_lang)

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
                    f"TAREA: Haz un roast o veredicto técnico contundente (MÁXIMO 2 ORACIONES, 25-35 palabras) sobre el perfil de {uname}:\n"
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
                    f"TASK: Write a biting technical roast (MAX 2 SHORT SENTENCES, 25-35 words) about {uname}'s profile in English:\n"
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
                    micro_prompt, "Skill Roast", uname,
                    max_tokens_override=350,
                    system_prompt_override=system_override,
                    language=server_lang
                )
            except Exception as nlp_err:
                logger.warning(f"No se pudo generar roast para slash skills ({uname}): {nlp_err}")

            if not _is_valid_roast(roast_text):
                fallback_default = f"Mucho número inflado en {dominant}, pero en {weakest} das pena ajena." if is_es else f"Over-inflated numbers in {dominant}, but your {weakest} is embarrassing."
                roast_text = fallback_roasts.get(weakest, fallback_default)

            embed = OsuPresenter.build_skills_card(user, skills_data, roast_text=roast_text, mode=mode, lang=server_lang)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /skills: {e}")
            await interaction.followup.send("⚠️ error calculando las habilidades.", ephemeral=True)

    @app_commands.command(name="rank", description="Server osu! leaderboard for linked members.")
    async def slash_rank(self, interaction: discord.Interaction):
        await interaction.response.defer()
        server_lang = "en"
        if interaction.guild_id:
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)
        try:
            guild_member_ids = [str(m.id) for m in interaction.guild.members if not m.bot]
            all_rows = await self.bot.osu_repo.get_ranking(limit=200)
            server_rows = [
                row for row in all_rows
                if str(row.get("UserID") or row.get("userid") or "") in guild_member_ids
            ][:10]

            if not server_rows:
                return await interaction.followup.send(t("rank.empty", server_lang))
            medals = ["✦", "◈", "◇"]
            lines = []
            for i, row in enumerate(server_rows):
                medal = medals[i] if i < 3 else f"`{i+1}.`"
                name = row.get("UserName") or row.get("username") or row.get("osuusername") or "??"
                pp = float(row.get("PP") or row.get("pp") or 0)
                acc = float(row.get("Accuracy") or row.get("accuracy") or 0)
                lines.append(f"{medal} **{name}** — {pp:,.0f}pp • {acc:.2f}%")
            embed = discord.Embed(
                title=f"{DaletAtoms.EMOJI_DALET} {t('rank.title', server_lang)}",
                description="\n".join(lines),
                color=DaletAtoms.COLOR_PRIMARY
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /rank: {e}")
            await interaction.followup.send(t("rank.error", server_lang), ephemeral=True)

    @app_commands.command(name="compare", description="Compares your osu! profile head-to-head against another player.")
    @app_commands.describe(username="Player to compare against")
    async def slash_compare(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer()
        user1_name = await self.bot.osu_repo.get_linked_username(interaction.user.id)
        if not user1_name:
            return await interaction.followup.send(
                "❌ necesitas vincular tu cuenta primero.", ephemeral=True
            )
        try:
            u1, u2 = await asyncio.gather(
                self.bot.osu_service.get_user(user1_name),
                self.bot.osu_service.get_user(username),
            )
            server_lang = "en"
            if interaction.guild:
                server_lang = await self.bot.admin_repo.get_server_language(interaction.guild.id)
            embed = OsuPresenter.build_compare_card(u1, u2, lang=server_lang)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /compare: {e}")
            await interaction.followup.send("⚠️ error comparando.", ephemeral=True)

    # ------------------------------------------------------------------
    # Conversaciones / Memoria
    # ------------------------------------------------------------------

    @app_commands.command(name="lore", description="Searches server history and chat archives with cynical AI commentary.")
    @app_commands.describe(query="Topic to research in server history")
    async def slash_lore(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        try:
            resultados = await self.bot.user_repo.search_lore(query, interaction.channel_id, limit=20)
            if not resultados:
                return await interaction.followup.send(
                    f"ni idea de qué es '{query}'. ese lore te lo inventaste."
                )
            lineas = []
            for r in resultados:
                ts = r['Timestamp'] if isinstance(r, dict) else r[2]
                fecha = str(ts)[:10] if ts else "??/??/????"
                usr = r['UserName'] if isinstance(r, dict) else r[0]
                cnt = r['Content'] if isinstance(r, dict) else r[1]
                lineas.append(f"[{fecha}] {usr}: {cnt}")

            prompt = (
                f"ESTÁS INVESTIGANDO EL LORE DEL SERVIDOR sobre \"{query}\":\n"
                + "\n".join(lineas)
                + "\nResponde de forma sarcástica y directa, como quien revisó los archivos."
            )
            respuesta = await self.bot.nlp_service.generate_reply(
                prompt, "", interaction.user.display_name
            )
            await interaction.followup.send(respuesta or "me dio pereza leer los archivos. inténtalo otra vez.")
        except Exception as e:
            logger.error(f"Error en /lore: {e}")
            await interaction.followup.send("error leyendo los archivos.", ephemeral=True)

    @app_commands.command(name="resumir", description="Generates a smart AI digest of recent channel conversations.")
    @app_commands.describe(limit="Number of messages to analyze (default: 50)")
    async def slash_resumir(self, interaction: discord.Interaction, limit: int = 50):
        await interaction.response.defer()
        try:
            registros = await self.bot.user_repo.get_channel_messages(
                interaction.channel_id, min(limit, 100)
            )
            if not registros:
                return await interaction.followup.send("no hay suficientes mensajes para resumir.")

            display_list = list(registros)
            display_list.reverse()
            historial = "\n".join([f"{r.get('username') or r.get('UserName') or 'Desconocido'}: {r.get('content') or r.get('Content') or ''}" for r in display_list])

            prompt = (
                f"Genera un resumen conciso y directo de esta conversación. "
                f"Tono casual, sin florituras:\n\n{historial}\n\nResumen:"
            )
            resumen = await self.bot.nlp_service.generate_reply(
                prompt, "Resumen", "Sistema",
                system_prompt_override="Eres un asistente analítico y neutral especializado en resumir conversaciones. No tienes personalidad, no haces chistes."
            )
            if not resumen:
                return await interaction.followup.send("no pude generar el resumen.")

            embed = discord.Embed(
                title=f"📄 Resumen de {len(registros)} mensajes",
                description=resumen,
                color=0xFF8C42
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en /resumir: {e}")
            await interaction.followup.send("error generando el resumen.", ephemeral=True)

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
            await interaction.response.send_message("❌ Error", ephemeral=True)

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
            await interaction.response.send_message("❌ Error", ephemeral=True)


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
    # Admin: Idioma del servidor (English / Español)
    # ------------------------------------------------------------------

    @app_commands.command(name="language", description="[ADMIN] Configures or displays the server language.")
    @app_commands.describe(language="Choose server language (en: English, es: Español)")
    @app_commands.choices(language=[
        app_commands.Choice(name="English (Default)", value="en"),
        app_commands.Choice(name="Español", value="es"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_language(self, interaction: discord.Interaction, language: str = None):
        if not interaction.guild_id:
            return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)

        if not language:
            current = await self.bot.admin_repo.get_server_language(interaction.guild_id)
            lang_name = "English" if current == "en" else "Español"
            return await interaction.response.send_message(
                f"{DaletAtoms.GLYPH_POINTER} Current server language is **{lang_name}** (`{current}`).\n"
                f"{DaletAtoms.GLYPH_SUB} Use `/language [language]` to change it.",
                ephemeral=True
            )

        await self.bot.admin_repo.set_server_language(interaction.guild_id, language)
        if language == "es":
            await interaction.response.send_message(
                f"{DaletAtoms.EMOJI_DALET} Idioma del servidor actualizado a **Español**. Dalet responderá y mostrará estadísticas en español.",
                ephemeral=False
            )
        else:
            await interaction.response.send_message(
                f"{DaletAtoms.EMOJI_DALET} Server language updated to **English**. Dalet will now chat and format statistics in English.",
                ephemeral=False
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(SlashCommands(bot))

