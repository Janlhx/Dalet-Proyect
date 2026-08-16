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
BANNER_URL: str | None = "https://i.imgur.com/Gng663Z.jpeg"
BANNER_FILE_PATH = "assets/bannersito.png"

# ─── Definición de categorías del menú ──────────────────────────────────────

SLASH_CATEGORIES = {
    "osu!": {
        "color": discord.Color.from_rgb(255, 102, 170),
        "commands": [
            ("/op [usuario]",       "Perfil completo de osu! de un jugador"),
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
            ("/gemini <prompt>",    "Consulta rápida a Gemini"),
        ]
    },
    "Servidor": {
        "color": discord.Color.from_rgb(52, 152, 219),
        "commands": [
            ("/ping",               "Latencia del bot en ms"),
            ("/stats [usuario]",    "Estadísticas sociales de un miembro"),
            ("/userinfo [usuario]", "Información detallada de un usuario"),
            ("/serverinfo",         "Información del servidor actual"),
            ("/status",             "Estado técnico: DB, IA y caché"),
        ]
    },
    "Recordatorios": {
        "color": discord.Color.from_rgb(255, 165, 0),
        "commands": [
            ("/reminder add",       "Crea un recordatorio diario, semanal o para fecha específica"),
            ("/reminder list",      "Lista tus recordatorios activos"),
            ("/reminder edit",      "Edita un recordatorio existente"),
            ("/reminder delete",    "Elimina un recordatorio por ID"),
            ("/reminder toggle",    "Activa o desactiva un recordatorio"),
        ]
    },
    "Admin": {
        "color": discord.Color.from_rgb(231, 76, 60),
        "commands": [
            ("/lock",               "Bloquea los comandos de Dalet en este canal"),
            ("/unlock",             "Desbloquea los comandos de Dalet en este canal"),
            ("/proactive",          "Activa/desactiva el modo proactivo en el canal"),
            ("/reactive",           "Activa/desactiva la respuesta a menciones"),
            ("/setwelcome",         "Establece el canal de bienvenida"),
            ("/removewelcome",      "Elimina el canal de bienvenida"),
            ("/setname <nombre>",   "Nombre personalizado de Dalet en el servidor"),
            ("d.sync",              "Sincroniza slash commands al instante (solo bot owner)"),
            ("d.reload <módulo>",   "Recarga un módulo del bot (solo bot owner)"),
        ]
    },
}


# ─── Modal para saltar a página ──────────────────────────────────────────────

class PageInputModal(Modal, title="Ir a Categoría"):
    """Modal emergente que pide un número de categoría."""
    def __init__(self, pages_view):
        super().__init__()
        self.pages_view = pages_view
        total = len(self.pages_view.pages) - 1
        self.page_number = TextInput(
            label="Número de Categoría",
            placeholder=f"Escribe el número de la categoría (1-{total})",
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
                await interaction.response.send_message(
                    f"Número fuera de rango. Usa entre 1 y {total}.", ephemeral=True
                )
        except ValueError:
            await interaction.response.send_message("Eso no es un número válido.", ephemeral=True)


# ─── Select menu de categorías ───────────────────────────────────────────────

class CategorySelect(Select):
    """Menú desplegable para saltar directamente a una categoría."""
    def __init__(self, pages_view, category_names: list[str]):
        self.pages_view = pages_view
        options = [
            discord.SelectOption(label="Portada", value="0", description="Volver a la portada principal")
        ]
        for i, name in enumerate(category_names, start=1):
            options.append(
                discord.SelectOption(label=name, value=str(i), description=f"Ver comandos de {name}")
            )
        super().__init__(
            placeholder="Ir a una categoría...",
            options=options,
            custom_id="help_category_select"
        )

    async def callback(self, interaction: discord.Interaction):
        self.pages_view.index = int(self.values[0])
        await self.pages_view.update_page(interaction)


# ─── Vista principal del paginador ───────────────────────────────────────────

class HelpPaginator(View):
    """Vista con botones de navegación y select menu de categorías."""
    def __init__(self, pages: list[discord.Embed], category_names: list[str]):
        super().__init__(timeout=300)
        self.pages = pages
        self.index = 0
        # Añadir select menu dinámico
        self.select = CategorySelect(self, category_names)
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
        modal = PageInputModal(self)
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
        pages = []
        category_names = []

        # 1. Páginas de slash commands por categoría
        for cat_name, cat_data in SLASH_CATEGORIES.items():
            category_names.append(cat_name)
            embed = discord.Embed(
                title=cat_name,
                color=cat_data["color"],
            )
            cmd_lines = []
            for cmd, desc in cat_data["commands"]:
                cmd_lines.append(f"`{cmd}`\n╰ {desc}")
            embed.description = "\n\n".join(cmd_lines)
            embed.set_footer(
                text=f"Dalet · {len(pages)+1} de {len(SLASH_CATEGORIES)}  —  Escribe / para autocompletar",
                icon_url=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None
            )
            pages.append(embed)

        # 2. Portada
        total_slash = sum(len(v["commands"]) for v in SLASH_CATEGORIES.values())
        nav_lines = "\n".join(
            [f"> **{i+1}.** {name}" for i, name in enumerate(category_names)]
        )
        portada = discord.Embed(
            title="",
            description=(
                f"Hola, **{ctx.author.display_name}**.\n\n"
                f"Soy **Dalet** — bot de osu!, IA y recordatorios.\n"
                f"Todos mis comandos son slash commands. Escribe `/` en Discord para autocompletar.\n\n"
                f"**Categorías:**\n{nav_lines}\n\n"
                f"Usa el menú desplegable o los botones para navegar entre categorías."
            ),
            color=DaletAtoms.COLOR_PRIMARY,
        )
        portada.set_footer(
            text="Dalet · Centro de Control  •  d.help para ver esto de nuevo",
            icon_url=ctx.bot.user.avatar.url if ctx.bot.user.avatar else None
        )
        pages.insert(0, portada)

        # 3. Enviar con paginador
        view = HelpPaginator(pages, category_names)

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