"""
Handler (Cog) para el Registro de Mensajes.

Este Cog tiene una responsabilidad principal: escuchar todos los mensajes
en los canales donde el bot está presente y guardarlos en la base de datos
usando el procedimiento 'sp_LogMessage'.

También incluye un comando de administrador ('d.chatlog') para depurar
y ver los últimos mensajes guardados desde la base de datos.
"""
import discord
from discord.ext import commands
from datetime import datetime
import db_connector
import traceback

class ChatLogger(commands.Cog, name="Memoria Global"):
    """Maneja el registro de todos los mensajes en la base de datos."""
    def __init__(self, bot):
        self.bot = bot
        # (Opcional) Se podría añadir un filtro de canales aquí si fuera necesario
        # self.allowed_channels = [] 

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Listener que se activa con cada mensaje.

        Guarda el contenido del mensaje en la tabla 'Messages' de la BD.
        Ignora los mensajes de otros bots y los comandos del propio bot.
        """
        # Ignorar bots y mensajes privados (DM)
        if message.author.bot or not message.guild:
            return
        
        # Ignorar mensajes que son comandos para este bot
        if message.content.lower().startswith(("d.", "D.")):
            return

        try:
            # Llama al SP que también registra al usuario, servidor y canal si no existen
            db_connector.execute_procedure(
                    "sp_LogMessage",
                    (
                        message.author.id,
                        str(message.author),
                        message.guild.id,
                        str(message.guild.name),
                        message.channel.id,
                        str(message.channel.name),
                        message.content.strip()
                    )
                )
        except Exception as e:
            print(f"!!!!!! [ChatLogger] Error al guardar mensaje en la BD: {e}")
            traceback.print_exc()

    @commands.command(name="chatlog")
    @commands.is_owner()
    async def chatlog(self, ctx, cantidad: int = 10):
        """
        [ADMIN] Muestra los últimos mensajes guardados desde la BD.
        
        Utiliza la vista 'V_ChannelMessages' para obtener los mensajes
        formateados del canal actual.
        """
        try:
            # Usamos la VISTA (Req 4) para obtener los mensajes con el nombre de usuario
            query = """
                SELECT UserName, Content
                FROM V_ChannelMessages
                WHERE ChannelID = %s
                ORDER BY Timestamp DESC
                LIMIT %s
            """
            registros = db_connector.fetch_all(query, (ctx.channel.id, cantidad))
            
            if not registros:
                return await ctx.send("No hay mensajes registrados en este canal.")

            # Invertimos para mostrar en orden cronológico
            registros.reverse()
            texto = "\n".join([f"**{autor}**: {contenido}" for autor, contenido in registros])
            
            if len(texto) > 1900:
                texto = texto[:1900] + "..."

            embed = discord.Embed(
                title=f"📜 Últimos {len(registros)} Mensajes en #{ctx.channel.name}",
                description=texto,
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send("❌ Error al consultar los logs de la base de datos.")
            print(f"!!!!!! [ChatLogger] Error en el comando chatlog: {e}")
            traceback.print_exc()

async def setup(bot):
    """Función 'setup' para cargar el Cog."""
    await bot.add_cog(ChatLogger(bot))