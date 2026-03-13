import discord

class DaletAtoms:
    """Los ladrillos básicos de la identidad visual de Dalet."""
    
    # --- Colores ---
    COLOR_PRIMARY = discord.Color.from_rgb(255, 105, 180)  # Hot Pink (Dalet Pink)
    COLOR_DARK = discord.Color.from_rgb(31, 31, 31)       # Charcoal para embeds sobrios
    COLOR_SUCCESS = discord.Color.green()
    COLOR_ERROR = discord.Color.red()
    COLOR_INFO = discord.Color.blue()
    
    # --- Emojis Significativos ---
    EMOJI_DALET = "✨"
    EMOJI_OSU = "🍥"
    EMOJI_MEMORY = "🧠"
    EMOJI_ERROR = "❌"
    EMOJI_SUCCESS = "✅"
    EMOJI_INFO = "ℹ️"
    EMOJI_SEARCH = "🔍"
    
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
    def get_rank_color(rank):
        """Devuelve un color basado en el rank de osu!."""
        if rank <= 1000: return discord.Color.from_rgb(255, 215, 0) # Gold
        if rank <= 10000: return discord.Color.from_rgb(192, 192, 192) # Silver
        if rank <= 100000: return discord.Color.from_rgb(205, 127, 50) # Bronze
        return DaletAtoms.COLOR_PRIMARY
