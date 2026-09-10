"""
Handler de Eventos Globales de Discord.
Maneja: on_ready, on_command_error, on_guild_join.
"""
from discord.ext import commands
import discord
import logging
import traceback

logger = logging.getLogger("dalet.handlers.events")


class EventsHandler(commands.Cog):
    """Agrupa los listeners de eventos globales del bot."""

    def __init__(self, bot):
        self.bot = bot

    # -------------------------------------------------------------------------
    # on_ready
    # -------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_ready(self):
        """Se ejecuta cuando el bot está listo y conectado."""
        from ui.atoms import DaletAtoms
        await self.bot.tree.sync()
        logger.info(f"Bot conectado como {self.bot.user} (ID: {self.bot.user.id})")

        # Configuración de Presencia en Discord
        status_text = getattr(self.bot, "custom_status", f"{DaletAtoms.VERSION} • searching who asked │ d.help")
        try:
            await self.bot.change_presence(activity=discord.CustomActivity(name=status_text))
        except Exception:
            await self.bot.change_presence(activity=discord.Game(name=status_text))

    # -------------------------------------------------------------------------
    # on_command_error
    # -------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Manejo global de errores de comandos."""
        if isinstance(error, commands.CommandNotFound):
            # No responder a prefijos de otros bots
            if ctx.message.content.startswith(("!", "/", ".")):
                return
            await ctx.send("ese comando no lo tengo")

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"te faltan argumentos. revisa con `d.help {ctx.command.name}`"
            )

        elif isinstance(error, (commands.NotOwner, commands.MissingPermissions)):
            await ctx.send("no tienes permisos para hacer eso")

        elif isinstance(error, commands.CommandInvokeError):
            original = getattr(error, "original", error)
            if isinstance(original, discord.HTTPException) and original.status == 429:
                logger.warning(
                    f"Rate limit 429 en comando '{ctx.command}'. Throttle activo."
                )
                return
            logger.error(f"Error en comando '{ctx.command}': {error}")
            traceback.print_exc()

        else:
            logger.error(f"Error inesperado en comando: {error}")
            traceback.print_exc()

    # -------------------------------------------------------------------------
    # on_guild_join
    # -------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Envía una presentación y guía interactiva cuando el bot entra a un servidor nuevo."""
        from ui.atoms import DaletAtoms
        from ui.molecules import DaletMolecules

        # Búsqueda inteligente del canal más adecuado
        target_channel = guild.system_channel
        if not target_channel or not target_channel.permissions_for(guild.me).send_messages:
            priority_names = ["general", "chat", "bot", "bots", "comandos", "main"]
            candidates = [c for c in guild.text_channels if c.permissions_for(guild.me).send_messages]
            target_channel = None
            for name in priority_names:
                for c in candidates:
                    if name in c.name.lower():
                        target_channel = c
                        break
                if target_channel:
                    break
            if not target_channel and candidates:
                target_channel = candidates[0]

        if not target_channel:
            return

        embed = discord.Embed(
            title=f"{DaletAtoms.EMOJI_DALET} Thanks for adding Dalet to {guild.name}!",
            description=(
                f'> *"searching who asked"*\n\n'
                f"Hello! I am **Dalet {DaletAtoms.VERSION}** — your high-precision **osu! analytics companion**, "
                f"cynical conversational AI, and community utility bot.\n\n"
                f"Here is a quick guide to get started in your server:"
            ),
            color=DaletAtoms.COLOR_PRIMARY
        )

        if self.bot.user and self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        embed.add_field(
            name="🎮 osu! Analytics & Skill Radar",
            value=(
                f"• `/link <user>` {DaletAtoms.GLYPH_POINTER} Link your Discord account to your osu! profile\n"
                f"• `/skills [user]` {DaletAtoms.GLYPH_POINTER} 5-dimension radar (Aim, Speed, Acc, Stamina, Reading)\n"
                f"• `/recent` & `/top` {DaletAtoms.GLYPH_POINTER} Detailed score breakdown with PP, UR & star rating\n"
                f"• `/op [user]` {DaletAtoms.GLYPH_POINTER} Full profile overview, global rank, and statistics"
            ),
            inline=False
        )

        embed.add_field(
            name="🤖 Conversational AI & Lore",
            value=(
                f"• `@Dalet <message>` {DaletAtoms.GLYPH_POINTER} Chat directly with Dalet in any channel\n"
                f"• `/resumir` {DaletAtoms.GLYPH_POINTER} Instant smart AI digest of recent channel conversations\n"
                f"• `/lore <topic>` {DaletAtoms.GLYPH_POINTER} Search server chat history archives with cynical AI commentary"
            ),
            inline=False
        )

        embed.add_field(
            name="⚙️ Administration & Language",
            value=(
                f"• `/language [en/es]` {DaletAtoms.GLYPH_POINTER} Switch between English (default) and Español\n"
                f"• `/lock` & `/unlock` {DaletAtoms.GLYPH_POINTER} Restrict or allow Dalet interactions in specific channels\n"
                f"• `/proactive` {DaletAtoms.GLYPH_POINTER} Toggle proactive AI conversation in a channel\n"
                f"• `/setwelcome` {DaletAtoms.GLYPH_POINTER} Configure the welcome channel for new members"
            ),
            inline=False
        )

        embed.add_field(
            name="📬 Feedback & Developer Contact",
            value=(
                f"• `/feedback <message>` {DaletAtoms.GLYPH_POINTER} Send suggestions, bug reports, or ideas directly to the developer\n"
                f"• `/help` or `d.help` {DaletAtoms.GLYPH_POINTER} Open the interactive categorized command guide"
            ),
            inline=False
        )

        DaletMolecules.add_standard_footer(
            embed,
            context_text=f"Dalet v{DaletAtoms.VERSION} │ Litxe • Prefix: d. or /"
        )

        view = GuildJoinView(self.bot)

        try:
            await target_channel.send(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Error enviando bienvenida en {guild.name}: {e}")


# ─── Vista interactiva para nuevos servidores ────────────────────────────────

class GuildJoinView(discord.ui.View):
    """Botones interactivos adjuntos al mensaje de presentación de bienvenida."""

    def __init__(self, bot):
        super().__init__(timeout=86400)  # 24 horas
        self.bot = bot

    @discord.ui.button(label="🌐 Cambiar a Español", style=discord.ButtonStyle.secondary, custom_id="guild_join_lang_es")
    async def switch_lang_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Solo administradores del servidor pueden cambiar la configuración de idioma.",
                ephemeral=True
            )
        try:
            await self.bot.admin_repo.set_server_language(interaction.guild_id, "es")
            button.disabled = True
            button.label = "✅ Idioma: Español"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(
                "¡Listo! El idioma de Dalet en este servidor ha sido configurado en **Español**.\n"
                "Usa `/help` o `d.help` para explorar los comandos en español.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error cambiando idioma desde botón de bienvenida: {e}")
            await interaction.response.send_message("❌ Error configurando el idioma.", ephemeral=True)

    @discord.ui.button(label="📖 Command Guide / Guía", style=discord.ButtonStyle.primary, custom_id="guild_join_help")
    async def help_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from handlers.dalet_helpcommands_handlers import build_help_pages, HelpPaginator
        server_lang = "en"
        if interaction.guild_id and hasattr(self.bot, "admin_repo"):
            server_lang = await self.bot.admin_repo.get_server_language(interaction.guild_id)
        pages, cat_names = build_help_pages(self.bot, interaction.user, server_lang=server_lang)
        view = HelpPaginator(pages, cat_names, lang=server_lang)
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(EventsHandler(bot))