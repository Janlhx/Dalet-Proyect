"""
Handler (Cog) para Comandos de Administración.

Contiene comandos restringidos al dueño del bot (IS_OWNER)
para gestionar el estado del bot y depurar la base de datos.
"""
import discord
import os
import sys
from discord.ext import commands
import db_connector # Importado para el comando SQL
import traceback # Para mostrar errores de recarga

class AdminCommands(commands.Cog, name="Comandos para el Administrador del bot"):
    """Comandos para el Administrador del bot"""
    def __init__(self, bot):
        self.bot = bot

    # --- Comandos de Gestión del Bot ---

    @commands.command()
    @commands.is_owner()
    async def restart(self, ctx):
        """
        [ADMIN] Reinicia el bot (solo para el dueño).
        
        Uso: d.restart
        
        Cierra la conexión del bot. El servicio de hosting (Render)
        detectará la caída y reiniciará el servicio automáticamente.
        """
        await ctx.send("Cerrando conexión... Render debería reiniciarme.")
        await self.bot.close()

    @commands.command(name="reload")
    @commands.is_owner()
    async def reload_cog(self, ctx, *, cog_name: str):
        """
        [ADMIN] Recarga un módulo/handler (Cog).
        
        Uso: d.reload handlers.dalet_osucommands
        
        Actualiza el código de un handler sin reiniciar el bot.
        Ideal para desarrollo y corrección de bugs en caliente.
        """
        try:
            # Los cogs en subcarpetas se llaman 'handlers.nombrearchivo'
            await self.bot.reload_extension(cog_name)
            await ctx.send(f"✅ Módulo `{cog_name}` recargado exitosamente.")
        except Exception as e:
            await ctx.send(f"❌ Error al recargar `{cog_name}`:\n```\n{traceback.format_exc()}\n```")

    # --- Comandos de Base de Datos y Utilidad ---

    @commands.command(name="sql")
    @commands.is_owner()
    async def run_sql_select(self, ctx, *, query: str):
        """
        [ADMIN] Ejecuta una consulta SELECT en la BD.
        
        Uso: d.sql SELECT * FROM v_osurankingglobal LIMIT 3
        
        Permite depurar y consultar la base de datos de Neon
        directamente desde Discord. ¡Solo para consultas SELECT!
        """
        if not query.lower().strip().startswith("select"):
            return await ctx.send("❌ Este comando solo permite consultas `SELECT`.")

        try:
            results = db_connector.fetch_all(query)
            
            if not results:
                return await ctx.send("✅ Consulta ejecutada, no se devolvieron resultados.")

            # Formatear la respuesta
            response = ""
            for i, row in enumerate(results):
                response += f"Fila {i+1}: {row}\n"
                if len(response) > 1800:
                    response += "\n... (resultados truncados)"
                    break
            
            await ctx.send(f"Resultados de la consulta:\n```\n{response}\n```")

        except Exception as e:
            await ctx.send(f"❌ Error al ejecutar la consulta SQL:\n```\n{e}\n```")

    @commands.command(name="dm")
    @commands.is_owner()
    async def send_dm(self, ctx, user_id: int, *, message: str):
        """[ADMIN] Envía un DM a un usuario por su ID."""
        try:
            user = await self.bot.fetch_user(user_id)
            if not user:
                return await ctx.send("❌ Usuario no encontrado.")
                
            await user.send(f"Un mensaje del administrador del bot:\n\n{message}")
            await ctx.send(f"✅ Mensaje enviado a **{user.name}**.")
            
        except discord.Forbidden:
            await ctx.send("❌ No se pudo enviar el DM. Es probable que el usuario tenga los DMs cerrados.")
        except Exception as e:
            await ctx.send(f"❌ Error al enviar DM: {e}")

async def setup(bot):
    """Función 'setup' para cargar el Cog."""
    await bot.add_cog(AdminCommands(bot))