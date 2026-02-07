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
        await ctx.send("Usa `d.proactive add/remove/list/clear/debug`.")

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

    @proactive.command(name="debug")
    async def proactive_debug(self, ctx):
        """🔍 Muestra el estado interno del sistema proactivo para debugging."""
        try:
            # Importar constantes de dalet_nlpchat para que el debug sea real
            from handlers.dalet_nlpchat import (
                BASE_RESPONSE_RATE, COOLDOWN_TIME, 
                MIN_MESSAGES_BETWEEN_REPLIES, MAX_MESSAGES_WINDOW
            )
            
            # Obtener el cog de NLP para acceder a sus variables internas
            nlp_cog = self.bot.get_cog("DaletNLPChat")
            if not nlp_cog:
                return await ctx.send("❌ No se pudo encontrar el módulo de NLP.")
            
            import time
            now = time.time()
            time_since_last = now - nlp_cog.last_reply_time
            # Si el bot nunca ha respondido (last_reply_time = 0), evitamos números gigantes
            if nlp_cog.last_reply_time == 0:
                time_text = "Nunca"
                cooldown_remaining = 0
            else:
                time_text = f"{int(time_since_last)}s"
                cooldown_remaining = max(0, COOLDOWN_TIME - time_since_last)
            
            # Verificar si este canal es proactivo
            is_proactive = await self.repo.fetch_one(
                "SELECT fn_IsChannelProactive($1)", ctx.channel.id
            )
            channel_status = "✅ SÍ" if (is_proactive and is_proactive[0]) else "❌ NO"
            
            # Verificar si el canal está bloqueado (Lock)
            is_locked = await self.bot.admin_repo.is_channel_locked(ctx.channel.id)
            lock_status = "🔒 BLOQUEADO" if is_locked else "🔓 LIBRE"

            embed = discord.Embed(
                title="🔍 Estado del Sistema Proactivo",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="📊 Configuración Actual",
                value=f"• Probabilidad: **{int(BASE_RESPONSE_RATE * 100)}%**\n"
                      f"• Cooldown: **{COOLDOWN_TIME} segundos**\n"
                      f"• Mensajes mínimos: **{MIN_MESSAGES_BETWEEN_REPLIES}**\n"
                      f"• Ventana de Reset: **{MAX_MESSAGES_WINDOW} mensajes**",
                inline=False
            )
            embed.add_field(
                name="📈 Estado Actual",
                value=f"• Mensajes en ventana: **{nlp_cog.message_counter}**/{MIN_MESSAGES_BETWEEN_REPLIES}\n"
                      f"• Tiempo desde última respuesta: **{time_text}**\n"
                      f"• Cooldown restante: **{int(cooldown_remaining)}s**",
                inline=False
            )
            embed.add_field(
                name="🎯 Este Canal",
                value=f"• Modo proactivo: {channel_status}\n"
                      f"• Candado (Lock): {lock_status}",
                inline=False
            )
            
            # Calcular si podría responder ahora
            can_respond = (
                not is_locked and
                (is_proactive and is_proactive[0]) and
                nlp_cog.message_counter >= MIN_MESSAGES_BETWEEN_REPLIES and 
                cooldown_remaining == 0
            )
            
            if can_respond:
                embed.add_field(
                    name="✅ Estado",
                    value=f"El bot **PUEDE** responder ahora (con {int(BASE_RESPONSE_RATE * 100)}% de probabilidad en el próximo mensaje)",
                    inline=False
                )
            else:
                reasons = []
                if is_locked:
                    reasons.append("Los **comandos están bloqueados** (`d.unlock` para activar)")
                if not (is_proactive and is_proactive[0]):
                    reasons.append("El **modo proactivo** no está activado en este canal")
                if nlp_cog.message_counter < MIN_MESSAGES_BETWEEN_REPLIES:
                    reasons.append(f"Faltan **{MIN_MESSAGES_BETWEEN_REPLIES - nlp_cog.message_counter}** mensajes")
                if cooldown_remaining > 0:
                    reasons.append(f"Cooldown activo por **{int(cooldown_remaining)}s**")
                
                embed.add_field(
                    name="⏳ Estado",
                    value=f"El bot **NO PUEDE** responder aún:\n" + "\n".join(f"• {r}" for r in reasons),
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in proactive_debug: {e}")
            await ctx.send(f"❌ Error al obtener información de debug: {e}")

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
