import asyncio
import logging
from datetime import timedelta
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from services.moderation_service import ModerationService, ModerationResult
from ui.atoms import DaletAtoms
from ui.molecules import DaletMolecules

logger = logging.getLogger("dalet.handlers.moderation")

_SEVERITY_LABELS = {
    "adult": "Contenido adulto/NSFW",
    "illegal": "Contenido ilegal (CP/CSAM)",
    "flood": "Spam / Flood de mensajes",
}
_SEVERITY_COLORS = {
    "adult": DaletAtoms.COLOR_WARNING,
    "illegal": DaletAtoms.COLOR_ERROR,
    "flood": DaletAtoms.COLOR_PURPLE,
}
_ACTION_LABELS   = {"notify": "Notificar", "timeout": "Timeout", "ban": "Ban"}
_EXEMPT_MODULE_NAMES = {
    "all": "🛡️ Todo el canal",
    "flood": "🌊 Anti-Flood",
    "images": "🖼️ Imágenes (IA Visión)",
    "links": "🔗 Enlaces Adultos",
    "scams": "🎣 Phishing & Scams",
}


class ModerationCog(commands.Cog, name="Moderación"):
    """Auto-moderación de contenido NSFW e ilegal. Opt-in por servidor."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._mod_service: ModerationService | None = None

    async def cog_load(self):
        nlp = getattr(self.bot, "nlp_service", None)
        admin_repo = getattr(self.bot, "admin_repo", None)
        self._mod_service = ModerationService(nlp, admin_repo=admin_repo)
        if admin_repo:
            try:
                await self._mod_service.prewarm_blacklist()
            except Exception as e:
                logger.warning(f"Error precalentando lista negra de imágenes: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.webhook_id or not message.guild:
            return

        # Bypass para Administradores y Moderadores con permisos en el servidor
        if isinstance(message.author, discord.Member):
            perms = message.author.guild_permissions
            if perms.administrator or perms.manage_guild or perms.manage_messages:
                return

        config = await self.bot.admin_repo.get_moderation_config(message.guild.id)
        if not config or not config["enabled"]:
            return

        # Chequeo de canales y módulos exentos (ej: spam, mudae, waifu-posting)
        ignored_map = config.get("ignored_channels_map", {})
        exempt_mods = ignored_map.get(message.channel.id, set())
        if "all" in exempt_mods:
            return

        # 1. Chequeo de Anti-Flood en memoria (Ráfagas rápidas, links duplicados o misma foto repetida)
        if self._mod_service and config.get("anti_flood", True) and "flood" not in exempt_mods:
            att_sig = f"{message.attachments[0].filename}_{message.attachments[0].size}" if message.attachments else ""
            is_flood, flood_reason = self._mod_service.check_flood(
                message.author.id, message.channel.id, message.content or "", attachment_sig=att_sig
            )
            if is_flood:
                flood_result = ModerationResult(
                    flagged=True,
                    severity="flood",
                    confidence=1.0,
                    reason=flood_reason,
                    method="anti_flood",
                )
                await self._handle_violation(message, flood_result, config, is_cross_channel_spam=False)
                return

        # 2. Escaneo de contenido (regex en texto y Gemini Vision en imágenes)
        # En canales marcados en Discord como NSFW (18+), omitimos escaneo visual para ahorrar costos de API
        is_nsfw_channel = getattr(message.channel, "is_nsfw", lambda: False)()
        scan_images = config.get("scan_images", True) and not is_nsfw_channel and "images" not in exempt_mods
        filter_links = config.get("filter_links", True) and "links" not in exempt_mods
        filter_scams = config.get("filter_scams", True) and "scams" not in exempt_mods

        # Si todos los módulos activos están exentos en este canal, omitir escaneo
        if not scan_images and not filter_links and not filter_scams:
            return

        image_urls = ModerationService.extract_image_urls(message) if scan_images else []

        result = await self._mod_service.scan_message(
            content=message.content or "",
            image_urls=image_urls,
            filter_links=filter_links,
            filter_scams=filter_scams,
            scan_images=scan_images,
        )

        if not result.flagged:
            return

        is_spam = False
        try:
            is_spam = self._mod_service.track_flag(message.author.id, message.channel.id)
        except Exception as e:
            logger.warning(f"Error evaluando cross-channel spam: {e}")

        await self._handle_violation(message, result, config, is_spam)

    async def _handle_violation(
        self,
        message: discord.Message,
        result: ModerationResult,
        config: dict,
        is_cross_channel_spam: bool,
    ):
        guild = message.guild
        author = message.author

        try:
            await message.delete()
            logger.info(f"[MOD] Mensaje {message.id} de {author} eliminado por infracción ({result.severity}: {result.reason})")
        except discord.Forbidden:
            logger.warning(f"[MOD] Sin permisos (Manage Messages) para borrar mensaje {message.id} en #{message.channel.name}")
        except discord.NotFound:
            pass

        action = "notify"
        if result.severity == "illegal" and config.get("auto_ban_on_illegal", False):
            action = "ban"
        elif result.severity == "flood":
            action = "timeout"
        elif is_cross_channel_spam and config.get("action") == "notify":
            action = "timeout"
        elif config.get("action") in ("timeout", "ban"):
            action = config["action"]

        action_taken = await self._apply_action(author, guild, action, config["timeout_minutes"], result.severity)

        await self._log_to_channel(message, result, config, action_taken, is_cross_channel_spam)

        await self.bot.admin_repo.log_mod_action(
            server_id=guild.id,
            channel_id=message.channel.id,
            user_id=author.id,
            user_name=str(author),
            severity=result.severity,
            method=result.method,
            reason=result.reason,
            action_taken=action_taken,
        )

    async def _apply_action(
        self,
        member: discord.Member,
        guild: discord.Guild,
        action: str,
        timeout_minutes: int,
        severity: str,
    ) -> str:
        # Asegurar que tengamos el objeto Member con roles y permisos en el servidor
        if not isinstance(member, discord.Member):
            member = guild.get_member(member.id)
            if not member:
                return "user_not_in_guild"

        if action == "ban":
            if not guild.me or not (guild.me.guild_permissions.ban_members or guild.me.guild_permissions.administrator):
                return "ban_fallido (Dalet no tiene el permiso 'Banear miembros')"
            if member == guild.owner:
                return "ban_fallido (es owner)"
            if getattr(member, "guild_permissions", None) and member.guild_permissions.administrator:
                return "ban_fallido (es administrador)"
            if guild.me and member.top_role >= guild.me.top_role:
                return f"ban_fallido (rol '{member.top_role.name}' >= '{guild.me.top_role.name}')"
            try:
                await guild.ban(member, reason=f"Auto-mod: {severity}", delete_message_days=1)
                return "banned"
            except discord.Forbidden as e:
                logger.warning(f"Sin permisos para banear a {member} en {guild}: {e} (código {e.code})")
                return f"ban_fallido (código {e.code}: {e.text})"

        if action == "timeout":
            if not guild.me or not (guild.me.guild_permissions.moderate_members or guild.me.guild_permissions.administrator):
                return "timeout_fallido (Dalet no tiene el permiso 'Time out members' / 'Moderar miembros')"
            if member == guild.owner:
                return "timeout_fallido (es owner)"
            if getattr(member, "guild_permissions", None) and member.guild_permissions.administrator:
                return "timeout_fallido (es administrador)"
            if guild.me and member.top_role >= guild.me.top_role:
                return f"timeout_fallido (rol '{member.top_role.name}' >= '{guild.me.top_role.name}')"
            try:
                await member.timeout(
                    timedelta(minutes=timeout_minutes),
                    reason=f"Auto-mod: {severity}",
                )
                return f"timeout_{timeout_minutes}m"
            except discord.Forbidden as e:
                logger.warning(f"Sin permisos para timeout a {member} en {guild}: {e} (código {e.code})")
                return f"timeout_fallido (código {e.code}: {e.text})"

        return "deleted"

    async def _log_to_channel(
        self,
        message: discord.Message,
        result: ModerationResult,
        config: dict,
        action_taken: str,
        is_spam: bool,
    ):
        log_channel_id = config.get("log_channel_id")
        if not log_channel_id:
            return

        channel = message.guild.get_channel(log_channel_id)
        if not channel:
            return

        color = _SEVERITY_COLORS.get(result.severity, DaletAtoms.COLOR_WARNING)
        embed = discord.Embed(
            title=f"🛡️ Auto-mod — {_SEVERITY_LABELS.get(result.severity, result.severity)}",
            color=color,
        )
        embed.add_field(name="Usuario", value=f"{message.author.mention} (`{message.author}`)", inline=True)
        embed.add_field(name="Canal", value=message.channel.mention, inline=True)
        embed.add_field(name="Método", value=result.method, inline=True)
        embed.add_field(name="Razón", value=result.reason or "—", inline=True)
        embed.add_field(name="Confianza", value=f"{result.confidence:.0%}", inline=True)
        embed.add_field(name="Acción", value=action_taken, inline=True)

        if is_spam:
            embed.add_field(name="⚠️ Spam cross-canal", value="Detectado en múltiples canales", inline=False)

        if message.content:
            preview = message.content[:200]
            embed.add_field(name="Contenido (preview)", value=f"||{preview}||", inline=False)

        DaletMolecules.add_standard_footer(embed, context_text="Auto-mod")

        mention_prefix = ""
        if result.severity == "illegal":
            mention_prefix = "🚨 **ALERTA CRÍTICA (@here)** — Se detectó y eliminó posible contenido ilegal. Revisión urgente requerida:"
        elif result.severity == "flood":
            mention_prefix = "⚠️ **ALERTA DE FLOOD (@here)** — Ráfaga rápida o spam de mensajes repetidos detectado:"
        elif is_spam:
            mention_prefix = "⚠️ **ALERTA DE SPAM (@here)** — Usuario detectado enviando spam en múltiples canales:"

        try:
            await channel.send(content=mention_prefix or None, embed=embed)
        except discord.Forbidden:
            logger.warning(f"Sin permisos para enviar al canal de logs de mod ({log_channel_id})")

    # ------------------------------------------------------------------
    # Slash commands de configuración modular
    # ------------------------------------------------------------------

    mod_group = app_commands.Group(name="mod", description="Configuración granular de auto-moderación de Dalet.")

    @mod_group.command(name="setup", description="Configuración completa o activación inicial de moderación.")
    @app_commands.describe(
        log_channel="Canal donde se enviarán las alertas (opcional, default: canal actual).",
        action="Acción por defecto al detectar contenido adulto (NSFW).",
        timeout_minutes="Duración del timeout en modo 'timeout' (1-10080 min, default: 10).",
        auto_ban_on_illegal="Banear automáticamente al detectar contenido ilegal (default: False).",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def mod_setup(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel | None = None,
        action: Literal["notify", "timeout", "ban"] = "notify",
        timeout_minutes: int = 10,
        auto_ban_on_illegal: bool = False,
    ):
        await interaction.response.defer(ephemeral=True)
        target_channel = log_channel or interaction.channel

        await self.bot.admin_repo.update_moderation_config(
            server_id=interaction.guild_id,
            enabled=True,
            log_channel_id=target_channel.id,
            action=action,
            auto_ban_on_illegal=auto_ban_on_illegal,
            timeout_minutes=max(1, min(timeout_minutes, 10080)),
        )

        embed = discord.Embed(
            title=f"{DaletAtoms.EMOJI_DALET} Moderación activada y configurada",
            color=DaletAtoms.COLOR_SUCCESS,
        )
        embed.add_field(name="Canal de alertas", value=target_channel.mention, inline=True)
        embed.add_field(name="Acción NSFW", value=_ACTION_LABELS[action], inline=True)
        embed.add_field(name="Timeout", value=f"{timeout_minutes} min", inline=True)
        embed.add_field(name="Auto-ban ilegal", value="Sí" if auto_ban_on_illegal else "No", inline=True)
        DaletMolecules.add_standard_footer(embed, context_text="Admin • Usa /mod toggle para módulos específicos")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @mod_group.command(name="channel", description="Cambia solo el canal de alertas/logs de moderación.")
    @app_commands.describe(log_channel="Nuevo canal donde se enviarán los reportes.")
    @app_commands.checks.has_permissions(administrator=True)
    async def mod_channel(self, interaction: discord.Interaction, log_channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        await self.bot.admin_repo.update_moderation_config(
            server_id=interaction.guild_id,
            log_channel_id=log_channel.id,
            enabled=True,
        )
        await interaction.followup.send(f"✅ Canal de alertas de moderación actualizado a {log_channel.mention}.", ephemeral=True)

    @mod_group.command(name="action", description="Cambia la acción para contenido NSFW (notify, timeout o ban).")
    @app_commands.describe(action="Acción a aplicar al detectar contenido adulto.")
    @app_commands.checks.has_permissions(administrator=True)
    async def mod_action(self, interaction: discord.Interaction, action: Literal["notify", "timeout", "ban"]):
        await interaction.response.defer(ephemeral=True)
        await self.bot.admin_repo.update_moderation_config(
            server_id=interaction.guild_id,
            action=action,
        )
        await interaction.followup.send(f"✅ Acción por defecto para NSFW cambiada a: **{_ACTION_LABELS[action]}**.", ephemeral=True)

    @mod_group.command(name="timeout", description="Cambia la duración del timeout/aislamiento en minutos.")
    @app_commands.describe(minutes="Minutos de duración del timeout (1 a 10080).")
    @app_commands.checks.has_permissions(administrator=True)
    async def mod_timeout(self, interaction: discord.Interaction, minutes: int):
        await interaction.response.defer(ephemeral=True)
        minutes = max(1, min(minutes, 10080))
        await self.bot.admin_repo.update_moderation_config(
            server_id=interaction.guild_id,
            timeout_minutes=minutes,
        )
        await interaction.followup.send(f"✅ Duración de timeout actualizada a: **{minutes} minutos**.", ephemeral=True)

    @mod_group.command(name="toggle", description="Activa o desactiva módulos de moderación individualmente.")
    @app_commands.describe(
        module="Módulo a alternar: images (IA visión), flood (anti-spam), links (sitios adultos), scams (phishing/nitro).",
        enabled="Opcional: forzar True para activar o False para desactivar.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def mod_toggle(
        self,
        interaction: discord.Interaction,
        module: Literal["images", "flood", "links", "scams"],
        enabled: bool | None = None,
    ):
        await interaction.response.defer(ephemeral=True)
        cfg = await self.bot.admin_repo.get_moderation_config(interaction.guild_id)
        if not cfg:
            cfg = {
                "scan_images": True,
                "anti_flood": True,
                "filter_links": True,
                "filter_scams": True,
            }

        mod_map = {
            "images": ("scan_images", "🖼️ Escaneo de imágenes (IA)"),
            "flood": ("anti_flood", "🌊 Anti-Flood / Spam"),
            "links": ("filter_links", "🔗 Filtro de Enlaces Adultos"),
            "scams": ("filter_scams", "🎣 Anti-Phishing & Scams"),
        }
        col_name, display_name = mod_map[module]
        new_val = (not cfg.get(col_name, True)) if enabled is None else enabled

        await self.bot.admin_repo.update_moderation_config(
            server_id=interaction.guild_id,
            **{col_name: new_val}
        )

        state_str = "🟢 **Activado**" if new_val else "🔴 **Desactivado**"
        embed = discord.Embed(
            title=f"⚙️ Módulo {display_name}",
            description=f"El módulo {display_name} ahora está {state_str}.",
            color=DaletAtoms.COLOR_SUCCESS if new_val else DaletAtoms.COLOR_WARNING,
        )
        DaletMolecules.add_standard_footer(embed, context_text="Admin • /mod status para ver todos los módulos")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @mod_group.command(name="ignore", description="Gestiona canales y módulos específicos exentos de moderación.")
    @app_commands.describe(
        action="add (excluir módulo o canal), remove (re-incluir / vigilar), list (ver exenciones)",
        channel="Canal a ignorar o re-incluir (opcional si es list, default: canal actual)",
        module="Módulo a eximir: all (todo el canal), flood (anti-spam), images (visión IA), links (adultos), scams (phishing)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def mod_ignore(
        self,
        interaction: discord.Interaction,
        action: Literal["add", "remove", "list"],
        channel: discord.TextChannel | None = None,
        module: Literal["all", "flood", "images", "links", "scams"] = "all",
    ):
        await interaction.response.defer(ephemeral=True)
        server_id = interaction.guild_id

        if action == "list":
            cfg = await self.bot.admin_repo.get_moderation_config(server_id)
            ignored_map = cfg.get("ignored_channels_map", {}) if cfg else {}
            if not ignored_map:
                return await interaction.followup.send("ℹ️ No hay canales exentos de moderación.", ephemeral=True)

            lines = []
            for cid, mods in ignored_map.items():
                ch = interaction.guild.get_channel(cid)
                ch_str = ch.mention if ch else f"`#{cid}`"
                badges = ", ".join(_EXEMPT_MODULE_NAMES.get(m, m) for m in sorted(mods))
                lines.append(f"• {ch_str}: {badges}")

            embed = discord.Embed(
                title="🛡️ Canales y Módulos Exentos de Moderación",
                description="Los siguientes canales tienen reglas exentas configuradas:\n\n" + "\n".join(lines),
                color=DaletAtoms.COLOR_INFO,
            )
            DaletMolecules.add_standard_footer(embed, context_text="Admin • Usa /mod ignore add o remove")
            return await interaction.followup.send(embed=embed, ephemeral=True)

        target_ch = channel or interaction.channel
        if not isinstance(target_ch, discord.TextChannel):
            return await interaction.followup.send("❌ Debes especificar un canal de texto válido.", ephemeral=True)

        if action == "add":
            updated_map = await self.bot.admin_repo.add_ignored_channel_module(server_id, target_ch.id, module)
            current_mods = updated_map.get(target_ch.id, {module})
            mod_badges = ", ".join(_EXEMPT_MODULE_NAMES.get(m, m) for m in sorted(current_mods))
            module_desc = _EXEMPT_MODULE_NAMES.get(module, module)
            embed = discord.Embed(
                title="🛡️ Exención Añadida en Canal",
                description=(
                    f"Se ha añadido la exención de **{module_desc}** en {target_ch.mention}.\n\n"
                    f"**Exenciones activas en este canal:** {mod_badges}\n"
                    f"*(Dalet no aplicará esas reglas en {target_ch.mention})*"
                ),
                color=DaletAtoms.COLOR_SUCCESS,
            )
            DaletMolecules.add_standard_footer(embed, context_text="Admin • Usa /mod ignore list para ver todas")
            return await interaction.followup.send(embed=embed, ephemeral=True)

        elif action == "remove":
            updated_map = await self.bot.admin_repo.remove_ignored_channel_module(server_id, target_ch.id, module)
            remaining_mods = updated_map.get(target_ch.id, set())
            module_desc = _EXEMPT_MODULE_NAMES.get(module, module)

            if remaining_mods:
                rem_badges = ", ".join(_EXEMPT_MODULE_NAMES.get(m, m) for m in sorted(remaining_mods))
                desc = (
                    f"Se ha removido la exención de **{module_desc}** en {target_ch.mention}.\n\n"
                    f"**Exenciones restantes en este canal:** {rem_badges}"
                )
            else:
                desc = (
                    f"El canal {target_ch.mention} ya no tiene exenciones.\n"
                    f"Dalet volverá a vigilar y moderar todas las funciones en este canal con normalidad."
                )

            embed = discord.Embed(
                title="🛡️ Exención Removida de Canal",
                description=desc,
                color=DaletAtoms.COLOR_SUCCESS,
            )
            DaletMolecules.add_standard_footer(embed, context_text="Admin • Usa /mod status para ver la config")
            return await interaction.followup.send(embed=embed, ephemeral=True)

    @mod_group.command(name="off", description="Desactiva la auto-moderación en este servidor.")
    @app_commands.checks.has_permissions(administrator=True)
    async def mod_off(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        config = await self.bot.admin_repo.get_moderation_config(interaction.guild_id)
        if not config:
            return await interaction.followup.send("La moderación no estaba configurada.", ephemeral=True)

        await self.bot.admin_repo.update_moderation_config(
            server_id=interaction.guild_id,
            enabled=False,
        )
        await interaction.followup.send("🔇 Moderación desactivada. Usa `/mod setup` para reactivarla.", ephemeral=True)

    @mod_group.command(name="status", description="Muestra la configuración granular y módulos activos.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def mod_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        config = await self.bot.admin_repo.get_moderation_config(interaction.guild_id)

        embed = discord.Embed(title="🛡️ Estado de la Auto-Moderación", color=DaletAtoms.COLOR_INFO)

        if not config or not config["enabled"]:
            embed.description = "La auto-moderación está **desactivada** en este servidor.\nUsa `/mod setup` para activarla con un clic."
            return await interaction.followup.send(embed=embed, ephemeral=True)

        log_ch = interaction.guild.get_channel(config.get("log_channel_id") or 0)
        embed.add_field(name="Estado General", value="🟢 Activa", inline=True)
        embed.add_field(name="Canal de Alertas", value=log_ch.mention if log_ch else "⚠️ Sin canal", inline=True)
        embed.add_field(name="Acción Adulto (NSFW)", value=_ACTION_LABELS.get(config["action"], config["action"]), inline=True)
        embed.add_field(name="Duración Timeout", value=f"{config['timeout_minutes']} min", inline=True)
        embed.add_field(name="Auto-ban en Ilegal", value="Sí" if config["auto_ban_on_illegal"] else "No (Alertar)", inline=True)

        # Canales exentos
        ignored_map = config.get("ignored_channels_map", {})
        if ignored_map:
            lines = []
            for cid, mods in ignored_map.items():
                ch = interaction.guild.get_channel(cid)
                ch_str = ch.mention if ch else f"`#{cid}`"
                badges = ", ".join(_EXEMPT_MODULE_NAMES.get(m, m) for m in sorted(mods))
                lines.append(f"• {ch_str} ({badges})")
            exempt_str = "\n".join(lines)
        else:
            exempt_str = "Ninguno (todos vigilados)"
        embed.add_field(name="🛡️ Canales Exentos", value=exempt_str, inline=False)

        # Módulos granulares
        modules_lines = [
            f"{'🟢' if config.get('scan_images', True) else '🔴'} **Imágenes (IA Visión):** {'Activo' if config.get('scan_images', True) else 'Desactivado'}",
            f"{'🟢' if config.get('anti_flood', True) else '🔴'} **Anti-Flood / Ráfagas:** {'Activo' if config.get('anti_flood', True) else 'Desactivado'}",
            f"{'🟢' if config.get('filter_links', True) else '🔴'} **Filtro Enlaces Adultos:** {'Activo' if config.get('filter_links', True) else 'Desactivado'}",
            f"{'🟢' if config.get('filter_scams', True) else '🔴'} **Anti-Phishing & Scams:** {'Activo' if config.get('filter_scams', True) else 'Desactivado'}",
            "🛡️ **Protección Ilegal (CSAM):** 🟢 Siempre Activa",
        ]
        embed.add_field(name="🧩 Módulos Granulares", value="\n".join(modules_lines), inline=False)

        recent = await self.bot.admin_repo.get_recent_mod_actions(interaction.guild_id, limit=5)
        if recent:
            lines = [
                f"`{r['UserName']}` — {r['Severity']} — {r['ActionTaken']} ({r['OccurredAt'][:16]})"
                for r in recent
            ]
            embed.add_field(name="📋 Últimas acciones", value="\n".join(lines), inline=False)

        DaletMolecules.add_standard_footer(embed, context_text="Admin • Usa /mod toggle o /mod ignore")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @mod_setup.error
    @mod_channel.error
    @mod_action.error
    @mod_timeout.error
    @mod_toggle.error
    @mod_ignore.error
    @mod_off.error
    @mod_status.error
    async def mod_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Necesitas permisos de administrador.", ephemeral=True)
        else:
            logger.error(f"Error en comando /mod: {error}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error inesperado al procesar el comando.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
