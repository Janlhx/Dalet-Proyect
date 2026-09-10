"""
Handler (Cog) para el Comando de Ayuda Personalizado de Dalet.

Sistema interactivo y paginado con botones, categorías de slash commands,
comandos de prefijo y un banner visual en la portada.
"""
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
from ui.organisms import DaletOrganisms
from ui.molecules import DaletMolecules
from ui.atoms import DaletAtoms

# ─── URL pública del banner ───────────────────────────────────────────────────
BANNER_URL: str | None = "https://imgur.com/a/dalet-banner-Gng663Z"
BANNER_FILE_PATH = "assets/bannersito.png"

# ─── Definición de categorías del menú ──────────────────────────────────────

# Spanish categories
SLASH_CATEGORIES_ES = {
    "osu!": {
        "color": discord.Color.from_rgb(255, 102, 170),
        "commands": [
            ("/op [usuario]",       "Perfil completo de osu! de un jugador"),
            ("/skills [usuario]",   "Desglose de habilidades (Aim, Speed, Acc...) y roast"),
            ("/recent [usuario]",   "Última jugada registrada"),
            ("/top [usuario]",      "Mejores plays (top scores)"),
            ("/rank",               "Ranking del servidor de jugadores vinculados"),
            ("/compare [usuario]",  "Compara tu perfil contra otro jugador"),
            ("/link <usuario>",     "Vincula tu Discord con tu cuenta de osu!"),
        ]
    },
    "IA & Chat": {
        "color": discord.Color.from_rgb(130, 100, 255),
        "commands": [
            ("/resumir",            "Resume el chat reciente del canal con IA"),
            ("/lore <búsqueda>",    "Busca fragmentos del pasado del servidor"),
            ("@Dalet",              "Hablar directamente con Dalet (IA conversacional)"),
        ]
    },
    "Servidor": {
        "color": discord.Color.from_rgb(52, 152, 219),
        "commands": [
            ("/info",               "Tarjeta de presentación e información de Dalet"),
            ("/ping",               "Latencia del bot en ms"),
            ("/stats [usuario]",    "Estadísticas sociales de un miembro"),
            ("/userinfo [usuario]", "Información detallada de un usuario"),
            ("/serverinfo",         "Información del servidor actual"),
        ]
    },
    "Recordatorios": {
        "color": discord.Color.from_rgb(255, 165, 0),
        "commands": [
            ("/reminder add",       "Crea un recordatorio diario, semanal o para fecha específica"),
            ("/reminder list",      "Lista tus recordatorios activos en este servidor"),
            ("/reminder edit",      "Edita un recordatorio existente"),
            ("/reminder remove",    "Elimina un recordatorio por su ID"),
            ("/reminder toggle",    "Activa o desactiva un recordatorio por su ID"),
        ]
    },
    "Admin": {
        "color": discord.Color.from_rgb(231, 76, 60),
        "commands": [
            ("/lock",               "Bloquea los comandos de Dalet en este canal"),
            ("/unlock",             "Desbloquea los comandos de Dalet en este canal"),
            ("/proactive",          "Activa o desactiva el modo proactivo en el canal"),
            ("/reactive",           "Activa o desactiva la respuesta a menciones en el servidor"),
            ("/setwelcome",         "Establece el canal de bienvenida del servidor"),
            ("/removewelcome",      "Elimina el canal de bienvenida del servidor"),
            ("/setname <nombre>",   "Nombre personalizado de Dalet en este servidor"),
            ("/language [idioma]",  "Configura o muestra el idioma del servidor (en/es)"),
        ]
    },
}

