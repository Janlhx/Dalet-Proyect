import discord
from discord.ext import commands
import logging
from discord.utils import format_dt

logger = logging.getLogger("dalet.handlers.general")

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
        await ctx.send(embed=discord.Embed(
            title="🏓 Ping",
            description=f"`{latency}ms`",
            color=discord.Color.green()
        ))

    @commands.command()
    async def userinfo(self, ctx, member: discord.Member = None):
        """👤 Muestra información detallada de un usuario del servidor."""
        member = member or ctx.author
        embed = discord.Embed(
            title=f"👤 {member}",
            color=discord.Color.random()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else "")
        embed.add_field(name="ID", value=member.id)
        embed.add_field(name="Creado", value=member.created_at.strftime("%d/%m/%Y"))
        embed.add_field(name="Unido", value=member.joined_at.strftime("%d/%m/%Y"))
        await ctx.send(embed=embed)

    @commands.command()
    async def serverinfo(self, ctx):
        """🌐 Muestra información detallada del servidor actual."""
        g = ctx.guild
        embed = discord.Embed(
            title=f"🌐 {g.name}",
            color=discord.Color.random()
        )
        embed.set_thumbnail(url=g.icon.url if g.icon else "")
        embed.add_field(name="Miembros", value=g.member_count)
        embed.add_field(name="Dueño", value=g.owner.mention)
        embed.add_field(name="Creado", value=g.created_at.strftime("%d/%m/%Y"))
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

