import asyncio
import logging
import discord
from discord.ext import commands

from ui.atoms import DaletAtoms
from ui.molecules import DaletMolecules
from ui.locales import t
from database.sqlite_manager import SQLiteManager

logger = logging.getLogger("dalet.handlers.admin")

class AdminCommands(commands.Cog, name="Comandos para el Administrador del bot"):
    """Comandos para administrar el bot y depurar la base de datos."""
    def __init__(self, bot):
        self.bot = bot
        self.repo = bot.user_repo

    async def _resolve_lang(self, ctx) -> str:
        guild_id = ctx.guild.id if getattr(ctx, "guild", None) else None
        try:
            return await self.bot.admin_repo.resolve_language(ctx.author.id, guild_id, default="en")
        except Exception:
            return "en"

    # --- Comandos de Gestión del Bot ---

    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def restart(self, ctx):
        """[ADMIN] Reinicia el bot (solo para administradores)."""
        await ctx.send(f"{DaletAtoms.GLYPH_POINTER} Cerrando conexión... el contenedor debería reiniciarme.")
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
                msg = await ctx.send(f"{DaletAtoms.GLYPH_POINTER} Sincronizando slash commands **globalmente**... (Discord puede tardar hasta 1 hora)")
                synced = await self.bot.tree.sync()
                await msg.edit(content=f"{DaletAtoms.GLYPH_CHECK} Sincronización global completada. **{len(synced)}** slash commands registrados.")
            elif mode.lower() == "clear":
                msg = await ctx.send(f"{DaletAtoms.GLYPH_POINTER} Limpiando slash commands de este servidor...")
                self.bot.tree.clear_commands(guild=ctx.guild)
                await self.bot.tree.sync(guild=ctx.guild)
                await msg.edit(content=f"{DaletAtoms.GLYPH_CHECK} Comandos del servidor limpiados.")
            else:
                msg = await ctx.send(f"{DaletAtoms.GLYPH_POINTER} Sincronizando slash commands **al instante en este servidor**...")
                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)
                await msg.edit(content=f"{DaletAtoms.GLYPH_CHECK} **{len(synced)}** slash commands sincronizados al instante en **{ctx.guild.name}**.")
        except Exception as e:
            logger.error(f"Error syncing commands: {e}")
            await ctx.send(f"{DaletAtoms.GLYPH_CROSS} Error al sincronizar: {e}")


    @commands.command(name="reload", hidden=True)
    @commands.has_permissions(administrator=True)
    async def reload_cog(self, ctx, *, cog_name: str):
        """[ADMIN] Recarga un módulo/handler (Cog)."""
        try:
            await self.bot.reload_extension(cog_name)
            await ctx.send(f"{DaletAtoms.GLYPH_CHECK} Módulo `{cog_name}` recargado exitosamente.")
        except Exception as e:
            logger.error(f"Error reloading {cog_name}: {e}")
            await ctx.send(f"{DaletAtoms.GLYPH_CROSS} Error al recargar `{cog_name}`: `{e}`")

    # --- Comandos de Control del Servidor y Canal ---

    @commands.command(name="lock")
    @commands.has_permissions(administrator=True)
    async def lock_channel(self, ctx):
        """[ADMIN] Bloquea todos los comandos en este canal."""
        lang = await self._resolve_lang(ctx)
        try:
            await self.bot.admin_repo.set_channel_lock(
                ctx.channel.id, ctx.channel.name, ctx.guild.id, ctx.guild.name, True
            )
            await ctx.send(t("admin.lock_success", lang, channel=ctx.channel.mention))
        except Exception as e:
            logger.error(f"Error in lock: {e}")
            await ctx.send(t("admin.lock_error", lang))

    @commands.command(name="unlock")
    @commands.has_permissions(administrator=True)
    async def unlock_channel(self, ctx):
        """[ADMIN] Desbloquea los comandos en este canal."""
        lang = await self._resolve_lang(ctx)
        try:
            await self.bot.admin_repo.set_channel_lock(
                ctx.channel.id, ctx.channel.name, ctx.guild.id, ctx.guild.name, False
            )
            await ctx.send(t("admin.unlock_success", lang, channel=ctx.channel.mention))
        except Exception as e:
            logger.error(f"Error in unlock: {e}")
            await ctx.send(t("admin.unlock_error", lang))

    @commands.command(name="setname")
    @commands.has_permissions(administrator=True)
    async def set_bot_name(self, ctx, *, new_name: str):
        """[ADMIN] Cambia mi nombre en este servidor (máx 32 caracteres)."""
        lang = await self._resolve_lang(ctx)
        if len(new_name) > 32:
            return await ctx.send(t("admin.name_too_long", lang))

        try:
            await self.bot.admin_repo.set_server_custom_name(ctx.guild.id, new_name)
            await ctx.send(t("admin.setname_success", lang, name=new_name))
        except Exception as e:
            logger.error(f"Error in setname: {e}")
            await ctx.send(t("admin.setname_error", lang))

    @commands.command(name="setwelcome")
    @commands.has_permissions(administrator=True)
    async def set_welcome(self, ctx):
        """[ADMIN] Establece el canal actual para las bienvenidas y despedidas."""
        lang = await self._resolve_lang(ctx)
        try:
            await self.bot.admin_repo.set_welcome_channel(ctx.guild.id, ctx.channel.id)
            await ctx.send(t("admin.setwelcome_success", lang, channel=ctx.channel.mention))
        except Exception as e:
            logger.error(f"Error setwelcome: {e}")
            await ctx.send(t("admin.setwelcome_error", lang))

    @commands.command(name="removewelcome")
    @commands.has_permissions(administrator=True)
    async def remove_welcome(self, ctx):
        """[ADMIN] Desactiva las bienvenidas y despedidas en el servidor."""
        lang = await self._resolve_lang(ctx)
        try:
            await self.bot.admin_repo.set_welcome_channel(ctx.guild.id, None)
            await ctx.send(t("admin.removewelcome_success", lang))
        except Exception as e:
            logger.error(f"Error removewelcome: {e}")
            await ctx.send(t("admin.removewelcome_error", lang))

    @commands.command(name="cs", aliases=["channelstatus"])
    async def channel_status(self, ctx):
        """Muestra el estado de seguridad y IA del canal actual."""
        lang = await self._resolve_lang(ctx)
        try:
            is_locked = await self.bot.admin_repo.is_channel_locked(ctx.channel.id)
            is_proactive = await self.bot.user_repo.is_channel_proactive(ctx.channel.id)
            is_reactive = await self.bot.user_repo.is_server_reactive(ctx.guild.id)

            status_embed = discord.Embed(
                title=t("admin.cs_title", lang, channel=ctx.channel.name),
                color=DaletAtoms.COLOR_ERROR if is_locked else DaletAtoms.COLOR_SUCCESS
            )
            status_embed.add_field(
                name=t("admin.cs_commands", lang),
                value=t("admin.cs_blocked", lang) if is_locked else t("admin.cs_active", lang),
                inline=False
            )
            status_embed.add_field(
                name=t("admin.cs_proactive", lang),
                value=t("admin.cs_on", lang) if is_proactive else t("admin.cs_off", lang),
                inline=True
            )
            status_embed.add_field(
                name=t("admin.cs_reactive", lang),
                value=t("admin.cs_on", lang) if is_reactive else t("admin.cs_off", lang),
                inline=True
            )
            DaletMolecules.add_standard_footer(status_embed, context_text="Dalet")
            await ctx.send(embed=status_embed)
        except Exception as e:
            logger.error(f"Error in channel_status: {e}")
            await ctx.send(f"{DaletAtoms.GLYPH_CROSS} Error obteniendo el estado del canal.")

    @commands.command(name="dbstats", hidden=True)
    @commands.has_permissions(administrator=True)
    async def db_stats(self, ctx):
        """[ADMIN] Muestra un resumen de analíticas de SQLite: comandos, IA y errores."""
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
                title=f"{DaletAtoms.EMOJI_DALET} Analíticas (SQLite Local)",
                color=DaletAtoms.COLOR_PURPLE
            )

            # Top comandos
            if top_cmds:
                cmd_text = "\n".join([
                    f"`{r['CommandName']}` — {r['total_uses']} usos ({r['success_rate']}% éxito)"
                    for r in top_cmds
                ])
            else:
                cmd_text = "_Sin datos aún_"
            embed.add_field(name=f"{DaletAtoms.GLYPH_POINTER} Top 5 Comandos", value=cmd_text, inline=False)

            # IA hoy
            if ai_today:
                ai_text = "\n".join([
                    f"`{r['TriggerType']}` via **{r['Provider']}** — {r['n']} respuestas"
                    for r in ai_today
                ])
            else:
                ai_text = "_Sin interacciones hoy_"
            embed.add_field(name=f"{DaletAtoms.GLYPH_POINTER} Respuestas IA (24h)", value=ai_text, inline=False)

            # Errores recientes
            if recent_errors:
                err_text = "\n".join([
                    f"`{r['ErrorType']}` — {r['occurrences']}x"
                    for r in recent_errors
                ])
            else:
                err_text = f"{DaletAtoms.GLYPH_CHECK} Sin errores recientes"
            embed.add_field(name=f"{DaletAtoms.GLYPH_POINTER} Errores (7 días)", value=err_text, inline=False)

            embed.set_footer(text="Fuente: SQLite local │ CommandUsage │ AIInteractions │ BotErrors")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error en dbstats: {e}")
            await ctx.send(f"{DaletAtoms.GLYPH_CROSS} Error al obtener estadísticas:\n```{e}```")

    @commands.command(name="status", aliases=["setstatus"], hidden=True)
    @commands.is_owner()
    async def set_bot_status(self, ctx, *, text: str = None):
        """
        [OWNER] Cambia la presencia/estado de Dalet en Discord en tiempo real.
        Uso:
          d.status osu! • jugando │ d.help
          d.status default  -> Restablece al ciclo rotativo automático
        """
        if not text or text.lower() in ("default", "reset", "auto"):
            self.bot.custom_status = None
            events_cog = self.bot.get_cog("EventsHandler")
            if events_cog and hasattr(events_cog, "rotate_presence"):
                events_cog._presence_index = 0
                await events_cog.rotate_presence()
            return await ctx.send(f"{DaletAtoms.GLYPH_POINTER} Presencia restablecida al ciclo rotativo automático de Dalet.")

        self.bot.custom_status = text
        activity = discord.Game(name=text)
        await self.bot.change_presence(activity=activity)

        embed = discord.Embed(
            title=f"{DaletAtoms.EMOJI_DALET} Estado Actualizado",
            description=f"{DaletAtoms.GLYPH_POINTER} **Nueva presencia (Playing):** `{text}`",
            color=DaletAtoms.COLOR_PRIMARY
        )
        DaletMolecules.add_standard_footer(embed, context_text="Dalet")
        await ctx.send(embed=embed)

    @commands.command(name="setchangelog", hidden=True)
    @commands.is_owner()
    async def set_bot_changelog(self, ctx, *, text: str = None):
        """
        [OWNER] Actualiza la nota dinámica del comando d.changelog.
        Uso:
          d.setchangelog <texto>
          d.setchangelog reset  -> Vuelve a las notas oficiales de la versión
        """
        if not text:
            return await ctx.send(f"{DaletAtoms.GLYPH_POINTER} Especifica el texto del changelog o usa `d.setchangelog reset`.")

        if text.lower() == "reset":
            self.bot.custom_changelog = None
            return await ctx.send(f"{DaletAtoms.GLYPH_POINTER} Changelog restablecido a las notas predeterminadas de {DaletAtoms.VERSION}.")

        self.bot.custom_changelog = text
        await ctx.send(f"{DaletAtoms.GLYPH_POINTER} Changelog dinámico actualizado correctamente para {DaletAtoms.VERSION}.")

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
