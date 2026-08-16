import discord
from ui.organisms import DaletOrganisms
from ui.atoms import DaletAtoms
from ui.molecules import DaletMolecules

GRADE_EMOJIS = {
    "XH": "🌟", "X": "⭐", "SH": "🥈", "S": "🏅", "A": "🎯",
    "B": "🔵", "C": "🟡", "D": "🔴", "F": "💀"
}

MODE_EMOJIS = {"osu": "🎵", "taiko": "🥁", "fruits": "🍎", "mania": "🎹"}


def _mods_str(mods: list) -> str:
    if not mods:
        return "+NM"
    return "+" + "".join(mods)


def _acc_str(accuracy: float) -> str:
    return f"{accuracy * 100:.2f}%"


class OsuPresenter:
    """Clase utilitaria para construir Embeds de osu! de forma consistente."""

    @staticmethod
    def build_profile_card(user_data: dict, mode: str = "osu") -> discord.Embed:
        """Construye la tarjeta principal de perfil."""
        return DaletOrganisms.create_osu_card(user_data, mode)

    @staticmethod
    def build_recent_card(username: str, mode: str, play: dict) -> discord.Embed:
        """Construye un Embed para la jugada más reciente de un usuario."""
        beatmap = play.get("beatmap", {})
        beatmapset = play.get("beatmapset", {})
        rank = play.get("rank", "F")
        grade = GRADE_EMOJIS.get(rank, "❓")
        mods = _mods_str(play.get("mods", []))
        acc = _acc_str(play.get("accuracy", 0.0))
        pp = play.get("pp")
        pp_str = f"**{pp:.2f}pp**" if pp is not None else "*Sin PP*"

        title = f"{beatmapset.get('title', 'Unknown')} [{beatmap.get('version', '')}]"
        artist = beatmapset.get("artist", "")
        stars = beatmap.get("difficulty_rating", 0.0)

        color = DaletAtoms.COLOR_PRIMARY
        if rank in ("XH", "X"):
            color = 0xFFD700
        elif rank in ("SH", "S"):
            color = 0xC0C0C0

        embed = discord.Embed(
            title=f"{grade} {title}",
            url=play.get("url") or f"https://osu.ppy.sh/b/{beatmap.get('id', 0)}",
            description=f"por **{artist}**\n⭐ `{stars:.2f}*` | {mods} | **{acc}** | {pp_str}",
            color=color
        )
        embed.set_author(name=f"Jugada Reciente de {username} ({mode.upper()})")
        if beatmapset.get("covers", {}).get("cover"):
            embed.set_thumbnail(url=beatmapset["covers"]["cover"])

        return DaletMolecules.add_standard_footer(embed)

    @staticmethod
    def build_top_card(username: str, mode: str, plays: list) -> discord.Embed:
        """Construye un Embed con las mejores jugadas (Top Plays) de un usuario."""
        embed = discord.Embed(
            title=f"🏆 Top Scores de {username} ({mode.upper()})",
            color=DaletAtoms.COLOR_PRIMARY
        )

        if not plays:
            embed.description = "No se encontraron jugadas registradas."
            return DaletMolecules.add_standard_footer(embed)

        desc_lines = []
        for i, p in enumerate(plays[:5], 1):
            bm = p.get("beatmapset", {}).get("title", "Map")
            version = p.get("beatmap", {}).get("version", "")
            rank = p.get("rank", "F")
            grade = GRADE_EMOJIS.get(rank, "🎯")
            pp = p.get("pp", 0)
            acc = _acc_str(p.get("accuracy", 0.0))
            mods = _mods_str(p.get("mods", []))

            desc_lines.append(
                f"**{i}.** {grade} **[{bm} [{version}]]**\n"
                f"└ **{pp:.2f}pp** • `{acc}` • {mods}"
            )

        embed.description = "\n\n".join(desc_lines)
        return DaletMolecules.add_standard_footer(embed)

    @staticmethod
    def build_compare_card(user1_data: dict, user2_data: dict, mode: str = "osu") -> discord.Embed:
        """Construye una tarjeta comparativa entre dos jugadores."""
        u1_name = user1_data.get("username", "Jugador 1")
        u2_name = user2_data.get("username", "Jugador 2")

        u1_stats = user1_data.get("statistics", {})
        u2_stats = user2_data.get("statistics", {})

        u1_pp = u1_stats.get("pp", 0.0)
        u2_pp = u2_stats.get("pp", 0.0)

        u1_rank = u1_stats.get("global_rank", 0) or 9999999
        u2_rank = u2_stats.get("global_rank", 0) or 9999999

        u1_acc = u1_stats.get("hit_accuracy", 0.0)
        u2_acc = u2_stats.get("hit_accuracy", 0.0)

        winner_pp = u1_name if u1_pp > u2_pp else u2_name
        diff_pp = abs(u1_pp - u2_pp)

        embed = discord.Embed(
            title=f"⚔️ Comparación osu! ({mode.upper()})",
            description=f"**{u1_name}** vs **{u2_name}**\n\n🏆 Lidera en PP: **{winner_pp}** (+{diff_pp:,.2f}pp)",
            color=DaletAtoms.COLOR_PRIMARY
        )

        embed.add_field(
            name=u1_name,
            value=f"• **PP**: `{u1_pp:,.2f}pp`\n• **Rank Global**: `#{u1_rank:,}`\n• **Precisión**: `{u1_acc:.2f}%`",
            inline=True
        )

        embed.add_field(
            name=u2_name,
            value=f"• **PP**: `{u2_pp:,.2f}pp`\n• **Rank Global**: `#{u2_rank:,}`\n• **Precisión**: `{u2_acc:.2f}%`",
            inline=True
        )

        return DaletMolecules.add_standard_footer(embed)
