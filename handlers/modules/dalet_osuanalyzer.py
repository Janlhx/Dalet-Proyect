import logging

logger = logging.getLogger('dalet.handlers.osuanalyzer')

class OsuAnalyzer:
    """Calcula el desglose de habilidades técnicas para todos los modos de osu!."""

    MODE_SKILLS = {
        "osu": ['Aim', 'Speed', 'Accuracy', 'Stamina', 'Reading'],
        "taiko": ['Speed', 'Stamina', 'Accuracy', 'Reading', 'Patterning'],
        "fruits": ['Agility', 'Precision', 'Speed', 'Stamina', 'Reading'],
        "mania": ['Chordjack', 'Tech', 'Speed', 'Stamina', 'Accuracy']
    }

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
                eff_sr *= (1.08 + max(0.0, (cs - 4.0) * 0.02))
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
            miss_penalty = max(0.68, 1.0 - (misses * 0.035))
            combo_factor = combo_ratio ** 0.12
            exec_factor = min(1.05, max(0.50, acc_penalty * miss_penalty * combo_factor))

            scores = {}

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
                scores['Speed'] = eff_sr * bpm_mult * exec_factor

                stamina_mult = 1.0
                if total_objects >= 1600:
                    stamina_mult += min(0.20, (total_objects - 1600) * 0.00015)
                elif total_objects < 700:
                    stamina_mult -= min(0.18, (700 - total_objects) * 0.0003)
                if drain >= 200:
                    stamina_mult += min(0.12, (drain - 200) * 0.0008)
                scores['Stamina'] = eff_sr * min(1.22, max(0.65, stamina_mult)) * exec_factor

                eff_od = min(10.5, od * (1.4 if is_hr else (0.5 if is_ez else 1.0)))
                acc_scale = (acc / 0.985) ** 1.6
                scores['Accuracy'] = eff_sr * (eff_od / 9.2) * acc_scale * exec_factor

                reading_mult = 0.75
                if is_hd:
                    reading_mult += 0.18
                if is_fl:
                    reading_mult += 0.32
                if is_ez:
                    reading_mult += 0.22
                if is_dt:
                    reading_mult += 0.08
                scores['Reading'] = eff_sr * min(1.25, reading_mult) * exec_factor

                circle_ratio = count_circles / max(1, total_objects) if total_objects > 0 else 0.8
                pattern_mult = 0.90 + 0.15 * circle_ratio
                if is_hr:
                    pattern_mult += 0.08
                scores['Patterning'] = eff_sr * pattern_mult * exec_factor

            elif mode_clean == "fruits":
                # --- CATCH (FRUITS): Agility, Precision, Speed, Stamina, Reading ---
                eff_cs = cs * (1.3 if is_hr else (0.5 if is_ez else 1.0))
                cs_mult = 0.85 + max(-0.15, (eff_cs - 4.0) * 0.10)
                scores['Precision'] = eff_sr * min(1.25, cs_mult) * exec_factor

                agility_mult = 0.92
                if is_hr:
                    agility_mult += 0.12
                if is_dt:
                    agility_mult += 0.08
                scores['Agility'] = eff_sr * agility_mult * exec_factor

                eff_bpm = bpm * (1.5 if is_dt else 1.0)
                bpm_mult = 1.0
                if eff_bpm >= 200:
                    bpm_mult += min(0.18, (eff_bpm - 200) * 0.0025)
                elif eff_bpm < 150:
                    bpm_mult -= min(0.15, (150 - eff_bpm) * 0.0025)
                if is_dt:
                    bpm_mult += 0.10
                scores['Speed'] = eff_sr * bpm_mult * exec_factor

                stamina_mult = 1.0
                if total_objects >= 1400:
                    stamina_mult += min(0.18, (total_objects - 1400) * 0.00015)
                elif total_objects < 600:
                    stamina_mult -= min(0.15, (600 - total_objects) * 0.0003)
                if drain >= 180:
                    stamina_mult += min(0.10, (drain - 180) * 0.0008)
                scores['Stamina'] = eff_sr * min(1.20, max(0.70, stamina_mult)) * exec_factor

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
                scores['Reading'] = eff_sr * min(1.28, reading_mult) * exec_factor

            elif mode_clean == "mania":
                # --- MANIA: Chordjack, Tech, Speed, Stamina, Accuracy ---
                key_count = int(cs) if cs >= 4 else 4
                ln_ratio = count_sliders / max(1, total_objects) if total_objects > 0 else 0.0
                real_drain = drain / 1.5 if is_dt else drain
                nps = total_objects / max(1.0, real_drain)
                eff_bpm = bpm * (1.5 if is_dt else 1.0)

                # 1. Chordjack: Acordes densos simultáneos y tensión en los dedos (7K vs 4K)
                # Ocurre típicamente en BPM moderado (150 - 215 BPM).
                # A 230+ BPM es inviable hacer chordjacks puros sostenidos (son jumpstreams de Speed).
                key_bonus = 0.12 if key_count >= 7 else (0.06 if key_count >= 5 else 0.0)
                chord_mult = 0.95 + key_bonus
                if 150 <= eff_bpm <= 215 and nps >= 7.0:
                    chord_mult += min(0.28, (nps - 7.0) * 0.045)
                elif eff_bpm >= 230:
                    chord_mult -= min(0.30, (eff_bpm - 230) * 0.006)
                if ln_ratio >= 0.20:
                    chord_mult -= min(0.22, (ln_ratio - 0.20) * 0.70)
                if is_hr:
                    chord_mult += 0.06
                scores['Chordjack'] = eff_sr * max(0.55, chord_mult) * exec_factor

                # 2. Tech: Coordinación compleja de Long Notes (LN / Hold Notes), bursts rítmicos y minijacks.
                # Como definen los jugadores de Dans: bursts rápidos, densos y cortos, o LN noodles / inverses.
                # FILTRO ANTI-FALSO-POSITIVO (La X roja de Tatoris 1.5x):
                # Si el mapa es rate-up speed puro (eff_bpm >= 235 con 0% LN), es Speed farm, NO Tech.
                tech_mult = 0.85
                if ln_ratio >= 0.08:
                    tech_mult += min(0.38, (ln_ratio - 0.08) * 1.50)

                # Bursts rítmicos densos en BPM técnico (170 - 235 BPM):
                if 170 <= eff_bpm <= 235 and nps >= 7.5:
                    tech_mult += min(0.20, (nps - 7.5) * 0.035)

                if eff_bpm >= 235 and ln_ratio < 0.10:
                    # Penalización para speed streams planos a ultra alta velocidad
                    tech_mult -= min(0.30, (eff_bpm - 235) * 0.007)

                if is_hd or is_fl:
                    tech_mult += 0.08
                scores['Tech'] = eff_sr * min(1.35, max(0.50, tech_mult)) * exec_factor

                # 3. Speed: Velocidad bruta de repetición (BPM alto y NPS alto en ráfagas de rice)
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
                scores['Speed'] = eff_sr * min(1.30, speed_mult) * exec_factor

                # 4. Stamina: Resistencia en charts extensos de alta densidad (maratones reales >= 160s)
                stamina_mult = 0.95
                if real_drain >= 160:
                    stamina_mult += min(0.18, (real_drain - 160) * 0.001)
                    if nps >= 7.5:
                        stamina_mult += min(0.18, (nps - 7.5) * 0.03)
                elif real_drain < 120:
                    stamina_mult -= min(0.20, (120 - real_drain) * 0.003)

                if total_objects >= 1700:
                    stamina_mult += min(0.20, (total_objects - 1700) * 0.00015)
                elif total_objects < 800:
                    stamina_mult -= min(0.18, (800 - total_objects) * 0.0003)

                scores['Stamina'] = eff_sr * min(1.28, max(0.55, stamina_mult)) * exec_factor

                # 5. Accuracy: Ventana OD estricta y sincronización de pulsos
                eff_od = min(10.5, od * (1.4 if is_hr else 1.0))
                acc_scale = (acc / 0.985) ** 1.8
                scores['Accuracy'] = eff_sr * (eff_od / 9.2) * acc_scale * exec_factor

            else:
                # --- OSU (STANDARD): Aim, Speed, Accuracy, Stamina, Reading ---
                circle_ratio = count_circles / max(1, total_objects) if total_objects > 0 else 0.7
                cs_bonus = max(0.0, (cs - 4.0) * 0.06)
                aim_mult = 0.95 + 0.15 * circle_ratio + cs_bonus
                scores['Aim'] = eff_sr * aim_mult * exec_factor

                eff_bpm = bpm * (1.5 if is_dt else 1.0)
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
                scores['Speed'] = eff_sr * bpm_mult * exec_factor

                eff_od = min(11.0, od * (1.4 if is_hr else (0.5 if is_ez else 1.0)))
                od_scale = eff_od / 9.8
                acc_normalized = max(0.0, (acc - 0.90) / 0.10)
                acc_curve = acc_normalized ** 1.6
                acc_mult = min(1.15, max(0.50, 0.75 + 0.35 * acc_curve)) * od_scale
                scores['Accuracy'] = eff_sr * acc_mult * exec_factor

                # Resistencia (Stamina): Pondera densidad de notas por segundo (NPS) y maratones.
                # Con DT, el mapa dura menos tiempo pero la densidad de notas por segundo es 1.5x mayor.
                real_drain = drain / 1.5 if is_dt else drain
                density = total_objects / max(1.0, real_drain)
                stamina_mult = 1.0
                if density >= 6.0:
                    stamina_mult += min(0.22, (density - 6.0) * 0.04)
                elif density < 3.5:
                    stamina_mult -= min(0.15, (3.5 - density) * 0.04)

                if is_dt and bpm >= 160:
                    stamina_mult += 0.08

                if total_objects >= 1100:
                    stamina_mult += min(0.15, (total_objects - 1100) * 0.00015)
                elif total_objects < 500:
                    stamina_mult -= min(0.15, (500 - total_objects) * 0.0003)

                if real_drain >= 180:
                    stamina_mult += min(0.10, (real_drain - 180) * 0.0008)
                scores['Stamina'] = eff_sr * min(1.25, max(0.65, stamina_mult)) * exec_factor

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

                scores['Reading'] = eff_sr * min(1.30, reading_mult) * exec_factor

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
                skill: {'stars': 0.0, 'top_maps': []} for skill in skills_def
            } | {
                'dominant_skill': 'N/A',
                'weakest_skill': 'N/A',
                'overall_skill_stars': 0.0
            }

        skills_result = {}
        for skill in skills_def:
            sorted_by_skill = sorted(scored_plays, key=lambda x: x['scores'].get(skill, 0.0), reverse=True)
            top_3 = sorted_by_skill[:3]

            sample = sorted_by_skill[:25]
            weights = [0.95 ** i for i in range(len(sample))]
            weighted_stars = sum(sample[i]['scores'].get(skill, 0.0) * weights[i] for i in range(len(sample))) / max(0.001, sum(weights))

            skills_result[skill] = {
                'stars': round(weighted_stars, 2),
                'top_maps': [
                    {
                        'title': m['title'],
                        'version': m['version'],
                        'beatmap_id': m['beatmap_id'],
                        'mods_str': m['mods_str'],
                        'sr': m['sr'],
                        'skill_score': round(m['scores'].get(skill, 0.0), 2),
                        'pp': round(m['pp'], 1),
                        'acc': m['acc']
                    }
                    for m in top_3
                ]
            }

        dominant_skill = max(skills_def, key=lambda k: skills_result[k]['stars'])
        weakest_skill = min(skills_def, key=lambda k: skills_result[k]['stars'])
        overall = round(sum(skills_result[k]['stars'] for k in skills_def) / len(skills_def), 2)

        skills_result['dominant_skill'] = dominant_skill
        skills_result['weakest_skill'] = weakest_skill
        skills_result['overall_skill_stars'] = overall
        return skills_result

async def setup(bot):
    pass
