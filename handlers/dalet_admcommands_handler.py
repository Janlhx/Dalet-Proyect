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

    @commands.command(name="status")
    async def system_status(self, ctx):
        """Muestra el estado técnico global del bot (DB, Caché, IA)."""
        import time
        from database.pool import DatabasePool
        
        embed = discord.Embed(title="💾 Estado del Sistema Dalet", color=discord.Color.blue())
        
        # 1. Base de Datos
        db_status = "✅ CONECTADA" if DatabasePool._pool else "❌ DESCONECTADA"
        embed.add_field(name="Base de Datos", value=db_status, inline=True)
        
        # 2. Caché y Batching
        log_buffer_size = len(self.bot.user_repo._log_buffer)
        cache_count = len(self.bot.user_repo._cache)
        embed.add_field(name="Logs en Buffer", value=f"{log_buffer_size} / 20", inline=True)
        embed.add_field(name="Items en Caché", value=f"{cache_count}", inline=True)

        # 3. Proveedor de IA
        nlp_service = self.bot.nlp_service
        provider = nlp_service.active_provider.upper()
        embed.add_field(name="Proveedor IA", value=f"🤖 {provider}", inline=True)
        
        # 4. Throttling
        nlp_handler = self.bot.get_cog("DaletNLPChat")
        if nlp_handler:
            cooldown = max(0, int(nlp_handler.error_cooldown - time.time()))
            throttling = f"⚠️ ACTIVO ({cooldown}s)" if cooldown > 0 else "✅ NINGUNO"
            embed.add_field(name="Throttling Discord", value=throttling, inline=True)

        # 5. Memoria Local
        local_hist_count = sum(len(d) for d in self.bot.memory_service._local_history.values())
        embed.add_field(name="Mensajes en RAM", value=f"{local_hist_count}", inline=True)

        embed.set_footer(text=f"ID del Shard: {self.bot.shard_id or 'N/A'}")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
