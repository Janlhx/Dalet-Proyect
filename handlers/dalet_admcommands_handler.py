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

    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def restart(self, ctx):
        """[ADMIN] Reinicia el bot (solo para administradores)."""
        await ctx.send("Cerrando conexión... Render debería reiniciarme.")
        await self.bot.close()

    @commands.command(name="sync", hidden=True)
    @commands.has_permissions(administrator=True)
    async def sync_slash_commands(self, ctx, mode: str = "here"):
        """
        [ADMIN] Sincroniza slash commands.
        - `d.sync` o `d.sync here`: sincroniza al instante en este servidor (0s de espera).
        - `d.sync global`: sincroniza globalmente (puede tardar hasta 1h en propagarse en Discord).
        - `d.sync clear`: limpia comandos del servidor actual.
        """
        try:
            if mode.lower() == "global":
                msg = await ctx.send("🌍 Sincronizando slash commands **globalmente**... (Discord puede tardar hasta 1 hora en propagar a los clientes)")
                synced = await self.bot.tree.sync()
                await msg.edit(content=f"✅ Sincronización global completada. **{len(synced)}** slash commands registrados.")
            elif mode.lower() == "clear":
                msg = await ctx.send("🧹 Limpiando slash commands de este servidor...")
                self.bot.tree.clear_commands(guild=ctx.guild)
                await self.bot.tree.sync(guild=ctx.guild)
                await msg.edit(content="✅ Comandos del servidor limpiados.")
            else:
                msg = await ctx.send("⚡ Sincronizando slash commands **instantáneamente en este servidor**...")
                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)
                await msg.edit(content=f"✅ ¡Listo! **{len(synced)}** slash commands sincronizados al instante en **{ctx.guild.name}**.\nYa deberías verlos al escribir `/` (si no, presiona `Ctrl+R` en Discord para refrescar la app).")
        except Exception as e:
            logger.error(f"Error syncing commands: {e}")
            await ctx.send(f"❌ Error al sincronizar: {e}")


    @commands.command(name="reload", hidden=True)
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

    @commands.command(name="sql", hidden=True)
    @commands.is_owner()
    async def run_sql_select(self, ctx, *, query: str):
        """[ADMIN] Ejecuta una consulta SELECT en la BD (solo Owner)."""
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

    @commands.command(name="lock")
    @commands.has_permissions(administrator=True)
    async def lock_channel(self, ctx):
        """[ADMIN] Bloquea todos los comandos en este canal."""
        try:
            await self.bot.admin_repo.set_channel_lock(
                ctx.channel.id, ctx.channel.name, ctx.guild.id, ctx.guild.name, True
            )
            await ctx.send("🛑 **Canal Bloqueado.** Dalet ignorará todos los comandos aquí hasta que se use `d.unlock`.")
        except Exception as e:
            logger.error(f"Error in lock: {e}")
            await ctx.send("❌ Error al bloquear el canal.")

    @commands.command(name="unlock")
    @commands.has_permissions(administrator=True)
    async def unlock_channel(self, ctx):
        """[ADMIN] Desbloquea los comandos en este canal."""
        try:
            await self.bot.admin_repo.set_channel_lock(
                ctx.channel.id, ctx.channel.name, ctx.guild.id, ctx.guild.name, False
            )
            await ctx.send("🔓 **Canal Desbloqueado.** ¡Los comandos de Dalet ya están disponibles!")
        except Exception as e:
            logger.error(f"Error in unlock: {e}")
            await ctx.send("❌ Error al desbloquear el canal.")

    @commands.command(name="setname")
    @commands.has_permissions(administrator=True)
    async def set_bot_name(self, ctx, *, new_name: str):
        """[ADMIN] Cambia mi nombre en este servidor (máx 25 caracteres)."""
        if len(new_name) > 25:
            return await ctx.send("❌ El nombre es demasiado largo. El máximo son 25 caracteres.")
        
        try:
            await self.bot.admin_repo.set_server_custom_name(ctx.guild.id, new_name)
            await ctx.send(f"✅ ¡Entendido! En este servidor ahora respondo al nombre de **{new_name}**. (Y sigo siendo Dalet también).")
        except Exception as e:
            logger.error(f"Error in setname: {e}")
            await ctx.send("❌ Ocurrió un error al guardar mi nuevo nombre.")

    @commands.command(name="setwelcome")
    @commands.has_permissions(administrator=True)
    async def set_welcome(self, ctx):
        """[ADMIN] Establece el canal actual para las bienvenidas y despedidas."""
        try:
            await self.bot.admin_repo.set_welcome_channel(ctx.guild.id, ctx.channel.id)
            await ctx.send("🎉 **¡Canal establecido!** A partir de ahora, humillaré/saludaré a los que entren o salgan por este canal.")
        except Exception as e:
            logger.error(f"Error setwelcome: {e}")
            await ctx.send("❌ Error al configurar el canal de bienvenida.")

    @commands.command(name="removewelcome")
    @commands.has_permissions(administrator=True)
    async def remove_welcome(self, ctx):
        """[ADMIN] Desactiva las bienvenidas y despedidas en el servidor."""
        try:
            await self.bot.admin_repo.set_welcome_channel(ctx.guild.id, None)
            await ctx.send("🔇 **Bienvenidas desactivadas.** Volveré a ignorar civilizadamente a la gente que entra y sale.")
        except Exception as e:
            logger.error(f"Error removewelcome: {e}")
            await ctx.send("❌ Error al eliminar el canal de bienvenida.")

    @commands.command(name="cs", aliases=["channelstatus"])
    async def channel_status(self, ctx):
        """Muestra el estado de seguridad y IA del canal actual."""
        try:
            is_locked = await self.bot.admin_repo.is_channel_locked(ctx.channel.id)
            # Reaprovechamos UserRepository para proactividad
            is_proactive = await self.bot.user_repo.is_channel_proactive(ctx.channel.id)
            is_reactive = await self.bot.user_repo.is_server_reactive(ctx.guild.id)

            status_embed = discord.Embed(
                title=f"🛡️ Estado del Canal: #{ctx.channel.name}",
                color=discord.Color.red() if is_locked else discord.Color.green()
            )
            status_embed.add_field(
                name="🔒 Comandos", 
                value="⛔ **BLOQUEADOS** (Usa `d.unlock`)" if is_locked else "✅ **ACTIVOS**",
                inline=False
            )
            status_embed.add_field(
                name="🤖 IA Proactiva", 
                value="✨ **ACTIVA**" if is_proactive else "🌑 **INACTIVA**",
                inline=True
            )
            status_embed.add_field(
                name="💬 IA Reactiva (Menciones)", 
                value="✅ **ACTIVA**" if is_reactive else "❌ **INACTIVA**",
                inline=True
            )
            
            await ctx.send(embed=status_embed)
        except Exception as e:
            logger.error(f"Error in channel_status: {e}")
            await ctx.send("❌ Error al obtener el estado del canal.")


    @commands.command(name="dbstats", hidden=True)
    @commands.has_permissions(administrator=True)
    async def db_stats(self, ctx):
        """[ADMIN] Muestra un resumen de analíticas de SQLite: comandos, IA y errores."""
        from database.sqlite_manager import SQLiteManager

        try:
            # Top 5 comandos más usados (SQLite)
            top_cmds = await SQLiteManager.fetch_all("""
                SELECT CommandName,
                       COUNT(*) as total_uses,
                       ROUND(100.0 * SUM(Success) / COUNT(*), 1) as success_rate
                FROM CommandUsage
                GROUP BY CommandName
                ORDER BY total_uses DESC
                LIMIT 5
            """)

            # Respuestas de IA en las últimas 24h (SQLite)
            ai_today = await SQLiteManager.fetch_all("""
                SELECT TriggerType, Provider,
                       COUNT(*) as n,
                       ROUND(AVG(ResponseTimeMs)) as avg_ms
                FROM AIInteractions
                WHERE InteractedAt >= datetime('now', '-24 hours')
                GROUP BY TriggerType, Provider
                ORDER BY n DESC
            """)

            # Errores recientes (últimos 7 días)
            recent_errors = await SQLiteManager.fetch_all("""
                SELECT ErrorType,
                       COUNT(*) as occurrences,
                       MAX(OccurredAt) as last_seen
                FROM BotErrors
                WHERE OccurredAt >= datetime('now', '-7 days')
                GROUP BY ErrorType
                ORDER BY occurrences DESC
                LIMIT 5
            """)

            embed = discord.Embed(
                title="📊 Analíticas (SQLite Local)",
                color=discord.Color.purple()
            )

            # Top comandos
            if top_cmds:
                cmd_text = "\n".join([
                    f"`{r['CommandName']}` — {r['total_uses']} usos ({r['success_rate']}% éxito)"
                    for r in top_cmds
                ])
            else:
                cmd_text = "_Sin datos aún_"
            embed.add_field(name="🏆 Top 5 Comandos", value=cmd_text, inline=False)

            # IA hoy
            if ai_today:
                ai_text = "\n".join([
                    f"`{r['TriggerType']}` via **{r['Provider']}** — {r['n']} respuestas"
                    for r in ai_today
                ])
            else:
                ai_text = "_Sin interacciones hoy_"
            embed.add_field(name="🤖 Respuestas IA (24h)", value=ai_text, inline=False)

            # Errores recientes
            if recent_errors:
                err_text = "\n".join([
                    f"`{r['ErrorType']}` — {r['occurrences']}x"
                    for r in recent_errors
                ])
            else:
                err_text = "✅ Sin errores recientes"
            embed.add_field(name="⚠️ Errores (7 días)", value=err_text, inline=False)

            embed.set_footer(text="Fuente: SQLite local · CommandUsage · AIInteractions · BotErrors")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en dbstats: {e}")
            await ctx.send(f"❌ Error al obtener estadísticas:\n```{e}```")

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
