"""
Handler (Cog) para el Comando de Ayuda Personalizado.

Este archivo reemplaza el comando de ayuda por defecto de discord.py
por un sistema interactivo y paginado que usa Botones y Vistas.
"""
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput

class PageInputModal(Modal, title="Ir a Categoría"):
    """Un Modal (ventana emergente) que pide al usuario un número de página."""
    def __init__(self, pages_view):
        super().__init__()
        self.pages_view = pages_view
        total_categories = len(self.pages_view.pages) - 1

        self.page_number = TextInput(
            label="Número de Categoría",
            placeholder=f"Escribe el número de la categoría (1-{total_categories})",
            required=True,
            max_length=2,
        )
        self.add_item(self.page_number)

    async def on_submit(self, interaction: discord.Interaction):
        """Valida el número y salta a la página de categoría correspondiente."""
        try:
            num = int(self.page_number.value)
            total_categories = len(self.pages_view.pages) - 1

            # La portada es el índice 0, la categoría 1 es el índice 1, etc.
            if 1 <= num <= total_categories:
                self.pages_view.index = num
                await self.pages_view.update_page(interaction)
            else:
                await interaction.response.send_message(f"Por favor, introduce un número entre 1 y {total_categories}.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Entrada inválida. Debes escribir un número.", ephemeral=True)

class HelpPaginator(View):
    """
    Una Vista de Discord (UI) que maneja los botones de paginación.
    
    Controla los botones 'Anterior', 'Inicio', 'Ir a...' y 'Siguiente',
    y actualiza el Embed de ayuda según sea necesario.
    """
    def __init__(self, pages):
        super().__init__(timeout=180) # La vista se desactiva tras 3 minutos
        self.pages = pages
        self.index = 0
        self.update_buttons()

    def update_buttons(self):
        """Activa o desactiva los botones según la página actual."""
        self.children[0].disabled = self.index == 0 # Anterior
        self.children[1].disabled = self.index == 0 # Inicio
        self.children[3].disabled = self.index == len(self.pages) - 1 # Siguiente

    async def update_page(self, interaction: discord.Interaction):
        """Edita el mensaje de Discord para mostrar la página actual."""
        self.update_buttons()
        # Maneja la edición si la interacción ya fue respondida (ej. por el modal)
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=self.pages[self.index], view=self)
        else:
            await interaction.edit_original_response(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        if self.index > 0:
            self.index -= 1
            await self.update_page(interaction)
        else:
            await interaction.response.defer() # No hacer nada si ya está en la primera

    @discord.ui.button(label="🏠 Inicio", style=discord.ButtonStyle.blurple)
    async def home_button(self, interaction: discord.Interaction, button: Button):
        self.index = 0
        await self.update_page(interaction)

    @discord.ui.button(label="Ir a...", style=discord.ButtonStyle.green)
    async def goto_button(self, interaction: discord.Interaction, button: Button):
        """Abre el Modal 'PageInputModal'."""
        modal = PageInputModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Siguiente ➡️", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if self.index < len(self.pages) - 1:
            self.index += 1
            await self.update_page(interaction)
        else:
            await interaction.response.defer() # No hacer nada si ya está en la última

class CustomHelpCommand(commands.HelpCommand):
    """
    Clase que sobreescribe el comando de ayuda por defecto de Discord.
    
    Genera una portada y páginas separadas para cada Cog (categoría)
    y luego las envía usando la Vista 'HelpPaginator'.
    """

    async def send_bot_help(self, mapping):
        """Se activa cuando el usuario escribe 'd.help'."""
        ctx = self.context
        prefix = ctx.clean_prefix

        pages = []
        categorias = []

        # 1. Crear una página de Embed para cada Cog
        for cog, cmds in mapping.items():
            visible_cmds = [cmd for cmd in cmds if not cmd.hidden]
            if not visible_cmds:
                continue

            category_name = cog.qualified_name.replace("_", " ").title() if cog else "Otros Comandos"
            categorias.append(category_name)
            
            embed = discord.Embed(
                title=f"📘 {category_name}",
                color=discord.Color.blurple()
            )
            embed.set_footer(text=f"Usa {prefix}help <comando> para más detalles.")
            
            for cmd in visible_cmds:
                embed.add_field(
                    name=f"🔹 {prefix}{cmd.name}",
                    value=cmd.help or cmd.brief or 'Sin descripción.',
                    inline=False
                )
            pages.append(embed)

        # 2. Crear la Portada
        categorias_texto = "\n".join([f"**{i+1}.** {cat}" for i, cat in enumerate(categorias)]) or "*No hay categorías disponibles.*"

        portada = discord.Embed(
            title="✨ Centro de Ayuda de Dalet",
            description=(
                "Bienvenido al sistema de ayuda interactivo.\n\n"
                f"📂 **Categorías disponibles:**\n{categorias_texto}\n\n"
                "💡 Usa los botones `⬅️` y `➡️` para navegar.\n"
                "🔢 Usa el botón **`Ir a...`** para saltar a una categoría por su número.\n"
                f"🏠 Vuelve aquí con el botón de inicio.\n\n"
                f"📘 Escribe `{prefix}help <comando>` para más información."
            ),
            color=discord.Color.blurple()
        )
        portada.set_footer(text=f"Total: {len(categorias) + 1} páginas disponibles.")
        pages.insert(0, portada)

        # 3. Enviar la primera página con la Vista del Paginador
        view = HelpPaginator(pages)
        await ctx.send(embed=pages[0], view=view)


async def setup(bot):
    """Función 'setup' que reemplaza el comando de ayuda del bot."""
    bot.help_command = CustomHelpCommand()