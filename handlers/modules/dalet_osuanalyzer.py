import logging

logger = logging.getLogger('dalet.handlers.osuanalyzer')

class OsuAnalyzer:
    """Calcula el desglose de habilidades técnicas para todos los modos de osu!."""

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
    def calculate_skills(best_plays: list, mode: str = "osu") -> dict:
        mode_clean = (mode or "osu").lower().strip()
        skills_def = OsuAnalyzer.get_mode_skills(mode_clean)

        if not best_plays:
            return {
                skill: {'stars': 0.0, 'top_maps': []} for skill in skills_def
            } | {
                'dominant_skill': 'N/A',
                'weakest_skill': 'N/A',
                'overall_skill_stars': 0.0
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

            if mode_clean == "taiko":
                # --- TAIKO: Speed, Stamina, Accuracy, Reading, Patterning ---
                eff_bpm = bpm * (1.5 if is_dt else 1.0)
                bpm_mult = 1.0
                if eff_bpm >= 220:
                    bpm_mult += min(0.20, (eff_bpm - 220) * 0.003)
                elif eff_bpm < 160:
                    bpm_mult -= min(0.18, (160 - eff_bpm) * 0.003)
                if is_dt:
                    bpm_mult += 0.08
                raw_weights['Speed'] = bpm_mult

                stamina_mult = 1.0
                if total_objects >= 1600:
                    stamina_mult += min(0.20, (total_objects - 1600) * 0.00015)
                elif total_objects < 700:
                    stamina_mult -= min(0.18, (700 - total_objects) * 0.0003)
                if drain >= 200:
                    stamina_mult += min(0.12, (drain - 200) * 0.0008)
                raw_weights['Stamina'] = min(1.22, max(0.65, stamina_mult))

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

                eff_bpm = bpm * (1.5 if is_dt else 1.0)
                bpm_mult = 1.0
                if eff_bpm >= 200:
                    bpm_mult += min(0.18, (eff_bpm - 200) * 0.0025)
                elif eff_bpm < 150:
                    bpm_mult -= min(0.15, (150 - eff_bpm) * 0.0025)
                if is_dt:
                    bpm_mult += 0.10
                raw_weights['Speed'] = bpm_mult

                stamina_mult = 1.0
                if total_objects >= 1400:
                    stamina_mult += min(0.18, (total_objects - 1400) * 0.00015)
                elif total_objects < 600:
                    stamina_mult -= min(0.15, (600 - total_objects) * 0.0003)
                if drain >= 180:
                    stamina_mult += min(0.10, (drain - 180) * 0.0008)
                raw_weights['Stamina'] = min(1.20, max(0.70, stamina_mult))

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
                real_drain = drain / 1.5 if is_dt else drain
                nps = total_objects / max(1.0, real_drain)
                eff_bpm = bpm * (1.5 if is_dt else 1.0)

                # 1. LN (Long Notes): Coordinación de hold notes, release timing, fideos e inverse
                # Es el hogar de mapas con alta densidad de sliders (cryptarithm, end time, burning desires)
                ln_mult = 0.50
                if ln_ratio >= 0.15:
                    ln_mult += min(0.80, (ln_ratio - 0.15) * 2.20)
                    if ln_ratio >= 0.35:
                        ln_mult += 0.15
                elif ln_ratio < 0.10:
                    ln_mult -= min(0.25, (0.10 - ln_ratio) * 2.50)
                if key_count >= 7:
                    ln_mult += 0.08
                raw_weights['LN'] = min(1.35, max(0.20, ln_mult))

                # 2. Chordjack: Acordes densos simultáneos y tensión en los dedos (7K vs 4K) en notas regulares (Rice).
                # Ocurre típicamente en BPM moderado (150 - 215 BPM).
                # A 225+ BPM es inviable hacer chordjacks puros sostenidos (son jumpstreams de Speed).
                key_bonus = 0.12 if key_count >= 7 else (0.06 if key_count >= 5 else 0.0)
                chord_mult = 0.95 + key_bonus
                if 150 <= eff_bpm <= 215 and nps >= 7.0:
                    chord_mult += min(0.28, (nps - 7.0) * 0.045)
                elif eff_bpm >= 225:
                    chord_mult -= min(0.35, (eff_bpm - 225) * 0.007)

                # FILTRO ANTI-LN ESTRICTO: Si tiene más de 12% de LN (como cryptarithm o end time), NO es Chordjack puro
                if ln_ratio >= 0.12:
                    chord_mult -= min(0.60, (ln_ratio - 0.12) * 2.60)

                if is_hr:
                    chord_mult += 0.06
                raw_weights['Chordjack'] = min(1.30, max(0.30, chord_mult))

                # 3. Tech: Coordinación compleja, bursts rítmicos densos, polirritmias y minijacks.
                # FILTRO ANTI-SPEED (Tatoris 1.5x): Speed farm a ultra BPM sin LN es Speed puro.
                # FILTRO ANTI-LN (End time / Burning desires): Si es dominantemente LN (>= 35%), pertenece a LN.
                tech_mult = 0.90
                if 170 <= eff_bpm <= 235 and nps >= 7.5:
                    tech_mult += min(0.25, (nps - 7.5) * 0.035)

                if eff_bpm >= 235 and ln_ratio < 0.10:
                    tech_mult -= min(0.40, (eff_bpm - 235) * 0.008)

                if ln_ratio >= 0.35:
                    tech_mult -= min(0.45, (ln_ratio - 0.35) * 1.80)

                if is_hd or is_fl:
                    tech_mult += 0.08
                raw_weights['Tech'] = min(1.30, max(0.35, tech_mult))

                # 4. Speed: Velocidad bruta de repetición (BPM alto y NPS alto en ráfagas de rice)
                speed_mult = 0.92
                if eff_bpm >= 210:
                    speed_mult += min(0.22, (eff_bpm - 210) * 0.003)
                elif eff_bpm < 150:
                    speed_mult -= min(0.18, (150 - eff_bpm) * 0.003)
                if nps >= 8.5:
                    speed_mult += min(0.15, (nps - 8.5) * 0.025)
                if is_dt:
                    speed_mult += 0.08
                if ln_ratio < 0.10 and eff_bpm >= 220:
                    speed_mult += 0.06  # Bono extra para speed streams puros sin LN
                raw_weights['Speed'] = min(1.30, speed_mult)

                # 5. Stamina: Resistencia en charts extensos de alta densidad y strain sostenido (maratones reales >= 160s)
                # Mapas densos pero cortos (~2 minutos como cryptarithm) NO deben inflar stamina.
                stamina_mult = 0.85
                if real_drain >= 160:
                    stamina_mult += min(0.28, (real_drain - 160) * 0.0018)
                    if nps >= 7.5:
                        stamina_mult += min(0.20, (nps - 7.5) * 0.03)
                elif real_drain < 140:
                    stamina_mult -= min(0.35, (140 - real_drain) * 0.005)

                if total_objects >= 1800:
                    stamina_mult += min(0.20, (total_objects - 1800) * 0.00015)
                elif total_objects < 900:
                    stamina_mult -= min(0.25, (900 - total_objects) * 0.0003)

                raw_weights['Stamina'] = min(1.30, max(0.35, stamina_mult))

                # 6. Accuracy: Ventana OD estricta y sincronización de pulsos
                eff_od = min(10.5, od * (1.4 if is_hr else 1.0))
                acc_scale = (acc / 0.985) ** 1.8
                raw_weights['Accuracy'] = (eff_od / 9.2) * acc_scale

            else:
                # --- OSU (STANDARD): Aim, Speed, Accuracy, Stamina, Reading ---
                eff_bpm = bpm * (1.5 if is_dt else 1.0)
                circle_ratio = count_circles / max(1, total_objects) if total_objects > 0 else 0.7
                cs_bonus = max(0.0, (cs - 4.0) * 0.06)
                aim_mult = 0.95 + 0.15 * circle_ratio + cs_bonus
                if is_dt:
                    aim_mult += 0.08
                    if eff_bpm >= 210:
                        aim_mult += min(0.12, (eff_bpm - 210) * 0.002)
                raw_weights['Aim'] = aim_mult

                bpm_mult = 1.0
                if eff_bpm >= 210:
                    bpm_mult += min(0.18, (eff_bpm - 210) * 0.0028)
                elif eff_bpm < 160:
                    bpm_mult -= min(0.20, (160 - eff_bpm) * 0.003)
                if is_dt:
                    bpm_mult += 0.06
                # El tiempo de reacción en alta AR (>= 10.0) pertenece a Speed (mecánica y reflejos de lectura rápida)
                eff_ar = min(10.0, ar * 1.4) if is_hr else (ar * 0.5 if is_ez else ar)
                if is_dt:
                    eff_ar = min(11.1, (eff_ar * 2 + 13) / 3)
                if eff_ar >= 10.0:
                    bpm_mult += min(0.12, (eff_ar - 10.0) * 0.08)
                raw_weights['Speed'] = bpm_mult

                eff_od = min(11.0, od * (1.4 if is_hr else (0.5 if is_ez else 1.0)))
                od_scale = eff_od / 9.8
                acc_normalized = max(0.0, (acc - 0.90) / 0.10)
                acc_curve = acc_normalized ** 1.6
                acc_mult = min(1.15, max(0.50, 0.75 + 0.35 * acc_curve)) * od_scale
                raw_weights['Accuracy'] = acc_mult

                # Resistencia (Stamina): Pondera maratones continuos (drain extenso) y alta densidad sostenida.
                # Con DT, el mapa dura menos tiempo; el drain real se reduce en 1.5x.
                real_drain = drain / 1.5 if is_dt else drain
                density = total_objects / max(1.0, real_drain)

                # Base de Stamina reducida: debe demostrarse resistencia en tiempo real.
                stamina_mult = 0.85
                if real_drain >= 150:
                    stamina_mult += min(0.25, (real_drain - 150) * 0.0015)
                    if density >= 5.5:
                        stamina_mult += min(0.20, (density - 5.5) * 0.04)
                elif real_drain < 110:
                    # Penalización severa para mapas cortos de TV-size (< 110s drain real)
                    stamina_mult -= min(0.35, (110 - real_drain) * 0.006)

                if total_objects >= 1100:
                    stamina_mult += min(0.18, (total_objects - 1100) * 0.00015)
                elif total_objects < 700:
                    stamina_mult -= min(0.25, (700 - total_objects) * 0.0005)

                raw_weights['Stamina'] = min(1.30, max(0.40, stamina_mult))

                # Lectura (Reading): Dificultad visual genuina por solapamiento de notas, densidad y memorización.
                # Mantener una base armónica (~0.80 - 0.84) para que la métrica no colapse de forma irreal en el perfil,
                # pero sin otorgar ventajas a mapas de AR alta donde el desafío es puramente reacción/velocidad.
                if eff_ar >= 10.0:
                    reading_mult = 0.80
                elif eff_ar >= 9.6:
                    reading_mult = 0.82
                else:
                    reading_mult = 0.85

                # Bonificaciones genuinas de lectura:
                if eff_ar <= 8.5:
                    reading_mult += min(0.30, (8.5 - eff_ar) * 0.10)
                    if eff_ar <= 7.0:
                        reading_mult += 0.15

                if is_hd:
                    if eff_ar <= 8.5:
                        reading_mult += 0.22  # HD en baja AR es lectura extrema
                    elif eff_ar <= 9.6:
                        reading_mult += 0.10  # HD estándar
                    else:
                        reading_mult += 0.04  # HD en AR 10+ es casi puro músculo/reacción

                if is_fl:
                    reading_mult += 0.40
                if is_ez:
                    reading_mult += 0.30

                slider_ratio = count_sliders / max(1, total_objects) if total_objects > 0 else 0.3
                if slider_ratio >= 0.35:
                    reading_mult += min(0.18, (slider_ratio - 0.35) * 0.30)

                raw_weights['Reading'] = min(1.30, reading_mult)

            # --- NORMALIZACIÓN ANCLADA AL STAR RATING (OPCIÓN 1) ---
            # La habilidad dominante del mapa define la dificultad representativa (eff_sr).
            # Las demás habilidades se calculan como una fracción proporcional (<= eff_sr).
            # exec_factor (<= 1.00) modula según el desempeño real (acc, misses, combo).
            max_raw = max(raw_weights.values()) if raw_weights else 1.0
            max_raw = max(0.001, max_raw)

            scores = {}
            for skill in skills_def:
                rel_ratio = raw_weights.get(skill, 0.50) / max_raw
                scores[skill] = round(eff_sr * rel_ratio * exec_factor, 2)

            title = bset.get('title') or bm.get('title', 'Desconocido')
            version = bm.get('version', 'Normal')
            beatmap_id = bm.get('id') or p.get('beatmap_id', 0)
            pp_val = float(p.get('pp') or 0.0)

            scored_plays.append({
                'title': title,
                'version': version,
                'beatmap_id': beatmap_id,
                'mods_str': mods_str,
                'sr': eff_sr,
                'pp': pp_val,
                'acc': round(acc * 100.0, 2),
                'scores': scores
            })

        if not scored_plays:
            return {
                skill: {
                    'stars': 0.0,
                    'points': 0.0,
                    'tier_glyph': '▫',
                    'tier_name': 'Aprendiz',
                    'top_maps': []
                } for skill in skills_def
            } | {
                'dominant_skill': 'N/A',
                'weakest_skill': 'N/A',
                'overall_skill_stars': 0.0,
                'overall_skill_points': 0.0,
                'overall_tier_glyph': '▫',
                'overall_tier_name': 'Aprendiz'
            }

        skills_result = {}
        for skill in skills_def:
            sorted_by_skill = sorted(scored_plays, key=lambda x: x['scores'].get(skill, 0.0), reverse=True)
            top_3 = sorted_by_skill[:3]

            # Muestrear el top 10 con decaimiento (0.85^i) enfocado en el rendimiento pico del jugador
            sample = sorted_by_skill[:10]
            weights = [0.85 ** i for i in range(len(sample))]
            weighted_stars = sum(sample[i]['scores'].get(skill, 0.0) * weights[i] for i in range(len(sample))) / max(0.001, sum(weights))

            pts = OsuAnalyzer.score_to_points(weighted_stars)
            tier_glyph, tier_name = OsuAnalyzer.get_tier_info(pts)

            skills_result[skill] = {
                'points': pts,
                'stars': round(weighted_stars, 2),
                'tier_glyph': tier_glyph,
                'tier_name': tier_name,
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

        dominant_skill = max(skills_def, key=lambda k: skills_result[k]['points'])
        weakest_skill = min(skills_def, key=lambda k: skills_result[k]['points'])

        # Promedio Ponderado General: Valora el estilo de juego del usuario dando mayor relevancia a sus fortalezas
        # sin arrastrar el promedio por habilidades secundarias (como reading o acc estricto en jugadores de jumps)
        sorted_stars = sorted([skills_result[k]['stars'] for k in skills_def], reverse=True)
        overall_weights = [0.38, 0.28, 0.18, 0.10, 0.06, 0.04][:len(sorted_stars)]
        overall = round(
            sum(sorted_stars[i] * overall_weights[i] for i in range(len(sorted_stars))) / max(0.001, sum(overall_weights)),
            2
        )
        overall_pts = OsuAnalyzer.score_to_points(overall)
        ov_glyph, ov_tier = OsuAnalyzer.get_tier_info(overall_pts)

        skills_result['dominant_skill'] = dominant_skill
        skills_result['weakest_skill'] = weakest_skill
        skills_result['overall_skill_stars'] = overall
        skills_result['overall_skill_points'] = overall_pts
        skills_result['overall_tier_glyph'] = ov_glyph
        skills_result['overall_tier_name'] = ov_tier
        return skills_result

async def setup(bot):
    pass
