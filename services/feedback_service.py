import os
import logging
import discord
from ui.atoms import DaletAtoms

logger = logging.getLogger("dalet.services.feedback")


class FeedbackService:
    """Service to dispatch user feedback directly to the bot owner/developer via DM."""

    @staticmethod
    async def send_feedback(
        bot,
        author: discord.User | discord.Member,
        content: str,
        guild: discord.Guild | None = None,
        channel: discord.abc.GuildChannel | None = None
    ) -> bool:
        """Sends a private DM to the application owner with formatted feedback."""
        owner = None

        # 1. Check bot.owner_id
        if getattr(bot, "owner_id", None):
            owner = bot.get_user(bot.owner_id)
            if not owner:
                try:
                    owner = await bot.fetch_user(bot.owner_id)
                except Exception:
                    pass

        # 2. Check application info
        if not owner:
            try:
                app_info = await bot.application_info()
                target_user_id = None
                if app_info.team:
                    if app_info.team.owner:
                        target_user_id = app_info.team.owner.id
                    elif app_info.team.members:
                        target_user_id = app_info.team.members[0].id
                elif app_info.owner:
                    target_user_id = app_info.owner.id

                if target_user_id:
                    owner = bot.get_user(target_user_id) or await bot.fetch_user(target_user_id)
            except Exception as e:
                logger.error(f"Error resolving bot application owner: {e}")

        # 3. Fallback to OWNER_ID in environment
        if not owner and os.getenv("OWNER_ID"):
            try:
                owner = await bot.fetch_user(int(os.getenv("OWNER_ID")))
            except Exception as e:
                logger.error(f"Error fetching owner from OWNER_ID: {e}")

        if not owner:
            logger.error("Could not find any owner to deliver feedback DM.")
            return False

        try:
            embed = discord.Embed(
                title="📬 Nuevo Feedback / New Feedback",
                description=content,
                color=DaletAtoms.COLOR_PRIMARY,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(
                name="Autor / Author",
                value=f"{author.mention} (`{author.name}` • ID: `{author.id}`)",
                inline=False
            )
            guild_info = f"{guild.name} (ID: `{guild.id}`)" if guild else "Direct Message (DM)"
            embed.add_field(name="Servidor / Server", value=guild_info, inline=False)
            if channel and hasattr(channel, "mention"):
                embed.add_field(
                    name="Canal / Channel",
                    value=f"{channel.mention} (`#{channel.name}`)",
                    inline=False
                )
            if author.display_avatar:
                embed.set_thumbnail(url=author.display_avatar.url)
            embed.set_footer(text=f"Dalet Feedback Dispatcher │ v{DaletAtoms.VERSION}")

            dm_channel = await owner.create_dm()
            await dm_channel.send(
                content=f"🔔 {owner.mention}, ¡has recibido un nuevo feedback de un usuario!",
                embed=embed
            )
            return True
        except Exception as e:
            logger.error(f"Failed to deliver feedback DM to {owner}: {e}")
            return False
