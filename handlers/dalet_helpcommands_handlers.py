import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput

# --- Ventana emergente para ir a una página específica ---
class PageInputModal(Modal, title="Ir a Categoría"):
    def __init__(self, pages_view):
        super().__init__()
        self.pages_view = pages_view
        # El total de categorías es el número de páginas menos la portada
        total_categories = len(self.pages_view.pages) - 1

        self.page_number = TextInput(
            label="Número de Categoría",
            placeholder=f"Escribe el número de la categoría (1-{total_categories})",
            required=True,
            max_length=2,
        )
        self.add_item(self.page_number)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            num = int(self.page_number.value)
            total_categories = len(self.pages_view.pages) - 1

            # CORRECCIÓN: El índice de la página de categoría es el número que el usuario introduce.
            # La portada es el índice 0, la categoría 1 es el índice 1, etc.
            if 1 <= num <= total_categories:
                self.pages_view.index = num
                await self.pages_view.update_page(interaction)
            else:
                await interaction.response.send_message(f"Por favor, introduce un número entre 1 y {total_categories}.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Entrada inválida. Debes escribir un número.", ephemeral=True)

class HelpPaginator(View):
    def __init__(self, pages):
        super().__init__(timeout=180)
        self.pages = pages
        self.index = 0
        self.update_buttons()

    def update_buttons(self):
        # children[0] = Anterior, [1] = Inicio, [2] = Ir a..., [3] = Siguiente
        self.children[0].disabled = self.index == 0
        self.children[1].disabled = self.index == 0
        self.children[3].disabled = self.index == len(self.pages) - 1

    async def update_page(self, interaction: discord.Interaction):
        self.update_buttons()
        # Verificamos si la interacción ya ha sido respondida para evitar errores
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=self.pages[self.index], view=self)
        else:
            await interaction.edit_original_response(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        if self.index > 0:
            self.index -= 1
            await self.update_page(interaction)

    @discord.ui.button(label="🏠 Inicio", style=discord.ButtonStyle.blurple)
    async def home_button(self, interaction: discord.Interaction, button: Button):
        self.index = 0
        await self.update_page(interaction)

    @discord.ui.button(label="Ir a...", style=discord.ButtonStyle.green)
    async def goto_button(self, interaction: discord.Interaction, button: Button):
        modal = PageInputModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Siguiente ➡️", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if self.index < len(self.pages) - 1:
            self.index += 1
            await self.update_page(interaction)


class CustomHelpCommand(commands.HelpCommand):
    """Sistema de ayuda con paginación y menú principal detallado"""

    async def send_bot_help(self, mapping):
        ctx = self.context
        prefix = ctx.clean_prefix

        pages = []
        categorias = []

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
                    value=cmd.help or 'Sin descripción.',
                    inline=False
                )
            pages.append(embed)

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

        view = HelpPaginator(pages)
        await ctx.send(embed=pages[0], view=view)


async def setup(bot):
    bot.help_command = CustomHelpCommand()
