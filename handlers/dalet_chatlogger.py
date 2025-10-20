import discord
from discord.ext import commands
from collections import deque
# Se eliminan 'json' y 'os' porque ya no se manejan archivos aquí
from datetime import datetime

# ------------------------------------------------------------------
# 🚀 ¡NUEVA INTEGRACIÓN CON LA BASE DE DATOS! 🚀
# Importamos nuestro conector.
from handlers.modules import db_connector
# ------------------------------------------------------------------


class ChatLogger(commands.Cog, name="Memoria Global"):
    def __init__(self, bot):
        self.bot = bot
        # --- 🗑️ SECCIÓN ELIMINADA 🗑️ ---
        # Ya no necesitamos cargar el archivo JSON en memoria.
        # self.LOG_FILE = "chat_history.json"
        # self.MAX_MESSAGES = 100
        # self.chat_log = deque(...)
        # --- FIN DE LA SECCIÓN ELIMINADA ---
        self.allowed_channels = []

    # ------------------------------------------------------------------
    # ✨ LISTENER "on_message" MODIFICADO ✨
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # La lógica para ignorar bots o canales no permitidos no cambia
        if message.author.bot:
            return
        if self.allowed_channels and message.channel.id not in self.allowed_channels:
            return
        
        try:
            # ¡Aquí está el cambio!
            # En lugar de crear un diccionario y guardarlo en un JSON,
            # llamamos directamente al procedimiento almacenado.
            db_connector.execute_procedure(
                "sp_LogMessage",
                (
                    message.author.id,
                    str(message.author), # Pasamos el nombre del autor
                    message.channel.id,
                    message.content.strip()
                )
            )
        except Exception as e:
            print(f"Error en ChatLogger al guardar mensaje en la BD: {e}")

    # ------------------------------------------------------------------
    # ✨ COMANDO "chatlog" MODIFICADO ✨
    # ------------------------------------------------------------------
    @commands.command(name="chatlog")
    @commands.is_owner()
    async def chatlog(self, ctx, cantidad: int = 10):
        """[ADMIN] Muestra los últimos mensajes guardados desde la BD.
        
        Uso: d.chatlog [cantidad]
        Ejemplo: d.chatlog 25
        
        Muestra los últimos mensajes que el bot ha registrado
        globalmente en la base de datos.
        """
        try:
            # Hacemos una consulta SELECT para obtener los últimos mensajes
            # Uniendo las tablas Messages y Users para obtener el nombre del autor
            query = """
                SELECT u.UserName, m.Content
                FROM Messages m
                JOIN Users u ON m.UserID = u.UserID
                ORDER BY m.Timestamp DESC
                LIMIT %s
            """
            # fetch_all devuelve una lista de tuplas, ej: [('Litxe', 'hola'), ('OtroUser', 'chau')]
            registros = db_connector.fetch_all(query, (cantidad,))
            
            if not registros:
                return await ctx.send("No hay mensajes registrados en la base de datos.")

            # Invertimos la lista para que los mensajes se muestren en orden cronológico
            registros.reverse()

            # Formateamos el texto para el mensaje de Discord
            texto = "\n".join([f"**{autor}**: {contenido}" for autor, contenido in registros])
            
            # Dividimos el mensaje si es muy largo para Discord
            if len(texto) > 1900:
                texto = texto[:1900] + "..."

            embed = discord.Embed(
                title=f"📜 Últimos {len(registros)} Mensajes Registrados",
                description=texto,
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send("❌ Error al consultar los logs de la base de datos.")
            print(f"Error en el comando chatlog: {e}")


async def setup(bot):
    await bot.add_cog(ChatLogger(bot))