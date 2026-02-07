import discord
from discord.ext import commands
import logging

logger = logging.getLogger("dalet.handlers.aiconfig")

class AIConfigCommands(commands.Cog, name="Configuración de IA"):
    """Comandos para configurar cómo y dónde Dalet interactúa automáticamente."""

    def __init__(self, bot):
        self.bot = bot
        self.repo = bot.user_repo

    @commands.group(name="proactive", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def proactive(self, ctx):
        """🤖 [ADMIN] Configura en qué canales Dalet puede participar automáticamente en conversaciones."""
        await ctx.send("Usa `d.proactive add/remove/list/clear`.")

    @proactive.command(name="add")
    @commands.has_permissions(administrator=True)
    async def proactive_add(self, ctx, *channels: discord.TextChannel):
        """➕ Añade canales donde Dalet participará automáticamente. Uso: `d.proactive add #canal1 #canal2`"""
        if not channels: return await ctx.send("Menciona al menos un canal.")

        added = []
        try:
            for ch in channels:
                await self.repo.call_procedure(
                    "sp_SetChannelProactive",
                    ch.id, ch.name, ctx.guild.id, ctx.guild.name, True
                )
                added.append(ch)

            if added:
                await ctx.send(f"✅ Canales añadidos al modo proactivo: {', '.join([ch.mention for ch in added])}")
        except Exception as e:
            logger.error(f"Error in proactive_add: {e}")
            await ctx.send(f"❌ Error al añadir canales.")

    @proactive.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def proactive_remove(self, ctx, *channels: discord.TextChannel):
        """➖ Quita canales del modo proactivo. Uso: `d.proactive remove #canal1 #canal2`"""
        if not channels: return await ctx.send("Menciona al menos un canal.")

        removed = []
        try:
            for ch in channels:
                await self.repo.call_procedure(
                    "sp_SetChannelProactive",
                    ch.id, ch.name, ctx.guild.id, ctx.guild.name, False
                )
                removed.append(ch)

            if removed:
                await ctx.send(f"🗑️ Canales quitados del modo proactivo: {', '.join([ch.mention for ch in removed])}")
        except Exception as e:
            logger.error(f"Error in proactive_remove: {e}")
            await ctx.send(f"❌ Error al quitar canales.")

    @proactive.command(name="list")
    async def proactive_list(self, ctx):
        """📜 Muestra todos los canales donde Dalet participa automáticamente."""
        try:
            query = "SELECT * FROM fn_GetProactiveChannels($1)"
            result = await self.repo.fetch_one(query, ctx.guild.id)
            channel_ids = result[0] if result and result[0] else []

            if channel_ids:
                await ctx.send(f"📜 Canales con IA proactiva: {', '.join([f'<#{c}>' for c in channel_ids])}")
            else:
                await ctx.send("No hay canales configurados para el modo proactivo.")
        except Exception as e:
            logger.error(f"Error in proactive_list: {e}")
            await ctx.send(f"❌ Error al listar canales.")

    @proactive.command(name="clear")
    @commands.has_permissions(administrator=True)
    async def proactive_clear(self, ctx):
        """Desactiva el modo proactivo en todos los canales."""
        try:
            await self.repo.call_procedure("sp_ClearProactiveChannels", ctx.guild.id)
            await ctx.send("💥 Modo proactivo desactivado en todos los canales.")
        except Exception as e:
            logger.error(f"Error in proactive_clear: {e}")
            await ctx.send(f"❌ Error al limpiar la lista.")

    @commands.group(name="reactive", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def reactive(self, ctx):
        """💬 [ADMIN] Controla si Dalet responde cuando la mencionan en conversaciones."""
        await ctx.send("Usa `d.reactive on/off/status` para controlar el modo reactivo.")

    @reactive.command(name="on")
    @commands.has_permissions(administrator=True)
    async def reactive_on(self, ctx):
        """Activa la respuesta de Dalet a su nombre."""
        try:
            await self.repo.call_procedure("sp_SetServerReactive", ctx.guild.id, ctx.guild.name, True)
            await ctx.send("✅ **Modo Reactivo Activado.** Dalet ahora responderá cuando la llamen.")
        except Exception as e:
            logger.error(f"Error in reactive_on: {e}")
            await ctx.send(f"❌ Error al activar el modo reactivo.")

    @reactive.command(name="off")
    @commands.has_permissions(administrator=True)
    async def reactive_off(self, ctx):
        """Desactiva la respuesta de Dalet a su nombre."""
        try:
            await self.repo.call_procedure("sp_SetServerReactive", ctx.guild.id, ctx.guild.name, False)
            await ctx.send("🛑 **Modo Reactivo Desactivado.**")
        except Exception as e:
            logger.error(f"Error in reactive_off: {e}")
            await ctx.send(f"❌ Error al desactivar el modo reactivo.")

    @reactive.command(name="status")
    @commands.has_permissions(administrator=True)
    async def reactive_status(self, ctx):
        """Muestra si el modo reactivo está activado o desactivado."""
        try:
            query = "SELECT fn_IsServerReactive($1)"
            result = await self.repo.fetch_one(query, ctx.guild.id)
            is_on = result[0] if result and result[0] is not None else True

            status = "🟢 **Activado**" if is_on else "🔴 **Desactivado**"
            await ctx.send(f"El modo reactivo está {status}.")
        except Exception as e:
            logger.error(f"Error in reactive_status: {e}")
            await ctx.send(f"❌ Error al consultar el estado.")

async def setup(bot):
    await bot.add_cog(AIConfigCommands(bot))
