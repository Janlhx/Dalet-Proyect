import os
import time
import datetime
import logging
import discord
from ui.atoms import DaletAtoms
from database.sqlite_manager import SQLiteManager

logger = logging.getLogger("dalet.services.feedback")


class FeedbackService:
    """Service to dispatch user feedback directly to the bot owner/developer via DM and persist it."""

    COOLDOWN_SECONDS: int = 300  # 5 minutos de cooldown anti-spam
    _cooldowns: dict[int, float] = {}

    @classmethod
    def get_remaining_cooldown(cls, user_id: int) -> int:
        """Returns remaining cooldown in seconds for a user based on memory cache."""
        now = time.time()
        last_time = cls._cooldowns.get(user_id, 0.0)
        remaining = int(cls.COOLDOWN_SECONDS - (now - last_time))
        return max(0, remaining)

    @classmethod
    async def check_user_cooldown(cls, user_id: int) -> int:
        """Verifica cooldown en memoria y en SQLite para que persista incluso tras reinicios."""
        mem_rem = cls.get_remaining_cooldown(user_id)
        if mem_rem > 0:
            return mem_rem

        try:
            feedbacks = await SQLiteManager.fetch_all(
                "SELECT CreatedAt FROM Feedbacks WHERE UserID = ? ORDER BY CreatedAt DESC LIMIT 1",
                user_id
            )
            if feedbacks and feedbacks[0] and feedbacks[0][0]:
                raw_time = str(feedbacks[0][0])
                # SQLite CURRENT_TIMESTAMP is UTC: YYYY-MM-DD HH:MM:SS
                dt = datetime.datetime.fromisoformat(raw_time).replace(tzinfo=datetime.timezone.utc)
                diff = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds()
                if diff < cls.COOLDOWN_SECONDS:
                    rem = int(cls.COOLDOWN_SECONDS - diff)
                    cls._cooldowns[user_id] = time.time() - diff
                    return max(0, rem)
        except Exception:
            pass
        return 0

    @classmethod
    async def send_feedback(
        cls,
        bot,
        author: discord.User | discord.Member,
        content: str,
        guild: discord.Guild | None = None,
        channel: discord.abc.GuildChannel | None = None
    ) -> bool:
        """Sends a private DM to the application owner and saves feedback into SQLite."""
        # 1. Guardar siempre en SQLite para consulta en Dashboard
        try:
            avatar_url = author.display_avatar.url if author.display_avatar else ""
            await SQLiteManager.save_feedback(
                user_id=author.id,
                user_name=str(author.name),
                user_avatar=avatar_url,
                server_id=guild.id if guild else None,
                server_name=guild.name if guild else "Direct Message",
                channel_id=channel.id if channel else None,
                channel_name=channel.name if channel and hasattr(channel, "name") else "DM",
                content=content
            )
            cls._cooldowns[author.id] = time.time()
        except Exception as e:
            logger.error(f"Error persistiendo feedback en SQLite: {e}")
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
