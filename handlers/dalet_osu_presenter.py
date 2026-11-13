import io
from datetime import datetime
import discord
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Backend no interactivo sin GUI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import LinearSegmentedColormap

from ui.atoms import DaletAtoms
from ui.molecules import DaletMolecules
from ui.locales import t
from handlers.modules.dalet_osuanalyzer import OsuAnalyzer

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

def _format_stat_num(val) -> str:
    """Formatea AR/OD/CS/HP evitando decimales ruidosos (.0 o .333333)."""
    try:
        num = round(float(val or 0.0), 1)
    except (TypeError, ValueError):
        return "0"
    if abs(num - round(num)) < 0.05:
        return str(int(round(num)))
    return f"{num:.1f}"

def _format_play_pp(play: dict, lang: str = "en", compact: bool = False, decimals: int | None = None) -> str | None:
    """Formatea el PP real/simulado y su estimación 'if FC' cuando hubo fallo, misses o choke."""
    actual_raw = play.get("_pp_actual")
    pp_val = actual_raw if actual_raw is not None else play.get("pp")
    fc_raw = play.get("_pp_fc")
    is_sim = bool(play.get("_pp_is_simulated"))
    misses = (play.get("statistics") or {}).get("count_miss", 0) or 0
    is_fail = (play.get("passed") is False) or (str(play.get("rank", "")).upper() == "F")

    if pp_val is None and fc_raw is None:
        return None

    dec = (1 if compact else 2) if decimals is None else decimals
    prefix = "~" if is_sim else ""
    if pp_val is not None:
        pp_num = float(pp_val)
        pp_text = f"**{prefix}{pp_num:.{dec}f}pp**"
    else:
        pp_num = 0.0
        pp_text = f"**{t('osu.no_pp', lang)}**"

    if fc_raw is not None:
        fc_num = float(fc_raw)
        max_c = play.get("max_combo", 0) or 0
        bm_max = (play.get("beatmap") or {}).get("max_combo", 0) or 0
        has_break = is_fail or misses > 0 or (bm_max > 0 and max_c < int(bm_max * 0.98))
        if has_break and fc_num > max(pp_num + 0.5, 0.1):
            fc_fmt = f"{fc_num:.0f}pp" if compact else f"{fc_num:.2f}pp"
            pp_text += f" *({fc_fmt} FC)*"

    return pp_text

def _get_country_flag(country_code: str, plain: bool = False) -> str:
    """Formatea el código ISO de país (ej. 'CO', 'US') como etiqueta tipográfica sin emojis."""
    if not country_code or len(country_code) != 2:
        return ""
    if plain:
        return f"[{country_code.upper()}]"
    return f"`[{country_code.upper()}]`"

def _mode_title(mode: str) -> str:
    modes = {
        "osu": "Standard",
        "taiko": "Taiko",
        "fruits": "Catch the Beat",
        "mania": "Mania"
    }
    return modes.get((mode or "osu").lower(), str(mode).capitalize())

def _server_title(server: str) -> str:
    mapping = {
        "bancho": "Bancho Server",
        "akatsuki": "Akatsuki (Vanilla)",
        "akatsuki_rx": "Akatsuki (Relax)",
        "akatsuki_ap": "Akatsuki (Autopilot)",
        "gatari": "Gatari Server",
    }
    return mapping.get((server or "bancho").lower().strip(), "Bancho Server")

def _profile_url(user_data: dict, mode: str = "osu", fallback_username: str = "") -> str:
    if isinstance(user_data, dict):
        if user_data.get("profile_url"):
            return user_data["profile_url"]
        srv = (user_data.get("_server") or "bancho").lower()
        uid = user_data.get("id") or fallback_username
        if srv.startswith("akatsuki"):
            return f"https://akatsuki.gg/u/{uid}"
        if srv == "gatari":
            return f"https://osu.gatari.pw/u/{uid}"
        if uid:
            return f"https://osu.ppy.sh/users/{uid}/{mode}"
    return "https://osu.ppy.sh"

def _get_skill_glyph(skill_name: str) -> str:
    """Retorna el glifo tipográfico correspondiente a cada habilidad de osu! sin emojis."""
    mapping = {
        "aim": DaletAtoms.GLYPH_AIM,
        "speed": DaletAtoms.GLYPH_SPEED,
        "accuracy": DaletAtoms.GLYPH_ACCURACY,
        "stamina": DaletAtoms.GLYPH_STAMINA,
        "reading": DaletAtoms.GLYPH_READING,
        "patterning": DaletAtoms.GLYPH_PATTERNING,
        "agility": DaletAtoms.GLYPH_AGILITY,
        "precision": DaletAtoms.GLYPH_PRECISION,
        "chordjack": DaletAtoms.GLYPH_CHORDJACK,
        "ln": DaletAtoms.GLYPH_LN,
        "stream": DaletAtoms.GLYPH_STREAM,
        "tech": DaletAtoms.GLYPH_TECH,
    }
    return mapping.get((skill_name or "").lower().strip(), DaletAtoms.GLYPH_STAR)

def _calc_effective_sr(bm: dict, mods: list, mode: str = "osu") -> float:
    """Calcula el Star Rating efectivo considerando los mods (+DT, +HR, +EZ, +HT) calibrado con el rework moderno."""
    base_sr = float(bm.get("difficulty_rating", 0.0) or 0.0)
    if not mods or base_sr <= 0:
        return base_sr

    mod_list = []
    for m in mods:
        if isinstance(m, str):
            mod_list.append(m.upper())
        elif isinstance(m, dict) and "acronym" in m:
            mod_list.append(m["acronym"].upper())

    is_dt = any(m in ("DT", "NC") for m in mod_list)
    is_hr = "HR" in mod_list
    is_ez = "EZ" in mod_list
    is_ht = "HT" in mod_list

    bpm = float(bm.get("bpm", 170.0) or 170.0)
    cs = float(bm.get("cs", 4.0) or 4.0)
    mode_clean = (mode or "osu").lower().strip()

    eff_sr = base_sr
    if is_dt:
        eff_bpm = bpm * 1.5
        # En el rework de dificultad de Bancho, DT en mapas rápidos escala fuertemente
        if eff_bpm >= 260:
            dt_factor = 1.50 + min(0.06, (eff_bpm - 260) * 0.002)
        elif eff_bpm >= 210:
            dt_factor = 1.44 + (eff_bpm - 210) * 0.0012
        else:
            dt_factor = 1.38 + max(0.0, (eff_bpm - 150) * 0.001)
        eff_sr *= dt_factor
    if is_hr:
        if mode_clean in ("osu", "fruits"):
            eff_sr *= (1.08 + max(0.0, (cs - 4.0) * 0.02))
        else:
            eff_sr *= 1.05
    if is_ez:
        eff_sr *= 0.88
    if is_ht:
        eff_sr *= 0.75
    return round(eff_sr, 2)


