"""
Handler (Cog) para Eventos Globales de Discord.

Este Cog maneja eventos del bot que no son comandos, como
'on_ready' (cuando el bot se conecta) o 'on_command_error'
(para manejo de errores global).
"""
from discord.ext import commands
import discord
import random
import traceback
class EventsHandler(commands.Cog):
    """Agrupa los listeners de eventos globales del bot."""
    def __init__(self, bot):
        self.bot = bot 
       
    @commands.Cog.listener()
    async def on_ready(self):
        """
        Se ejecuta una vez cuando el bot se conecta y está listo.
        
        Sincroniza los comandos de barra (/) y confirma la conexión.
        """
        await self.bot.tree.sync() 
        print(f"Bot conectado como {self.bot.user}")
        
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """
        Listener global para errores de comandos.
        
        Se activa si un comando falla o no se encuentra.
        """
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("No tengo esa Función")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Te faltan argumentos. Revisa el comando con `d.help {ctx.command.name}`")
        elif isinstance(error, commands.NotOwner):
             await ctx.send("No tienes permiso para usar ese comando.")
        else:
            # Errores más serios se imprimen en la consola
            print(f"!!!!!! [EventsHandler] Error inesperado en on_command_error: {error}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """
        Se ejecuta cuando un nuevo miembro entra al servidor.
        
        Envía un mensaje de bienvenida a un canal predefinido.
        """
        # ID del canal de bienvenida
        channel_id = 790644877389201439
        channel = member.guild.get_channel(channel_id)

        if channel:
            await channel.send(f"¡Bienvenido {member.mention} al servidor!")

async def setup(bot):
    """Función 'setup' para cargar el Cog."""
    await bot.add_cog(EventsHandler(bot))