# English categories (Default)
SLASH_CATEGORIES_EN = {
    "osu!": {
        "color": discord.Color.from_rgb(255, 102, 170),
        "commands": [
            ("/op [user]",          "Full osu! player profile and statistics overview"),
            ("/skills [user]",      "5-dimension skill radar (Aim, Speed, Acc...) and Dalet's roast"),
            ("/recent [user]",      "Most recent registered play"),
            ("/top [user]",         "Top 5 best scores registered"),
            ("/rank",               "Server leaderboard of linked osu! players"),
            ("/compare [user]",     "Compare your profile head-to-head against another player"),
            ("/link <user>",        "Link your Discord account to your osu! profile"),
        ]
    },
    "AI & Chat": {
        "color": discord.Color.from_rgb(130, 100, 255),
        "commands": [
            ("/resumir",            "Smart AI digest of recent channel conversations"),
            ("/lore <search>",      "Search server chat history and archives"),
            ("@Dalet",              "Chat directly with Dalet (conversational AI)"),
        ]
    },
    "Server": {
        "color": discord.Color.from_rgb(52, 152, 219),
        "commands": [
            ("/info",               "Dalet showcase card and bot information"),
            ("/ping",               "Checks bot websocket and response latency in ms"),
            ("/stats [user]",       "Social activity statistics for a member"),
            ("/userinfo [user]",    "Detailed member account and server information"),
            ("/serverinfo",         "Current server overview and statistics"),
        ]
    },
    "Reminders": {
        "color": discord.Color.from_rgb(255, 165, 0),
        "commands": [
            ("/reminder add",       "Schedule daily, weekly, or specific date reminders"),
            ("/reminder list",      "List active reminders created in this server"),
            ("/reminder edit",      "Edit an existing scheduled reminder"),
            ("/reminder remove",    "Delete a reminder by ID"),
            ("/reminder toggle",    "Enable or disable a reminder by ID"),
        ]
    },
    "Admin": {
        "color": discord.Color.from_rgb(231, 76, 60),
        "commands": [
            ("/lock",               "Blocks Dalet interactions and commands in this channel"),
            ("/unlock",             "Unblocks Dalet interactions and commands in this channel"),
            ("/proactive",          "Enables or disables proactive AI chat in this channel"),
            ("/reactive",           "Enables or disables reactive AI replies to mentions"),
            ("/setwelcome",         "Sets the welcome message channel for this server"),
            ("/removewelcome",      "Removes the welcome channel and disables greetings"),
            ("/setname <name>",     "Sets a custom bot nickname in this server"),
            ("/language [lang]",    "Configures or displays the server language (en/es)"),
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

class CustomHelpCommand(commands.HelpCommand):
    """Reemplaza el comando de ayuda por defecto con un panel visual e interactivo."""

    async def send_bot_help(self, mapping):
        ctx = self.context
        server_lang = "en"
        if ctx.guild and hasattr(ctx.bot, "server_repo"):
            server_lang = await ctx.bot.server_repo.get_language(ctx.guild.id)

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
            cmd_lines = []
            for cmd, desc in cat_data["commands"]:
                cmd_lines.append(f"`{cmd}`\n╰ {desc}")
            embed.description = "\n\n".join(cmd_lines)

            footer_txt = (
                f"Dalet · {len(pages)+1} de {len(categories)}  —  Escribe / para autocompletar"
                if server_lang == "es"
                else f"Dalet · {len(pages)+1} of {len(categories)}  —  Type / to autocomplete"
            )
            embed.set_footer(
                text=footer_txt,
                icon_url=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None
            )
            pages.append(embed)

        # 2. Portada
        nav_lines = "\n".join(
            [f"> **{i+1}.** {name}" for i, name in enumerate(category_names)]
        )

        if server_lang == "es":
            portada_desc = (
                f"Hola, **{ctx.author.display_name}**.\n\n"
                f"Soy **Dalet {DaletAtoms.VERSION}** — bot de osu!, IA conversacional y utilidades.\n"
                f"Escribe `/` en Discord para autocompletar comandos, o usa `d.help`.\n\n"
                f"**Categorías:**\n{nav_lines}\n\n"
                f"{DaletAtoms.GLYPH_SUB} Usa el menú desplegable o botones para explorar.\n"
                f"{DaletAtoms.GLYPH_SUB} Escribe `d.changelog` para consultar las novedades de la versión."
            )
            footer_cover = f"Dalet {DaletAtoms.VERSION} │ Centro de Control • d.changelog para novedades"
        else:
            portada_desc = (
                f"Hello, **{ctx.author.display_name}**.\n\n"
                f"I am **Dalet {DaletAtoms.VERSION}** — osu! companion, conversational AI & server utilities.\n"
                f"Type `/` in Discord to autocomplete commands, or use `d.help`.\n\n"
                f"**Categories:**\n{nav_lines}\n\n"
                f"{DaletAtoms.GLYPH_SUB} Use the dropdown menu or navigation buttons to explore.\n"
                f"{DaletAtoms.GLYPH_SUB} Type `d.changelog` to check the latest updates."
            )
            footer_cover = f"Dalet {DaletAtoms.VERSION} │ Control Center • d.changelog for updates"

        portada = discord.Embed(
            title="",
            description=portada_desc,
            color=DaletAtoms.COLOR_PRIMARY,
        )
        portada.set_footer(
            text=footer_cover,
            icon_url=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None
        )
        pages.insert(0, portada)

        # 3. Enviar con paginador
        view = HelpPaginator(pages, category_names, lang=server_lang)

        # Intentar adjuntar el banner como archivo local o URL pública
        import os
        banner_file = None
        if BANNER_URL:
            portada.set_image(url=BANNER_URL)
            await ctx.send(embed=pages[0], view=view)
        elif os.path.exists(BANNER_FILE_PATH):
            banner_file = discord.File(BANNER_FILE_PATH, filename="dalet_help_banner.jpg")
            portada.set_image(url="attachment://dalet_help_banner.jpg")
            await ctx.send(embed=pages[0], view=view, file=banner_file)
        else:
            # Sin banner: usar el avatar del bot como thumbnail
            if ctx.bot.user.avatar:
                portada.set_thumbnail(url=ctx.bot.user.avatar.url)
            await ctx.send(embed=pages[0], view=view)



async def setup(bot):
    bot.help_command = CustomHelpCommand()