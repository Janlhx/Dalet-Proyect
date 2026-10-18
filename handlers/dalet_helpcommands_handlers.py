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
        "subtitle": "Estadísticas en tiempo real, radar 5D y comparativas para los 4 modos (`osu`, `taiko`, `fruits`, `mania`).",
        "commands": [
            ("/op [usuario] [modo]",             "Tarjeta de perfil completo, rango global/país, PP y precisión"),
            ("/skills [usuario] [modo]",         "Radar técnico 5D (Aim, Speed, Acc, Stamina, Reading) + veredicto de Dalet"),
            ("/recent [usuario] [modo]",         "Última jugada registrada (incluye fallos, PP, hits y atributos del mapa)"),
            ("/top [usuario] [modo]",            "Top 5 mejores jugadas registradas + gráfico de distribución de PP"),
            ("/compare <jugador1> [jugador2]",   "Duelo cara a cara de estadísticas y habilidades entre dos jugadores"),
            ("/rank [modo]",                     "Tabla de clasificación del servidor entre miembros vinculados"),
            ("/link <usuario>",                  "Vincula tu cuenta de Discord con tu perfil oficial de osu!"),
        ]
    },
    "IA & Chat": {
        "color": discord.Color.from_rgb(139, 92, 246),  # #8B5CF6 Violeta Amatista
        "subtitle": "Cerebro conversacional con memoria piramidal L0–L3, herramientas autónomas y reacciones con emojis.",
        "commands": [
            ("@Dalet / Dalet",                   "Charla directa con Dalet (analiza tus plays, recuerda contexto y reacciona con emojis)"),
            ("/resumir [limit] [estilo]",        "Resumen estructurado del canal (modo `dalet` con humor ácido o `neutral` objetivo)"),
            ("/lore <búsqueda>",                 "Investiga el archivo histórico del canal y comenta anécdotas pasadas"),
            ("/proactive <enabled>",             "[Admin] Activa o pausa las intervenciones y reacciones espontáneas en este canal"),
            ("/reactive <enabled>",              "[Admin] Activa o pausa las respuestas de Dalet cuando la mencionan en el servidor"),
        ]
    },
    "Servidor": {
        "color": discord.Color.from_rgb(56, 189, 248),  # #38BDF8 Cyan Cielo
        "subtitle": "Información del sistema, actividad social, notas de versión y buzón directo de sugerencias.",
        "commands": [
            ("/info",                            "Ficha técnica de presentación, estado y versión actual de Dalet"),
            ("/changelog",                       "Notas de versión, hito arquitectónico actual y últimos commits en vivo"),
            ("/stats [usuario]",                 "Estadísticas de actividad social y mensajes de un miembro en el servidor"),
            ("/userinfo [usuario]",              "Detalles de cuenta, antigüedad e ingreso de un miembro"),
            ("/serverinfo",                      "Resumen general del servidor, propietario y total de miembros"),
            ("/ping",                            "Comprueba la latencia de respuesta en milisegundos"),
            ("/feedback <mensaje>",              "Envía sugerencias, ideas o reportes de bugs en privado al creador (Litxe)"),
        ]
    },
    "Recordatorios": {
        "color": discord.Color.from_rgb(251, 191, 36),  # #FBBF24 Ámbar Dorado
        "subtitle": "Alarmas programables con soporte de zonas horarias, repetición por días o fechas específicas.",
        "commands": [
            ("/reminder add <hora> [mensaje]",   "Programa un recordatorio diario, por días de la semana o fecha exacta"),
            ("/reminder list",                   "Muestra todos tus recordatorios activos en este servidor"),
            ("/reminder edit <id>",              "Modifica la hora, mensaje, días o zona horaria de un recordatorio"),
            ("/reminder toggle <id>",            "Pausa o reactiva un recordatorio existente sin borrarlo"),
            ("/reminder remove <id>",            "Elimina permanentemente un recordatorio por su ID"),
        ]
    },
    "Moderación": {
        "color": discord.Color.from_rgb(16, 185, 129),  # #10B981 Esmeralda Seguridad
        "subtitle": "Protección automática con IA multimodal (Gemini Vision), blacklist SHA-256, anti-flood y anti-scam.",
        "commands": [
            ("/mod setup [canal] [acción]...",   "[Admin] Configuración inicial o actualización general de auto-moderación"),
            ("/mod toggle <módulo> [activo]",    "[Admin] Activa o apaga módulos individuales (`images`, `flood`, `links`, `scams`)"),
            ("/mod ignore <acción> [ch] [mod]",  "[Admin] Exime o re-incluye canales o hilos por módulo específico o completo"),
            ("/mod status",                      "Muestra el panel de estado, módulos activos, exenciones y acciones recientes"),
            ("/mod action <acción>",             "[Admin] Define el castigo por defecto en NSFW (`notify`, `timeout`, `ban`)"),
            ("/mod timeout <minutos>",           "[Admin] Ajusta la duración del aislamiento temporal (1 a 10080 min)"),
            ("/mod channel <canal>",             "[Admin] Cambia el canal donde se envían las alertas de auditoría"),
            ("/mod off",                         "[Admin] Desactiva por completo la auto-moderación en el servidor"),
        ]
    },
    "Admin": {
        "color": discord.Color.from_rgb(244, 63, 94),   # #F43F5E Carmesí Admin
        "subtitle": "Ajustes generales del servidor, idioma, identidad personalizada y control de canales.",
        "commands": [
            ("/language [idioma]",               "Cambia o muestra el idioma de Dalet en el servidor (`en` Inglés / `es` Español)"),
            ("/setname <nombre>",                "Personaliza el nombre o apodo al que responde Dalet en este servidor"),
            ("/setwelcome <canal>",              "Configura el canal donde Dalet da la bienvenida a nuevos miembros"),
            ("/removewelcome",                   "Desactiva los mensajes de bienvenida en el servidor"),
            ("/lock",                            "Bloquea el uso de comandos de Dalet en el canal actual"),
            ("/unlock",                          "Desbloquea el uso de comandos de Dalet en el canal actual"),
        ]
    },
}

