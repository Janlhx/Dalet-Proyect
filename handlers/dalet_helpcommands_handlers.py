"""
Handler (Cog) para el Comando de Ayuda Personalizado.

Este archivo reemplaza el comando de ayuda por defecto de discord.py
por un sistema interactivo y paginado que usa Botones y Vistas.
"""
import discord
from discord.ext import commands
from ui.organisms import DaletOrganisms
from ui.molecules import DaletMolecules
from ui.atoms import DaletAtoms

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

        # 1. Crear una página para cada Cog
        for cog, cmds in mapping.items():
            visible_cmds = [cmd for cmd in cmds if not cmd.hidden]
            if not visible_cmds:
                continue

            category_name = cog.qualified_name.replace("_", " ").title() if cog else "Otros Comandos"
            categorias.append(category_name)
            
            embed = discord.Embed(
                title=f"📘 Categoría: {category_name}",
                color=DaletAtoms.COLOR_PRIMARY
            )
            
            for cmd in visible_cmds:
                desc = cmd.help or cmd.brief or 'Sin descripción.'
                embed.add_field(
                    name=f"🔹 {prefix}{cmd.name}",
                    value=f"> {desc}",
                    inline=False
                )
            
            pages.append(DaletMolecules.add_standard_footer(embed))

        # 2. Crear la Portada
        categorias_texto = "\n".join([f"**{i+1}.** {cat}" for i, cat in enumerate(categorias)])
        
        description = (
            f"Bienvenido al sistema de ayuda de {DaletAtoms.bold('Dalet')}.\n\n"
            f"📂 **Categorías:**\n{categorias_texto}\n\n"
            f"💡 Navega con {DaletAtoms.code('Anterior')} y {DaletAtoms.code('Siguiente')}.\n"
            f"🏠 {DaletAtoms.italic('Vuelve a esta portada en cualquier momento.')}\n"
        )
        
        portada = DaletOrganisms.create_simple_embed("Centro de Control de Dalet", description)
        pages.insert(0, portada)

        # 3. Enviar
        view = HelpPaginator(pages)
        await ctx.send(embed=pages[0], view=view)


async def setup(bot):
    bot.help_command = CustomHelpCommand()