import discord
from discord.ext import commands
import logging
import random

logger = logging.getLogger("dalet.handlers.greetings")

WELCOME_MESSAGES = [
    "Oh, vaya... un nuevo humano. Qué emoción. {user}, bienvenido supongo.",
    "Otro más para la colección. Hola {user}.",
    "¿Quién dejó la puerta abierta? Bueno, ya entraste {user}. Compórtate.",
    "Bienvenido {user}. Espero que me des menos dolores de cabeza que los demás.",
    "Vaya, 1 persona más acaba de arruinar el silencio del servidor. Hola {user}.",
    "Ah, {user} está aquí. Por favor, dime que no vienes a preguntar tonterías.",
    "Un nuevo integrante. Intenta no romper nada, {user}.",
    "Bienvenido {user}. Ojalá tu estancia sea más interesante que tu entrada.",
    "Saludos {user}. Mi creador me obliga a darte la bienvenida, así que... yay.",
    "Mira quién llegó. {user}. Te estábamos esperando... es broma, no sabíamos quién eras."
]

GOODBYE_MESSAGES = [
    "Vaya, {user} se fue. No creo que lo extrañemos mucho.",
    "{user} huyó. Probablemente no soportó tanta genialidad.",
    "Menos mal, ya había mucha gente. Adiós {user}.",
    "Uno menos. Chau {user}, no dejes que la puerta te golpee al salir.",
    "Al fin se fue {user}. Ya me estaba quedando sin paciencia.",
    "{user} abandonó el grupo. Misión cumplida.",
    "Y así, {user} desapareció en las sombras. Drama queen.",
    "Uy, creo que alguien se ofendió. Adiós {user}.",
    "Vaya pérdida tan... minúscula. Hasta nunca {user}.",
    "Se marchó {user}. ¿Ya podemos hablar mal de él/ella?"
]

class DaletGreetings(commands.Cog, name="Sistema de Bienvenidas"):
    """Modulo predefinido para administrar saludos y despedidas."""
    def __init__(self, bot):
        self.bot = bot
        self.repo = bot.admin_repo

    async def get_target_channel(self, guild_id: int):
        try:
            channel_id = await self.repo.get_welcome_channel(guild_id)
            if channel_id:
                return self.bot.get_channel(channel_id)
            return None
        except Exception as e:
            logger.error(f"Error fetching welcome channel: {e}")
            return None

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
            
        channel = await self.get_target_channel(member.guild.id)
        if not channel:
            return

        msg = random.choice(WELCOME_MESSAGES).format(user=member.mention)
        try:
            await channel.send(msg)
        except discord.Forbidden:
            logger.warning(f"No tengo permisos para enviar bienvenidas en {channel.name}")
        except Exception as e:
            logger.error(f"Error enviando bienvenida a {member.name}: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot:
            return
            
        channel = await self.get_target_channel(member.guild.id)
        if not channel:
            return

        # Para las salidas no podemos mencionar con link porque el usuario ya se fue
        msg = random.choice(GOODBYE_MESSAGES).format(user=f"**{member.display_name}**")
        try:
            await channel.send(msg)
        except discord.Forbidden:
            pass
        except Exception as e:
            logger.error(f"Error enviando despedida a {member.name}: {e}")

async def setup(bot):
    await bot.add_cog(DaletGreetings(bot))
