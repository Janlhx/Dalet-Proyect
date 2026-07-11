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
            from ui.atoms import DaletAtoms
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
                time_text = f"{int(time_since_last)}s atrás"
                cooldown_remaining = max(0, COOLDOWN_TIME - time_since_last)

            # Verificar si este canal es proactivo
            is_proactive = await self.repo.fetch_one(
                "SELECT fn_IsChannelProactive($1)", ctx.channel.id
            )
            channel_is_proactive = bool(is_proactive and is_proactive[0])
            channel_status = "Activa" if channel_is_proactive else "Inactiva"

            # Verificar si el canal está bloqueado (Lock)
            is_locked = await self.bot.admin_repo.is_channel_locked(ctx.channel.id)
            lock_status = "Bloqueado" if is_locked else "Libre"

            # Rate Limit Info — calcular tokens actuales del canal
            rl_entry = nlp_cog.channel_ratelimits.get(ctx.channel.id)
            if rl_entry:
                stored_tokens, last_ts = rl_entry
                c_tokens = min(5.0, stored_tokens + (now - last_ts) * (1.0 / 12.0))
            else:
                c_tokens = 5.0  # Canal fresco, bucket lleno

            embed = discord.Embed(
                title=f"Diagnóstico del Sistema Proactivo",
                color=DaletAtoms.COLOR_PRIMARY
            )
            embed.add_field(
                name="Ajustes Técnicos",
                value=(
                    f"• Probabilidad: `{int(BASE_RESPONSE_RATE * 100)}%` por mensaje\n"
                    f"• Cooldown mínimo: `{COOLDOWN_TIME}s` entre respuestas\n"
                    f"• Mínimo de mensajes: `{MIN_MESSAGES_BETWEEN_REPLIES}`\n"
                    f"• Ventana de reset: `{MAX_MESSAGES_WINDOW} mensajes`"
                ),
                inline=False
            )
            embed.add_field(
                name="Estado en Tiempo Real",
                value=(
                    f"• Mensajes acumulados: **{nlp_cog.message_counter}** / {MIN_MESSAGES_BETWEEN_REPLIES}\n"
                    f"• Última respuesta: {time_text}\n"
                    f"• Cooldown restante: **{int(cooldown_remaining)}s**\n"
                    f"• Tokens canal (rate-limit): **{c_tokens:.2f}** / 5.0"
                ),
                inline=False
            )
            embed.add_field(
                name="Estado del Canal",
                value=(
                    f"• Proactividad: {channel_status}\n"
                    f"• Candado (Lock): {lock_status}"
                ),
                inline=False
            )

            # Calcular si podría responder ahora mismo
            can_respond = (
                not is_locked
                and channel_is_proactive
                and nlp_cog.message_counter >= MIN_MESSAGES_BETWEEN_REPLIES
                and cooldown_remaining == 0
                and c_tokens >= 1.0
            )

            if can_respond:
                embed.add_field(
                    name="Disponibilidad",
                    value=f"Dalet **puede hablar** en el próximo mensaje (probabilidad `{int(BASE_RESPONSE_RATE * 100)}%`).",
                    inline=False
                )
            else:
                reasons = []
                if is_locked:
                    reasons.append("los comandos están bloqueados — usa `d.unlock`")
                if not channel_is_proactive:
                    reasons.append("el modo proactivo no está activo — usa `d.proactive add`")
                if nlp_cog.message_counter < MIN_MESSAGES_BETWEEN_REPLIES:
                    missing = MIN_MESSAGES_BETWEEN_REPLIES - nlp_cog.message_counter
                    reasons.append(f"faltan **{missing}** mensajes para el mínimo")
                if cooldown_remaining > 0:
                    reasons.append(f"cooldown activo por **{int(cooldown_remaining)}s**")
                if c_tokens < 1.0:
                    reasons.append("rate limit de canal activo (bucket vacío)")

                embed.add_field(
                    name="Bloqueos Activos",
                    value="\n".join(f"• {r}" for r in reasons) if reasons else "Ninguno",
                    inline=False
                )

            embed.set_footer(text="sistema de proactividad · Dalet")
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
            query = "SELECT fn_IsServerReactive($1::BIGINT)"
            result = await self.repo.fetch_one(query, ctx.guild.id)
            is_on = result[0] if result and result[0] is not None else False

            status = "🟢 **Activado**" if is_on else "🔴 **Desactivado**"
            await ctx.send(f"El modo reactivo está {status}.")
        except Exception as e:
            logger.error(f"Error in reactive_status: {e}")
            await ctx.send(f"❌ Error al consultar el estado.")

async def setup(bot):
    await bot.add_cog(AIConfigCommands(bot))
