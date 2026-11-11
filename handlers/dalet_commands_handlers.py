import logging
import discord
from discord.ext import commands
from discord.utils import format_dt

from ui.organisms import DaletOrganisms
from ui.atoms import DaletAtoms
from ui.molecules import DaletMolecules
from ui.locales import t
from services.feedback_service import FeedbackService

logger = logging.getLogger("dalet.handlers.general")


class CommandsHandler(commands.Cog, name="Comandos Generales"):
    """Comandos generales de utilidad, métricas e información de Dalet."""

    def __init__(self, bot):
        self.bot = bot
        self.repo = bot.user_repo

    async def _resolve_lang(self, ctx) -> str:
        guild_id = ctx.guild.id if getattr(ctx, "guild", None) else None
        try:
            return await self.bot.admin_repo.resolve_language(ctx.author.id, guild_id, default="en")
        except Exception:
            return "en"

    @commands.command(name="ping", aliases=["ms"])
    async def ping_cmd(self, ctx):
        """Muestra la latencia de respuesta del bot en milisegundos."""
        lang = await self._resolve_lang(ctx)
        latency = round(self.bot.latency * 1000)
        embed = DaletOrganisms.create_simple_embed(
            f"{DaletAtoms.GLYPH_CHECK} {t('general.latency_title', lang)}",
            t("general.latency_desc", lang, latency=latency)
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def stats(self, ctx, member: discord.Member = None):
        """Muestra estadísticas sociales y métricas de actividad de un usuario."""
        lang = await self._resolve_lang(ctx)
        member = member or ctx.author
        try:
            async with ctx.typing():
                stats = await self.repo.get_user_social_stats(member.id)
            avatar = member.display_avatar.url if member.display_avatar else None
            embed = DaletOrganisms.create_user_stats_card(member.display_name, stats, avatar, lang=lang)
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en stats: {e}")
            await ctx.send(f"{DaletAtoms.GLYPH_CROSS} {t('general.user_stats_fail', lang)}")

    @commands.command()
    async def userinfo(self, ctx, member: discord.Member = None):
        """Muestra información detallada de un usuario del servidor."""
        lang = await self._resolve_lang(ctx)
        member = member or ctx.author
        joined_line = (
            f"{DaletAtoms.GLYPH_SUB} {DaletAtoms.bold(t('userinfo.joined', lang))}: {format_dt(member.joined_at, 'D')}\n"
            if getattr(member, "joined_at", None) else ""
        )
        desc = (
            f"{DaletAtoms.GLYPH_SUB} {DaletAtoms.bold(t('userinfo.id', lang))}: {DaletAtoms.code(member.id)}\n"
            f"{DaletAtoms.GLYPH_SUB} {DaletAtoms.bold(t('userinfo.created', lang))}: {format_dt(member.created_at, 'D')}\n"
            f"{joined_line}"
        )
        embed = DaletOrganisms.create_simple_embed(t("userinfo.title", lang, username=member.display_name), desc)
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command()
    async def serverinfo(self, ctx):
        """Muestra información detallada del servidor actual."""
        lang = await self._resolve_lang(ctx)
        g = ctx.guild
        if not g:
            msg = (
                f"{DaletAtoms.GLYPH_CROSS} Este comando solo funciona dentro de un servidor."
                if lang.startswith("es") else
                f"{DaletAtoms.GLYPH_CROSS} This command can only be used inside a server."
            )
            return await ctx.send(msg)
        owner_str = g.owner.mention if g.owner else "N/A"
        desc = (
            f"{DaletAtoms.GLYPH_SUB} {DaletAtoms.bold(t('serverinfo.members', lang))}: {DaletAtoms.code(g.member_count)}\n"
            f"{DaletAtoms.GLYPH_SUB} {DaletAtoms.bold(t('serverinfo.owner', lang))}: {owner_str}\n"
            f"{DaletAtoms.GLYPH_SUB} {DaletAtoms.bold(t('serverinfo.created', lang))}: {format_dt(g.created_at, 'D')}\n"
        )
        embed = DaletOrganisms.create_simple_embed(t("serverinfo.title", lang, name=g.name), desc)
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        await ctx.send(embed=embed)

    @commands.command(name="feedback", aliases=["sugerencia", "suggest"])
    async def feedback(self, ctx: commands.Context, *, mensaje: str):
        """Envía comentarios o sugerencias directamente al desarrollador."""
        lang = await self._resolve_lang(ctx)

        # Anti-spam Cooldown (5 minutos)
        cooldown_remaining = await FeedbackService.check_user_cooldown(ctx.author.id)
        if cooldown_remaining > 0:
            mins = max(1, (cooldown_remaining + 59) // 60)
            warning_msg = (
                f"{DaletAtoms.GLYPH_POINTER} Has enviado una sugerencia recientemente. Para evitar saturación, por favor espera **{mins} minuto(s)** antes de enviar otra."
                if lang.startswith("es")
                else f"{DaletAtoms.GLYPH_POINTER} You have submitted feedback recently. To prevent spam, please wait **{mins} minute(s)** before sending another."
            )
            await ctx.send(warning_msg)
            return

        sent = await FeedbackService.send_feedback(
            bot=self.bot,
            author=ctx.author,
            content=mensaje,
            guild=ctx.guild,
            channel=ctx.channel
        )
        if sent:
            await ctx.send(t("feedback.success", lang))
        else:
            await ctx.send(t("feedback.error", lang))

    @commands.command()
    async def say(self, ctx: commands.Context, *, mensaje: str):
        """Hace que Dalet repita el mensaje indicado (con menciones desactivadas por seguridad)."""
        clean_msg = mensaje.strip()
        if not clean_msg:
            return
        await ctx.send(clean_msg, allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name="lore")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def lore(self, ctx: commands.Context, *, busqueda: str):
        """Investiga el pasado del servidor sobre un tema específico."""
        lang = await self._resolve_lang(ctx)
        is_es = lang.startswith("es")
        try:
            async with ctx.typing():
                # 1. Buscar en SQLite
                resultados = await self.repo.search_lore(busqueda, ctx.channel.id, limit=25)

                if not resultados:
                    msg = (
                        f"{DaletAtoms.GLYPH_POINTER} Ni idea de qué es '{busqueda}'. Ese lore te lo inventaste tú o es demasiado aburrido para guardarlo."
                        if is_es else
                        f"{DaletAtoms.GLYPH_POINTER} No idea what '{busqueda}' is. Either you made that lore up or it was too boring to archive."
                    )
                    await ctx.send(msg)
                    return

                bot_name = "Dalet"
                if ctx.guild:
                    try:
                        bot_name = await self.bot.admin_repo.get_server_custom_name(ctx.guild.id)
                    except Exception:
                        pass

                # 2. Formatear — SQLite devuelve timestamps como string, no datetime
                lineas = []
                for r in resultados:
                    ts = r['Timestamp'] if isinstance(r, dict) else r[2]
                    if hasattr(ts, 'strftime'):
                        fecha = ts.strftime('%d/%m/%Y')
                    else:
                        fecha = str(ts)[:10] if ts else "??/??/????"
                    username = r['UserName'] if isinstance(r, dict) else r[0]
                    content = r['Content'] if isinstance(r, dict) else r[1]
                    if username and username.lower() in ("dalet", (bot_name or "").lower()):
                        username = f"Tú ({bot_name})"
                    lineas.append(f"[{fecha}] {username}: {content}")

                contexto_lore = "\n".join(lineas)

                # 3. Generar respuesta con personalidad
                prompt_especial = (
                    f"ESTÁS INVESTIGANDO EL \"LORE\" DEL SERVIDOR.\n"
                    f"Fragmentos encontrados en la base de datos sobre \"{busqueda}\":\n"
                    f"{contexto_lore}\n\n"
                    f"Responde sobre el tema \"{busqueda}\" usando estos datos. "
                    f"Sé sarcástica, directa y cotilla — como alguien que revisó los archivos del servidor."
                )
                respuesta = await self.bot.nlp_service.generate_reply(
                    prompt_especial, "", ctx.author.display_name, bot_name=bot_name, language=lang
                )

                if respuesta:
                    await ctx.send(respuesta, allowed_mentions=discord.AllowedMentions.none())
                else:
                    await ctx.send(
                        f"{DaletAtoms.GLYPH_POINTER} Me dio pereza terminar de leer los archivos. Pregúntame otra vez."
                        if is_es else
                        f"{DaletAtoms.GLYPH_POINTER} Got too lazy finishing the logs. Ask again."
                    )

        except Exception as e:
            logger.error(f"Error en lore: {e}")
            await ctx.send(
                f"{DaletAtoms.GLYPH_CROSS} Se me han empolvado los archivos y no puedo leer nada ahora mismo."
                if is_es else
                f"{DaletAtoms.GLYPH_CROSS} The archive got dusty and I couldn't read the logs right now."
            )

    @commands.command(name="info", aliases=["about", "botinfo"])
    async def show_info(self, ctx):
        """Muestra la tarjeta de presentación de Dalet."""
        lang = await self._resolve_lang(ctx)

        tagline = t("info.tagline", lang)
        lbl_creator = t("info.creator", lang)
        lbl_status = t("info.status", lang)
        status_desc = t("info.status_desc", lang)
        lbl_prefix = t("info.prefix", lang)
        prefix_desc = t("info.prefix_desc", lang)
        hint_changelog = t("info.changelog_hint", lang)
        hint_help = t("info.help_hint", lang)
        hint_feedback = t("info.feedback_hint", lang)

        embed = discord.Embed(
            title=f"{DaletAtoms.EMOJI_DALET} " + t("info.title", lang, version=DaletAtoms.VERSION),
            description=(
                f"{tagline}\n\n"
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
        await ctx.send(embed=embed)

    @commands.command(name="changelog", aliases=["novedades", "changes", "updates"])
    async def show_changelog(self, ctx):
        """Muestra las notas de actualización, hito mayor y commits recientes de Dalet."""
        lang = await self._resolve_lang(ctx)

        custom = getattr(self.bot, "custom_changelog", None)
        from services.changelog_service import ChangelogService
        embed = ChangelogService.build_embed(server_lang=lang, custom_banner=custom)

        if self.bot.user and self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CommandsHandler(bot))
