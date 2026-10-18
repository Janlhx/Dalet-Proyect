"""
Handler (Cog) para el Comando de Ayuda Personalizado de Dalet.

Sistema interactivo y paginado con botones, categorías de slash commands,
comandos de prefijo y un banner visual en la portada.
"""
import os
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
from ui.organisms import DaletOrganisms
from ui.molecules import DaletMolecules
from ui.atoms import DaletAtoms

# ─── URL pública del banner (Dibujo original en Paint de Dalet) ──────────────
BANNER_URL: str | None = "https://raw.githubusercontent.com/Janlhx/Dalet-Proyect/main/assets/bannersito.png"
BANNER_FILE_PATH = "assets/bannersito.png"

# ─── Definición de categorías del menú ──────────────────────────────────────

# Spanish categories
SLASH_CATEGORIES_ES = {
    "osu!": {
        "color": discord.Color.from_rgb(255, 94, 158),  # #FF5E9E Rosa osu!
        "card_desc": "Perfil, plays y radar 5D.\n`/op` `/recent` `/top`",
        "subtitle": "Estadísticas y comparativas para los 4 modos de juego.",
        "commands": [
            ("/op",               "Perfil general, rango y PP"),
            ("/skills",           "Radar de habilidades y veredicto"),
            ("/recent",           "Última jugada (incluye fails)"),
            ("/top",              "Top 5 mejores jugadas"),
            ("/compare",          "Comparativa entre 2 jugadores"),
            ("/rank",             "Ranking del servidor"),
            ("/link",             "Vincular tu cuenta de osu!"),
        ]
    },
    "IA & Chat": {
        "color": discord.Color.from_rgb(139, 92, 246),  # #8B5CF6 Violeta Amatista
        "card_desc": "Charla, resúmenes y lore.\n`@Dalet` `/resumir` `/lore`",
        "subtitle": "Conversación con Dalet, memoria del canal y búsqueda web.",
        "commands": [
            ("@Dalet / Dalet",    "Habla con Dalet o pídele buscar algo"),
            ("/resumir",          "Resumen rápido de lo hablado en el canal"),
            ("/lore",             "Busca momentos o temas pasados del chat"),
            ("/proactive",        "`Admin` Activa respuestas espontáneas en el canal"),
            ("/reactive",         "`Admin` Activa o pausa respuestas al mencionarla"),
        ]
    },
    "Servidor": {
        "color": discord.Color.from_rgb(56, 189, 248),  # #38BDF8 Cyan Cielo
        "card_desc": "Info, actividad y buzón.\n`/info` `/stats` `/feedback`",
        "subtitle": "Información del bot, actividad social y sugerencias.",
        "commands": [
            ("/info",             "Estado y versión actual de Dalet"),
            ("/changelog",        "Últimas novedades y cambios"),
            ("/stats",            "Actividad de mensajes de un usuario"),
            ("/userinfo",         "Datos y antigüedad de una cuenta"),
            ("/serverinfo",       "Información general del servidor"),
            ("/ping",             "Latencia del bot en milisegundos"),
            ("/feedback",         "Envía sugerencias o bugs en privado a Litxe"),
        ]
    },
    "Recordatorios": {
        "color": discord.Color.from_rgb(251, 191, 36),  # #FBBF24 Ámbar Dorado
        "card_desc": "Alarmas y avisos.\n`/reminder add` `list`",
        "subtitle": "Avisos programables por hora, días o fecha exacta.",
        "commands": [
            ("/reminder add",     "Crear un recordatorio nuevo"),
            ("/reminder list",    "Ver tus recordatorios activos"),
            ("/reminder edit",    "Cambiar hora, mensaje o días"),
            ("/reminder toggle",  "Pausar o reactivar un aviso"),
            ("/reminder remove",  "Borrar un recordatorio"),
        ]
    },
    "Moderación": {
        "color": discord.Color.from_rgb(16, 185, 129),  # #10B981 Esmeralda Seguridad
        "card_desc": "Filtro NSFW, anti-scam y flood.\n`/mod setup` `status`",
        "subtitle": "Protección automática del servidor.",
        "commands": [
            ("/mod setup",        "`Admin` Configuración rápida de moderación"),
            ("/mod status",       "Ver módulos activos y estado actual"),
            ("/mod toggle",       "`Admin` Encender o apagar un filtro"),
            ("/mod ignore",       "`Admin` Eximir un canal de la moderación"),
            ("/mod action",       "`Admin` Castigo por defecto (`notify`, `timeout`, `ban`)"),
            ("/mod timeout",      "`Admin` Duración del aislamiento en minutos"),
            ("/mod channel",      "`Admin` Canal para alertas de moderación"),
            ("/mod off",          "`Admin` Apagar toda la auto-moderación"),
        ]
    },
    "Admin": {
        "color": discord.Color.from_rgb(244, 63, 94),   # #F43F5E Carmesí Admin
        "card_desc": "Idioma, bienvenida y canales.\n`/language` `/lock`",
        "subtitle": "Ajustes generales del servidor.",
        "commands": [
            ("/language",         "Cambiar idioma (`es` / `en`)"),
            ("/setname",          "Cambiar el apodo al que responde Dalet"),
            ("/setwelcome",       "Definir canal de bienvenidas"),
            ("/removewelcome",    "Desactivar mensajes de bienvenida"),
            ("/lock",             "Bloquear comandos de Dalet en este canal"),
            ("/unlock",           "Desbloquear comandos en este canal"),
        ]
    },
}

