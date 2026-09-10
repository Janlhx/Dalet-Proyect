import logging

logger = logging.getLogger('dalet.handlers.osuanalyzer')

class OsuAnalyzer:
    '''Calcula el desglose de habilidades tecnicas para osu!.'''

    @staticmethod
    def calculate_skills(best_plays: list) -> dict:
        skills_def = ['Aim', 'Speed', 'Accuracy', 'Stamina', 'Reading']
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

            acc_penalty = (acc / 0.98) ** 1.25 if acc > 0 else 0.5
            miss_penalty = max(0.72, 1.0 - (misses * 0.03))
            combo_factor = combo_ratio ** 0.10
            exec_factor = min(1.04, max(0.55, acc_penalty * miss_penalty * combo_factor))

            circle_ratio = count_circles / max(1, total_objects) if total_objects > 0 else 0.7
            cs_bonus = max(0.0, (cs - 4.0) * 0.05)
            aim_score = eff_sr * (0.90 + 0.15 * circle_ratio + cs_bonus) * exec_factor

            eff_bpm = bpm * (1.5 if is_dt else 1.0)
            bpm_mult = 1.0
            if eff_bpm >= 210:
                bpm_mult += min(0.15, (eff_bpm - 210) * 0.0025)
            elif eff_bpm < 160:
                bpm_mult -= min(0.20, (160 - eff_bpm) * 0.003)
            if is_dt:
                bpm_mult += 0.05
            speed_score = eff_sr * bpm_mult * exec_factor

            eff_od = min(11.0, od * (1.4 if is_hr else (0.5 if is_ez else 1.0)))
            acc_factor = (acc / 0.98) ** 1.5 if acc > 0 else 0.5
            acc_score = eff_sr * (eff_od / 9.2) * acc_factor

            eff_drain = drain / 1.5 if is_dt else drain
            stamina_mult = 1.0
            if eff_drain >= 210:
                stamina_mult += min(0.12, (eff_drain - 210) * 0.0008)
            elif eff_drain < 90:
                stamina_mult -= min(0.20, (90 - eff_drain) * 0.003)
            if total_objects >= 1200:
                stamina_mult += min(0.10, (total_objects - 1200) * 0.0001)
            elif total_objects < 500:
                stamina_mult -= min(0.15, (500 - total_objects) * 0.0003)
            stamina_score = eff_sr * min(1.18, max(0.70, stamina_mult)) * exec_factor

            eff_ar = min(10.0, ar * 1.4) if is_hr else (ar * 0.5 if is_ez else ar)
            if is_dt:
                eff_ar = min(11.1, (eff_ar * 2 + 13) / 3)
            
            reading_mult = 1.0
            if eff_ar <= 8.5:
                reading_mult += min(0.15, (8.5 - eff_ar) * 0.08)
            elif eff_ar >= 10.3:
                reading_mult += min(0.12, (eff_ar - 10.3) * 0.08)
            if is_hd:
                reading_mult += 0.08
            if is_fl:
                reading_mult += 0.25
            if is_ez:
                reading_mult += 0.15
            reading_score = eff_sr * min(1.20, reading_mult) * exec_factor

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
                'scores': {
                    'Aim': aim_score,
                    'Speed': speed_score,
                    'Accuracy': acc_score,
                    'Stamina': stamina_score,
                    'Reading': reading_score
                }
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
            sorted_by_skill = sorted(scored_plays, key=lambda x: x['scores'][skill], reverse=True)
            top_3 = sorted_by_skill[:3]
            
            sample = sorted_by_skill[:25]
            weights = [0.95 ** i for i in range(len(sample))]
            weighted_stars = sum(sample[i]['scores'][skill] * weights[i] for i in range(len(sample))) / max(0.001, sum(weights))
            
            skills_result[skill] = {
                'stars': round(weighted_stars, 2),
                'top_maps': [
                    {
                        'title': m['title'],
                        'version': m['version'],
                        'beatmap_id': m['beatmap_id'],
                        'mods_str': m['mods_str'],
                        'sr': m['sr'],
                        'skill_score': round(m['scores'][skill], 2),
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
