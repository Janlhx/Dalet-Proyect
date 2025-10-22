import discord
from discord.ext import commands
# Quitamos imports innecesarios: genai, json, MemoryManager, random, asyncio
import os

# --- Importamos nuestro conector de base de datos ---
from handlers import db_connector

# --- 🗑️ SECCIÓN ELIMINADA 🗑️ ---
# Ya no necesitamos variables de archivos JSON ni funciones auxiliares para ellos
# --- FIN DE LA SECCIÓN ELIMINADA ---


# Cambiamos el nombre de la clase para reflejar su nuevo propósito
class AIConfigCommands(commands.Cog, name="Configuración de IA"):
    """Comandos para configurar cómo y dónde Dalet interactúa automáticamente."""

    def __init__(self, bot):
        self.bot = bot
        # Ya no necesitamos inicializar memoria, modelo ni instrucciones aquí

    # --- 🗑️ SECCIÓN ELIMINADA 🗑️ ---
    # Eliminado _validate_role_ids
    # Eliminado ask_gemini
    # Eliminado el grupo de comandos whitelist (add, remove, list, clear)
    # Eliminado el comando limpiar_memoria (ya que la memoria de usuario se gestiona en MemoryManager)
    # --- FIN DE LA SECCIÓN ELIMINADA ---


    # ----------------------------------------------------------------------
    # 💬 Gestión de canales con IA activa (PROACTIVE - Sin cambios en funcionalidad)
    # ----------------------------------------------------------------------
    @commands.group(name="proactive", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def proactive(self, ctx):
        """Configura en qué canales Dalet puede participar automáticamente."""
        await ctx.send("Usa `d.proactive add/remove/list/clear`.")

    @proactive.command(name="add")
    @commands.has_permissions(administrator=True)
    async def proactive_add(self, ctx, *channels: discord.TextChannel):
        """Añade canales a la lista de IA activa. Puedes mencionar varios."""
        if not channels: return await ctx.send("Menciona al menos un canal.")

        added = []
        try:
            for ch in channels:
                db_connector.execute_procedure(
                    "sp_SetChannelProactive",
                    (ch.id, ch.name, ctx.guild.id, ctx.guild.name, True)
                )
                added.append(ch)

            if added:
                await ctx.send(f"✅ Canales añadidos al modo proactivo: {', '.join([ch.mention for ch in added])}")
            else:
                await ctx.send("No se añadieron canales (quizás ya estaban).") # Mensaje más claro
        except Exception as e:
            await ctx.send(f"❌ Error al añadir canales: {e}")

    @proactive.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def proactive_remove(self, ctx, *channels: discord.TextChannel):
        """Quita canales de la lista de IA activa. Puedes mencionar varios."""
        if not channels: return await ctx.send("Menciona al menos un canal.")

        removed = []
        try:
            for ch in channels:
                db_connector.execute_procedure(
                    "sp_SetChannelProactive",
                    (ch.id, ch.name, ctx.guild.id, ctx.guild.name, False)
                )
                removed.append(ch)

            if removed:
                await ctx.send(f"🗑️ Canales quitados del modo proactivo: {', '.join([ch.mention for ch in removed])}")
            else:
                await ctx.send("No se quitaron canales (quizás no estaban).") # Mensaje más claro
        except Exception as e:
            await ctx.send(f"❌ Error al quitar canales: {e}")

    @proactive.command(name="list")
    async def proactive_list(self, ctx):
        """Muestra los canales donde la IA está activa."""
        try:
            query = "SELECT fn_GetProactiveChannels(%s)"
            result = db_connector.fetch_one(query, (ctx.guild.id,))

            channel_ids = result[0] if result and result[0] else []

            if channel_ids:
                await ctx.send(f"📜 Canales con IA proactiva: {', '.join([f'<#{c}>' for c in channel_ids])}")
            else:
                await ctx.send("No hay canales configurados para el modo proactivo.")
        except Exception as e:
            await ctx.send(f"❌ Error al listar canales: {e}")

    @proactive.command(name="clear")
    @commands.has_permissions(administrator=True)
    async def proactive_clear(self, ctx):
        """Desactiva el modo proactivo en todos los canales de este servidor."""
        try:
            db_connector.execute_procedure("sp_ClearProactiveChannels", (ctx.guild.id,))
            await ctx.send("💥 Modo proactivo desactivado en todos los canales.")
        except Exception as e:
            await ctx.send(f"❌ Error al limpiar la lista: {e}")


   # ----------------------------------------------------------------------
   # 💡 Gestión de Modo Reactivo (REACTIVE - Sin cambios en funcionalidad)
   # ----------------------------------------------------------------------
    @commands.group(name="reactive", invoke_without_command=True, brief="Activa/desactiva la respuesta a su nombre ('dalet').")
    @commands.has_permissions(administrator=True)
    async def reactive(self, ctx):
        """Activa o desactiva la capacidad de Dalet para responder a su nombre."""
        await ctx.send_help(ctx.command)

    @reactive.command(name="on")
    @commands.has_permissions(administrator=True)
    async def reactive_on(self, ctx):
        """Activa la respuesta de Dalet a su nombre."""
        try:
            db_connector.execute_procedure(
                "sp_SetServerReactive",
                (ctx.guild.id, ctx.guild.name, True)
            )
            await ctx.send("✅ **Modo Reactivo Activado.** Dalet ahora responderá cuando la llamen.")
        except Exception as e:
            await ctx.send(f"❌ Error al activar el modo reactivo: {e}")

    @reactive.command(name="off")
    @commands.has_permissions(administrator=True)
    async def reactive_off(self, ctx):
        """Desactiva la respuesta de Dalet a su nombre."""
        try:
            db_connector.execute_procedure(
                "sp_SetServerReactive",
                (ctx.guild.id, ctx.guild.name, False)
            )
            await ctx.send("🛑 **Modo Reactivo Desactivado.**")
        except Exception as e:
            await ctx.send(f"❌ Error al desactivar el modo reactivo: {e}")

    @reactive.command(name="status")
    async def reactive_status(self, ctx):
        """Muestra si el modo reactivo está activado o desactivado."""
        try:
            query = "SELECT fn_IsServerReactive(%s)"
            result = db_connector.fetch_one(query, (ctx.guild.id,))

            is_on = result[0] if result and result[0] is not None else True # Por defecto es True

            if is_on:
                await ctx.send("🟢 El modo reactivo está **Activado**.")
            else:
                await ctx.send("🔴 El modo reactivo está **Desactivado**.")
        except Exception as e:
            await ctx.send(f"❌ Error al consultar el estado: {e}")


async def setup(bot):
    # Asegúrate de usar el nuevo nombre de la clase
    await bot.add_cog(AIConfigCommands(bot))