# English categories (Default)
SLASH_CATEGORIES_EN = {
    "osu!": {
        "color": discord.Color.from_rgb(255, 94, 158),  # #FF5E9E osu! Pink
        "card_desc": "Profiles, plays & 5D radar.\n`/op` `/recent` `/top`",
        "subtitle": "Stats and comparisons across all 4 game modes.",
        "commands": [
            ("/op",               "Profile card, rank, and PP"),
            ("/skills",           "5D skill radar and Dalet's verdict"),
            ("/recent",           "Most recent play (includes fails)"),
            ("/top",              "Top 5 best scores"),
            ("/compare",          "Compare 2 players head-to-head"),
            ("/rank",             "Server osu! leaderboard"),
            ("/link",             "Link your osu! account"),
        ]
    },
    "AI & Chat": {
        "color": discord.Color.from_rgb(139, 92, 246),  # #8B5CF6 Amethyst Violet
        "card_desc": "Chat, digests & channel lore.\n`@Dalet` `/resumir` `/lore`",
        "subtitle": "Chat with Dalet, channel memory, and web search.",
        "commands": [
            ("@Dalet / Dalet",    "Chat with Dalet or ask her to search the web"),
            ("/resumir",          "Quick summary of recent channel chat"),
            ("/lore",             "Search past topics and server moments"),
            ("/proactive",        "`Admin` Toggle spontaneous replies in this channel"),
            ("/reactive",         "`Admin` Toggle replies when mentioned"),
        ]
    },
    "Server": {
        "color": discord.Color.from_rgb(56, 189, 248),  # #38BDF8 Sky Cyan
        "card_desc": "Bot info, stats & feedback.\n`/info` `/stats` `/feedback`",
        "subtitle": "Bot status, member activity, and feedback.",
        "commands": [
            ("/info",             "Dalet's status and current version"),
            ("/changelog",        "Latest updates and release notes"),
            ("/stats",            "Message activity for a member"),
            ("/userinfo",         "Account and join details"),
            ("/serverinfo",       "Server overview and member count"),
            ("/ping",             "Bot latency in milliseconds"),
            ("/feedback",         "Send private suggestions or bugs to Litxe"),
        ]
    },
    "Reminders": {
        "color": discord.Color.from_rgb(251, 191, 36),  # #FBBF24 Amber Gold
        "card_desc": "Scheduled alerts & alarms.\n`/reminder add` `list`",
        "subtitle": "Custom alerts by time, weekday, or date.",
        "commands": [
            ("/reminder add",     "Create a new reminder"),
            ("/reminder list",    "View your active reminders"),
            ("/reminder edit",    "Edit time, message, or days"),
            ("/reminder toggle",  "Pause or resume a reminder"),
            ("/reminder remove",  "Delete a reminder"),
        ]
    },
    "Moderation": {
        "color": discord.Color.from_rgb(16, 185, 129),  # #10B981 Safety Emerald
        "card_desc": "NSFW, anti-scam & flood filter.\n`/mod setup` `status`",
        "subtitle": "Automated server protection.",
        "commands": [
            ("/mod setup",        "`Admin` Quick auto-moderation setup"),
            ("/mod status",       "View active filters and status"),
            ("/mod toggle",       "`Admin` Enable or disable a filter"),
            ("/mod ignore",       "`Admin` Exempt a channel from moderation"),
            ("/mod action",       "`Admin` Default penalty (`notify`, `timeout`, `ban`)"),
            ("/mod timeout",      "`Admin` Timeout duration in minutes"),
            ("/mod channel",      "`Admin` Channel for moderation alerts"),
            ("/mod off",          "`Admin` Disable all auto-moderation"),
        ]
    },
    "Admin": {
        "color": discord.Color.from_rgb(244, 63, 94),   # #F43F5E Admin Crimson
        "card_desc": "Language, welcome & locks.\n`/language` `/lock`",
        "subtitle": "General server settings.",
        "commands": [
            ("/language",         "Change bot language (`es` / `en`)"),
            ("/setname",          "Change the nickname Dalet responds to"),
            ("/setwelcome",       "Set the welcome message channel"),
            ("/removewelcome",    "Disable welcome messages"),
            ("/lock",             "Lock Dalet commands in this channel"),
            ("/unlock",           "Unlock commands in this channel"),
        ]
    },
}

