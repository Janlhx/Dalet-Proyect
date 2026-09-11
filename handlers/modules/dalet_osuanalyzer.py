import logging
import json
import os
from ui.locales import t

logger = logging.getLogger('dalet.handlers.osuanalyzer')

class OsuAnalyzer:
    """Calcula el desglose de habilidades técnicas para todos los modos de osu!."""

    _BENCHMARKS = None

    @classmethod
    def get_benchmarks(cls) -> dict:
        """Carga el catálogo de referencia de mapas competitivos certificados por la comunidad."""
        if cls._BENCHMARKS is not None:
            return cls._BENCHMARKS
        try:
            data_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "community_skillsets.json")
            data_path = os.path.abspath(data_path)
            if os.path.exists(data_path):
                with open(data_path, "r", encoding="utf-8") as f:
                    cls._BENCHMARKS = json.load(f)
                    return cls._BENCHMARKS
        except Exception as e:
            logger.warning(f"No se pudo cargar community_skillsets.json: {e}")
        cls._BENCHMARKS = {"osu": [], "mania": []}
        return cls._BENCHMARKS

    @classmethod
    def match_benchmark(cls, title: str, version: str, mode: str = "osu") -> dict | None:
        """Busca si un mapa coincide con el catálogo verificado de la comunidad."""
        benchmarks = cls.get_benchmarks().get(mode, [])
        full_text = f"{title} {version}".lower()
        for b in benchmarks:
            pat = b.get("pattern", "").lower()
            if pat and pat in full_text:
                return b
        return None

    MODE_SKILLS = {
        "osu": ['Aim', 'Speed', 'Accuracy', 'Stamina', 'Reading'],
        "taiko": ['Speed', 'Stamina', 'Accuracy', 'Reading', 'Patterning'],
        "fruits": ['Agility', 'Precision', 'Speed', 'Stamina', 'Reading'],
        "mania": ['Chordjack', 'LN', 'Tech', 'Speed', 'Stamina', 'Accuracy']
    }

    @staticmethod
    def score_to_points(score_stars: float) -> float:
        """Convierte dificultad de habilidad (estrellas) en Puntos de Maestría (0 a 100 pts).
        Curva cóncava calibrada:
        - 4.0★ -> ~59.4 pts (Competente)
        - 5.0★ -> ~70.9 pts (Avanzado)
        - 6.0★ -> ~80.0 pts (Maestro)
        - 7.0★ -> ~88.0 pts (Maestro alto)
        - 7.5★ -> ~92.0 pts (Élite)
        - 8.5★ -> ~97.6 pts (Top Mundial)
        - 9.5★+ -> 100.0 pts (Máximo)
        """
        if score_stars <= 0.0:
            return 0.0
        x = min(1.0, score_stars / 9.5)
        pts = 100.0 * (1.0 - (1.0 - x) ** 1.65)
        return round(min(100.0, max(0.0, pts)), 1)

    @staticmethod
    def get_tier_info(points: float, lang: str = "es") -> tuple:
        """Retorna (glifo_tier, nombre_tier) sin emojis, usando glifos limpios de Dalet."""
        is_es = (lang or "es").lower().startswith("es")
        if points >= 90.0:
            return ("✦", "Élite" if is_es else "Elite")
        elif points >= 80.0:
            return ("◆", "Maestro" if is_es else "Master")
        elif points >= 70.0:
            return ("▲", "Avanzado" if is_es else "Advanced")
        elif points >= 60.0:
            return ("▸", "Competente" if is_es else "Competent")
        else:
            return ("▫", "Aprendiz" if is_es else "Novice")

    @classmethod
    def get_mode_skills(cls, mode: str = "osu") -> list:
        m = (mode or "osu").lower().strip()
        return cls.MODE_SKILLS.get(m, cls.MODE_SKILLS["osu"])

    @staticmethod
    def calculate_skills(best_plays: list, mode: str = "osu", lang: str = "es") -> dict:
        mode_clean = (mode or "osu").lower().strip()
        skills_def = OsuAnalyzer.get_mode_skills(mode_clean)

        if not best_plays:
            def_glyph, def_tier = OsuAnalyzer.get_tier_info(0.0, lang=lang)
            return {
                skill: {
                    'stars': 0.0,
                    'points': 0.0,
                    'tier_glyph': def_glyph,
                    'tier_name': def_tier,
                    'top_maps': []
                } for skill in skills_def
            } | {
                'dominant_skill': 'N/A',
                'weakest_skill': 'N/A',
                'overall_skill_stars': 0.0,
                'overall_skill_points': 0.0,
                'overall_tier_glyph': def_glyph,
                'overall_tier_name': def_tier
            }

        scored_plays = []
        for p in best_plays:
            bm = p.get('beatmap', {})
            bset = p.get('beatmapset', {})
            if not bm:
                continue

            base_sr = float(bm.get('difficulty_rating', 0.0))
            mods = p.get('mods', [])
            mods_str = '+' + ''.join(mods) if mods else '+NM'
            acc = float(p.get('accuracy', 1.0))
            bpm = float(bm.get('bpm', 170.0) or 170.0)
            ar = float(bm.get('ar', 9.0) or 9.0)
            od = float(bm.get('accuracy', 8.0) or 8.0)
            cs = float(bm.get('cs', 4.0) or 4.0)
            drain = float(bm.get('hit_length', 120.0) or 120.0)
            count_circles = int(bm.get('count_circles', 0) or 0)
            count_sliders = int(bm.get('count_sliders', 0) or 0)
            count_spinners = int(bm.get('count_spinners', 0) or 0)
            total_objects = count_circles + count_sliders + count_spinners

            is_dt = any(m in ['DT', 'NC'] for m in mods)
            is_hr = 'HR' in mods
            is_ez = 'EZ' in mods
            is_ht = 'HT' in mods
            is_fl = 'FL' in mods
            is_hd = 'HD' in mods

            eff_sr = base_sr
            if is_dt:
                dt_factor = 1.38
                if bpm >= 200:
                    dt_factor += min(0.08, (bpm - 200) * 0.001)
                elif bpm < 150:
                    dt_factor -= min(0.06, (150 - bpm) * 0.001)
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
            eff_sr = round(eff_sr, 2)

            # Factor de Rendimiento de Ejecución (Pondera según acc real, misses y combo alcanzado)
            misses = int(p.get('statistics', {}).get('count_miss', 0) or 0)
            max_combo = int(p.get('max_combo', 0) or 0)
            bm_max = bm.get('max_combo') or total_objects or 1
            combo_ratio = min(1.0, max(0.15, max_combo / max(1, bm_max)))

            acc_penalty = (acc / 0.985) ** 1.35 if acc > 0 else 0.5
            miss_penalty = max(0.65, 1.0 - (misses * 0.035))
            combo_factor = combo_ratio ** 0.12
            exec_factor = min(1.00, max(0.40, acc_penalty * miss_penalty * combo_factor))

            raw_weights = {}

            # Métricas universales de física y subdivisión rítmica
            eff_bpm = bpm * (1.5 if is_dt else (0.75 if is_ht else 1.0))
            real_drain = drain / 1.5 if is_dt else (drain / 0.75 if is_ht else drain)
            real_drain = max(1.0, real_drain)
            nps = total_objects / real_drain
            beats_per_sec = max(0.1, eff_bpm / 60.0)
            opb = nps / beats_per_sec  # Objects per Beat (Subdivisión rítmica promedio)

            if mode_clean == "taiko":
                # --- TAIKO: Speed, Stamina, Accuracy, Reading, Patterning ---
                bpm_mult = 0.90
                if eff_bpm >= 200:
                    bpm_mult += min(0.28, (eff_bpm - 200) * 0.003)
                elif eff_bpm < 160:
                    bpm_mult -= min(0.20, (160 - eff_bpm) * 0.003)
                if is_dt:
                    bpm_mult += 0.08
                raw_weights['Speed'] = min(1.30, max(0.40, bpm_mult))

                stamina_mult = 0.85
                if real_drain >= 160:
                    stamina_mult += min(0.25, (real_drain - 160) * 0.0016)
                    if total_objects >= 1500:
                        stamina_mult += min(0.20, (total_objects - 1500) * 0.00015)
                elif real_drain < 120:
                    stamina_mult -= min(0.35, (120 - real_drain) * 0.005)
                raw_weights['Stamina'] = min(1.30, max(0.35, stamina_mult))

                eff_od = min(10.5, od * (1.4 if is_hr else (0.5 if is_ez else 1.0)))
                acc_scale = (acc / 0.985) ** 1.6
                raw_weights['Accuracy'] = (eff_od / 9.2) * acc_scale

                reading_mult = 0.75
                if is_hd:
                    reading_mult += 0.18
                if is_fl:
                    reading_mult += 0.32
                if is_ez:
                    reading_mult += 0.22
                if is_dt:
                    reading_mult += 0.08
                raw_weights['Reading'] = min(1.25, reading_mult)

                circle_ratio = count_circles / max(1, total_objects) if total_objects > 0 else 0.8
                pattern_mult = 0.90 + 0.15 * circle_ratio
                if is_hr:
                    pattern_mult += 0.08
                raw_weights['Patterning'] = pattern_mult

            elif mode_clean == "fruits":
                # --- CATCH (FRUITS): Agility, Precision, Speed, Stamina, Reading ---
                eff_cs = cs * (1.3 if is_hr else (0.5 if is_ez else 1.0))
                cs_mult = 0.85 + max(-0.15, (eff_cs - 4.0) * 0.10)
                raw_weights['Precision'] = min(1.25, cs_mult)

                agility_mult = 0.92
                if is_hr:
                    agility_mult += 0.12
                if is_dt:
                    agility_mult += 0.08
                raw_weights['Agility'] = agility_mult

                bpm_mult = 0.90
                if eff_bpm >= 190:
                    bpm_mult += min(0.25, (eff_bpm - 190) * 0.0028)
                elif eff_bpm < 150:
                    bpm_mult -= min(0.18, (150 - eff_bpm) * 0.0025)
                if is_dt:
                    bpm_mult += 0.10
                raw_weights['Speed'] = min(1.25, bpm_mult)

                stamina_mult = 0.85
                if real_drain >= 160:
                    stamina_mult += min(0.22, (real_drain - 160) * 0.0015)
                    if total_objects >= 1400:
                        stamina_mult += min(0.18, (total_objects - 1400) * 0.00015)
                elif real_drain < 120:
                    stamina_mult -= min(0.30, (120 - real_drain) * 0.004)
                raw_weights['Stamina'] = min(1.25, max(0.40, stamina_mult))

                eff_ar = min(10.0, ar * 1.4) if is_hr else (ar * 0.5 if is_ez else ar)
                if is_dt:
                    eff_ar = min(11.1, (eff_ar * 2 + 13) / 3)
                reading_mult = 0.72
                if eff_ar <= 8.5:
                    reading_mult += min(0.20, (8.5 - eff_ar) * 0.08)
                elif eff_ar >= 10.3:
                    reading_mult += min(0.15, (eff_ar - 10.3) * 0.08)
                if is_hd:
                    reading_mult += 0.20
                if is_fl:
                    reading_mult += 0.35
                if is_ez:
                    reading_mult += 0.18
                raw_weights['Reading'] = min(1.28, reading_mult)

            elif mode_clean == "mania":
                # --- MANIA: Chordjack, LN, Tech, Speed, Stamina, Accuracy ---
                key_count = int(cs) if cs >= 4 else 4
                ln_ratio = count_sliders / max(1, total_objects) if total_objects > 0 else 0.0

                # 1. LN (Long Notes): Coordinación de hold notes, release timing, fideos e inverse
                ln_mult = 0.50
                if ln_ratio >= 0.15:
                    ln_mult += min(0.85, (ln_ratio - 0.15) * 2.30)
                    if ln_ratio >= 0.35:
                        ln_mult += 0.15  # Dominio absoluto de LN / Inverse
                elif ln_ratio < 0.10:
                    ln_mult -= min(0.25, (0.10 - ln_ratio) * 2.50)
                if key_count >= 7:
                    ln_mult += 0.06
                raw_weights['LN'] = min(1.35, max(0.20, ln_mult))

                # 2. Chordjack: Acordes densos simultáneos (densidad de notas por pulso muy alta en Rice)
                # En 4K: 1 nota en cada 1/4 = 4.0 OPB. Acordes continuos (dobles/triples jacks) = OPB >= 4.0.
                # Ocurre a BPM moderado (130 - 205 BPM). A 215+ BPM se convierte físicamente en jumpstream/speed.
                chord_mult = 0.82
                min_opb = 4.0 if key_count == 4 else 5.0
                if opb >= min_opb and 130 <= eff_bpm <= 205:
                    chord_mult += min(0.48, (opb - min_opb) * 0.15 + 0.24)
                elif opb < 3.6:
                    chord_mult -= min(0.40, (3.6 - opb) * 0.20)

                # Penalización si el BPM excede el umbral humano de jacks de acordes densos
                if eff_bpm > 215:
                    chord_mult -= min(0.45, (eff_bpm - 215) * 0.008)

                # Si es dominantemente LN (>= 15%), pertenece a LN
                if ln_ratio >= 0.15:
                    chord_mult -= min(0.60, (ln_ratio - 0.15) * 2.50)

                if key_count >= 7:
                    chord_mult += 0.08
                raw_weights['Chordjack'] = min(1.35, max(0.25, chord_mult))

                # 3. Speed: Velocidad bruta de repetición (BPM alto >= 200 con patrones de roll/jumpstream ligeros y bajo LN)
                speed_mult = 0.85
                if eff_bpm >= 200:
                    speed_mult += min(0.35, (eff_bpm - 200) * 0.004)
                elif eff_bpm < 160:
                    speed_mult -= min(0.30, (160 - eff_bpm) * 0.004)

                if nps >= 8.5:
                    speed_mult += min(0.18, (nps - 8.5) * 0.025)

                # Si la densidad de notas por pulso corresponde a jumpstream/rolls (3.0 a 4.6 OPB a alto BPM) en arroz (rice)
                if 3.0 <= opb <= 4.6 and eff_bpm >= 200 and ln_ratio < 0.15:
                    speed_mult += 0.12

                # Penalización si el mapa tiene LN significativa (la retención de teclas bloquea el streaming puro de speed)
                if ln_ratio >= 0.15:
                    speed_mult -= min(0.45, (ln_ratio - 0.15) * 2.20)

                raw_weights['Speed'] = min(1.35, max(0.30, speed_mult))

                # 4. Tech: Coordinación compleja, polirritmias, SVs y patrones híbridos (LN + Rice)
                tech_mult = 0.88
                if 170 <= eff_bpm <= 230 and nps >= 7.5:
                    tech_mult += min(0.25, (nps - 7.5) * 0.035)

                # Bono característico de Tech: coordinación híbrida de LN con notas arroz (12% a 28% LN)
                if 0.12 <= ln_ratio <= 0.28:
                    tech_mult += 0.16

                # Acordes pesados de rice puro (OPB >= 4.0 a BPM moderado) pertenecen a Chordjack, no a Tech
                if opb >= 4.0 and ln_ratio < 0.10 and eff_bpm <= 205:
                    tech_mult -= min(0.30, (opb - 4.0) * 0.15 + 0.12)

                if eff_bpm >= 235 and ln_ratio < 0.10:
                    tech_mult -= min(0.35, (eff_bpm - 235) * 0.008)

                # Si tiene 30% o más de LN, es predominantemente un mapa de LN
                if ln_ratio >= 0.30:
                    tech_mult -= min(0.55, (ln_ratio - 0.30) * 2.50)

                if is_hd or is_fl:
                    tech_mult += 0.08
                raw_weights['Tech'] = min(1.30, max(0.35, tech_mult))

                # 5. Stamina: Resistencia en charts extensos (real_drain >= 160s) y alto strain sostenido
                # Mapas densos pero cortos (< 140s) sufren penalización
                stamina_mult = 0.80
                if real_drain >= 160:
                    stamina_mult += min(0.35, (real_drain - 160) * 0.002)
                    if total_objects >= 1700:
                        stamina_mult += min(0.20, (total_objects - 1700) * 0.00015)
                elif real_drain < 140:
                    stamina_mult -= min(0.40, (140 - real_drain) * 0.005)

                if total_objects < 900:
                    stamina_mult -= min(0.25, (900 - total_objects) * 0.0003)

                raw_weights['Stamina'] = min(1.35, max(0.30, stamina_mult))

                # 6. Accuracy: Ventana OD estricta y sincronización de pulsos
                eff_od = min(10.5, od * (1.4 if is_hr else 1.0))
                acc_scale = (acc / 0.985) ** 1.8
                raw_weights['Accuracy'] = (eff_od / 9.2) * acc_scale

            else:
                # --- OSU (STANDARD): Aim, Speed, Accuracy, Stamina, Reading ---
                circle_ratio = count_circles / max(1, total_objects) if total_objects > 0 else 0.7
                slider_ratio = count_sliders / max(1, total_objects) if total_objects > 0 else 0.3
                cs_bonus = max(0.0, (cs - 4.0) * 0.08)

                # 1. Aim: Puntería, spacing y movimiento de cursor.
                # Si OPB <= 1.9 (ej. Wizard's Tower con 1.44 OPB, Harumachi con 1.60 OPB), el mapa es de saltos 1-2 puros.
                # El BPM alto en saltos mide la velocidad de movimiento del cursor (Aim flicking).
                aim_mult = 0.94 + 0.18 * circle_ratio + cs_bonus
                if opb <= 2.0:
                    aim_mult += 0.16
                    if eff_bpm >= 200:
                        aim_mult += min(0.25, (eff_bpm - 200) * 0.003)
                elif opb <= 2.8:
                    aim_mult += 0.10
                    if eff_bpm >= 220:
                        aim_mult += min(0.15, (eff_bpm - 220) * 0.002)
                elif opb >= 3.4:
                    aim_mult -= min(0.20, (opb - 3.4) * 0.20)

                # Si es un maratón de alta densidad (ej. Freedom Dive >= 160s y >= 8.0 NPS), domina Stamina/Speed
                if real_drain >= 160 and nps >= 8.0:
                    aim_mult -= 0.15

                if is_dt:
                    aim_mult += 0.08
                if is_hr:
                    aim_mult += 0.08
                raw_weights['Aim'] = min(1.35, max(0.40, aim_mult))

                # 2. Speed: Digitación a alta velocidad en el teclado (streams de 1/4, ráfagas rápidas y DT de alto BPM).
                # Si es NoMod y OPB <= 1.9 (como Wizard's Tower con 1.44 OPB), SPEED SE PENALIZA por carecer de streams de digitación.
                # Con DT a alto BPM (>= 240 BPM), la digitación rápida a 1.5x velocidad SÍ es Speed genuino.
                speed_mult = 0.85
                if opb >= 2.2 and eff_bpm >= 185:
                    speed_mult += min(0.32, (eff_bpm - 185) * 0.0035)
                    speed_mult += min(0.18, (opb - 2.2) * 0.12)
                    if nps >= 8.0 and eff_bpm >= 200:
                        speed_mult += min(0.15, (nps - 8.0) * 0.05)
                elif opb <= 1.9 and not is_dt:
                    speed_mult -= min(0.42, (1.9 - opb) * 0.60)
                    if eff_bpm < 200:
                        speed_mult -= 0.10

                # Bono para DT / High BPM Speed
                if is_dt and eff_bpm >= 230:
                    speed_mult += min(0.20, (eff_bpm - 230) * 0.004)
                elif eff_bpm >= 260 and opb >= 2.0:
                    speed_mult += 0.08

                # Reacción en AR extrema (>= 10.3)
                eff_ar = min(10.0, ar * 1.4) if is_hr else (ar * 0.5 if is_ez else ar)
                if is_dt:
                    eff_ar = min(11.1, (eff_ar * 2 + 13) / 3)
                if eff_ar >= 10.3:
                    speed_mult += min(0.10, (eff_ar - 10.3) * 0.08)

                raw_weights['Speed'] = min(1.35, max(0.30, speed_mult))

                # 3. Accuracy: Ventana OD y consistencia rítmica
                eff_od = min(11.0, od * (1.4 if is_hr else (0.5 if is_ez else 1.0)))
                od_scale = eff_od / 9.8
                acc_normalized = max(0.0, (acc - 0.90) / 0.10)
                acc_curve = acc_normalized ** 1.6
                acc_mult = min(1.15, max(0.50, 0.75 + 0.35 * acc_curve)) * od_scale
                raw_weights['Accuracy'] = acc_mult

                # 4. Stamina: Resistencia física prolongada (real_drain >= 160s y alto conteo de objetos)
                # Mapas cortos / TV-size (< 120s) sufren penalización proporcional
                stamina_mult = 0.82
                if real_drain >= 160:
                    stamina_mult += min(0.35, (real_drain - 160) * 0.0022)
                    if nps >= 6.5:
                        stamina_mult += min(0.25, (nps - 6.5) * 0.045)
                elif real_drain < 120:
                    stamina_mult -= min(0.40, (120 - real_drain) * 0.006)

                if total_objects >= 1200:
                    stamina_mult += min(0.22, (total_objects - 1200) * 0.00015)
                elif total_objects < 700:
                    stamina_mult -= min(0.25, (700 - total_objects) * 0.0004)

                raw_weights['Stamina'] = min(1.35, max(0.30, stamina_mult))

                # 5. Reading: Complejidad visual, solapamiento de notas (baja AR), HD, FL, EZ
                if eff_ar >= 10.0:
                    reading_mult = 0.80
                elif eff_ar >= 9.6:
                    reading_mult = 0.82
                else:
                    reading_mult = 0.85

                if eff_ar <= 8.5:
                    reading_mult += min(0.30, (8.5 - eff_ar) * 0.10)
                    if eff_ar <= 7.0:
                        reading_mult += 0.15

                if is_hd:
                    if eff_ar <= 8.5:
                        reading_mult += 0.22
                    elif eff_ar <= 9.6:
                        reading_mult += 0.10
                    else:
                        reading_mult += 0.04

                if is_fl:
                    reading_mult += 0.40
                if is_ez:
                    reading_mult += 0.30

                if slider_ratio >= 0.35:
                    reading_mult += min(0.18, (slider_ratio - 0.35) * 0.30)

                raw_weights['Reading'] = min(1.30, reading_mult)

            title = bset.get('title') or bm.get('title', 'Desconocido')
            version = bm.get('version', 'Normal')
            beatmap_id = bm.get('id') or p.get('beatmap_id', 0)
            pp_val = float(p.get('pp') or 0.0)

            # 1. Integración de Atributos Modernos de osu! Lazer / API v2 (si están disponibles)
            attrs = bm.get('attributes') or p.get('beatmap_attributes') or {}
            aim_diff = float(attrs.get('aim_difficulty') or 0.0)
            speed_diff = float(attrs.get('speed_difficulty') or 0.0)
            if aim_diff > 0 and speed_diff > 0 and mode_clean == "osu":
                # Bancho / Lazer calculó oficialmente la dificultad de aim y speed
                if aim_diff >= speed_diff * 1.05:
                    raw_weights['Aim'] = max(raw_weights.get('Aim', 1.0), raw_weights.get('Speed', 0.9) * 1.15)
                elif speed_diff >= aim_diff * 1.05:
                    raw_weights['Speed'] = max(raw_weights.get('Speed', 1.0), raw_weights.get('Aim', 0.9) * 1.15)

            # 2. Catálogo de Referencia de la Comunidad (Golden Benchmark Pool)
            benchmark = OsuAnalyzer.match_benchmark(title, version, mode_clean)
            if benchmark:
                primary = benchmark.get("primary")
                secondary = benchmark.get("secondary")
                if primary and primary in skills_def:
                    other_vals = [v for k, v in raw_weights.items() if k != primary]
                    max_other = max(other_vals) if other_vals else 1.0
                    raw_weights[primary] = max(raw_weights.get(primary, 1.0), max_other + 0.18)
                if secondary and secondary in skills_def and raw_weights.get(secondary, 0.0) >= 0.70:
                    raw_weights[secondary] = max(raw_weights.get(secondary, 0.9), 1.05)

            # --- NORMALIZACIÓN ANCLADA AL STAR RATING ---
            max_raw = max(raw_weights.values()) if raw_weights else 1.0
            max_raw = max(0.001, max_raw)

            scores = {}
            for skill in skills_def:
                rel_ratio = raw_weights.get(skill, 0.50) / max_raw
                scores[skill] = round(eff_sr * rel_ratio * exec_factor, 2)

            # --- COMPUERTA DE ELEGIBILIDAD POR HABILIDAD (COMPETENCY ELIGIBILITY GATE) ---
            # Un mapa solo puede ser elegido para evaluar y representar una habilidad si físicamente
            # la pone a prueba de manera sustancial (evita que un mapa de saltos cortos evalúe Stamina o Speed).
            eligible_skills = set()

            # 1. Validación de Catálogo Canónico / Benchmarks de la Comunidad
            if benchmark:
                if benchmark.get("primary"):
                    eligible_skills.add(benchmark["primary"])
                if benchmark.get("secondary") and raw_weights.get(benchmark["secondary"], 0.0) >= 0.70:
                    eligible_skills.add(benchmark["secondary"])

            # 2. Criterios de física y subdivisión rítmica por modo
            if mode_clean == "osu":
                # Aim: Componente de saltos y espaciado
                if raw_weights.get('Aim', 0) >= 0.85 and (opb <= 2.6 or raw_weights.get('Aim', 0) >= raw_weights.get('Speed', 0)):
                    eligible_skills.add('Aim')

                # Speed: Exige ráfagas o streams de digitación (OPB >= 2.0 o DT a alto BPM)
                # Mapas de saltos 1/2 sin ráfagas quedan 100% descalificados para Speed
                has_speed_density = opb >= 2.0 or (is_dt and eff_bpm >= 230)
                if has_speed_density and raw_weights.get('Speed', 0) >= 0.85:
                    eligible_skills.add('Speed')

                # Stamina: Resistencia prolongada en duración continua (drain >= 110s) y notas (>= 650)
                # Mapas TV-size y cortos (< 110s) quedan 100% descalificados para juzgar Stamina
                if real_drain >= 110.0 and total_objects >= 650 and raw_weights.get('Stamina', 0) >= 0.80:
                    eligible_skills.add('Stamina')

                # Accuracy: Ventana OD exigente (OD >= 9.0) y rendimiento de acc sólido (>= 92%)
                eff_od_val = od * (1.4 if is_hr else (0.5 if is_ez else 1.0))
                if eff_od_val >= 9.0 and acc >= 0.92:
                    eligible_skills.add('Accuracy')

                # Reading: Modificadores visuales o densidad visual compleja
                slider_ratio = count_sliders / max(1, total_objects) if total_objects > 0 else 0
                if is_hd or is_fl or is_ez or eff_ar <= 8.5 or eff_ar >= 10.3 or slider_ratio >= 0.35:
                    eligible_skills.add('Reading')

            elif mode_clean == "mania":
                ln_ratio = count_sliders / max(1, total_objects) if total_objects > 0 else 0.0

                # LN: Requiere ratio sustancial de Long Notes (>= 12%)
                if ln_ratio >= 0.12 and raw_weights.get('LN', 0) >= 0.80:
                    eligible_skills.add('LN')

                # Chordjack: Acordes densos simultáneos a BPM moderado en rice
                if opb >= 3.6 and eff_bpm <= 215 and ln_ratio < 0.15:
                    eligible_skills.add('Chordjack')

                # Speed: Jumpstream y rolls a alto BPM
                if eff_bpm >= 190 and ln_ratio < 0.15 and raw_weights.get('Speed', 0) >= 0.85:
                    eligible_skills.add('Speed')

                # Tech: Patrones híbridos LN+Rice o cambios de velocidad
                if (0.10 <= ln_ratio <= 0.35) or raw_weights.get('Tech', 0) >= 0.90:
                    eligible_skills.add('Tech')

                # Stamina: Charts prolongados y continuos
                if real_drain >= 120.0 and total_objects >= 1100:
                    eligible_skills.add('Stamina')

                # Accuracy:
                if acc >= 0.94 and od >= 8.0:
                    eligible_skills.add('Accuracy')

            elif mode_clean == "taiko":
                if raw_weights.get('Speed', 0) >= 0.88 and eff_bpm >= 190:
                    eligible_skills.add('Speed')
                if real_drain >= 120.0 and total_objects >= 800:
                    eligible_skills.add('Stamina')
                if acc >= 0.94:
                    eligible_skills.add('Accuracy')
                if is_hd or is_fl or is_ez or is_dt:
                    eligible_skills.add('Reading')
                if raw_weights.get('Patterning', 0) >= 0.90:
                    eligible_skills.add('Patterning')

            elif mode_clean == "fruits":
                if raw_weights.get('Precision', 0) >= 0.88:
                    eligible_skills.add('Precision')
                if raw_weights.get('Agility', 0) >= 0.88:
                    eligible_skills.add('Agility')
                if raw_weights.get('Speed', 0) >= 0.88 and eff_bpm >= 180:
                    eligible_skills.add('Speed')
                if real_drain >= 120.0 and total_objects >= 800:
                    eligible_skills.add('Stamina')
                if is_hd or is_fl or is_ez:
                    eligible_skills.add('Reading')

            scored_plays.append({
                'title': title,
                'version': version,
                'beatmap_id': beatmap_id,
                'mods_str': mods_str,
                'sr': eff_sr,
                'pp': pp_val,
                'acc': round(acc * 100.0, 2),
                'scores': scores,
                'eligible_skills': eligible_skills
            })

        if not scored_plays:
            tier_uncalibrated = t("osu.tier_unranked", lang)
            return {
                skill: {
                    'stars': 0.0,
                    'points': 0.0,
                    'tier_glyph': '▫',
                    'tier_name': tier_uncalibrated,
                    'top_maps': [],
                    'has_data': False
                } for skill in skills_def
            } | {
                'dominant_skill': 'N/A',
                'weakest_skill': 'N/A',
                'overall_skill_stars': 0.0,
                'overall_skill_points': 0.0,
                'overall_tier_glyph': '▫',
                'overall_tier_name': tier_uncalibrated
            }

        skills_result = {}
        for skill in skills_def:
            # Filtrar EXCLUSIVAMENTE jugadas cualificadas para esta habilidad
            qualifying_plays = [p for p in scored_plays if skill in p.get('eligible_skills', set())]

            if not qualifying_plays:
                # El jugador no tiene suficientes jugadas registradas en su top que pongan a prueba esta disciplina
                tier_uncalibrated = t("osu.tier_unranked", lang)
                skills_result[skill] = {
                    'points': 0.0,
                    'stars': 0.0,
                    'tier_glyph': '▫',
                    'tier_name': tier_uncalibrated,
                    'top_maps': [],
                    'has_data': False
                }
                continue

            sorted_by_skill = sorted(qualifying_plays, key=lambda x: x['scores'].get(skill, 0.0), reverse=True)
            top_3 = sorted_by_skill[:3]

            # Muestrear hasta las 10 mejores jugadas CUALIFICADAS con decaimiento (0.85^i)
            # sin rellenar artificialmente con mapas descalificados
            sample = sorted_by_skill[:min(10, len(sorted_by_skill))]
            weights = [0.85 ** i for i in range(len(sample))]
            weighted_stars = sum(sample[i]['scores'].get(skill, 0.0) * weights[i] for i in range(len(sample))) / max(0.001, sum(weights))

            pts = OsuAnalyzer.score_to_points(weighted_stars)
            tier_glyph, tier_name = OsuAnalyzer.get_tier_info(pts, lang=lang)

            skills_result[skill] = {
                'points': pts,
                'stars': round(weighted_stars, 2),
                'tier_glyph': tier_glyph,
                'tier_name': tier_name,
                'has_data': True,
                'top_maps': [
                    {
                        'title': m['title'],
                        'version': m['version'],
                        'beatmap_id': m['beatmap_id'],
                        'mods_str': m['mods_str'],
                        'sr': m['sr'],
                        'skill_score': round(m['scores'].get(skill, 0.0), 2),
                        'skill_points': OsuAnalyzer.score_to_points(m['scores'].get(skill, 0.0)),
                        'pp': round(m['pp'], 1),
                        'acc': m['acc']
                    }
                    for m in top_3
                ]
            }

        # Filtrar solo las habilidades con datos calificados para determinar fortalezas y debilidades
        calibrated_skills = [k for k in skills_def if skills_result[k].get('has_data', False)]

        if calibrated_skills:
            dominant_skill = max(calibrated_skills, key=lambda k: skills_result[k]['points'])
            weakest_skill = min(calibrated_skills, key=lambda k: skills_result[k]['points'])
            sorted_stars = sorted([skills_result[k]['stars'] for k in calibrated_skills], reverse=True)
        else:
            dominant_skill = skills_def[0] if skills_def else "N/A"
            weakest_skill = skills_def[-1] if skills_def else "N/A"
            sorted_stars = [0.0]

        # Promedio Ponderado General de habilidades calibradas
        overall_weights = [0.38, 0.28, 0.18, 0.10, 0.06, 0.04][:len(sorted_stars)]
        overall = round(
            sum(sorted_stars[i] * overall_weights[i] for i in range(len(sorted_stars))) / max(0.001, sum(overall_weights)),
            2
        )
        overall_pts = OsuAnalyzer.score_to_points(overall) if calibrated_skills else 0.0
        ov_glyph, ov_tier = OsuAnalyzer.get_tier_info(overall_pts, lang=lang) if calibrated_skills else ('▫', t('osu.tier_unranked', lang))

        skills_result['dominant_skill'] = dominant_skill
        skills_result['weakest_skill'] = weakest_skill
        skills_result['overall_skill_stars'] = overall
        skills_result['overall_skill_points'] = overall_pts
        skills_result['overall_tier_glyph'] = ov_glyph
        skills_result['overall_tier_name'] = ov_tier
        return skills_result

async def setup(bot):
    pass
