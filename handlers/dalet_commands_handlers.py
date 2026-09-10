import discord
from discord.ext import commands
import logging
from discord.utils import format_dt

logger = logging.getLogger("dalet.handlers.general")

from ui.organisms import DaletOrganisms
from ui.atoms import DaletAtoms
from ui.molecules import DaletMolecules


class CommandsHandler(commands.Cog, name="Comandos Generales"):
    """Comandos básicos de Dalet (utilidades, info y herramientas generales)."""

    def __init__(self, bot):
        self.bot = bot
        self.repo = bot.user_repo

    @commands.command()
    async def ms(self, ctx):
        """🏓 Muestra la latencia del bot en milisegundos."""
        latency = round(self.bot.latency * 1000)
        embed = DaletOrganisms.create_simple_embed(
            f"{DaletAtoms.EMOJI_SUCCESS} Latencia",
            f"Mi respuesta está tardando unos {DaletAtoms.code(f'{latency}ms')}. No me presiones."
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def stats(self, ctx, member: discord.Member = None):
        """📊 Muestra tus estadísticas sociales o las de otro usuario."""
        member = member or ctx.author
        try:
            async with ctx.typing():
                stats = await self.repo.get_user_social_stats(member.id)
            avatar = member.avatar.url if member.avatar else None
            embed = DaletOrganisms.create_user_stats_card(member.display_name, stats, avatar)
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error en stats: {e}")
            await ctx.send("No pude calcular tus vicios sociales hoy.")

    @commands.command()
    async def userinfo(self, ctx, member: discord.Member = None):
        """Muestra información detallada de un usuario del servidor."""
        member = member or ctx.author
        desc = (
            f"• {DaletAtoms.bold('ID')}: {DaletAtoms.code(member.id)}\n"
            f"• {DaletAtoms.bold('Cuenta creada')}: {format_dt(member.created_at, 'D')}\n"
            f"• {DaletAtoms.bold('Se unió al grupo')}: {format_dt(member.joined_at, 'D')}\n"
        )
        embed = DaletOrganisms.create_simple_embed(f"Expediente: {member.display_name}", desc)
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        await ctx.send(embed=embed)

    @commands.command()
    async def serverinfo(self, ctx):
        """Muestra información detallada del servidor actual."""
        g = ctx.guild
        desc = (
            f"• {DaletAtoms.bold('Miembros')}: {DaletAtoms.code(g.member_count)}\n"
            f"• {DaletAtoms.bold('Propietario')}: {g.owner.mention}\n"
            f"• {DaletAtoms.bold('Fundación')}: {format_dt(g.created_at, 'D')}\n"
        )
        embed = DaletOrganisms.create_simple_embed(f"Territorio: {g.name}", desc)
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        await ctx.send(embed=embed)

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
        embed = discord.Embed(
            title=f"{DaletAtoms.EMOJI_DALET} Dalet {DaletAtoms.VERSION}",
            description=(
                f'> *"searching who asked"*\n\n'
                f"{DaletAtoms.GLYPH_POINTER} **Creador**: Litxe\n"
                f"{DaletAtoms.GLYPH_POINTER} **Estado**: En línea y juzgando tus jugadas\n"
                f"{DaletAtoms.GLYPH_POINTER} **Prefijo**: `d.` o mención `@Dalet`\n\n"
                f"{DaletAtoms.GLYPH_SUB} Escribe `d.changelog` para ver las novedades de la versión.\n"
                f"{DaletAtoms.GLYPH_SUB} Escribe `d.help` para consultar el menú de comandos."
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
        custom = getattr(self.bot, "custom_changelog", None)

        embed = discord.Embed(
            title=f"{DaletAtoms.EMOJI_DALET} Novedades — Dalet {DaletAtoms.VERSION}",
            color=DaletAtoms.COLOR_PRIMARY
        )

        if custom:
            embed.description = f'> *"{custom}"*\n'

        embed.add_field(
            name=f"{DaletAtoms.GLYPH_POINTER} Cerebro v3.0",
            value=(
                f"{DaletAtoms.GLYPH_SUB} Mayor agilidad conversacional y fluidez de memoria.\n"
                f"{DaletAtoms.GLYPH_SUB} Personalidad ácida calibrada para respuestas directas y contundentes."
            ),
            inline=False
        )

        embed.add_field(
            name=f"{DaletAtoms.GLYPH_POINTER} Desglose de Habilidades (`d.skills`)",
            value=(
                f"{DaletAtoms.GLYPH_SUB} Evaluación visual en 5 áreas (Aim, Speed, Accuracy, Stamina, Reading).\n"
                f"{DaletAtoms.GLYPH_SUB} Calibración de dificultad real en mods (DT, HR, EZ, FL) y veredicto mordaz."
            ),
            inline=False
        )

        embed.add_field(
            name=f"{DaletAtoms.GLYPH_POINTER} Rendimiento y Ajustes",
            value=(
                f"{DaletAtoms.GLYPH_SUB} Optimización de tiempos de respuesta en todos los servidores.\n"
                f"{DaletAtoms.GLYPH_SUB} Retiro del viejo comando `osuanalyzer` (ahora integrado en `d.skills`)."
            ),
            inline=False
        )

        if self.bot.user and self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        DaletMolecules.add_standard_footer(embed, context_text=f"{DaletAtoms.VERSION} │ d.help para comandos")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CommandsHandler(bot))