# Default backwards-compatible alias
SLASH_CATEGORIES = SLASH_CATEGORIES_EN


# ─── Modal para saltar a página ──────────────────────────────────────────────

class PageInputModal(Modal):
    """Modal emergente que pide un número de categoría."""
    def __init__(self, pages_view, lang: str = "en"):
        self.pages_view = pages_view
        self.lang = lang
        title = "Ir a Categoría" if lang == "es" else "Go to Category"
        super().__init__(title=title)
        total = len(self.pages_view.pages) - 1
        label = "Número de Categoría" if lang == "es" else "Category Number"
        ph = f"Escribe el número (1-{total})" if lang == "es" else f"Enter number (1-{total})"
        self.page_number = TextInput(
            label=label,
            placeholder=ph,
            required=True,
            max_length=2,
        )
        self.add_item(self.page_number)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            num = int(self.page_number.value)
            total = len(self.pages_view.pages) - 1
            if 1 <= num <= total:
                self.pages_view.index = num
                await self.pages_view.update_page(interaction)
            else:
                err_msg = f"Número fuera de rango. Usa entre 1 y {total}." if self.lang == "es" else f"Out of range. Please enter 1 to {total}."
                await interaction.response.send_message(err_msg, ephemeral=True)
        except ValueError:
            err_val = "Eso no es un número válido." if self.lang == "es" else "That is not a valid number."
            await interaction.response.send_message(err_val, ephemeral=True)


# ─── Select menu de categorías ───────────────────────────────────────────────

class CategorySelect(Select):
    """Menú desplegable para saltar directamente a una categoría."""
    def __init__(self, pages_view, category_names: list[str], lang: str = "en"):
        self.pages_view = pages_view
        self.lang = lang
        home_lbl = "Portada" if lang == "es" else "Overview"
        home_desc = "Volver a la portada principal" if lang == "es" else "Return to main overview"
        placeholder = "Ir a una categoría..." if lang == "es" else "Select a category..."
        options = [
            discord.SelectOption(label=home_lbl, value="0", description=home_desc)
        ]
        for i, name in enumerate(category_names, start=1):
            desc = f"Ver comandos de {name}" if lang == "es" else f"View {name} commands"
            options.append(
                discord.SelectOption(label=name, value=str(i), description=desc)
            )
        super().__init__(
            placeholder=placeholder,
            options=options,
            custom_id="help_category_select"
        )

    async def callback(self, interaction: discord.Interaction):
        self.pages_view.index = int(self.values[0])
        await self.pages_view.update_page(interaction)


# ─── Vista principal del paginador ───────────────────────────────────────────

