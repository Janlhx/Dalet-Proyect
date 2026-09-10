import discord
from discord.ext import commands
import logging
from discord.utils import format_dt

logger = logging.getLogger("dalet.handlers.general")

from ui.organisms import DaletOrganisms
from ui.atoms import DaletAtoms
from ui.molecules import DaletMolecules
from ui.locales import t


class CommandsHandler(commands.Cog, name="Comandos Generales"):
    """Comandos básicos de Dalet (utilidades, info y herramientas generales)."""

    def __init__(self, bot):
        self.bot = bot
        self.repo = bot.user_repo

    @commands.command()
    async def ms(self, ctx):
        """🏓 Muestra la latencia del bot en milisegundos."""
        server_lang = "en"
        if ctx.guild:
            server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)
        latency = round(self.bot.latency * 1000)
        embed = DaletOrganisms.create_simple_embed(
            f"{DaletAtoms.EMOJI_SUCCESS} {t('general.latency_title', server_lang)}",
            t("general.latency_desc", server_lang, latency=latency)
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def stats(self, ctx, member: discord.Member = None):
        """📊 Muestra tus estadísticas sociales o las de otro usuario."""
        server_lang = "en"
        if ctx.guild:
            server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)
        member = member or ctx.author
        try:
            async with ctx.typing():
                stats = await self.repo.get_user_social_stats(member.id)
            avatar = member.avatar.url if member.avatar else None
            embed = DaletOrganisms.create_user_stats_card(member.display_name, stats, avatar, lang=server_lang)
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en stats: {e}")
            await ctx.send(t("general.user_stats_fail", server_lang))

    @commands.command()
    async def userinfo(self, ctx, member: discord.Member = None):
        """Muestra información detallada de un usuario del servidor."""
        server_lang = "en"
        if ctx.guild:
            server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)
        member = member or ctx.author
        desc = (
            f"• {DaletAtoms.bold(t('userinfo.id', server_lang))}: {DaletAtoms.code(member.id)}\n"
            f"• {DaletAtoms.bold(t('userinfo.created', server_lang))}: {format_dt(member.created_at, 'D')}\n"
            f"• {DaletAtoms.bold(t('userinfo.joined', server_lang))}: {format_dt(member.joined_at, 'D')}\n"
        )
        embed = DaletOrganisms.create_simple_embed(t("userinfo.title", server_lang, username=member.display_name), desc)
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        await ctx.send(embed=embed)

    @commands.command()
    async def serverinfo(self, ctx):
        """Muestra información detallada del servidor actual."""
        server_lang = "en"
        if ctx.guild:
            server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)
        g = ctx.guild
        desc = (
            f"• {DaletAtoms.bold(t('serverinfo.members', server_lang))}: {DaletAtoms.code(g.member_count)}\n"
            f"• {DaletAtoms.bold(t('serverinfo.owner', server_lang))}: {g.owner.mention}\n"
            f"• {DaletAtoms.bold(t('serverinfo.created', server_lang))}: {format_dt(g.created_at, 'D')}\n"
        )
        embed = DaletOrganisms.create_simple_embed(t("serverinfo.title", server_lang, name=g.name), desc)
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        await ctx.send(embed=embed)

    @commands.command(name="feedback", aliases=["sugerencia", "suggest"])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def feedback(self, ctx, *, mensaje: str):
        """📬 Envía comentarios o sugerencias directamente al desarrollador."""
        from services.feedback_service import FeedbackService
        server_lang = "en"
        if ctx.guild:
            server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)

        sent = await FeedbackService.send_feedback(
            bot=self.bot,
            author=ctx.author,
            content=mensaje,
            guild=ctx.guild,
            channel=ctx.channel
        )
        if sent:
            await ctx.send(t("feedback.success", server_lang))
        else:
            await ctx.send(t("feedback.error", server_lang))

    @commands.command()
    async def say(self, ctx, *, mensaje):
        """💬 Hace que Dalet repita tu mensaje."""
        await ctx.send(mensaje)

    @commands.command(name="lore")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def lore(self, ctx, *, busqueda: str):
        """📜 Investiga el pasado del servidor sobre un tema específico."""
        try:
            async with ctx.typing():
                # 1. Buscar en SQLite
                resultados = await self.repo.search_lore(busqueda, ctx.channel.id, limit=25)

                if not resultados:
                    await ctx.send(
                        f"Ni idea de qué es '{busqueda}'. Ese lore te lo has inventado tú "
                        f"o es demasiado aburrido para que lo guarde."
                    )
                    return

                # 2. Formatear — SQLite devuelve timestamps como string, no datetime
                lineas = []
                for r in resultados:
                    ts = r['Timestamp'] if isinstance(r, dict) else r[2]
                    # El timestamp puede venir como string "2025-01-15 12:30:00" o similar
                    if hasattr(ts, 'strftime'):
                        fecha = ts.strftime('%d/%m/%Y')
                    else:
                        # Es string de SQLite — cortamos los primeros 10 chars (YYYY-MM-DD)
                        fecha = str(ts)[:10] if ts else "??/??/????"
                    username = r['UserName'] if isinstance(r, dict) else r[0]
                    content = r['Content'] if isinstance(r, dict) else r[1]
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
                    prompt_especial, "", ctx.author.display_name
                )

                if respuesta:
                    await ctx.send(respuesta)
                else:
                    await ctx.send("Me dio pereza terminar de leer los archivos. Pregúntame otra vez.")

        except Exception as e:
            logger.error(f"Error en lore: {e}")
            await ctx.send("Se me han empolvado los archivos y no puedo leer nada ahora mismo.")

    @commands.command(name="info", aliases=["about", "botinfo"])
    async def show_info(self, ctx):
        """Muestra la tarjeta de presentación de Dalet."""
        server_lang = "en"
        if ctx.guild:
            server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)

        tagline = t("info.tagline", server_lang)
        lbl_creator = t("info.creator", server_lang)
        lbl_status = t("info.status", server_lang)
        status_desc = t("info.status_desc", server_lang)
        lbl_prefix = t("info.prefix", server_lang)
        prefix_desc = t("info.prefix_desc", server_lang)
        hint_changelog = t("info.changelog_hint", server_lang)
        hint_help = t("info.help_hint", server_lang)

        embed = discord.Embed(
            title=f"{DaletAtoms.EMOJI_DALET} " + t("info.title", server_lang, version=DaletAtoms.VERSION),
            description=(
                f"{tagline}\n\n"
                f"{DaletAtoms.GLYPH_POINTER} **{lbl_creator}**: Litxe\n"
                f"{DaletAtoms.GLYPH_POINTER} **{lbl_status}**: {status_desc}\n"
                f"{DaletAtoms.GLYPH_POINTER} **{lbl_prefix}**: {prefix_desc}\n\n"
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
        """Muestra las notas de actualización y novedades de Dalet."""
        server_lang = "en"
        if ctx.guild:
            server_lang = await self.bot.admin_repo.get_server_language(ctx.guild.id)

        custom = getattr(self.bot, "custom_changelog", None)

        embed = discord.Embed(
            title=f"{DaletAtoms.EMOJI_DALET} " + t("changelog.title", server_lang, version=DaletAtoms.VERSION),
            color=DaletAtoms.COLOR_PRIMARY
        )

        if custom:
            embed.description = f'> *"{custom}"*\n'

        embed.add_field(
            name=f"{DaletAtoms.GLYPH_POINTER} " + t("changelog.brain_title", server_lang),
            value=t("changelog.brain_desc", server_lang),
            inline=False
        )

        embed.add_field(
            name=f"{DaletAtoms.GLYPH_POINTER} " + t("changelog.skills_title", server_lang),
            value=t("changelog.skills_desc", server_lang),
            inline=False
        )

        embed.add_field(
            name=f"{DaletAtoms.GLYPH_POINTER} " + t("changelog.i18n_title", server_lang),
            value=t("changelog.i18n_desc", server_lang),
            inline=False
        )

        if self.bot.user and self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        footer_hint = "d.help for commands" if server_lang == "en" else "d.help para comandos"
        DaletMolecules.add_standard_footer(embed, context_text=f"{DaletAtoms.VERSION} │ {footer_hint}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CommandsHandler(bot))
