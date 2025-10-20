import discord
from discord.ext import commands
from datetime import datetime
# --- Import corregido (solo queda una línea y apunta al lugar correcto) ---
from handlers import db_connector

class ChatLogger(commands.Cog, name="Memoria Global"):
    def __init__(self, bot):
        self.bot = bot
        self.allowed_channels = []

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if self.allowed_channels and message.channel.id not in self.allowed_channels:
            return
        
        try:
            db_connector.execute_procedure(
                "sp_LogMessage",
                (
                    message.author.id,
                    str(message.author),
                    message.channel.id,
                    message.content.strip()
                )
            )
        except Exception as e:
            print(f"Error en ChatLogger al guardar mensaje en la BD: {e}")

    @commands.command(name="chatlog")
    @commands.is_owner()
    async def chatlog(self, ctx, cantidad: int = 10):
        """[ADMIN] Muestra los últimos mensajes guardados desde la BD."""
        try:
            query = """
                SELECT u.UserName, m.Content
                FROM Messages m
                JOIN Users u ON m.UserID = u.UserID
                ORDER BY m.Timestamp DESC
                LIMIT %s
            """
            registros = db_connector.fetch_all(query, (cantidad,))
            
            if not registros:
                return await ctx.send("No hay mensajes registrados en la base de datos.")

            registros.reverse()
            texto = "\n".join([f"**{autor}**: {contenido}" for autor, contenido in registros])
            
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