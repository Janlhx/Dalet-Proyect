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
        elif isinstance(error, commands.NotOwner) or isinstance(error, commands.MissingPermissions):
             await ctx.send("No tienes permiso para usar ese comando.")
        else:
            # Errores más serios se imprimen en la consola
            print(f"!!!!!! [EventsHandler] Error inesperado en on_command_error: {error}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """
        Se ejecuta cuando el bot entra a un servidor nuevo.
        
        Envía un mensaje de bienvenida dinámico con instrucciones iniciales.
        """
        # Buscar el mejor canal para enviar el mensaje (system_channel o el primero con permisos)
        target_channel = guild.system_channel
        if not target_channel or not target_channel.permissions_for(guild.me).send_messages:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    target_channel = channel
                    break
        
        if not target_channel:
            return

        embed = discord.Embed(
            title="✨ ¡Hola! Soy Dalet ✨",
            description=(
                "Gracias por invitarme a **" + guild.name + "**. "
                "Soy una inteligencia artificial conversacional con memoria persistente e integración con osu!."
            ),
            color=discord.Color.from_rgb(138, 43, 226) # Púrpura elegante
        )
        
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        
        embed.add_field(
            name="🔒 Estado Inicial",
            value="Por seguridad, entro a los servidores con los comandos bloqueados. Usa `d.unlock` para activarme.",
            inline=False
        )
        
        embed.add_field(
            name="🤖 IA Conversacional",
            value="Puedo charlar contigo de forma natural. Solo mencióname o actívame en un canal con `d.proactive add #canal`.",
            inline=True
        )
        
        embed.add_field(
            name="🎮 osu! Integration",
            value="Usa `d.link [usuario]` para conectar tu cuenta y ver tus stats con `d.osu`.",
            inline=True
        )
        
        embed.add_field(
            name="❓ Ayuda",
            value="Escribe `d.help` para ver mi lista completa de comandos organizada por categorías.",
            inline=False
        )
        
        embed.set_footer(text="Desarrollado con ❤️ por Litxe")
        
        try:
            await target_channel.send(embed=embed)
        except Exception as e:
            print(f"Error enviando mensaje de bienvenida en {guild.name}: {e}")

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
            
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """
        Se ejecuta cuando un miembro sale del servidor.
        
        Envía un mensaje de despedida a un canal predefinido.
        """
        # ID del canal de despedida
        channel_id = 790645132121604126
        channel = member.guild.get_channel(channel_id)

        if channel:
            await channel.send(f"hola no {member.name}")
            
async def setup(bot):
    """Función 'setup' para cargar el Cog."""
    await bot.add_cog(EventsHandler(bot))