class OsuPresenter:
    """Presentador de UI para osu! con la identidad visual única de Dalet."""

    format_mods = staticmethod(_format_mods)
    format_acc = staticmethod(_format_acc)
    mode_title = staticmethod(_mode_title)
    server_title = staticmethod(_server_title)

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
    def matches_mods(play: dict, mods_filter: str | None) -> bool:
        """
        Verifica si una jugada coincide con el filtro de mods especificado (ej. 'DT', 'HDDT', 'NM').
        Soporta equivalencias estándar de osu! (NC cuenta como DT, PF cuenta como SD).
        """
        if not mods_filter or not str(mods_filter).strip():
            return True

        clean_req = str(mods_filter).upper().replace("+", "").replace("-", "").replace(" ", "").strip()
        if not clean_req or clean_req in ("ALL", "ANY"):
            return True

        raw_mods = play.get("mods", []) or []
        play_mods = []
        for m in raw_mods:
            if isinstance(m, str):
                play_mods.append(m.upper())
            elif isinstance(m, dict) and "acronym" in m:
                play_mods.append(str(m["acronym"]).upper())

        effective_play_mods = [m for m in play_mods if m != "CL"]

        if clean_req in ("NM", "NOMOD"):
            return len(effective_play_mods) == 0

        req_acronyms = [clean_req[i:i + 2] for i in range(0, len(clean_req), 2) if len(clean_req[i:i + 2]) == 2]
        if not req_acronyms:
            return True

        normalized_play_set = set(effective_play_mods)
        if "NC" in normalized_play_set:
            normalized_play_set.add("DT")
        if "PF" in normalized_play_set:
            normalized_play_set.add("SD")

        return all(req in normalized_play_set for req in req_acronyms)

    @staticmethod
    def filter_recent_scores(scores: list, filter_by: str = "last", mods_filter: str | None = None) -> list:
        """
        Filtra y ordena la lista de jugadas recientes (últimas 24h en Bancho):
        - filter_by='last': orden cronológico (la más reciente primero).
        - filter_by='pass': solo jugadas completadas sin fallar (passed=True y rank != 'F').
        - filter_by='best': la mejor jugada reciente por PP / precisión / score.
        """
        if not scores:
            return []

        mode_filter = (filter_by or "last").lower().strip()
        filtered = []
        for idx, s in enumerate(scores):
            if not isinstance(s, dict):
                continue
            if not OsuPresenter.matches_mods(s, mods_filter):
                continue
            passed = s.get("passed", True) and str(s.get("rank", "")).upper() != "F"
            if mode_filter == "pass" and not passed:
                continue
            s_copy = dict(s)
            if "_recent_index" not in s_copy:
                s_copy["_recent_index"] = idx + 1
            filtered.append(s_copy)

        if mode_filter == "best":
            def _best_key(play_item: dict):
                is_pass = 1 if (play_item.get("passed", True) and str(play_item.get("rank", "")).upper() != "F") else 0
                pp_val = float(play_item.get("pp") or 0.0)
                acc_val = float(play_item.get("accuracy") or 0.0)
                score_val = int(play_item.get("classic_total_score") or play_item.get("total_score") or play_item.get("score") or 0)
                return (is_pass, pp_val, acc_val, score_val)

            filtered.sort(key=_best_key, reverse=True)

        return filtered

    @staticmethod
    def filter_and_sort_top_scores(scores: list, sort_by: str = "pp", mods_filter: str | None = None) -> list:
        """
        Anota cada jugada con su posición real (#1..#100) en el Top del jugador,
        aplica filtro de mods opcional y ordena según sort_by:
        - 'pp': Mayor PP (orden original).
        - 'recent': Más recientes primero ('Recent Best').
        - 'acc': Mayor precisión primero.
        """
        if not scores:
            return []

        annotated = []
        for idx, s in enumerate(scores):
            if not isinstance(s, dict):
                continue
            s_copy = dict(s)
            if "_top_rank" not in s_copy:
                s_copy["_top_rank"] = idx + 1
            if OsuPresenter.matches_mods(s_copy, mods_filter):
                annotated.append(s_copy)

        sort_mode = (sort_by or "pp").lower().strip()
        if sort_mode in ("recent", "rb", "recent_best", "date"):
            annotated.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
        elif sort_mode in ("acc", "accuracy"):
            annotated.sort(
                key=lambda x: (float(x.get("accuracy") or 0.0), float(x.get("pp") or 0.0)),
                reverse=True,
            )

        return annotated

    @staticmethod
    def build_recent_card(
        username: str,
        mode: str,
        play: dict,
        user_data: dict = None,
        lang: str = "en",
        filter_by: str = "last",
        mods_filter: str | None = None,
    ) -> discord.Embed:
        """Construye una tarjeta de jugada reciente única, estructurada y sin ruido visual."""
        beatmap = play.get("beatmap", {})
        beatmapset = play.get("beatmapset", {})
        stats = play.get("statistics", {})

        title = beatmapset.get("title", "Desconocido")
        artist = beatmapset.get("artist", "")
        version = beatmap.get("version", "Normal")
        beatmap_id = beatmap.get("id", 0)
        map_url = f"https://osu.ppy.sh/b/{beatmap_id}" if beatmap_id else "https://osu.ppy.sh"

        b_attrs = play.get("beatmap_attributes") or {}
        stars = play.get("official_sr") or b_attrs.get("star_rating") or _calc_effective_sr(beatmap, play.get("mods", []), mode=mode)
        mods = _format_mods(play.get("mods", []))
        rank = play.get("rank", "F").upper()
        acc = _format_acc(play.get("accuracy", 0.0))

        pp_str = _format_play_pp(play, lang=lang, compact=False) or f"**{t('osu.no_pp', lang)}**"

        score = OsuPresenter._extract_score(play)
        max_combo = play.get("max_combo", 0)
        map_max_combo = beatmap.get("max_combo")
        combo_str = f"x{max_combo:,}/{map_max_combo:,}" if map_max_combo else f"x{max_combo:,}"

        c300 = stats.get("count_300", 0)
        c100 = stats.get("count_100", 0)
        c50 = stats.get("count_50", 0)
        miss = stats.get("count_miss", 0)
        hits_str = f"[{c300}/{c100}/{c50}/{miss}]"

        # Atributos del beatmap (con prioridad para rosu-pp / mods aplicados)
        mods_list = play.get("mods", [])
        mods_upper = [m.upper() if isinstance(m, str) else m.get("acronym", "").upper() for m in mods_list]
        clock_rate = float(b_attrs.get("clock_rate") or 1.0)
        if clock_rate == 1.0:
            if any(m in ("DT", "NC") for m in mods_upper):
                clock_rate = 1.5
            elif any(m in ("HT", "DC") for m in mods_upper):
                clock_rate = 0.75

        ar = _format_stat_num(b_attrs.get("approach_rate") if b_attrs.get("approach_rate") is not None else beatmap.get("ar", 0.0))
        od = _format_stat_num(b_attrs.get("overall_difficulty") if b_attrs.get("overall_difficulty") is not None else beatmap.get("accuracy", 0.0))
        hp = _format_stat_num(b_attrs.get("hp") if b_attrs.get("hp") is not None else beatmap.get("drain", 0.0))
        cs = _format_stat_num(b_attrs.get("cs") if b_attrs.get("cs") is not None else beatmap.get("cs", 0.0))
        bpm = float(beatmap.get("bpm", 0) or 0) * clock_rate

        length_sec = beatmap.get("total_length") or beatmap.get("hit_length") or 0
        if length_sec and clock_rate != 1.0:
            length_sec = int(length_sec / clock_rate)
        length_str = DaletAtoms.format_duration(length_sec)

        rel_time = DaletAtoms.parse_timestamp_relative(play.get("created_at", ""))
        country_code = user_data.get("country", {}).get("code", "").upper() if user_data else ""
        flag_md = f"`[{country_code}]` " if country_code else ""

        # Indicador de estado y porcentaje de progreso si falló el mapa
        passed = play.get("passed", True)
        is_failed = (passed is False) or (rank == "F")
        if is_failed:
            rank = "F"
            total_objects = (
                (beatmap.get("count_circles", 0) or 0)
                + (beatmap.get("count_sliders", 0) or 0)
                + (beatmap.get("count_spinners", 0) or 0)
            )
            total_hits = (c300 or 0) + (c100 or 0) + (c50 or 0) + (miss or 0)
            if total_objects > 0:
                completion_pct = min(100.0, (total_hits / total_objects) * 100.0)
                rank_badge = DaletAtoms.get_grade_emoji(rank, suffix=f"{completion_pct:.1f}%")
            else:
                fail_txt = t("osu.failed", lang)
                rank_badge = DaletAtoms.get_grade_emoji(rank, suffix=fail_txt)
        else:
            rank_badge = DaletAtoms.get_grade_emoji(rank)

        filter_clean = (filter_by or "last").lower().strip()
        if filter_clean == "best":
            author_key = "osu.recent_best_author"
        elif filter_clean == "pass":
            author_key = "osu.recent_pass_author"
        else:
            author_key = "osu.recent_author"

        author_text = t(author_key, lang, username=username, mode=_mode_title(mode))
        if mods_filter and str(mods_filter).strip():
            clean_mod_tag = str(mods_filter).upper().replace("+", "").strip()
            author_text += f" · +{clean_mod_tag}"

        recent_idx = play.get("_recent_index")
        has_active_filter = (filter_clean != "last") or bool(mods_filter and str(mods_filter).strip())
        try_segment = ""
        if recent_idx and (int(recent_idx) > 1 or has_active_filter):
            try_word = "Intento" if (lang or "en").lower().startswith("es") else "Try"
            try_label = f"{try_word} #{int(recent_idx)}"
            author_text += f" · {try_label}"
            try_segment = f" · `{try_label}`"

        embed = discord.Embed(
            color=DaletAtoms.get_grade_color(rank)
        )
        embed.set_author(
            name=author_text,
            icon_url=user_data.get("avatar_url") if user_data else None,
            url=_profile_url(user_data, mode=mode, fallback_username=username) if user_data else None
        )

        # Diseño limpio mobile-first en 3 niveles (Application Emojis con fallback seguro)
        mode_emoji = DaletAtoms.get_mode_emoji(mode)
        mode_prefix = f"{mode_emoji} " if mode_emoji else ""
        line_map = f"{flag_md}{mode_prefix}**[{artist} - {title} [{version}]]({map_url})** `{mods}` · `{stars:.2f}★`"
        line_score = f"{rank_badge} · {pp_str} · **{acc}**{try_segment}"
        line_hits = f"`{combo_str}` · `{hits_str}` · {score} · {rel_time}"
        line_meta = f"`{length_str}` · `{bpm:.0f} BPM` · AR {ar} · OD {od} · CS {cs} · HP {hp}"
        embed.description = f"{line_map}\n\n{line_score}\n{line_hits}\n\n{line_meta}"

        # Thumbnail con la portada del mapa
        covers = beatmapset.get("covers", {})
        thumb_url = covers.get("list") or covers.get("cover") or covers.get("card")
        if thumb_url:
            embed.set_thumbnail(url=thumb_url)

        srv_name = _server_title(play.get("_server") or (user_data.get("_server") if user_data else "bancho"))
        DaletMolecules.add_standard_footer(embed, context_text=srv_name)
        return embed

    @staticmethod
    def build_top_card(
        username_or_user,
        mode_or_scores = "osu",
        plays: list = None,
        user_data: dict = None,
        mode: str = "osu",
        lang: str = "en",
        sort_by: str = "pp",
        mods_filter: str | None = None,
    ) -> discord.Embed:
        """Construye un Embed estructurado con los Top Plays del usuario con la identidad visual de Dalet."""
        if isinstance(username_or_user, dict):
            # Formato: build_top_card(user, best, mode="osu", lang="en")
            actual_user = username_or_user
            actual_scores = mode_or_scores if isinstance(mode_or_scores, list) else (plays or [])
            actual_mode = mode if isinstance(mode, str) else "osu"
            actual_lang = lang
            username = actual_user.get("username", "Jugador")
        else:
            # Formato: build_top_card(username, mode, best, user_data=user, lang="en")
            username = str(username_or_user)
            actual_mode = str(mode_or_scores) if isinstance(mode_or_scores, str) else mode
            actual_scores = plays if isinstance(plays, list) else []
            actual_user = user_data or {}
            actual_lang = lang

        user_id = actual_user.get("id", 0)
        stats = actual_user.get("statistics", {})

        pp_real = stats.get("pp", 0) or 0
        rank = stats.get("global_rank", 0) or 0
        unranked_txt = t("osu.unranked", actual_lang)
        rank_str = f"#{rank:,}" if rank else unranked_txt

        country = actual_user.get("country_code") or actual_user.get("country", {}).get("code", "")
        flag = _get_country_flag(country)
        avatar_url = actual_user.get("avatar_url", "")
        acc_global = stats.get("hit_accuracy", 0.0) or 0.0

        # Weighted PP estimado con decaimiento oficial del 0.95 (ordenado por PP descendente)
        scores_by_pp = sorted(actual_scores, key=lambda s: float(s.get("pp") or 0.0), reverse=True)
        raw_weighted = sum(float(s.get("pp") or 0.0) * (0.95 ** i) for i, s in enumerate(scores_by_pp))
        play_count_val = int(stats.get("play_count", 0) or 0)
        # Bonus PP de Bancho por cantidad de jugadas (máximo ~416.6667pp)
        bonus_pp = 416.6667 * (1.0 - (0.9994 ** min(play_count_val, 25000))) if play_count_val > 0 else 0.0
        weighted_pp = raw_weighted + bonus_pp if (not mods_filter and len(actual_scores) >= 50) else raw_weighted

        title_str = f"✦ Top Plays ({_mode_title(actual_mode)}) — {username}"
        if flag:
            title_str += f" {flag}"

        embed = discord.Embed(
            title=title_str,
            url=_profile_url(actual_user, mode=actual_mode, fallback_username=username),
            color=DaletAtoms.COLOR_PRIMARY
        )
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        lbl_raw_pp = t("osu.raw_pp", actual_lang)
        lbl_weighted_pp = t("osu.weighted_pp", actual_lang) if not mods_filter else "PP Sum (+Mods)"
        lbl_analyzed = t("osu.plays_analyzed", actual_lang)
        lbl_acc = t("osu.accuracy", actual_lang)

        mode_emoji = DaletAtoms.get_mode_emoji(actual_mode)
        mode_prefix = f"{mode_emoji} " if mode_emoji else ""
        desc_lines = [
            f"{mode_prefix}**{lbl_raw_pp}**: `{pp_real:,.0f}pp` · **{lbl_weighted_pp}**: `{weighted_pp:,.0f}pp` · **Rank**: `{rank_str}`",
            f"**{lbl_analyzed}**: {len(actual_scores)} · **{lbl_acc}**: {acc_global:.2f}%"
        ]
        embed.description = "\n".join(desc_lines)

        top_plays = actual_scores[:5]
        play_lines = []
        for i, s in enumerate(top_plays, 1):
            bm = s.get("beatmap", {})
            bms = s.get("beatmapset", {})
            acc = _format_acc(s.get("accuracy", 0.0))
            mods_str = _format_mods(s.get("mods", []))
            grade = s.get("rank", "?").upper()
            badge = DaletAtoms.get_grade_emoji(grade)
            title = bms.get("title", "Desconocido")
            ver = bm.get("version", "Normal")
            sr = s.get("official_sr") or s.get("beatmap_attributes", {}).get("star_rating") or _calc_effective_sr(bm, s.get("mods", []), mode=actual_mode)
            bm_id = bm.get("id", 0)
            max_c = s.get("max_combo", 0)
            bm_max = bm.get("max_combo") or ""
            combo_str = f"{max_c}x/{bm_max}x" if bm_max else f"{max_c}x"
            misses = s.get("statistics", {}).get("count_miss", 0) or 0
            miss_str = f"{misses}m" if misses > 0 else "FC"

            pp_disp = _format_play_pp(s, lang=lang, compact=True) or f"**{float(s.get('pp') or 0.0):.1f}pp**"

            if len(title) > 28:
                title = title[:26] + ".."
            if len(ver) > 18:
                ver = ver[:16] + ".."

            map_link = f"https://osu.ppy.sh/b/{bm_id}" if bm_id else "https://osu.ppy.sh"
            orig_rank = s.get("_top_rank", i)
            rel_time = DaletAtoms.parse_timestamp_relative(s.get("created_at", ""))
            time_suffix = f" · {rel_time}" if rel_time else ""

            header = f"**#{orig_rank}** [{title} [{ver}]]({map_link}) **{mods_str}** · {sr:.2f}★"
            stats_line = f"└ {badge} · {pp_disp} · **{acc}** · {combo_str} ({miss_str}){time_suffix}"
            play_lines.append(f"{header}\n{stats_line}")

        if play_lines:
            sort_clean = (sort_by or "pp").lower().strip()
            if sort_clean in ("recent", "rb", "recent_best", "date"):
                header_key = "osu.top_recent_header"
            elif sort_clean in ("acc", "accuracy"):
                header_key = "osu.top_acc_header"
            else:
                header_key = "osu.top_header"

            header_label = t(header_key, actual_lang, count=len(top_plays))
            if mods_filter and str(mods_filter).strip():
                clean_mod_tag = str(mods_filter).upper().replace("+", "").strip()
                header_label += f" · +{clean_mod_tag}"

            # Dividir dinámicamente en fields <= 980 chars para respetar el límite de 1024 de Discord
            chunks = []
            current_chunk = []
            current_len = 0
            for pl in play_lines:
                added_len = len(pl) + (2 if current_chunk else 0)
                if current_chunk and (current_len + added_len > 980):
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = [pl]
                    current_len = len(pl)
                else:
                    current_chunk.append(pl)
                    current_len += added_len
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))

            for idx_c, chunk_val in enumerate(chunks):
                embed.add_field(
                    name=f"{DaletAtoms.GLYPH_STAR} {header_label}" if idx_c == 0 else "\u200b",
                    value=chunk_val[:1024],
                    inline=False
                )

        srv_name = _server_title(actual_user.get("_server") if isinstance(actual_user, dict) else "bancho")
        DaletMolecules.add_standard_footer(embed, context_text=srv_name)
        return embed

    @staticmethod
    def generate_pp_chart(username: str, scores: list, lang: str = "en") -> discord.File | None:
        """Genera un gráfico de barras de distribución de PP ajustado dinámicamente al rango real para acentuar la diferencia entre plays."""
        try:
            pp_values = [s.get("pp", 0) for s in scores if s.get("pp")]
            if not pp_values:
                return None

            indices = np.arange(1, len(pp_values) + 1)
            min_pp = float(min(pp_values))
            max_pp = float(max(pp_values))
            pp_range = max_pp - min_pp

            # Gradiente Dalet carmesí profundo a vino
            dalet_crimson = LinearSegmentedColormap.from_list(
                'dalet_crimson', ['#d96b82', '#b3475c', '#802637', '#4a121c']
            )
            colors = dalet_crimson(np.linspace(0.0, 1.0, len(pp_values)))

            # Resaltar top 5 con acentos de rosa suave en sintonía con las jugadas principales
            if len(colors) >= 5:
                accent_shades = [
                    [0.97, 0.72, 0.78, 1.0],
                    [0.95, 0.65, 0.72, 1.0],
                    [0.93, 0.58, 0.66, 1.0],
                    [0.90, 0.52, 0.60, 1.0],
                    [0.87, 0.46, 0.55, 1.0],
                ]
                colors[:5] = accent_shades

            fig, ax = plt.subplots(figsize=(10, 4.2))
            fig.patch.set_facecolor("#131315")  # Dark Matte Dalet
            ax.set_facecolor("#101012")

            # Escalado dinámico ajustado al rango real (elimina el "zoom out" plano y acentúa caídas)
            if len(pp_values) >= 5 and pp_range >= 15:
                y_min = max(0.0, min_pp - pp_range * 0.10)
                y_max = max_pp + pp_range * 0.10
            elif len(pp_values) >= 5:
                y_min = max(0.0, min_pp - 15.0)
                y_max = max_pp + 15.0
            else:
                y_min = 0.0
                y_max = max_pp * 1.08
            ax.set_ylim(bottom=y_min, top=y_max)

            # Barras individuales limpias
            ax.bar(indices, pp_values, color=colors, width=0.72, zorder=3)

            # Línea de contorno escalonada (ax.step) para hacer resaltar cada escalón, caída y plateau
            ax.step(indices, pp_values, where="mid", color="#f7c1cb", linewidth=1.4, alpha=0.9, zorder=4)

            # Puntos luminosos en el top 5
            top_n = min(5, len(pp_values))
            ax.scatter(indices[:top_n], pp_values[:top_n], color="#ffffff", s=16, zorder=5,
                       edgecolors="#f7c1cb", linewidth=1.2)

            # Badge estadístico en la esquina superior derecha
            median_pp = float(np.median(pp_values))
            summary_txt = t("osu.chart_summary", lang,
                            top1=max_pp, median=median_pp, last_idx=len(pp_values),
                            min_pp=min_pp, delta=pp_range)
            ax.text(0.98, 0.92, summary_txt, transform=ax.transAxes,
                    fontsize=8.5, color="#e4d8dc", horizontalalignment="right",
                    bbox=dict(boxstyle="round,pad=0.4", facecolor="#1e171b", edgecolor="#3d2731", alpha=0.85))

            lbl_x = t("osu.chart_rank", lang)
            lbl_title = t("osu.chart_title", lang, username=username)

            ax.set_xlabel(lbl_x, color="#a89ca2", fontsize=9)
            ax.set_ylabel("PP", color="#a89ca2", fontsize=9)
            ax.set_title(lbl_title, color="white", fontsize=12, pad=12, fontweight="bold")
            ax.tick_params(colors="#8c8087", labelsize=8)
            ax.spines[:].set_color("#2a1f24")
            ax.grid(axis="y", color="#2a1f24", alpha=0.5, linestyle=":", zorder=1)

            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            return discord.File(buf, filename="pp_distribution.png")

        except Exception as e:
            return None

    @staticmethod
    def generate_progress_chart(username: str, history: list, lang: str = "en") -> discord.File | None:
        """Genera un gráfico de progreso de PP a lo largo del tiempo con estética Dalet."""
        try:
            # history viene ordenado DESC (el más reciente primero); invertimos a cronológico (más antiguo primero)
            history_chron = list(reversed(history))
            dates, pp_vals = [], []
            for h in history_chron:
                ts = h.get("log_date") or h.get("recorded_at") or ""
                pp = h.get("pp", 0)
                if ts:
                    try:
                        if hasattr(ts, "year"):
                            dates.append(ts)
                        else:
                            dates.append(datetime.fromisoformat(str(ts)[:19]))
                        pp_vals.append(float(pp))
                    except Exception:
                        continue

            if len(dates) < 2:
                return None

            fig, ax = plt.subplots(figsize=(10, 4.2))
            fig.patch.set_facecolor("#131315")
            ax.set_facecolor("#101012")

            min_pp, max_pp = min(pp_vals), max(pp_vals)
            pp_range = max_pp - min_pp
            if pp_range >= 10:
                ax.set_ylim(bottom=max(0.0, min_pp - pp_range * 0.15), top=max_pp + pp_range * 0.15)
            else:
                ax.set_ylim(bottom=max(0.0, min_pp - 10.0), top=max_pp + 10.0)

            # Sombra y línea Dalet carmesí
            ax.fill_between(dates, pp_vals, alpha=0.18, color="#d96b82")
            ax.plot(dates, pp_vals, color="#d96b82", linewidth=2.2, zorder=5)
            ax.scatter(dates, pp_vals, color="#f7c1cb", s=32, zorder=6, edgecolors="#101012", linewidth=1.0)

            # Tendencia polinomial / lineal si hay >= 3 puntos
            if len(dates) >= 3:
                x_num = mdates.date2num(dates)
                z = np.polyfit(x_num, pp_vals, 1)
                p = np.poly1d(z)
                x_smooth = np.linspace(x_num[0], x_num[-1], 200)
                ax.plot(
                    mdates.num2date(x_smooth), p(x_smooth),
                    color="#2cb67d", linewidth=1.2, linestyle="--", alpha=0.7, zorder=4
                )

            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            plt.xticks(rotation=25, fontsize=8)

            title_txt = f"Progreso PP — {username}" if (lang or "en").lower().startswith("es") else f"PP Progress — {username}"
            ax.set_ylabel("PP", color="#a89ca2", fontsize=9)
            ax.set_title(title_txt, color="white", fontsize=12, pad=12, fontweight="bold")
            ax.tick_params(colors="#8c8087", labelsize=8)
            ax.spines[:].set_color("#2a1f24")
            ax.grid(color="#2a1f24", alpha=0.45, zorder=1, linestyle=":")

            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            return discord.File(buf, filename="progress.png")
        except Exception:
            return None

    @staticmethod
    def build_profile_card(user_data: dict, mode: str = "osu", lang: str = "en") -> discord.Embed:
        """Construye la tarjeta de perfil osu! limpia, enriquecida y fiel a la API v2 y servidores privados."""
        username = user_data.get("username", "Desconocido")
        user_id = user_data.get("id", 0)
        stats = user_data.get("statistics", {}) or {}
        country = user_data.get("country", {}) or {}
        country_code = country.get("code") or user_data.get("country_code", "")
        srv_key = user_data.get("_server", "bancho")
        srv_label = _server_title(srv_key)

        rank_val = stats.get("global_rank") or 9999999
        color = DaletAtoms.get_rank_color(rank_val)
        flag = _get_country_flag(country_code, plain=True)
        flag_prefix = f"{flag} " if flag else ""

        embed = discord.Embed(
            color=color
        )
        embed.set_author(
            name=f"{flag_prefix}" + t("osu.profile_author", lang, username=username, mode=_mode_title(mode)),
            icon_url=user_data.get("avatar_url"),
            url=_profile_url(user_data, mode=mode, fallback_username=username)
        )

        if user_data.get("avatar_url"):
            embed.set_thumbnail(url=user_data["avatar_url"])
        if user_data.get("cover_url"):
            embed.set_image(url=user_data["cover_url"])

        # Sección 1: Ranking & Performance (incluye Peak Rank)
        pp = stats.get("pp", 0.0) or 0.0
        global_rank = stats.get("global_rank", 0)
        country_rank = stats.get("country_rank", 0)
        unranked_txt = t("osu.unranked", lang)
        gr_str = f"#{global_rank:,}" if global_rank else unranked_txt
        cr_str = f"#{country_rank:,}" if country_rank else unranked_txt

        rank_highest = user_data.get("rank_highest", {}) or {}
        peak_rank_val = rank_highest.get("rank")
        peak_str = f"#{peak_rank_val:,}" if peak_rank_val else gr_str

        perf_lines = [
            f"{DaletAtoms.GLYPH_POINTER} **PP**: `{pp:,.2f}pp`",
            f"{DaletAtoms.GLYPH_POINTER} **{t('osu.global_rank', lang)}**: `{gr_str}`",
            f"{DaletAtoms.GLYPH_POINTER} **{t('osu.country_rank', lang, code=country_code or '??')}**: `{cr_str}`",
            f"{DaletAtoms.GLYPH_POINTER} **{t('osu.peak_rank', lang)}**: `{peak_str}`",
        ]
        mode_emoji = DaletAtoms.get_mode_emoji(mode)
        perf_glyph = mode_emoji or DaletAtoms.GLYPH_POINTER
        embed.add_field(
            name=f"{perf_glyph} {t('osu.performance', lang)}",
            value="\n".join(perf_lines),
            inline=True
        )

        # Sección 2: Precisión & Nivel
        accuracy = stats.get("hit_accuracy", 0.0) or 0.0
        level_data = stats.get("level", {}) or {}
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

        # Sección 3: Actividad & Scores (Max Combo & Ranked Score)
        play_count = stats.get("play_count", 0) or 0
        play_time_hours = (stats.get("play_time", 0) or 0) // 3600
        max_combo = stats.get("maximum_combo", 0) or 0
        ranked_score = stats.get("ranked_score", 0) or 0

        act_lines = [
            f"{DaletAtoms.GLYPH_POINTER} **{t('osu.plays', lang)}**: `{play_count:,}` │ **{t('osu.play_time', lang)}**: `{play_time_hours:,}h`",
            f"{DaletAtoms.GLYPH_POINTER} **{t('osu.max_combo', lang)}**: `{max_combo:,}x` │ **{t('osu.ranked_score', lang)}**: `{ranked_score:,}`",
        ]
        embed.add_field(
            name=f"{DaletAtoms.GLYPH_SPEED} {t('osu.activity', lang)}",
            value="\n".join(act_lines),
            inline=False
        )

        # Sección 4: Desglose de Récords
        grades = stats.get("grade_counts", {}) or {}
        ssh, ss = grades.get("ssh", 0) or 0, grades.get("ss", 0) or 0
        sh, s = grades.get("sh", 0) or 0, grades.get("s", 0) or 0
        a = grades.get("a", 0) or 0

        ss_badge = DaletAtoms.get_grade_emoji("X")
        s_badge = DaletAtoms.get_grade_emoji("S")
        a_badge = DaletAtoms.get_grade_emoji("A")

        embed.add_field(
            name=f"{DaletAtoms.GLYPH_STAR} {t('osu.grade_history', lang)}",
            value=f"{ss_badge} **{ssh+ss:,}** │ {s_badge} **{sh+s:,}** │ {a_badge} **{a:,}**",
            inline=False
        )

        DaletMolecules.add_standard_footer(embed, context_text=f"ID: {user_id} {DaletAtoms.GLYPH_PIPE} {srv_label}")
        return embed

    @staticmethod
    def build_firsts_card(
        username: str,
        firsts: list,
        user_data: dict = None,
        mode: str = "osu",
        lang: str = "en"
    ) -> discord.Embed:
        """Construye una tarjeta elegante con los récords #1 globales del jugador sin emojis."""
        avatar_url = user_data.get("avatar_url") if user_data else None
        country = (user_data.get("country", {}).get("code", "") or user_data.get("country_code", "")) if user_data else ""
        flag = _get_country_flag(country, plain=True)
        srv_key = user_data.get("_server", "bancho") if user_data else "bancho"
        srv_label = _server_title(srv_key)

        title_str = f"✦ {t('osu.firsts_title', lang, username=username, mode=_mode_title(mode))}"
        if flag:
            title_str += f" {flag}"

        embed = discord.Embed(
            title=title_str,
            url=_profile_url(user_data, mode=mode, fallback_username=username),
            color=DaletAtoms.COLOR_PRIMARY
        )
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        play_lines = []
        for i, s in enumerate(firsts[:10], 1):
            bm = s.get("beatmap", {}) or {}
            bms = s.get("beatmapset", {}) or {}
            pp_val = s.get("pp")
            acc = _format_acc(s.get("accuracy", 0.0))
            mods_str = _format_mods(s.get("mods", []))
            grade = str(s.get("rank", "?")).upper()
            badge = DaletAtoms.get_grade_emoji(grade)
            title = bms.get("title", "Desconocido")
            ver = bm.get("version", "Normal")
            sr = s.get("official_sr") or s.get("beatmap_attributes", {}).get("star_rating") or _calc_effective_sr(bm, s.get("mods", []), mode=mode)
            bm_id = bm.get("id", 0)
            map_link = f"https://osu.ppy.sh/b/{bm_id}" if bm_id else "https://osu.ppy.sh"

            max_c = s.get("max_combo", 0) or 0
            bm_max = bm.get("max_combo") or ""
            combo_str = f"{max_c}x/{bm_max}x" if bm_max else f"{max_c}x"

            if len(title) > 26:
                title = title[:24] + ".."
            if len(ver) > 16:
                ver = ver[:14] + ".."

            pp_disp = _format_play_pp(s, lang=lang, compact=True, decimals=0)
            if not pp_disp:
                score_str = OsuPresenter._extract_score(s)
                pp_disp = f"`{score_str}`"

            header = f"`#{i}` {badge} **[{title} [{ver}]]({map_link})**"
            stats_line = f"└─ {pp_disp} │ `{acc}` │ `{combo_str}` │ **{mods_str}** │ `{sr:.2f}★`"
            play_lines.append(f"{header}\n{stats_line}")

        embed.description = "\n\n".join(play_lines)
        DaletMolecules.add_standard_footer(embed, context_text=f"Total: {len(firsts)} #1s {DaletAtoms.GLYPH_PIPE} osu! {_mode_title(mode)} {DaletAtoms.GLYPH_PIPE} {srv_label}")
        return embed

    @staticmethod
    def build_compare_card(
        user1_data: dict,
        user2_data: dict,
        skills1: dict = None,
        skills2: dict = None,
        mode: str = "osu",
        lang: str = "en",
        common_maps_data: dict = None,
        verdict_text: str = None,
    ) -> discord.Embed:
        """Construye una tarjeta comparativa profesional y profunda entre dos jugadores sin emojis."""
        u1_name = user1_data.get("username", "Jugador 1")
        u2_name = user2_data.get("username", "Jugador 2")

        s1 = user1_data.get("statistics", {}) or {}
        s2 = user2_data.get("statistics", {}) or {}

        pp1 = float(s1.get("pp", 0.0) or 0.0)
        pp2 = float(s2.get("pp", 0.0) or 0.0)

        gr1 = int(s1.get("global_rank", 0) or 0)
        gr2 = int(s2.get("global_rank", 0) or 0)

        cr1 = int(s1.get("country_rank", 0) or 0)
        cr2 = int(s2.get("country_rank", 0) or 0)

        c1 = user1_data.get("country_code") or user1_data.get("country", {}).get("code", "")
        c2 = user2_data.get("country_code") or user2_data.get("country", {}).get("code", "")

        acc1 = float(s1.get("hit_accuracy", 0.0) or 0.0)
        acc2 = float(s2.get("hit_accuracy", 0.0) or 0.0)

        pc1 = int(s1.get("play_count", 0) or 0)
        pc2 = int(s2.get("play_count", 0) or 0)

        h1 = int((s1.get("play_time", 0) or 0) // 3600)
        h2 = int((s2.get("play_time", 0) or 0) // 3600)

        mc1 = int(s1.get("maximum_combo", 0) or 0)
        mc2 = int(s2.get("maximum_combo", 0) or 0)

        grades1 = s1.get("grade_counts", {}) or {}
        grades2 = s2.get("grade_counts", {}) or {}
        ss1 = int(grades1.get("ss", 0) or 0) + int(grades1.get("ssh", 0) or 0)
        ss2 = int(grades2.get("ss", 0) or 0) + int(grades2.get("ssh", 0) or 0)
        s_count1 = int(grades1.get("s", 0) or 0) + int(grades1.get("sh", 0) or 0)
        s_count2 = int(grades2.get("s", 0) or 0) + int(grades2.get("sh", 0) or 0)

        has_skills = bool(skills1 and skills2)
        ov_pts1 = float(skills1.get("overall_skill_points", 0.0) or 0.0) if has_skills else 0.0
        ov_pts2 = float(skills2.get("overall_skill_points", 0.0) or 0.0) if has_skills else 0.0
        dom1 = skills1.get("dominant_skill", "N/A") if has_skills else "N/A"
        dom2 = skills2.get("dominant_skill", "N/A") if has_skills else "N/A"
        tier1 = skills1.get("overall_tier_name", "") if has_skills else ""
        tier2 = skills2.get("overall_tier_name", "") if has_skills else ""

        # Head-to-Head Scoring
        wins1, wins2 = 0, 0
        if pp1 > pp2: wins1 += 1
        elif pp2 > pp1: wins2 += 1

        if gr1 and gr2:
            if gr1 < gr2: wins1 += 1
            elif gr2 < gr1: wins2 += 1
        elif gr1 and not gr2:
            wins1 += 1
        elif gr2 and not gr1:
            wins2 += 1

        if acc1 > acc2: wins1 += 1
        elif acc2 > acc1: wins2 += 1

        if has_skills and (ov_pts1 or ov_pts2):
            if ov_pts1 > ov_pts2: wins1 += 1
            elif ov_pts2 > ov_pts1: wins2 += 1

        mode_clean = (mode or "osu").lower().strip()
        mode_skills = OsuAnalyzer.get_mode_skills(mode_clean) if has_skills else []
        for sk in mode_skills:
            pt1 = float(skills1.get(sk, {}).get("points", 0.0) or 0.0)
            pt2 = float(skills2.get(sk, {}).get("points", 0.0) or 0.0)
            if pt1 > pt2: wins1 += 1
            elif pt2 > pt1: wins2 += 1

        if mc1 > mc2: wins1 += 1
        elif mc2 > mc1: wins2 += 1

        if h1 > h2: wins1 += 1
        elif h2 > h1: wins2 += 1

        if (ss1 + s_count1) > (ss2 + s_count2): wins1 += 1
        elif (ss2 + s_count2) > (ss1 + s_count1): wins2 += 1

        diff_pp = abs(pp1 - pp2)
        pp_winner = u1_name if pp1 >= pp2 else u2_name
        lead_txt = t("osu.leads_pp", lang, winner=pp_winner, diff_pp=diff_pp)

        mode_name = _mode_title(mode_clean)
        if wins1 > wins2:
            h2h_summary = t("osu.compare_score_lead", lang, winner=u1_name, wins1=wins1, wins2=wins2, mode=mode_name)
        elif wins2 > wins1:
            h2h_summary = t("osu.compare_score_lead", lang, winner=u2_name, wins1=wins2, wins2=wins1, mode=mode_name)
        else:
            h2h_summary = t("osu.compare_score_tie", lang, wins1=wins1, wins2=wins2, mode=mode_name)

        mode_emoji = DaletAtoms.get_mode_emoji(mode_clean)
        mode_prefix = f"{mode_emoji} " if mode_emoji else ""
        embed = discord.Embed(
            title=f"✦ Head-to-Head {DaletAtoms.GLYPH_PIPE} {u1_name} vs {u2_name}",
            description=f"{mode_prefix}{h2h_summary}\n{DaletAtoms.GLYPH_POINTER} {lead_txt}",
            color=DaletAtoms.COLOR_PRIMARY
        )

        unranked_txt = t("osu.unranked", lang)
        u1_gr_str = f"#{gr1:,}" if gr1 else unranked_txt
        u2_gr_str = f"#{gr2:,}" if gr2 else unranked_txt

        u1_cr_str = f" (#{cr1:,} {c1})" if (cr1 and c1) else ""
        u2_cr_str = f" (#{cr2:,} {c2})" if (cr2 and c2) else ""

        u1_skill_line = f"\n{DaletAtoms.GLYPH_POINTER} **Skill**: `{ov_pts1:.1f} pts` `[{tier1}]`" if (has_skills and ov_pts1 > 0) else ""
        u2_skill_line = f"\n{DaletAtoms.GLYPH_POINTER} **Skill**: `{ov_pts2:.1f} pts` `[{tier2}]`" if (has_skills and ov_pts2 > 0) else ""

        str_lbl = t("osu.skills_strength", lang)
        u1_spec_line = f"\n{DaletAtoms.GLYPH_POINTER} **{str_lbl}**: `{dom1}`" if (has_skills and dom1 != 'N/A') else ""
        u2_spec_line = f"\n{DaletAtoms.GLYPH_POINTER} **{str_lbl}**: `{dom2}`" if (has_skills and dom2 != 'N/A') else ""

        embed.add_field(
            name=f"{DaletAtoms.GLYPH_STAR} {u1_name}",
            value=(
                f"{DaletAtoms.GLYPH_POINTER} **PP**: `{pp1:,.1f}pp`\n"
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.global_rank', lang)}**: `{u1_gr_str}`{u1_cr_str}\n"
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.accuracy', lang)}**: `{acc1:.2f}%`"
                f"{u1_skill_line}"
                f"{u1_spec_line}"
            ),
            inline=True
        )

        embed.add_field(
            name=f"{DaletAtoms.GLYPH_STAR} {u2_name}",
            value=(
                f"{DaletAtoms.GLYPH_POINTER} **PP**: `{pp2:,.1f}pp`\n"
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.global_rank', lang)}**: `{u2_gr_str}`{u2_cr_str}\n"
                f"{DaletAtoms.GLYPH_POINTER} **{t('osu.accuracy', lang)}**: `{acc2:.2f}%`"
                f"{u2_skill_line}"
                f"{u2_spec_line}"
            ),
            inline=True
        )

        is_es = lang.lower().startswith("es")
        if has_skills and mode_skills:
            skill_lines = []
            for sk in mode_skills:
                glyph = _get_skill_glyph(sk)
                pt1 = float(skills1.get(sk, {}).get("points", 0.0) or 0.0)
                pt2 = float(skills2.get(sk, {}).get("points", 0.0) or 0.0)
                diff = abs(pt1 - pt2)
                if pt1 > pt2:
                    lead_badge = f"▲ +{diff:.1f} {u1_name[:10]}"
                    arrow = "»"
                elif pt2 > pt1:
                    lead_badge = f"▲ +{diff:.1f} {u2_name[:10]}"
                    arrow = "«"
                else:
                    lead_badge = "Empate" if is_es else "Tie"
                    arrow = "="

                skill_lines.append(
                    f"{glyph} **{sk}**: `{pt1:.1f} pts` {arrow} `{pt2:.1f} pts` │ *{lead_badge}*"
                )

            embed.add_field(
                name=f"{DaletAtoms.GLYPH_POINTER} {t('osu.compare_skills_title', lang)}",
                value="\n".join(skill_lines),
                inline=False
            )

        # Sección: Mapas en Común (Duelos Directos en el Top)
        if common_maps_data and common_maps_data.get("total_common", 0) > 0:
            tot_c = common_maps_data["total_common"]
            cw1 = common_maps_data.get("wins1", 0)
            cw2 = common_maps_data.get("wins2", 0)
            c_maps = common_maps_data.get("maps", [])

            if is_es:
                c_title = f"{DaletAtoms.GLYPH_STAR} Mapas en Común en Top ({tot_c}) │ {u1_name[:10]} {cw1} – {cw2} {u2_name[:10]}"
            else:
                c_title = f"{DaletAtoms.GLYPH_STAR} Shared Top Maps ({tot_c}) │ {u1_name[:10]} {cw1} – {cw2} {u2_name[:10]}"

            duel_lines = []
            for dm in c_maps[:3]:
                m_title = dm["title"]
                m_ver = dm["version"]
                if len(m_title) > 22:
                    m_title = m_title[:20] + ".."
                if len(m_ver) > 12:
                    m_ver = m_ver[:10] + ".."
                bid = dm["beatmap_id"]
                m_link = f"[{m_title} [{m_ver}]](https://osu.ppy.sh/b/{bid})"
                w_tag = u1_name[:9] if dm["winner"] == 1 else (u2_name[:9] if dm["winner"] == 2 else "=")
                duel_lines.append(
                    f"{DaletAtoms.GLYPH_SUB} **{m_link}** (`▲ {w_tag}`)\n"
                    f"└─ `{u1_name[:8]}`: **{dm['pp1']:.0f}pp** (`{dm['acc1']:.1f}%` {dm['mods1']}) │ "
                    f"`{u2_name[:8]}`: **{dm['pp2']:.0f}pp** (`{dm['acc2']:.1f}%` {dm['mods2']})"
                )
            embed.add_field(name=c_title, value="\n\n".join(duel_lines), inline=False)

        combo_winner = u1_name[:10] if mc1 > mc2 else (u2_name[:10] if mc2 > mc1 else "=")
        play_winner = u1_name[:10] if pc1 > pc2 else (u2_name[:10] if pc2 > pc1 else "=")
        hours_winner = u1_name[:10] if h1 > h2 else (u2_name[:10] if h2 > h1 else "=")
        tot_grades1 = ss1 + s_count1
        tot_grades2 = ss2 + s_count2
        grades_winner = u1_name[:10] if tot_grades1 > tot_grades2 else (u2_name[:10] if tot_grades2 > tot_grades1 else "=")

        consistency_lines = [
            f"{DaletAtoms.GLYPH_SUB} **Max Combo**: `{mc1:,}x` vs `{mc2:,}x` ({combo_winner})",
            f"{DaletAtoms.GLYPH_SUB} **{t('osu.plays', lang)}**: `{pc1:,}` vs `{pc2:,}` ({play_winner})",
            f"{DaletAtoms.GLYPH_SUB} **{t('osu.play_time', lang)}**: `{h1:,}h` vs `{h2:,}h` ({hours_winner})",
            f"{DaletAtoms.GLYPH_SUB} **SS / S**: `{ss1} / {s_count1}` vs `{ss2} / {s_count2}` ({grades_winner})",
        ]
        embed.add_field(
            name=f"{DaletAtoms.GLYPH_POINTER} {t('osu.compare_consistency_title', lang)}",
            value="\n".join(consistency_lines),
            inline=False
        )

        if verdict_text and verdict_text.strip():
            clean_verdict = verdict_text.strip().replace('"', '')
            v_title = f"{DaletAtoms.GLYPH_VERDICT} " + ("Veredicto del Duelo" if is_es else "Duel Verdict")
            embed.add_field(
                name=v_title,
                value=f"> *\"{clean_verdict}\"*",
                inline=False
            )

        fav_avatar = user1_data.get("avatar_url") if wins1 >= wins2 else user2_data.get("avatar_url")
        if fav_avatar:
            embed.set_thumbnail(url=fav_avatar)

        srv_key = user1_data.get("_server", "bancho")
        srv_label = _server_title(srv_key)
        DaletMolecules.add_standard_footer(embed, context_text=f"Modo: {mode_name} {DaletAtoms.GLYPH_PIPE} {srv_label}")
        return embed


    @staticmethod
    def build_skills_card(
        user_data: dict,
        skills_data: dict,
        roast_text: str = None,
        mode: str = "osu",
        lang: str = "en",
        mods_filter: str | None = None,
    ) -> discord.Embed:
        """Construye una tarjeta visual y detallada del desglose de habilidades (Skill Breakdown)."""
        username = user_data.get("username", "Jugador")
        user_id = user_data.get("id", 0)
        stats = user_data.get("statistics", {})
        srv_key = user_data.get("_server", "bancho")
        srv_label = _server_title(srv_key)

        pp = stats.get("pp", 0) or 0
        rank = stats.get("global_rank", 0) or 0
        unranked_txt = t("osu.unranked", lang)
        rank_str = f"#{rank:,}" if rank else unranked_txt
        country = user_data.get("country_code") or user_data.get("country", {}).get("code", "")
        flag = _get_country_flag(country, plain=True)
        avatar_url = user_data.get("avatar_url", "")

        dominant = skills_data.get("dominant_skill", "N/A")
        weakest = skills_data.get("weakest_skill", "N/A")

        mod_tag = ""
        if mods_filter and str(mods_filter).strip():
            clean_mod = str(mods_filter).upper().replace("+", "").strip()
            mod_tag = f" · +{clean_mod}"

        embed = discord.Embed(
            title=f"✦ Skill Breakdown ({_mode_title(mode)}{mod_tag}) — {username} {flag}".strip(),
            url=_profile_url(user_data, mode=mode, fallback_username=username),
            color=DaletAtoms.COLOR_PRIMARY
        )
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        lbl_overall = t("osu.skills_overall", lang)
        lbl_strength = t("osu.skills_strength", lang)
        lbl_weakness = t("osu.skills_weakness", lang)

        ov_pts = skills_data.get("overall_skill_points", 0.0)
        ov_glyph, ov_tier = OsuAnalyzer.get_tier_info(ov_pts, lang=lang)

        dom_info = skills_data.get(dominant, {})
        dom_pts = dom_info.get("points", 0.0)
        weak_info = skills_data.get(weakest, {})
        weak_pts = weak_info.get("points", 0.0)

        mode_emoji = DaletAtoms.get_mode_emoji(mode)
        ov_prefix = mode_emoji or DaletAtoms.GLYPH_POINTER
        desc_lines = [
            f"{ov_prefix} **{lbl_overall}**: `{ov_pts:.1f} pts` {ov_glyph} `[{ov_tier}]` │ **PP**: `{pp:,.0f}` │ **Rank**: `{rank_str}`",
            f"{DaletAtoms.GLYPH_POINTER} **{lbl_strength}**: `{dominant}` (`{dom_pts:.1f} pts`) │ **{lbl_weakness}**: `{weakest}` (`{weak_pts:.1f} pts`)",
            "`──────────────────────────────────────────`"
        ]
        embed.description = "\n".join(desc_lines)

        skill_icons = {
            "Aim": DaletAtoms.GLYPH_AIM,
            "Speed": DaletAtoms.GLYPH_SPEED,
            "Accuracy": DaletAtoms.GLYPH_ACCURACY,
            "Stamina": DaletAtoms.GLYPH_STAMINA,
            "Reading": DaletAtoms.GLYPH_READING,
            "Patterning": DaletAtoms.GLYPH_PATTERNING,
            "Agility": DaletAtoms.GLYPH_AGILITY,
            "Precision": DaletAtoms.GLYPH_PRECISION,
            "Chordjack": DaletAtoms.GLYPH_CHORDJACK,
            "LN": DaletAtoms.GLYPH_LN,
            "Stream": DaletAtoms.GLYPH_STREAM,
            "Tech": DaletAtoms.GLYPH_TECH
        }

        active_skills = OsuAnalyzer.get_mode_skills(mode)
        skill_metadata = [(sk, skill_icons.get(sk, "✦")) for sk in active_skills]

        for sk_name, icon in skill_metadata:
            sk_info = skills_data.get(sk_name, {})
            pts = float(sk_info.get("points", 0.0) or 0.0)
            t_glyph, t_name = OsuAnalyzer.get_tier_info(pts, lang=lang)
            top_maps = sk_info.get("top_maps", [])
            bar_str = DaletMolecules.create_progress_bar(pts, length=8)

            lines = []
            for m in top_maps[:2]:
                title = m.get("title", "Desconocido")
                ver = m.get("version", "Normal")
                if len(title) > 22:
                    title = title[:20] + ".."
                if len(ver) > 12:
                    ver = ver[:10] + ".."
                mods = m.get("mods_str", "+NM")
                sr = m.get("sr", 0.0)
                pp_val = m.get("pp", 0.0)
                b_id = m.get("beatmap_id")

                name_part = f"[{title} [{ver}]](https://osu.ppy.sh/b/{b_id})" if b_id else f"{title} [{ver}]"
                pp_str = f" · **{pp_val:.0f}pp**" if pp_val > 0 else ""
                lines.append(f"{DaletAtoms.GLYPH_SUB} `{mods}` {name_part} (`{sr:.2f}★`){pp_str}")

            no_data_msg = t("osu.skills_no_qualifying", lang)
            field_val = "\n".join(lines) if lines else no_data_msg
            embed.add_field(
                name=f"{icon} {sk_name} │ `{bar_str}` `{pts:.1f} pts` {t_glyph} `[{t_name}]`",
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

        DaletMolecules.add_standard_footer(embed, context_text=f"ID: {user_id} {DaletAtoms.GLYPH_PIPE} osu! {_mode_title(mode)} {DaletAtoms.GLYPH_PIPE} {srv_label}")
        return embed

    @staticmethod
    def build_map_card(
        beatmap_data: dict,
        pp_table: dict | None = None,
        mode: str = "osu",
        mods: list | None = None,
        lang: str = "en",
    ) -> discord.Embed:
        """Construye una ficha técnica completa de beatmap con simulación PP (95/98/99/100%)."""
        bm = beatmap_data or {}
        bms = bm.get("beatmapset") or {}
        sim = pp_table or {}

        bm_id = bm.get("id", 0)
        set_id = bms.get("id") or bm.get("beatmapset_id") or 0
        title = bms.get("title") or bm.get("title") or "Desconocido"
        artist = bms.get("artist") or bm.get("artist") or ""
        version = bm.get("version") or "Normal"
        mapper = bms.get("creator") or "Desconocido"
        status = str(bm.get("status") or bms.get("status") or "unknown").capitalize()
        map_url = f"https://osu.ppy.sh/b/{bm_id}" if bm_id else "https://osu.ppy.sh"

        mods_clean = mods or []
        mods_str = _format_mods(mods_clean)
        clock_rate = float(sim.get("clock_rate") or 1.0)
        if clock_rate == 1.0:
            mods_up = [str(m).upper() for m in mods_clean]
            if any(m in ("DT", "NC") for m in mods_up):
                clock_rate = 1.5
            elif any(m in ("HT", "DC") for m in mods_up):
                clock_rate = 0.75

        stars = float(sim.get("stars") or bm.get("difficulty_rating") or _calc_effective_sr(bm, mods_clean, mode=mode))
        ar = _format_stat_num(sim.get("ar") if sim.get("ar") is not None else bm.get("ar", 0.0))
        od = _format_stat_num(sim.get("od") if sim.get("od") is not None else bm.get("accuracy", 0.0))
        hp = _format_stat_num(sim.get("hp") if sim.get("hp") is not None else bm.get("drain", 0.0))
        cs = _format_stat_num(sim.get("cs") if sim.get("cs") is not None else bm.get("cs", 0.0))

        base_bpm = float(bm.get("bpm") or sim.get("bpm") or 0.0)
        eff_bpm = base_bpm * clock_rate
        raw_len = int(bm.get("total_length") or bm.get("hit_length") or 0)
        eff_len = int(raw_len / clock_rate) if (raw_len and clock_rate > 0) else raw_len
        length_str = DaletAtoms.format_duration(eff_len)

        max_combo = int(sim.get("max_combo") or bm.get("max_combo") or 0)
        n_circles = int(sim.get("n_circles") if sim.get("n_circles") is not None else (bm.get("count_circles") or 0))
        n_sliders = int(sim.get("n_sliders") if sim.get("n_sliders") is not None else (bm.get("count_sliders") or 0))
        n_spinners = int(sim.get("n_spinners") if sim.get("n_spinners") is not None else (bm.get("count_spinners") or 0))

        header_title = f"{artist} - {title} [{version}]" if artist else f"{title} [{version}]"
        embed = discord.Embed(
            title=f"✦ {header_title}",
            url=map_url,
            color=DaletAtoms.COLOR_PRIMARY,
        )
        mode_emoji = DaletAtoms.get_mode_emoji(mode)
        mode_txt = f"{mode_emoji} {_mode_title(mode)}" if mode_emoji else _mode_title(mode)
        embed.description = (
            f"**{mods_str}** · `{stars:.2f}★` · {status} · {mode_txt}\n"
            f"**{t('osu.map_mapper', lang)}**: {mapper}"
        )

        combo_txt = f"{max_combo:,}x" if max_combo > 0 else "N/A"
        embed.add_field(
            name=f"{DaletAtoms.GLYPH_AIM} {t('osu.map_difficulty', lang)}",
            value=(
                f"`{length_str}` · `{eff_bpm:.0f} BPM` · Max Combo **{combo_txt}**\n"
                f"AR {ar} · OD {od} · HP {hp} · CS {cs}\n"
                f"○ {n_circles} · ◐ {n_sliders} · ◎ {n_spinners}"
            ),
            inline=False,
        )

        pp_dict = sim.get("pp") or {}
        if pp_dict:
            pp_95 = pp_dict.get(95, 0.0)
            pp_98 = pp_dict.get(98, 0.0)
            pp_99 = pp_dict.get(99, 0.0)
            pp_100 = pp_dict.get(100, 0.0)
            pp_val_txt = (
                f"95% **{pp_95:.0f}pp** · "
                f"98% **{pp_98:.0f}pp** · "
                f"99% **{pp_99:.0f}pp** · "
                f"SS **{pp_100:.0f}pp**"
            )
            embed.add_field(
                name=f"{DaletAtoms.GLYPH_ACCURACY} {t('osu.map_pp_table', lang)}",
                value=pp_val_txt,
                inline=False,
            )

        covers = bms.get("covers", {})
        cover_url = covers.get("cover") or covers.get("card") or covers.get("list")
        if cover_url:
            embed.set_image(url=cover_url)

        DaletMolecules.add_standard_footer(
            embed,
            context_text=f"Map ID: {bm_id} {DaletAtoms.GLYPH_PIPE} Set: {set_id}" if set_id else f"Map ID: {bm_id}",
        )
        return embed

    @staticmethod
    def build_map_compare_card(
        user_data: dict,
        beatmap_data: dict,
        scores: list,
        mode: str = "osu",
        mods_filter: str | None = None,
        total_unfiltered: int = 0,
        lang: str = "en",
    ) -> discord.Embed:
        """Construye la tarjeta clásica >c / d.c con todas las mejores jugadas del jugador en ese mapa."""
        u = user_data or {}
        bm = beatmap_data or {}
        bms = bm.get("beatmapset") or {}

        username = u.get("username", "Jugador")
        bm_id = int(bm.get("id") or 0)
        title = bms.get("title") or bm.get("title") or "Desconocido"
        artist = bms.get("artist") or bm.get("artist") or ""
        version = bm.get("version") or "Normal"
        map_url = f"https://osu.ppy.sh/b/{bm_id}" if bm_id else "https://osu.ppy.sh"

        base_sr = float(bm.get("difficulty_rating") or 0.0)
        base_bpm = float(bm.get("bpm") or 0.0)
        raw_len = int(bm.get("total_length") or bm.get("hit_length") or 0)
        length_str = DaletAtoms.format_duration(raw_len)

        author_title = t("osu.map_compare_author", lang, username=username, mode=_mode_title(mode))
        if mods_filter and str(mods_filter).strip():
            clean_mod = str(mods_filter).upper().replace("+", "").strip()
            author_title += f" · +{clean_mod}"

        top_grade = str(scores[0].get("rank", "?")).upper() if scores else "?"
        embed_color = DaletAtoms.get_grade_color(top_grade) if scores else DaletAtoms.COLOR_PRIMARY
        embed = discord.Embed(color=embed_color)
        embed.set_author(
            name=author_title,
            icon_url=u.get("avatar_url"),
            url=_profile_url(u, mode=mode, fallback_username=username),
        )

        mode_emoji = DaletAtoms.get_mode_emoji(mode)
        header_line = f"**[{artist} - {title} [{version}]]({map_url})**" if artist else f"**[{title} [{version}]]({map_url})**"
        meta_prefix = f"{mode_emoji} · " if mode_emoji else ""
        meta_line = f"{meta_prefix}`{base_sr:.2f}★` · `{base_bpm:.0f} BPM` · `{length_str}`"

        if not scores:
            if mods_filter and total_unfiltered > 0:
                empty_msg = t("osu.map_compare_none_filtered", lang, username=username, mods=str(mods_filter).upper().replace("+", "").strip())
            else:
                empty_msg = t("osu.map_compare_none", lang, username=username)
            embed.description = f"{header_line}\n{meta_line}\n\n{DaletAtoms.GLYPH_POINTER} {empty_msg}"
        else:
            lines = []
            for idx, s in enumerate(scores[:6], 1):
                grade = str(s.get("rank", "?")).upper()
                badge = DaletAtoms.get_grade_emoji(grade)
                pp_disp = _format_play_pp(s, lang=lang, compact=True, decimals=2) or f"**{t('osu.no_pp', lang)}**"
                acc = _format_acc(s.get("accuracy", 0.0))
                mods_str = _format_mods(s.get("mods", []))
                sr = s.get("official_sr") or (s.get("beatmap_attributes") or {}).get("star_rating") or _calc_effective_sr(bm, s.get("mods", []), mode=mode)

                stats = s.get("statistics") or {}
                c300 = int(stats.get("count_300") or 0)
                c100 = int(stats.get("count_100") or 0)
                c50 = int(stats.get("count_50") or 0)
                misses = int(stats.get("count_miss") or 0)

                max_c = int(s.get("max_combo") or 0)
                bm_max = (s.get("beatmap") or {}).get("max_combo") or bm.get("max_combo") or ""
                combo_str = f"{max_c:,}x/{int(bm_max):,}x" if bm_max else f"{max_c:,}x"
                miss_str = f"{misses}m" if misses > 0 else "FC"
                score_str = OsuPresenter._extract_score(s)

                rel_time = DaletAtoms.parse_timestamp_relative(s.get("created_at", ""))
                time_part = f" · {rel_time}" if rel_time else ""

                row1 = f"**#{idx}** {badge} · {pp_disp} · **{acc}** · **{mods_str}** · {sr:.2f}★"
                row2 = f"└ {combo_str} ({miss_str}) · `[{c300}/{c100}/{c50}/{misses}]` · {score_str}{time_part}"
                lines.append(f"{row1}\n{row2}")

            embed.description = f"{header_line}\n{meta_line}\n\n" + "\n\n".join(lines)

        covers = bms.get("covers", {})
        thumb_url = covers.get("list") or covers.get("cover") or covers.get("card")
        if thumb_url:
            embed.set_thumbnail(url=thumb_url)

        srv_label = _server_title((u.get("_server") or "bancho"))
        DaletMolecules.add_standard_footer(
            embed,
            context_text=f"{srv_label} {DaletAtoms.GLYPH_PIPE} Map ID: {bm_id} {DaletAtoms.GLYPH_PIPE} d.m",
        )
        return embed


async def setup(bot):
    pass