# English categories (Default)
SLASH_CATEGORIES_EN = {
    "osu!": {
        "color": discord.Color.from_rgb(255, 94, 158),  # #FF5E9E osu! Pink
        "subtitle": "Real-time stats, 5D skill radar, and head-to-head comparisons across all 4 modes (`osu`, `taiko`, `fruits`, `mania`).",
        "commands": [
            ("/op [user] [mode]",                "Full osu! profile card, global/country rank, total PP, and accuracy"),
            ("/skills [user] [mode]",            "5-dimension skill radar (Aim, Speed, Acc, Stamina, Reading) + Dalet's verdict"),
            ("/recent [user] [mode]",            "Most recent play (includes fails, PP, hit counts, and beatmap attributes)"),
            ("/top [user] [mode]",               "Top 5 best registered scores + visual PP distribution chart"),
            ("/compare <player1> [player2]",     "Head-to-head profile and skill comparison between two players"),
            ("/rank [mode]",                     "Server leaderboard among linked osu! members"),
            ("/link <username>",                 "Link your Discord account to your official osu! profile"),
        ]
    },
    "AI & Chat": {
        "color": discord.Color.from_rgb(139, 92, 246),  # #8B5CF6 Amethyst Violet
        "subtitle": "Conversational brain powered by L0–L3 semantic pyramid memory, live tools, and emoji reactions.",
        "commands": [
            ("@Dalet / Dalet",                   "Chat directly with Dalet (analyzes plays, remembers context & reacts with emojis)"),
            ("/resumir [limit] [estilo]",        "Structured AI digest of recent channel chat (`dalet` witty mode or `neutral` mode)"),
            ("/lore <query>",                    "Searches server chat archives and delivers cynical commentary on past lore"),
            ("/proactive <enabled>",             "[Admin] Enables or pauses spontaneous AI interventions & emoji reactions in this channel"),
            ("/reactive <enabled>",              "[Admin] Enables or pauses Dalet's replies when mentioned across the server"),
        ]
    },
    "Server": {
        "color": discord.Color.from_rgb(56, 189, 248),  # #38BDF8 Sky Cyan
        "subtitle": "System overview, member social activity, live release notes, and private developer feedback.",
        "commands": [
            ("/info",                            "Dalet's profile card, operational status, and current version"),
            ("/changelog",                       "Release notes, current architectural milestone, and recent Git commits"),
            ("/stats [user]",                    "Server message activity and social statistics for a member"),
            ("/userinfo [user]",                 "Detailed account creation and server join dates for a member"),
            ("/serverinfo",                      "Current server overview, owner, and member count"),
            ("/ping",                            "Checks bot response latency in milliseconds"),
            ("/feedback <message>",              "Sends private suggestions, ideas, or bug reports directly to Litxe"),
        ]
    },
    "Reminders": {
        "color": discord.Color.from_rgb(251, 191, 36),  # #FBBF24 Amber Gold
        "subtitle": "Scheduled notifications with timezone support, recurring weekdays, or specific dates.",
        "commands": [
            ("/reminder add <time> [message]",   "Schedule a daily, weekly, or specific-date reminder with pings"),
            ("/reminder list",                   "List all your active reminders in this server"),
            ("/reminder edit <id>",              "Modify time, message, days, or timezone of an existing reminder"),
            ("/reminder toggle <id>",            "Pause or resume a scheduled reminder by ID"),
            ("/reminder remove <id>",            "Permanently delete a reminder by ID"),
        ]
    },
    "Moderation": {
        "color": discord.Color.from_rgb(16, 185, 129),  # #10B981 Safety Emerald
        "subtitle": "Automated protection with multimodal AI (Gemini Vision), SHA-256 blacklist, anti-flood & anti-scam.",
        "commands": [
            ("/mod setup [channel] [action]...", "[Admin] Initial setup or full update of auto-moderation settings"),
            ("/mod toggle <module> [enabled]",   "[Admin] Enable or disable specific modules (`images`, `flood`, `links`, `scams`)"),
            ("/mod ignore <action> [ch] [mod]",  "[Admin] Exempt or re-include channels/threads per module or completely"),
            ("/mod status",                      "Displays operational status, active modules, exemptions, and recent log"),
            ("/mod action <action>",             "[Admin] Sets default NSFW enforcement action (`notify`, `timeout`, `ban`)"),
            ("/mod timeout <minutes>",           "[Admin] Configures timeout isolation duration (1 to 10080 minutes)"),
            ("/mod channel <channel>",           "[Admin] Updates the moderation audit and alert log channel"),
            ("/mod off",                         "[Admin] Disables auto-moderation across the server"),
        ]
    },
    "Admin": {
        "color": discord.Color.from_rgb(244, 63, 94),   # #F43F5E Admin Crimson
        "subtitle": "General server settings, language configuration, custom bot identity, and channel locks.",
        "commands": [
            ("/language [language]",             "Configures or displays the server language (`en` English / `es` Español)"),
            ("/setname <name>",                  "Sets a custom nickname that Dalet responds to in this server"),
            ("/setwelcome <channel>",            "Sets the welcome message channel for new server members"),
            ("/removewelcome",                   "Removes the welcome channel and disables welcome greetings"),
            ("/lock",                            "Blocks Dalet commands in the current channel"),
            ("/unlock",                          "Unblocks Dalet commands in the current channel"),
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
        cmd_lines = []
        if subtitle:
            cmd_lines.append(f"*{subtitle}*\n{DaletAtoms.DIVIDER_LIGHT}")

        for cmd, desc in cat_data["commands"]:
            cmd_lines.append(f"{DaletAtoms.GLYPH_STAR} **`{cmd}`**\n╰ {desc}")
        embed.description = "\n\n".join(cmd_lines)

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

    # 2. Portada
    nav_lines = "\n".join(
        [
            f"> **{i+1}.** {name} — *{categories[name].get('subtitle', '')}*"
            for i, name in enumerate(category_names)
        ]
    )

    version = DaletAtoms.VERSION
    if server_lang == "es":
        portada_desc = (
            f"Hola, **{user.display_name}**.\n"
            f"Soy **Dalet {version}** — compañera con IA conversacional, rastreador de osu!, auto-moderación y utilidades.\n"
            f"{DaletAtoms.DIVIDER_MAIN}\n"
            f"{DaletAtoms.GLYPH_POINTER} **Categorías del Sistema**\n{nav_lines}\n\n"
            f"{DaletAtoms.GLYPH_SUB} Usa el **menú desplegable** o los botones de abajo para navegar.\n"
            f"{DaletAtoms.GLYPH_SUB} Escribe `/` o usa el prefijo `d.` para ejecutar comandos.\n"
            f"{DaletAtoms.GLYPH_SUB} Usa `/changelog` para ver novedades o `/feedback` para enviar sugerencias."
        )
        footer_cover = f"Dalet {version} │ Centro de Control • /feedback para sugerencias"
    else:
        portada_desc = (
            f"Hello, **{user.display_name}**.\n"
            f"I am **Dalet {version}** — conversational AI companion, osu! tracker, auto-moderation & server utilities.\n"
            f"{DaletAtoms.DIVIDER_MAIN}\n"
            f"{DaletAtoms.GLYPH_POINTER} **System Categories**\n{nav_lines}\n\n"
            f"{DaletAtoms.GLYPH_SUB} Use the **dropdown menu** or the buttons below to navigate.\n"
            f"{DaletAtoms.GLYPH_SUB} Type `/` or use the `d.` prefix to run commands.\n"
            f"{DaletAtoms.GLYPH_SUB} Use `/changelog` for updates or `/feedback` to send suggestions."
        )
        footer_cover = f"Dalet {version} │ Control Center • /feedback for suggestions"

    portada = discord.Embed(
        title=f"{DaletAtoms.EMOJI_DALET} Dalet {version} {DaletAtoms.GLYPH_PIPE} {'Guía Interactiva' if server_lang == 'es' else 'Interactive Guide'}",
        description=portada_desc,
        color=DaletAtoms.COLOR_PRIMARY,
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