class HelpPaginator(View):
    """Vista con botones de navegación y select menu de categorías."""
    def __init__(self, pages: list[discord.Embed], category_names: list[str], lang: str = "en"):
        super().__init__(timeout=300)
        self.pages = pages
        self.index = 0
        self.lang = lang
        # Configurar etiquetas de botones según idioma
        if lang == "es":
            self.previous_button.label = "Anterior"
            self.home_button.label = "Portada"
            self.goto_button.label = "Ir a..."
            self.next_button.label = "Siguiente"
        else:
            self.previous_button.label = "Previous"
            self.home_button.label = "Overview"
            self.goto_button.label = "Go to..."
            self.next_button.label = "Next"

        # Añadir select menu dinámico
        self.select = CategorySelect(self, category_names, lang=lang)
        self.add_item(self.select)
        self.update_buttons()

    def update_buttons(self):
        self.previous_button.disabled = self.index == 0
        self.home_button.disabled = self.index == 0
        self.next_button.disabled = self.index == len(self.pages) - 1

    async def update_page(self, interaction: discord.Interaction):
        self.update_buttons()
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=self.pages[self.index], view=self)
        else:
            await interaction.edit_original_response(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.grey, row=1)
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        if self.index > 0:
            self.index -= 1
            await self.update_page(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Portada", style=discord.ButtonStyle.blurple, row=1)
    async def home_button(self, interaction: discord.Interaction, button: Button):
        self.index = 0
        await self.update_page(interaction)

    @discord.ui.button(label="Ir a...", style=discord.ButtonStyle.green, row=1)
    async def goto_button(self, interaction: discord.Interaction, button: Button):
        modal = PageInputModal(self, lang=self.lang)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Siguiente", style=discord.ButtonStyle.grey, row=1)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if self.index < len(self.pages) - 1:
            self.index += 1
            await self.update_page(interaction)
        else:
            await interaction.response.defer()

    async def on_timeout(self):
        """Deshabilitar todos los componentes al vencer el timeout."""
        for item in self.children:
            item.disabled = True


# ─── Help Command ─────────────────────────────────────────────────────────────

# ─── Constructor de páginas de ayuda ─────────────────────────────────────────

def build_help_pages(bot, user, server_lang: str = "en") -> tuple[list[discord.Embed], list[str]]:
    """Construye las páginas del menú de ayuda según el idioma del servidor."""
    categories = SLASH_CATEGORIES_ES if server_lang == "es" else SLASH_CATEGORIES_EN
    pages = []
    category_names = []

    # 1. Páginas de slash commands por categoría
    for cat_name, cat_data in categories.items():
        category_names.append(cat_name)
        embed = discord.Embed(
            title=cat_name,
            color=cat_data["color"],
        )
        subtitle = cat_data.get("subtitle", "")
        header = f"*{subtitle}*\n\n" if subtitle else ""
        cmd_lines = [
            f"{DaletAtoms.GLYPH_POINTER} **`{cmd}`** — {desc}"
            for cmd, desc in cat_data["commands"]
        ]
        embed.description = header + "\n".join(cmd_lines)

        footer_txt = (
            f"Dalet · Página {len(pages)+1} de {len(categories)}  │  Escribe / para autocompletar"
            if server_lang == "es"
            else f"Dalet · Page {len(pages)+1} of {len(categories)}  │  Type / to autocomplete"
        )
        embed.set_footer(
            text=footer_txt,
            icon_url=bot.user.avatar.url if bot.user and bot.user.avatar else None
        )
        pages.append(embed)

    # 2. Portada en cuadrícula 3x2 (inline=True)
    version = DaletAtoms.VERSION
    if server_lang == "es":
        portada_desc = (
            f"Hola, **{user.display_name}**. Soy **Dalet {version}**.\n"
            f"Elige una categoría en el menú de abajo para ver sus comandos:"
        )
        footer_cover = f"Dalet {version}  │  /changelog • /feedback"
    else:
        portada_desc = (
            f"Hello, **{user.display_name}**. I'm **Dalet {version}**.\n"
            f"Pick a category from the menu below to see its commands:"
        )
        footer_cover = f"Dalet {version}  │  /changelog • /feedback"

    portada = discord.Embed(
        title=f"{DaletAtoms.EMOJI_DALET} Dalet {version} {DaletAtoms.GLYPH_PIPE} {'Guía de Comandos' if server_lang == 'es' else 'Command Guide'}",
        description=portada_desc,
        color=DaletAtoms.COLOR_PRIMARY,
    )
    for i, name in enumerate(category_names, start=1):
        card_text = categories[name].get("card_desc", categories[name].get("subtitle", ""))
        portada.add_field(
            name=f"`{i}.` {name}",
            value=card_text,
            inline=True,
        )

    portada.set_footer(
        text=footer_cover,
        icon_url=bot.user.avatar.url if bot.user and bot.user.avatar else None
    )
    if BANNER_URL:
        portada.set_image(url=BANNER_URL)

    pages.insert(0, portada)
    return pages, category_names


# ─── Help Command ─────────────────────────────────────────────────────────────

class CustomHelpCommand(commands.HelpCommand):
    """Reemplaza el comando de ayuda por defecto con un panel visual e interactivo."""

    async def send_bot_help(self, mapping):
        ctx = self.context
        server_lang = "en"
        if ctx.guild and hasattr(ctx.bot, "admin_repo"):
            server_lang = await ctx.bot.admin_repo.get_server_language(ctx.guild.id)

        pages, category_names = build_help_pages(ctx.bot, ctx.author, server_lang=server_lang)
        view = HelpPaginator(pages, category_names, lang=server_lang)

        if BANNER_URL:
            await ctx.send(embed=pages[0], view=view)
        elif os.path.exists(BANNER_FILE_PATH):
            banner_file = discord.File(BANNER_FILE_PATH, filename="dalet_help_banner.jpg")
            pages[0].set_image(url="attachment://dalet_help_banner.jpg")
            await ctx.send(embed=pages[0], view=view, file=banner_file)
        else:
            if ctx.bot.user and ctx.bot.user.avatar:
                pages[0].set_thumbnail(url=ctx.bot.user.avatar.url)
            await ctx.send(embed=pages[0], view=view)



async def setup(bot):
    bot.help_command = CustomHelpCommand()