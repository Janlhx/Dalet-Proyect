import discord
from ui.atoms import DaletAtoms

class DaletMolecules:
    """Componentes reutilizables formados por la unión de átomos."""
    
    @staticmethod
    def create_field(name, value, inline=False):
        """Crea una tupla compatible con add_field de Embed."""
        return {"name": name, "value": value, "inline": inline}

    @staticmethod
    def add_standard_footer(embed, author_name=None):
        """Añade el footer característico de Dalet a un embed."""
        text = f"Generado con {DaletAtoms.EMOJI_DALET} por Dalet"
        if author_name:
            text += f" | Para {author_name}"
        embed.set_footer(text=text)
        return embed

    @staticmethod
    def create_button(label, style=discord.ButtonStyle.grey, emoji=None, custom_id=None, disabled=False):
        """Crea un botón de Discord con el estilo Dalet."""
        return discord.ui.Button(label=label, style=style, emoji=emoji, custom_id=custom_id, disabled=disabled)

    @staticmethod
    def create_navigation_buttons(index, total_pages):
        """Crea una lista de botones de navegación estándar."""
        return [
            DaletMolecules.create_button("⬅️", style=discord.ButtonStyle.grey, disabled=(index == 0)),
            DaletMolecules.create_button("🏠", style=discord.ButtonStyle.blurple, disabled=(index == 0)),
            DaletMolecules.create_button("Ir a...", style=discord.ButtonStyle.green),
            DaletMolecules.create_button("➡️", style=discord.ButtonStyle.grey, disabled=(index == total_pages - 1))
        ]

    @staticmethod
    def create_labeled_text(label, text, emoji=None):
        """Crea una línea de texto formateada con etiqueta y emoji opcional."""
        prefix = f"{emoji} " if emoji else ""
        return f"{prefix}{DaletAtoms.bold(label)}: {text}"
