import discord
from ui.atoms import DaletAtoms
from ui.molecules import DaletMolecules
from ui.locales import t

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
    """Presentador de UI para osu! con la identidad visual única de Dalet."""

    @staticmethod
    def _extract_score(play: dict) -> str:
        """Obtiene el puntaje formateado tanto para scores de Lazer como Classic/Bancho y fallidos."""
        for key in ("classic_total_score", "total_score", "legacy_total_score", "score"):
            val = play.get(key)
            if val is not None and val > 0:
                return f"{val:,}"

        # Si el score viene en 0 por ser jugada en osu! Lazer (solo_score)
        if play.get("passed", True) and (not play.get("score") or play.get("score") == 0):
            stats = play.get("statistics", {})
            c300 = stats.get("count_300", 0) or 0
            c100 = stats.get("count_100", 0) or 0
            c50 = stats.get("count_50", 0) or 0
            miss = stats.get("count_miss", 0) or 0
            total_hits = c300 + c100 + c50 + miss
            acc = float(play.get("accuracy", 0.0) or 0.0)
            max_combo = int(play.get("max_combo", 0) or 0)
            bm = play.get("beatmap", {})
            bm_max = bm.get("max_combo") or total_hits or 1
            combo_portion = (max_combo / max(1, bm_max)) * 700000
            acc_portion = (acc ** 2) * 300000
            lazer_score = int(combo_portion + acc_portion)
            if lazer_score > 0:
                return f"{lazer_score:,}"

        # Si el score viene en 0 de Bancho por ser jugada fallida (F)
        if not play.get("passed", True) or str(play.get("rank", "")).upper() == "F":
            stats = play.get("statistics", {})
            c300 = stats.get("count_300", 0)
            c100 = stats.get("count_100", 0)
            c50 = stats.get("count_50", 0)
            base_score = (c300 * 300) + (c100 * 100) + (c50 * 50)
            if base_score > 0:
                return f"~{base_score:,}"
            return "Fallido"

        return "0"

    @staticmethod
    def build_recent_card(username: str, mode: str, play: dict, user_data: dict = None, lang: str = "en") -> discord.Embed:
        """Construye una tarjeta de jugada reciente única, estructurada y sin ruido visual."""
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
        no_pp_label = t("osu.no_pp", lang)
        pp_str = f"**{pp:.2f}pp**" if pp is not None else f"**{no_pp_label}**"

        score = OsuPresenter._extract_score(play)
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
        country_code = user_data.get("country", {}).get("code", "").lower() if user_data else ""
        flag_md = f":flag_{country_code}: " if country_code else ""

        # Indicador de estado si falló el mapa
        passed = play.get("passed", True)
        fail_txt = t("osu.failed", lang)
        rank_badge = f"` {rank} `" if passed else f"` {rank} ({fail_txt}) `"

        embed = discord.Embed(
            color=DaletAtoms.get_grade_color(rank)
        )
        embed.set_author(
            name=t("osu.recent_author", lang, username=username, mode=_mode_title(mode)),
            icon_url=user_data.get("avatar_url") if user_data else None,
            url=f"https://osu.ppy.sh/users/{user_data.get('id', username)}/{mode}" if user_data else None
        )

        # Encabezado del mapa
        embed.description = (
            f"{flag_md}**[{artist} - {title} [{version}]]({map_url})**\n"
            f"**{mods}** │ ` {stars:.2f}★ ` │ {rank_badge} │ {rel_time}"
        )

        # Sección 1: Rendimiento
        embed.add_field(
            name=f"{DaletAtoms.GLYPH_POINTER} {t('osu.performance', lang)}",
            value=(
                f"{DaletAtoms.GLYPH_POINTER} **PP**: {pp_str}\n"
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.accuracy', lang)}**: `{acc}`\n"
                f"{DaletAtoms.GLYPH_POINTER} **Combo**: `{combo_str}`"
            ),
            inline=True
        )

        # Sección 2: Puntuación & Hits
        embed.add_field(
            name=f"{DaletAtoms.GLYPH_ACCURACY} {t('osu.score_hits', lang)}",
            value=(
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.score', lang)}**: `{score}`\n"
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.hits', lang)}**: `{hits_str}`\n"
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.misses', lang)}**: `{miss}`"
            ),
            inline=True
        )

        # Sección 3: Datos del Beatmap
        embed.add_field(
            name=f"{DaletAtoms.GLYPH_AIM} {t('osu.map', lang)}",
            value=(
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.length', lang)}**: `{length_str}` │ **BPM**: `{bpm:.0f}`\n"
                f"{DaletAtoms.GLYPH_POINTER} `AR {ar}` · `OD {od}` · `HP {hp}` · `CS {cs}`"
            ),
            inline=False
        )

        # Thumbnail con la portada del mapa
        covers = beatmapset.get("covers", {})
        thumb_url = covers.get("list") or covers.get("cover") or covers.get("card")
        if thumb_url:
            embed.set_thumbnail(url=thumb_url)

        DaletMolecules.add_standard_footer(embed, context_text="Bancho Server")
        return embed

    @staticmethod
    def build_top_card(username: str, mode: str, plays: list, user_data: dict = None, lang: str = "en") -> discord.Embed:
        """Construye un Embed estructurado con los Top Plays del usuario."""
        country_code = user_data.get("country", {}).get("code", "").lower() if user_data else ""
        flag_md = f":flag_{country_code}: " if country_code else ""

        title_txt = t("osu.top_title", lang, username=username, mode=_mode_title(mode))
        embed = discord.Embed(
            title=f"{flag_md}{title_txt}",
            color=DaletAtoms.COLOR_PRIMARY
        )
        embed.set_author(
            name=t("osu.top_author", lang, username=username),
            icon_url=user_data.get("avatar_url") if user_data else None,
            url=f"https://osu.ppy.sh/users/{user_data.get('id', username)}/{mode}" if user_data else None
        )

        if not plays:
            embed.description = t("osu.top_none", lang)
            DaletMolecules.add_standard_footer(embed, context_text="Bancho Server")
            return embed

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
            score = OsuPresenter._extract_score(p)

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
                f"**{i}.** **[{title} [{version}]]({map_url})** **{mods}** ` {stars:.2f}★ `\n"
                f"{DaletAtoms.GLYPH_POINTER} ` {rank} ` │ **{pp:.2f}pp** │ `{acc}` │ `{combo_str}`\n"
                f"{DaletAtoms.GLYPH_POINTER} Score: `{score}` │ `{hits_str}` │ {rel_time}\n"
                f"{DaletAtoms.GLYPH_POINTER} `{length_str}` │ `{bpm:.0f} BPM` │ `AR {ar} OD {od} HP {hp} CS {cs}`"
            )
            entries.append(block)

        embed.description = "\n\n".join(entries)
        DaletMolecules.add_standard_footer(embed, context_text="Bancho Server • Top 5")
        return embed

    @staticmethod
    def build_profile_card(user_data: dict, mode: str = "osu", lang: str = "en") -> discord.Embed:
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
            name=f"{flag} " + t("osu.top_author", lang, username=username),
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
        unranked_txt = t("osu.unranked", lang)
        gr_str = f"#{global_rank:,}" if global_rank else unranked_txt
        cr_str = f"#{country_rank:,}" if country_rank else unranked_txt

        embed.add_field(
            name=f"{DaletAtoms.GLYPH_POINTER} {t('osu.performance', lang)}",
            value=(
                f"{DaletAtoms.GLYPH_POINTER} **PP**: `{pp:,.2f}pp`\n"
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.global_rank', lang)}**: `{gr_str}`\n"
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.country_rank', lang, code=country.get('code', '??'))}**: `{cr_str}`"
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
            name=f"{DaletAtoms.GLYPH_ACCURACY} {t('osu.accuracy_level', lang)}",
            value=(
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.accuracy', lang)}**: `{accuracy:.2f}%`\n"
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.level', lang)}**: `{level}` ({progress}%)\n"
                f"`{bar}`"
            ),
            inline=True
        )

        # Sección 3: Actividad
        play_count = stats.get("play_count", 0)
        play_time_hours = (stats.get("play_time", 0) or 0) // 3600

        embed.add_field(
            name=f"{DaletAtoms.GLYPH_SPEED} {t('osu.activity', lang)}",
            value=(
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.plays', lang)}**: `{play_count:,}`\n"
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.play_time', lang)}**: `{play_time_hours:,}h`"
            ),
            inline=True
        )

        # Sección 4: Desglose de Récords
        grades = stats.get("grade_counts", {})
        ssh, ss = grades.get("ssh", 0), grades.get("ss", 0)
        sh, s = grades.get("sh", 0), grades.get("s", 0)
        a = grades.get("a", 0)

        embed.add_field(
            name=f"{DaletAtoms.GLYPH_STAR} {t('osu.grade_history', lang)}",
            value=f"`SS` **{ssh+ss:,}** │ `S` **{sh+s:,}** │ `A` **{a:,}**",
            inline=False
        )

        DaletMolecules.add_standard_footer(embed, context_text=f"ID: {user_id}")
        return embed

    @staticmethod
    def build_compare_card(user1_data: dict, user2_data: dict, mode: str = "osu", lang: str = "en") -> discord.Embed:
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

        title_txt = t("osu.comparison_title", lang, mode=_mode_title(mode))
        lead_txt = t("osu.leads_pp", lang, winner=winner, diff_pp=diff_pp)
        embed = discord.Embed(
            title=title_txt,
            description=f"**{u1_name}** vs **{u2_name}**\n{DaletAtoms.GLYPH_POINTER} {lead_txt}",
            color=DaletAtoms.COLOR_PRIMARY
        )

        unranked_txt = t("osu.unranked", lang)
        u1_gr_str = f"#{u1_rank:,}" if u1_rank else unranked_txt
        u2_gr_str = f"#{u2_rank:,}" if u2_rank else unranked_txt

        embed.add_field(
            name=u1_name,
            value=(
                f"{DaletAtoms.GLYPH_POINTER} **PP**: `{u1_pp:,.2f}pp`\n"
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.global_rank', lang)}**: `{u1_gr_str}`\n"
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.accuracy', lang)}**: `{u1_acc:.2f}%`"
            ),
            inline=True
        )

        embed.add_field(
            name=u2_name,
            value=(
                f"{DaletAtoms.GLYPH_POINTER} **PP**: `{u2_pp:,.2f}pp`\n"
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.global_rank', lang)}**: `{u2_gr_str}`\n"
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.accuracy', lang)}**: `{u2_acc:.2f}%`"
            ),
            inline=True
        )

        DaletMolecules.add_standard_footer(embed)
        return embed

    @staticmethod
    def build_skills_card(user_data: dict, skills_data: dict, roast_text: str = None, mode: str = "osu", lang: str = "en") -> discord.Embed:
        """Construye una tarjeta visual y detallada del desglose de habilidades (Skill Breakdown)."""
        username = user_data.get("username", "Jugador")
        user_id = user_data.get("id", 0)
        stats = user_data.get("statistics", {})

        pp = stats.get("pp", 0) or 0
        rank = stats.get("global_rank", 0) or 0
        unranked_txt = t("osu.unranked", lang)
        rank_str = f"#{rank:,}" if rank else unranked_txt
        country = user_data.get("country_code", "")
        flag = _get_country_flag(country)
        avatar_url = user_data.get("avatar_url", "")

        dominant = skills_data.get("dominant_skill", "N/A")
        weakest = skills_data.get("weakest_skill", "N/A")
        overall = skills_data.get("overall_skill_stars", 0.0)

        embed = discord.Embed(
            title=f"✦ Skill Breakdown — {username} {flag}",
            url=f"https://osu.ppy.sh/users/{user_id}/{mode}",
            color=DaletAtoms.COLOR_PRIMARY
        )
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        lbl_overall = t("osu.skills_overall", lang)
        lbl_strength = t("osu.skills_strength", lang)
        lbl_weakness = t("osu.skills_weakness", lang)

        desc_lines = [
            f"{DaletAtoms.GLYPH_POINTER} **{lbl_overall}**: `{overall:.2f}★` │ **PP**: `{pp:,.0f}` │ **Rank**: `{rank_str}`",
            f"{DaletAtoms.GLYPH_POINTER} **{lbl_strength}**: `{dominant}` │ **{lbl_weakness}**: `{weakest}`"
        ]
        embed.description = "\n".join(desc_lines)

        skill_metadata = [
            ("Aim", DaletAtoms.GLYPH_AIM),
            ("Speed", DaletAtoms.GLYPH_SPEED),
            ("Accuracy", DaletAtoms.GLYPH_ACCURACY),
            ("Stamina", DaletAtoms.GLYPH_STAMINA),
            ("Reading", DaletAtoms.GLYPH_READING)
        ]

        for sk_name, icon in skill_metadata:
            sk_info = skills_data.get(sk_name, {})
            stars = sk_info.get("stars", 0.0)
            top_maps = sk_info.get("top_maps", [])

            lines = []
            for m in top_maps[:3]:
                title = m.get("title", "Desconocido")
                ver = m.get("version", "Normal")
                if len(title) > 18:
                    title = title[:16] + ".."
                if len(ver) > 10:
                    ver = ver[:8] + ".."
                mods = m.get("mods_str", "+NM")
                sr = m.get("sr", 0.0)
                pp_val = m.get("pp", 0.0)
                b_id = m.get("beatmap_id")

                name_part = f"[{title} [{ver}]](https://osu.ppy.sh/b/{b_id})" if b_id else f"{title} [{ver}]"
                pp_str = f" ({pp_val:.0f}pp)" if pp_val > 0 else ""
                lines.append(f"{DaletAtoms.GLYPH_SUB} `{mods}` {name_part} • `{sr:.2f}★`{pp_str}")

            no_data_msg = t("osu.skills_no_data", lang)
            field_val = "\n".join(lines) if lines else no_data_msg
            embed.add_field(
                name=f"{icon} {sk_name} — `{stars:.2f}★`",
                value=field_val,
                inline=False
            )

        if roast_text:
            clean_roast = roast_text.strip().replace('"', '')
            verdict_title = f"{DaletAtoms.GLYPH_VERDICT} " + t("osu.skills_verdict", lang)
            embed.add_field(
                name=verdict_title,
                value=f"> *\"{clean_roast}\"*",
                inline=False
            )

        DaletMolecules.add_standard_footer(embed, context_text=f"ID: {user_id} • osu! {_mode_title(mode)}")
        return embed


async def setup(bot):
    pass


