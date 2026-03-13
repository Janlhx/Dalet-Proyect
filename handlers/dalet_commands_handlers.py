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

    # --- 💬 UTILIDADES ---
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
        async with ctx.typing():
            try:
                stats = await self.repo.get_user_social_stats(member.id)
                avatar = member.avatar.url if member.avatar else None
                embed = DaletOrganisms.create_user_stats_card(member.display_name, stats, avatar)
                await ctx.send(embed=embed)
            except Exception as e:
                logger.error(f"Error en stats: {e}")
                await ctx.send("No pude calcular tus vicios sociales hoy.")

    @commands.command()
    async def userinfo(self, ctx, member: discord.Member = None):
        """👤 Muestra información detallada de un usuario del servidor."""
        member = member or ctx.author
        desc = (
            f"{DaletAtoms.EMOJI_INFO} {DaletAtoms.bold('ID')}: {DaletAtoms.code(member.id)}\n"
            f"📅 {DaletAtoms.bold('Cuenta creada')}: {format_dt(member.created_at, 'D')}\n"
            f"🤝 {DaletAtoms.bold('Se unió al grupo')}: {format_dt(member.joined_at, 'D')}\n"
        )
        embed = DaletOrganisms.create_simple_embed(f"Expediente: {member.display_name}", desc)
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        await ctx.send(embed=embed)

    @commands.command()
    async def serverinfo(self, ctx):
        """🌐 Muestra información detallada del servidor actual."""
        g = ctx.guild
        desc = (
            f"👥 {DaletAtoms.bold('Habitantes')}: {DaletAtoms.code(g.member_count)}\n"
            f"👑 {DaletAtoms.bold('Dueño del lugar')}: {g.owner.mention}\n"
            f"✨ {DaletAtoms.bold('Fundación')}: {format_dt(g.created_at, 'D')}\n"
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
        async with ctx.typing():
            try:
                # 1. Buscar en la DB
                resultados = await self.repo.search_lore(busqueda, ctx.channel.id, limit=25)
                
                if not resultados:
                    await ctx.send(f"Ni idea de qué es '{busqueda}'. Ese lore te lo has inventado tú o es demasiado aburrido para que lo guarde.")
                    return

                # 2. Formatear contexto para la IA
                contexto_lore = "\n".join([f"[{r['timestamp'].strftime('%d/%m/%Y')}] {r['username']}: {r['content']}" for r in resultados])
                
                # 3. Generar respuesta con personalidad
                prompt_especial = f"""
ESTÁS INVESTIGANDO EL "LORE" DEL SERVIDOR.
Fragmentos encontrados en la base de datos sobre "{busqueda}":
{contexto_lore}

INSTRUCCIONES DE RESPUESTA:
- Responde a la pregunta o comenta sobre el tema "{busqueda}" usando estos datos.
- Sé sarcástica, un poco cínica y directa.
- Si los mensajes son vergonzosos, búrlate de los usuarios implicados.
- No parezcas una enciclopedia, parece una persona cotilla que revisó los archivos.
"""
                respuesta = await self.bot.nlp_service.generate_reply(prompt_especial, "", ctx.author.display_name)
                
                if respuesta:
                    await ctx.send(respuesta)
                else:
                    await ctx.send("Me dio pereza terminar de leer los archivos. Pregúntame otra vez.")

            except Exception as e:
                logger.error(f"Error en comando lore: {e}")
                await ctx.send("Se me han empolvado los archivos y no puedo leer nada ahora mismo.")

async def setup(bot):
    await bot.add_cog(CommandsHandler(bot))

