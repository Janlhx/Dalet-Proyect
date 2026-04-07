"""
Handler de Eventos Globales de Discord.
Maneja: on_ready, on_command_error, on_guild_join, on_member_join, on_member_remove.
"""
from discord.ext import commands
import discord
import random
import logging
import traceback

logger = logging.getLogger("dalet.handlers.events")

# Mensajes de bienvenida con personalidad de Dalet
WELCOME_MESSAGES = [
    "ey, {mention} apareció por aquí. bienvenido al caos",
    "llegó {mention}. espero que traiga buen rollo",
    "miren quién se unió: {mention}. que no se pierda",
    "oh, {mention} decidió aparecer. qué sorpresa",
    "{mention} acaba de llegar. uno más para la colección",
    "bienvenido {mention}, intenta no armar lío desde el primer día",
]

# Mensajes de salida con personalidad de Dalet
LEAVE_MESSAGES = [
    "{name} se fue. menos mal que aún quedamos los buenos",
    "adios {name}, fue un gusto (o no tanto)",
    "{name} decidió irse. la vida sigue",
    "se fue {name}. el servidor seguirá sin dormir por eso",
    "chao {name}, que te vaya bien por ahí",
]


class EventsHandler(commands.Cog):
    """Agrupa los listeners de eventos globales del bot."""

    def __init__(self, bot):
        self.bot = bot

    # -------------------------------------------------------------------------
    # on_ready
    # -------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_ready(self):
        """Se ejecuta cuando el bot está listo y conectado."""
        await self.bot.tree.sync()
        logger.info(f"Bot conectado como {self.bot.user} (ID: {self.bot.user.id})")

    # -------------------------------------------------------------------------
    # on_command_error
    # -------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Manejo global de errores de comandos."""
        if isinstance(error, commands.CommandNotFound):
            # No responder a prefijos de otros bots
            if ctx.message.content.startswith(("!", "/", ".")):
                return
            await ctx.send("ese comando no lo tengo")

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"te faltan argumentos. revisa con `d.help {ctx.command.name}`"
            )

        elif isinstance(error, (commands.NotOwner, commands.MissingPermissions)):
            await ctx.send("no tienes permisos para hacer eso")

        elif isinstance(error, commands.CommandInvokeError):
            original = getattr(error, "original", error)
            if isinstance(original, discord.HTTPException) and original.status == 429:
                logger.warning(
                    f"Rate limit 429 en comando '{ctx.command}'. Throttle activo."
                )
                return
            logger.error(f"Error en comando '{ctx.command}': {error}")
            traceback.print_exc()

        else:
            logger.error(f"Error inesperado en comando: {error}")
            traceback.print_exc()

    # -------------------------------------------------------------------------
    # on_guild_join
    # -------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Envía presentación cuando el bot entra a un servidor nuevo."""
        target_channel = guild.system_channel
        if not target_channel or not target_channel.permissions_for(guild.me).send_messages:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    target_channel = channel
                    break

        if not target_channel:
            return

        embed = discord.Embed(
            title="hola, soy Dalet",
            description=(
                f"gracias por agregarme a **{guild.name}**. "
                "soy una IA conversacional con memoria, integración con osu! "
                "y buen humor (la mayoría del tiempo)."
            ),
            color=discord.Color.from_rgb(138, 43, 226)
        )

        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)

        embed.add_field(
            name="cómo empezar",
            value=(
                "los comandos empiezan bloqueados por seguridad. "
                "usa `d.unlock` para activarme."
            ),
            inline=False
        )
        embed.add_field(
            name="IA conversacional",
            value="mencióneme o actívame en canales con `d.proactive add #canal`",
            inline=True
        )
        embed.add_field(
            name="osu!",
            value="vincula tu cuenta con `d.link [usuario]` → stats con `d.osu`",
            inline=True
        )
        embed.add_field(
            name="ayuda",
            value="`d.help` para ver todos los comandos",
            inline=False
        )
        embed.set_footer(text="hecha por Litxe")

        try:
            await target_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error enviando bienvenida en {guild.name}: {e}")

    # -------------------------------------------------------------------------
    # on_member_join
    # -------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Saluda a los nuevos miembros con personalidad de Dalet."""
        # Buscar el canal configurado en el servidor o el canal del sistema
        channel = None

        # Intentar canal del sistema primero
        if member.guild.system_channel:
            sys_ch = member.guild.system_channel
            if sys_ch.permissions_for(member.guild.me).send_messages:
                channel = sys_ch

        # Si no hay canal del sistema, buscar por nombre
        if not channel:
            for ch in member.guild.text_channels:
                if any(keyword in ch.name.lower() for keyword in ("bienvenida", "welcome", "general", "lobby")):
                    if ch.permissions_for(member.guild.me).send_messages:
                        channel = ch
                        break

        if not channel:
            return

        msg = random.choice(WELCOME_MESSAGES).format(
            mention=member.mention,
            name=member.display_name
        )

        try:
            await channel.send(msg)
        except Exception as e:
            logger.error(f"Error enviando bienvenida a {member.display_name}: {e}")

    # -------------------------------------------------------------------------
    # on_member_remove
    # -------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Despide a quien se va con el tono característico de Dalet."""
        channel = None

        if member.guild.system_channel:
            sys_ch = member.guild.system_channel
            if sys_ch.permissions_for(member.guild.me).send_messages:
                channel = sys_ch

        if not channel:
            for ch in member.guild.text_channels:
                if any(keyword in ch.name.lower() for keyword in ("bienvenida", "welcome", "general", "lobby")):
                    if ch.permissions_for(member.guild.me).send_messages:
                        channel = ch
                        break

        if not channel:
            return

        msg = random.choice(LEAVE_MESSAGES).format(name=member.display_name)

        try:
            await channel.send(msg)
        except Exception as e:
            logger.error(f"Error enviando despedida de {member.display_name}: {e}")


async def setup(bot):
    await bot.add_cog(EventsHandler(bot))