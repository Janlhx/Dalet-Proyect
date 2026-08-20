import discord
from datetime import datetime, timezone

class DaletAtoms:
    """Design Tokens e Identidad Visual de Dalet."""

    # --- Paleta de Colores ---
    COLOR_PRIMARY = discord.Color.from_rgb(255, 105, 180)  # #FF69B4 (Dalet Pink)
    COLOR_DARK = discord.Color.from_rgb(24, 24, 27)        # #18181B (Zinc Dark)
    COLOR_SUCCESS = discord.Color.from_rgb(34, 197, 94)    # #22C55E (Emerald Green)
    COLOR_WARNING = discord.Color.from_rgb(245, 158, 11)   # #F59E0B (Amber Gold)
    COLOR_ERROR = discord.Color.from_rgb(239, 68, 68)      # #EF4444 (Coral Red)
    COLOR_INFO = discord.Color.from_rgb(14, 165, 233)      # #0EA5E9 (Sky Blue)
    COLOR_PURPLE = discord.Color.from_rgb(168, 85, 247)    # #A855F7 (Amethyst)

    # --- Colores por Rango / Grade ---
    GRADE_COLORS = {
        "XH": discord.Color.from_rgb(0, 229, 255),   # Platinum Diamond (Silver SS)
        "X": discord.Color.from_rgb(255, 215, 0),    # Pure Gold (Gold SS)
        "SH": discord.Color.from_rgb(0, 229, 255),   # Platinum Diamond (Silver S)
        "S": discord.Color.from_rgb(255, 215, 0),    # Pure Gold (Gold S)
        "A": discord.Color.from_rgb(34, 197, 94),    # Emerald Green
        "B": discord.Color.from_rgb(59, 130, 246),   # Royal Blue
        "C": discord.Color.from_rgb(168, 85, 247),   # Purple
        "D": discord.Color.from_rgb(239, 68, 68),    # Coral Red
        "F": discord.Color.from_rgb(113, 113, 122)   # Zinc Slate
    }

    GRADE_BADGES = {
        "XH": "SS",
        "X": "SS",
        "SH": "S",
        "S": "S",
        "A": "A",
        "B": "B",
        "C": "C",
        "D": "D",
        "F": "F"
    }

    # --- Símbolos y Marcadores Geométricos ---
    GLYPH_POINTER = "▸"
    GLYPH_SUB = "▫"
    GLYPH_PIPE = "│"
    GLYPH_STAR = "★"
    GLYPH_CORNER = "└"

    # --- Emojis Funcionales y Limpios ---
    EMOJI_DALET = "✦"

    # --- Estilos de Texto ---
    @staticmethod
    def bold(text):
        return f"**{text}**"

    @staticmethod
    def italic(text):
        return f"*{text}*"

    @staticmethod
    def code(text):
        return f"`{text}`"

    @staticmethod
    def quote(text):
        return f"> {text}"

    @staticmethod
    def badge(text):
        return f"`{text}`"

    @staticmethod
    def get_rank_color(rank: int) -> discord.Color:
        """Devuelve un color de acento basado en el rango global numérico."""
        if not rank or rank <= 0:
            return DaletAtoms.COLOR_PRIMARY
        if rank <= 1000:
            return discord.Color.from_rgb(255, 215, 0)      # Gold
        if rank <= 10000:
            return discord.Color.from_rgb(0, 229, 255)     # Diamond
        if rank <= 50000:
            return discord.Color.from_rgb(192, 192, 192)   # Silver
        if rank <= 100000:
            return discord.Color.from_rgb(205, 127, 50)    # Bronze
        return DaletAtoms.COLOR_PRIMARY

    @staticmethod
    def get_grade_color(grade: str) -> discord.Color:
        """Devuelve el color correspondiente al grade de osu!."""
        return DaletAtoms.GRADE_COLORS.get(grade.upper(), DaletAtoms.COLOR_PRIMARY)

    @staticmethod
    def format_duration(seconds: int | float) -> str:
        """Convierte segundos a formato MM:SS."""
        if not seconds or seconds < 0:
            return "0:00"
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f"{m}:{s:02d}"

    @staticmethod
    def parse_timestamp_relative(iso_str: str) -> str:
        """Convierte una fecha ISO a formato Discord timestamp relativo."""
        if not iso_str:
            return ""
        try:
            clean_str = iso_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
            unix_ts = int(dt.timestamp())
            return f"<t:{unix_ts}:R>"
        except Exception:
            return iso_str[:10]
