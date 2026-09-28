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

_SEVERITY_LABELS = {"adult": "Contenido adulto/NSFW", "illegal": "Contenido ilegal (CP/CSAM)"}
_SEVERITY_COLORS = {"adult": DaletAtoms.COLOR_WARNING, "illegal": DaletAtoms.COLOR_ERROR}
_ACTION_LABELS   = {"notify": "Notificar", "timeout": "Timeout", "ban": "Ban"}


class ModerationCog(commands.Cog, name="Moderación"):
    """Auto-moderación de contenido NSFW e ilegal. Opt-in por servidor."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._mod_service: ModerationService | None = None

    async def cog_load(self):
        nlp = getattr(self.bot, "nlp_service", None)
        self._mod_service = ModerationService(nlp)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        config = await self.bot.admin_repo.get_moderation_config(message.guild.id)
        if not config or not config["enabled"]:
            return

        image_urls = ModerationService.extract_image_urls(message)
        result = await self._mod_service.scan_message(message.content or "", image_urls)

        if not result.flagged:
            return

        is_spam = self._mod_service.track_flag(message.author.id, message.channel.id)
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
        except discord.Forbidden:
            logger.warning(f"[MOD] Sin permisos (Manage Messages) para borrar mensaje {message.id} en #{message.channel.name}")
        except discord.NotFound:
            pass

        action = "notify"
        if result.severity == "illegal" and config["auto_ban_on_illegal"]:
            action = "ban"
        elif is_cross_channel_spam or config["action"] in ("timeout", "ban"):
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
        if action == "ban":
            try:
                await guild.ban(member, reason=f"Auto-mod: {severity}", delete_message_days=1)
                return "banned"
            except discord.Forbidden:
                logger.warning(f"Sin permisos para banear a {member} en {guild}")
                return "ban_failed"

        if action == "timeout":
            try:
                await member.timeout(
                    timedelta(minutes=timeout_minutes),
                    reason=f"Auto-mod: {severity}",
                )
                return f"timeout_{timeout_minutes}m"
            except discord.Forbidden:
                logger.warning(f"Sin permisos para timeout a {member} en {guild}")
                return "timeout_failed"

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

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning(f"Sin permisos para enviar al canal de logs de mod ({log_channel_id})")

    # ------------------------------------------------------------------
    # Slash commands de configuración
    # ------------------------------------------------------------------

    mod_group = app_commands.Group(name="mod", description="Configuración de auto-moderación de Dalet.")

    @mod_group.command(name="setup", description="Activa la moderación y configura el canal de logs.")
    @app_commands.describe(
        log_channel="Canal donde se enviarán los reportes de moderación.",
        action="Acción por defecto al detectar contenido adulto (NSFW).",
        timeout_minutes="Duración del timeout en modo 'timeout' (default: 10).",
        auto_ban_on_illegal="Banear automáticamente al detectar contenido ilegal/CP.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def mod_setup(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel,
        action: Literal["notify", "timeout", "ban"] = "notify",
        timeout_minutes: int = 10,
        auto_ban_on_illegal: bool = True,
    ):
        await interaction.response.defer(ephemeral=True)

        await self.bot.admin_repo.set_moderation_config(
            server_id=interaction.guild_id,
            enabled=True,
            log_channel_id=log_channel.id,
            action=action,
            auto_ban_on_illegal=auto_ban_on_illegal,
            timeout_minutes=max(1, min(timeout_minutes, 10080)),
        )

        embed = discord.Embed(
            title=f"{DaletAtoms.EMOJI_DALET} Moderación activada",
            color=DaletAtoms.COLOR_SUCCESS,
        )
        embed.add_field(name="Canal de logs", value=log_channel.mention, inline=True)
        embed.add_field(name="Acción NSFW", value=_ACTION_LABELS[action], inline=True)
        embed.add_field(name="Timeout", value=f"{timeout_minutes} min", inline=True)
        embed.add_field(name="Auto-ban en CP/ilegal", value="Sí" if auto_ban_on_illegal else "No", inline=True)
        DaletMolecules.add_standard_footer(embed, context_text="Admin")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @mod_group.command(name="off", description="Desactiva la auto-moderación en este servidor.")
    @app_commands.checks.has_permissions(administrator=True)
    async def mod_off(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        config = await self.bot.admin_repo.get_moderation_config(interaction.guild_id)
        if not config:
            return await interaction.followup.send("La moderación no estaba configurada.", ephemeral=True)

        await self.bot.admin_repo.set_moderation_config(
            server_id=interaction.guild_id,
            enabled=False,
            log_channel_id=config["log_channel_id"],
            action=config["action"],
            auto_ban_on_illegal=config["auto_ban_on_illegal"],
            timeout_minutes=config["timeout_minutes"],
        )
        await interaction.followup.send("🔇 Moderación desactivada. Usa `/mod setup` para reactivarla.", ephemeral=True)

    @mod_group.command(name="status", description="Muestra la configuración actual y las últimas acciones.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def mod_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        config = await self.bot.admin_repo.get_moderation_config(interaction.guild_id)

        embed = discord.Embed(title="🛡️ Estado de la Moderación", color=DaletAtoms.COLOR_INFO)

        if not config or not config["enabled"]:
            embed.description = "La auto-moderación está **desactivada**. Usa `/mod setup` para activarla."
            return await interaction.followup.send(embed=embed, ephemeral=True)

        log_ch = interaction.guild.get_channel(config["log_channel_id"])
        embed.add_field(name="Estado", value="✅ Activa", inline=True)
        embed.add_field(name="Canal de logs", value=log_ch.mention if log_ch else "Sin canal", inline=True)
        embed.add_field(name="Acción NSFW", value=_ACTION_LABELS.get(config["action"], config["action"]), inline=True)
        embed.add_field(name="Auto-ban ilegal", value="Sí" if config["auto_ban_on_illegal"] else "No", inline=True)
        embed.add_field(name="Timeout", value=f"{config['timeout_minutes']} min", inline=True)

        recent = await self.bot.admin_repo.get_recent_mod_actions(interaction.guild_id, limit=5)
        if recent:
            lines = [
                f"`{r['UserName']}` — {r['Severity']} — {r['ActionTaken']} ({r['OccurredAt'][:16]})"
                for r in recent
            ]
            embed.add_field(name="Últimas acciones", value="\n".join(lines), inline=False)

        DaletMolecules.add_standard_footer(embed, context_text="Admin")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @mod_setup.error
    @mod_off.error
    @mod_status.error
    async def mod_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Necesitas permisos de administrador.", ephemeral=True)
        else:
            logger.error(f"Error en comando /mod: {error}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Error inesperado.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
