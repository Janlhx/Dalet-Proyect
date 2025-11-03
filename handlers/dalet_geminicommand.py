"""
Handler (Cog) para Comandos de Configuración de la IA.

Este Cog permite a los administradores del servidor configurar
el comportamiento de la IA (Gemini) a través de comandos de Discord.

Estos comandos escriben en la base de datos (ej. 'sp_SetChannelProactive'),
y el listener 'dalet_nlpchat' lee estas configuraciones
(ej. 'fn_IsChannelProactive') para decidir si debe responder.
"""
import discord
from discord.ext import commands
import os
import db_connector # Importamos nuestro conector de base de datos
import traceback

class AIConfigCommands(commands.Cog, name="Configuración de IA"):
    """Comandos para configurar cómo y dónde Dalet interactúa automáticamente."""

    def __init__(self, bot):
        self.bot = bot

    # ----------------------------------------------------------------------
    # 💬 Gestión de canales con IA activa (PROACTIVE)
    # ----------------------------------------------------------------------
    @commands.group(name="proactive", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def proactive(self, ctx):
        """Configura en qué canales Dalet puede participar automáticamente."""
        await ctx.send("Usa `d.proactive add/remove/list/clear`.")

    @proactive.command(name="add")
    @commands.has_permissions(administrator=True)
    async def proactive_add(self, ctx, *channels: discord.TextChannel):
        """
        Añade canales a la lista de IA activa. Puedes mencionar varios.
        
        Llama al SP 'sp_SetChannelProactive' con 'True'.
        """
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
        except Exception as e:
            await ctx.send(f"❌ Error al añadir canales: {e}")
            print(f"!!!!!! [AIConfig] Error en proactive_add: {e}")

    @proactive.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def proactive_remove(self, ctx, *channels: discord.TextChannel):
        """
        Quita canales de la lista de IA activa. Puedes mencionar varios.
        
        Llama al SP 'sp_SetChannelProactive' con 'False'.
        """
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
        except Exception as e:
            await ctx.send(f"❌ Error al quitar canales: {e}")
            print(f"!!!!!! [AIConfig] Error en proactive_remove: {e}")

    @proactive.command(name="list")
    async def proactive_list(self, ctx):
        """
        Muestra los canales donde la IA está activa.
        
        Llama a la función 'fn_GetProactiveChannels'.
        """
        try:
            query = "SELECT * FROM fn_GetProactiveChannels(%s)"
            # fetch_one devuelve una tupla con un array de IDs: ([id1, id2],)
            result = db_connector.fetch_one(query, (ctx.guild.id,))

            channel_ids = result[0] if result and result[0] else []

            if channel_ids:
                await ctx.send(f"📜 Canales con IA proactiva: {', '.join([f'<#{c}>' for c in channel_ids])}")
            else:
                await ctx.send("No hay canales configurados para el modo proactivo.")
        except Exception as e:
            await ctx.send(f"❌ Error al listar canales: {e}")
            print(f"!!!!!! [AIConfig] Error en proactive_list: {e}")

    @proactive.command(name="clear")
    @commands.has_permissions(administrator=True)
    async def proactive_clear(self, ctx):
        """
        Desactiva el modo proactivo en todos los canales de este servidor.
        
        Llama al SP 'sp_ClearProactiveChannels'.
        """
        try:
            db_connector.execute_procedure("sp_ClearProactiveChannels", (ctx.guild.id,))
            await ctx.send("💥 Modo proactivo desactivado en todos los canales.")
        except Exception as e:
            await ctx.send(f"❌ Error al limpiar la lista: {e}")
            print(f"!!!!!! [AIConfig] Error en proactive_clear: {e}")


   # ----------------------------------------------------------------------
   # 💡 Gestión de Modo Reactivo (REACTIVE)
   # ----------------------------------------------------------------------
    @commands.group(name="reactive", invoke_without_command=True, brief="Activa/desactiva la respuesta a su nombre ('dalet').")
    @commands.has_permissions(administrator=True)
    async def reactive(self, ctx):
        """Activa o desactiva la capacidad de Dalet para responder a su nombre."""
        await ctx.send_help(ctx.command)

    @reactive.command(name="on")
    @commands.has_permissions(administrator=True)
    async def reactive_on(self, ctx):
        """
        Activa la respuesta de Dalet a su nombre.
        
        Llama al SP 'sp_SetServerReactive' con 'True'.
        """
        try:
            db_connector.execute_procedure(
                "sp_SetServerReactive",
                (ctx.guild.id, ctx.guild.name, True)
            )
            await ctx.send("✅ **Modo Reactivo Activado.** Dalet ahora responderá cuando la llamen.")
        except Exception as e:
            await ctx.send(f"❌ Error al activar el modo reactivo: {e}")
            print(f"!!!!!! [AIConfig] Error en reactive_on: {e}")

    @reactive.command(name="off")
    @commands.has_permissions(administrator=True)
    async def reactive_off(self, ctx):
        """
        Desactiva la respuesta de Dalet a su nombre.
        
        Llama al SP 'sp_SetServerReactive' con 'False'.
        """
        try:
            db_connector.execute_procedure(
                "sp_SetServerReactive",
                (ctx.guild.id, ctx.guild.name, False)
            )
            await ctx.send("🛑 **Modo Reactivo Desactivado.**")
        except Exception as e:
            await ctx.send(f"❌ Error al desactivar el modo reactivo: {e}")
            print(f"!!!!!! [AIConfig] Error en reactive_off: {e}")

    @reactive.command(name="status")
    async def reactive_status(self, ctx):
        """
        Muestra si el modo reactivo está activado o desactivado.
        
        Llama a la función 'fn_IsServerReactive'.
        """
        try:
            query = "SELECT fn_IsServerReactive(%s)"
            result = db_connector.fetch_one(query, (ctx.guild.id,))

            # Por defecto es True si no hay registro
            is_on = result[0] if result and result[0] is not None else True

            if is_on:
                await ctx.send("🟢 El modo reactivo está **Activado**.")
            else:
                await ctx.send("🔴 El modo reactivo está **Desactivado**.")
        except Exception as e:
            await ctx.send(f"❌ Error al consultar el estado: {e}")
            print(f"!!!!!! [AIConfig] Error en reactive_status: {e}")


async def setup(bot):
    """Función 'setup' para cargar el Cog."""
    await bot.add_cog(AIConfigCommands(bot))