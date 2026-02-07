import discord
import os
import sys
from discord.ext import commands
import logging
import traceback

logger = logging.getLogger("dalet.handlers.admin")

class AdminCommands(commands.Cog, name="Comandos para el Administrador del bot"):
    """Comandos para administrar el bot y depurar la base de datos."""
    def __init__(self, bot):
        self.bot = bot
        self.repo = bot.user_repo

    # --- Comandos de Gestión del Bot ---

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def restart(self, ctx):
        """[ADMIN] Reinicia el bot (solo para administradores)."""
        await ctx.send("Cerrando conexión... Render debería reiniciarme.")
        await self.bot.close()

    @commands.command(name="reload")
    @commands.has_permissions(administrator=True)
    async def reload_cog(self, ctx, *, cog_name: str):
        """[ADMIN] Recarga un módulo/handler (Cog)."""
        try:
            await self.bot.reload_extension(cog_name)
            await ctx.send(f"✅ Módulo `{cog_name}` recargado exitosamente.")
        except Exception as e:
            logger.error(f"Error reloading {cog_name}: {e}")
            await ctx.send(f"❌ Error al recargar `{cog_name}`:\n```\n{traceback.format_exc()}\n```")

    # --- Comandos de Base de Datos y Utilidad ---

    @commands.command(name="sql")
    @commands.has_permissions(administrator=True)
    async def run_sql_select(self, ctx, *, query: str):
        """[ADMIN] Ejecuta una consulta SELECT en la BD."""
        if not query.lower().strip().startswith("select"):
            return await ctx.send("❌ Este comando solo permite consultas `SELECT`.")

        try:
            # Usando el repositorio base para consultas directas
            results = await self.repo.fetch_all(query)
            
            if not results:
                return await ctx.send("✅ Consulta ejecutada, no se devolvieron resultados.")

            # Formatear la respuesta
            response = ""
            for i, row in enumerate(results):
                response += f"Fila {i+1}: {dict(row)}\n"
                if len(response) > 1800:
                    response += "\n... (resultados truncados)"
                    break
            
            await ctx.send(f"Resultados de la consulta:\n```\n{response}\n```")

        except Exception as e:
            logger.error(f"SQL command error: {e}")
            await ctx.send(f"❌ Error al ejecutar la consulta SQL:\n```\n{e}\n```")

    @commands.command(name="dm")
    @commands.has_permissions(administrator=True)
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
            logger.error(f"DM command error: {e}")
            await ctx.send(f"❌ Error al enviar DM.")

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
