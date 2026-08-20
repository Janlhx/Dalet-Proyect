import discord
from ui.atoms import DaletAtoms
from ui.molecules import DaletMolecules

def _format_mods(mods: list) -> str:
    """Formatea la lista de mods en un string compacto tipo +HDDT o +NM."""
    if not mods:
        return "+NM"
    mod_strs = []
    for m in mods:
        if isinstance(m, str):
            mod_strs.append(m)
        elif isinstance(m, dict) and "acronym" in m:
            mod_strs.append(m["acronym"])
    return "+" + "".join(mod_strs) if mod_strs else "+NM"

def _format_acc(acc: float) -> str:
    """Formatea la precisión (0.0 a 1.0) a porcentaje XX.XX%."""
    if acc is None:
        return "0.00%"
    # Si viene como 0.985 -> 98.50%, si viene como 98.5 -> 98.50%
    val = acc * 100 if acc <= 1.0 else acc
    return f"{val:.2f}%"

def _get_country_flag(country_code: str) -> str:
    """Convierte un código ISO de país (ej. 'CO', 'US') en su emoji de bandera."""
    if not country_code or len(country_code) != 2:
        return "🌐"
    try:
        code = country_code.upper()
        return chr(ord(code[0]) + 127397) + chr(ord(code[1]) + 127397)
    except Exception:
        return "🌐"

def _mode_title(mode: str) -> str:
    modes = {
        "osu": "Standard",
        "taiko": "Taiko",
        "fruits": "Catch the Beat",
        "mania": "Mania"
    }
    return modes.get(mode.lower(), mode.capitalize())


