import discord
from ui.atoms import DaletAtoms

class DaletMolecules:
    """Componentes visuales reutilizables de Dalet."""

    @staticmethod
    def create_field(name: str, value: str, inline: bool = False):
        """Crea un diccionario compatible con add_field."""
        return {"name": name, "value": value, "inline": inline}

    @staticmethod
    def add_standard_footer(embed: discord.Embed, context_text: str = None, icon_url: str = None):
        """Añade el footer minimalista y característico de Dalet."""
        text = "Dalet"
        if context_text:
            text += f" • {context_text}"
        embed.set_footer(text=text, icon_url=icon_url)
        return embed

    @staticmethod
    def create_progress_bar(percentage: float, length: int = 10) -> str:
        """Genera una barra de progreso limpia."""
        pct = max(0.0, min(100.0, percentage))
        filled = int(round(length * pct / 100))
        return f"[{'█' * filled}{'░' * (length - filled)}]"

    @staticmethod
    def create_button(label: str, style=discord.ButtonStyle.grey, emoji=None, custom_id=None, disabled=False):
        """Crea un botón de Discord con el estilo Dalet."""
        return discord.ui.Button(label=label, style=style, emoji=emoji, custom_id=custom_id, disabled=disabled)