class OsuPresenter:
    """Presentador de UI para osu! de Dalet — Alta densidad, limpio y sin ruido visual."""

    @staticmethod
    def build_recent_card(username: str, mode: str, play: dict, user_data: dict = None) -> discord.Embed:
        """Construye una tarjeta de jugada reciente de alta densidad informativa."""
        beatmap = play.get("beatmap", {})
        beatmapset = play.get("beatmapset", {})
        stats = play.get("statistics", {})

        title = beatmapset.get("title", "Desconocido")
        artist = beatmapset.get("artist", "")
        version = beatmap.get("version", "Normal")
        beatmap_id = beatmap.get("id", 0)
        map_url = f"https://osu.ppy.sh/b/{beatmap_id}" if beatmap_id else "https://osu.ppy.sh"

        stars = beatmap.get("difficulty_rating", 0.0)
        mods = _format_mods(play.get("mods", []))
        rank = play.get("rank", "F").upper()
        acc = _format_acc(play.get("accuracy", 0.0))

        pp = play.get("pp")
        pp_str = f"**{pp:.2f}PP**" if pp is not None else "**Sin PP**"

        score = play.get("score") or play.get("classic_total_score") or play.get("legacy_total_score") or 0
        max_combo = play.get("max_combo", 0)
        map_max_combo = beatmap.get("max_combo")
        combo_str = f"x{max_combo:,}/{map_max_combo:,}" if map_max_combo else f"x{max_combo:,}"

        c300 = stats.get("count_300", 0)
        c100 = stats.get("count_100", 0)
        c50 = stats.get("count_50", 0)
        miss = stats.get("count_miss", 0)
        hits_str = f"[{c300}/{c100}/{c50}/{miss}]"

        # Atributos del beatmap
        ar = beatmap.get("ar", 0.0)
        od = beatmap.get("accuracy", 0.0)
        hp = beatmap.get("drain", 0.0)
        cs = beatmap.get("cs", 0.0)
        bpm = beatmap.get("bpm", 0)
        length_sec = beatmap.get("total_length") or beatmap.get("hit_length") or 0
        length_str = DaletAtoms.format_duration(length_sec)

        rel_time = DaletAtoms.parse_timestamp_relative(play.get("created_at", ""))
        flag = _get_country_flag(user_data.get("country", {}).get("code") if user_data else "")

        embed = discord.Embed(
            color=DaletAtoms.get_grade_color(rank)
        )
        embed.set_author(
            name=f"{flag} Recent osu! {_mode_title(mode)} Play for {username}",
            icon_url=user_data.get("avatar_url") if user_data else None,
            url=f"https://osu.ppy.sh/users/{user_data.get('id', username)}/{mode}" if user_data else None
        )

        # Bloque principal de contenido en description
        lines = [
            f"**[{artist} - {title} [{version}]]({map_url})** **{mods}** `[{stars:.2f}★]`",
            f"{DaletAtoms.GLYPH_POINTER} ` {rank} ` {DaletAtoms.GLYPH_POINTER} {pp_str} {DaletAtoms.GLYPH_POINTER} **{acc}**",
            f"{DaletAtoms.GLYPH_POINTER} {score:,} {DaletAtoms.GLYPH_POINTER} {combo_str} {DaletAtoms.GLYPH_POINTER} `{hits_str}` {DaletAtoms.GLYPH_POINTER} {rel_time}",
            f"{DaletAtoms.GLYPH_POINTER} ⏱ {length_str} {DaletAtoms.GLYPH_POINTER} 🎵 {bpm:.0f} BPM {DaletAtoms.GLYPH_POINTER} `AR {ar} OD {od} HP {hp} CS {cs}`"
        ]
        embed.description = "\n".join(lines)

        # Thumbnail con la portada del mapa
        covers = beatmapset.get("covers", {})
        thumb_url = covers.get("list") or covers.get("cover") or covers.get("card")
        if thumb_url:
            embed.set_thumbnail(url=thumb_url)

        DaletMolecules.add_standard_footer(embed, context_text="On osu! Bancho Server")
        return embed

    @staticmethod
    def build_top_card(username: str, mode: str, plays: list, user_data: dict = None) -> discord.Embed:
        """Construye un Embed de alta densidad con los Top Plays del usuario."""
        flag = _get_country_flag(user_data.get("country", {}).get("code") if user_data else "")

        embed = discord.Embed(
            color=DaletAtoms.COLOR_PRIMARY
        )
        embed.set_author(
            name=f"{flag} Top osu! {_mode_title(mode)} Plays for {username}",
            icon_url=user_data.get("avatar_url") if user_data else None,
            url=f"https://osu.ppy.sh/users/{user_data.get('id', username)}/{mode}" if user_data else None
        )

        if not plays:
            embed.description = "No se encontraron jugadas registradas en este modo."
            DaletMolecules.add_standard_footer(embed, context_text="On osu! Bancho Server")
            return embed

        # Thumbnail del usuario
        if user_data and user_data.get("avatar_url"):
            embed.set_thumbnail(url=user_data["avatar_url"])

        entries = []
        for i, p in enumerate(plays[:5], 1):
            bm = p.get("beatmap", {})
            bms = p.get("beatmapset", {})
            stats = p.get("statistics", {})

            title = bms.get("title", "Map")
            version = bm.get("version", "")
            bm_id = bm.get("id", 0)
            map_url = f"https://osu.ppy.sh/b/{bm_id}" if bm_id else "https://osu.ppy.sh"

            rank = p.get("rank", "F").upper()
            stars = bm.get("difficulty_rating", 0.0)
            mods = _format_mods(p.get("mods", []))
            acc = _format_acc(p.get("accuracy", 0.0))
            pp = p.get("pp", 0.0) or 0.0
            score = p.get("score") or p.get("classic_total_score") or p.get("legacy_total_score") or 0

            max_combo = p.get("max_combo", 0)
            map_max_combo = bm.get("max_combo")
            combo_str = f"x{max_combo:,}/{map_max_combo:,}" if map_max_combo else f"x{max_combo:,}"

            c300 = stats.get("count_300", 0)
            c100 = stats.get("count_100", 0)
            c50 = stats.get("count_50", 0)
            miss = stats.get("count_miss", 0)
            hits_str = f"[{c300}/{c100}/{c50}/{miss}]"

            ar = bm.get("ar", 0.0)
            od = bm.get("accuracy", 0.0)
            hp = bm.get("drain", 0.0)
            cs = bm.get("cs", 0.0)
            bpm = bm.get("bpm", 0)
            length_sec = bm.get("total_length") or bm.get("hit_length") or 0
            length_str = DaletAtoms.format_duration(length_sec)

            rel_time = DaletAtoms.parse_timestamp_relative(p.get("created_at", ""))

            block = (
                f"**{i})** **[{title} [{version}]]({map_url})** **{mods}** `[{stars:.2f}★]`\n"
                f"{DaletAtoms.GLYPH_POINTER} ` {rank} ` {DaletAtoms.GLYPH_POINTER} **{pp:.2f}PP** {DaletAtoms.GLYPH_POINTER} **{acc}**\n"
                f"{DaletAtoms.GLYPH_POINTER} {score:,} {DaletAtoms.GLYPH_POINTER} {combo_str} {DaletAtoms.GLYPH_POINTER} `{hits_str}` {DaletAtoms.GLYPH_POINTER} {rel_time}\n"
                f"{DaletAtoms.GLYPH_POINTER} ⏱ {length_str} {DaletAtoms.GLYPH_POINTER} 🎵 {bpm:.0f} BPM {DaletAtoms.GLYPH_POINTER} `AR {ar} OD {od} HP {hp} CS {cs}`"
            )
            entries.append(block)

        embed.description = "\n\n".join(entries)
        DaletMolecules.add_standard_footer(embed, context_text="On osu! Bancho Server • Top 5")
        return embed

    @staticmethod
    def build_profile_card(user_data: dict, mode: str = "osu") -> discord.Embed:
        """Construye la tarjeta de perfil osu! limpia y estructurada."""
        username = user_data.get("username", "Desconocido")
        user_id = user_data.get("id", 0)
        stats = user_data.get("statistics", {})
        country = user_data.get("country", {})

        rank_val = stats.get("global_rank") or 9999999
        color = DaletAtoms.get_rank_color(rank_val)
        flag = _get_country_flag(country.get("code", ""))

        embed = discord.Embed(
            color=color
        )
        embed.set_author(
            name=f"{flag} osu! {_mode_title(mode)} Profile for {username}",
            icon_url=user_data.get("avatar_url"),
            url=f"https://osu.ppy.sh/users/{user_id}/{mode}"
        )

        if user_data.get("avatar_url"):
            embed.set_thumbnail(url=user_data["avatar_url"])
        if user_data.get("cover_url"):
            embed.set_image(url=user_data["cover_url"])

        # Sección 1: Ranking & Performance
        pp = stats.get("pp", 0)
        global_rank = stats.get("global_rank", 0)
        country_rank = stats.get("country_rank", 0)
        gr_str = f"#{global_rank:,}" if global_rank else "Sin rank"
        cr_str = f"#{country_rank:,}" if country_rank else "Sin rank"

        embed.add_field(
            name="Rendimiento",
            value=(
                f"{DaletAtoms.GLYPH_POINTER} **PP**: `{pp:,.2f}pp`\n"
                f"{DaletAtoms.GLYPH_POINTER} **Global**: `{gr_str}`\n"
                f"{DaletAtoms.GLYPH_POINTER} **País** ({country.get('code', '??')}): `{cr_str}`"
            ),
            inline=True
        )

        # Sección 2: Precisión & Nivel
        accuracy = stats.get("hit_accuracy", 0)
        level_data = stats.get("level", {})
        level = level_data.get("current", 0)
        progress = level_data.get("progress", 0)
        bar = DaletMolecules.create_progress_bar(progress, length=8)

        embed.add_field(
            name="Precisión & Nivel",
            value=(
                f"{DaletAtoms.GLYPH_POINTER} **Precisión**: `{accuracy:.2f}%`\n"
                f"{DaletAtoms.GLYPH_POINTER} **Nivel**: `{level}` ({progress}%)\n"
                f"`{bar}`"
            ),
            inline=True
        )

        # Sección 3: Actividad
        play_count = stats.get("play_count", 0)
        play_time_hours = (stats.get("play_time", 0) or 0) // 3600

        embed.add_field(
            name="Actividad",
            value=(
                f"{DaletAtoms.GLYPH_POINTER} **Partidas**: `{play_count:,}`\n"
                f"{DaletAtoms.GLYPH_POINTER} **Tiempo de juego**: `{play_time_hours:,}h`"
            ),
            inline=True
        )

        # Sección 4: Desglose de Récords
        grades = stats.get("grade_counts", {})
        ssh, ss = grades.get("ssh", 0), grades.get("ss", 0)
        sh, s = grades.get("sh", 0), grades.get("s", 0)
        a = grades.get("a", 0)

        embed.add_field(
            name="Récords Obtenidos",
            value=f"`SS` **{ssh+ss:,}** │ `S` **{sh+s:,}** │ `A` **{a:,}**",
            inline=False
        )

        DaletMolecules.add_standard_footer(embed, context_text=f"ID: {user_id}")
        return embed

    @staticmethod
    def build_compare_card(user1_data: dict, user2_data: dict, mode: str = "osu") -> discord.Embed:
        """Construye una tarjeta comparativa limpia entre dos jugadores."""
        u1_name = user1_data.get("username", "Jugador 1")
        u2_name = user2_data.get("username", "Jugador 2")

        u1_stats = user1_data.get("statistics", {})
        u2_stats = user2_data.get("statistics", {})

        u1_pp = u1_stats.get("pp", 0.0) or 0.0
        u2_pp = u2_stats.get("pp", 0.0) or 0.0

        u1_rank = u1_stats.get("global_rank", 0) or 0
        u2_rank = u2_stats.get("global_rank", 0) or 0

        u1_acc = u1_stats.get("hit_accuracy", 0.0) or 0.0
        u2_acc = u2_stats.get("hit_accuracy", 0.0) or 0.0

        winner = u1_name if u1_pp >= u2_pp else u2_name
        diff_pp = abs(u1_pp - u2_pp)

        embed = discord.Embed(
            title=f"Comparación osu! {_mode_title(mode)}",
            description=f"**{u1_name}** vs **{u2_name}**\n{DaletAtoms.GLYPH_POINTER} Lidera en PP: **{winner}** (`+{diff_pp:,.2f}pp`)",
            color=DaletAtoms.COLOR_PRIMARY
        )

        u1_gr_str = f"#{u1_rank:,}" if u1_rank else "Sin rank"
        u2_gr_str = f"#{u2_rank:,}" if u2_rank else "Sin rank"

        embed.add_field(
            name=u1_name,
            value=(
                f"{DaletAtoms.GLYPH_POINTER} **PP**: `{u1_pp:,.2f}pp`\n"
                f"{DaletAtoms.GLYPH_POINTER} **Global**: `{u1_gr_str}`\n"
                f"{DaletAtoms.GLYPH_POINTER} **Precisión**: `{u1_acc:.2f}%`"
            ),
            inline=True
        )

        embed.add_field(
            name=u2_name,
            value=(
                f"{DaletAtoms.GLYPH_POINTER} **PP**: `{u2_pp:,.2f}pp`\n"
                f"{DaletAtoms.GLYPH_POINTER} **Global**: `{u2_gr_str}`\n"
                f"{DaletAtoms.GLYPH_POINTER} **Precisión**: `{u2_acc:.2f}%`"
            ),
            inline=True
        )

        DaletMolecules.add_standard_footer(embed)
        return embed


async def setup(bot):
    pass


