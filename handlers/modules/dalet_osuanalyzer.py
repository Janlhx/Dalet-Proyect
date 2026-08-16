"""
Módulo de Lógica de Análisis de osu! (v4.1)

Esta versión corrige el 'edge case' donde el 'acc promedio'
daba 0.0% si todas las partidas recientes eran 'fails'.
Ahora maneja este caso como 'N/A' (No Aplicable).
"""
from collections import Counter
import statistics
import random

# Diccionario de Palabras Clave (sin cambios)
FOCUS_KEYWORDS = {
    "precisión": ["technical", "aim control", "consistency", "low ar"],
    "consistencia": ["stamina", "stream", "long map", "marathon"],
    "stamina y control en velocidad": ["deathstream", "speed", "high bpm", "stamina"],
    "lectura y aim complejo": ["reading", "tech", "pattern", "aim"],
    "velocidad": ["jump", "speed", "dt farm"],
    "lectura": ["low ar", "reading", "hd farm"],
    "stamina": ["stream", "stamina", "endurance"]
}

class OsuAnalyzer:
    """Analiza datos de osu! (v4.1) y genera prompts detallados para la IA."""

    def __init__(self, osu_api, user_data: dict, recent_plays: list = None, best_plays: list = None, user_focus: str = None):
        self.osu_api = osu_api
        self.user = user_data or {}
        self.recent = recent_plays or [] # 50 recents (incluye fails)
        self.best = best_plays or [] # 50 best
        self.mode = self.user.get("playmode", "osu")
        self.user_focus = user_focus
        
        self.stats = self.user.get("statistics", {})
        self.grades = self.stats.get("grade_counts", {})
        self.play_count = self.stats.get("play_count", 0)
        
        self.analysis_summary = {}

    # --- ANÁLISIS DE "BEST PLAYS" (TOP 50) ---

    def _analyze_best_playstyle(self) -> dict:
        """Analiza los 'best plays' (Top 50) para detectar el estilo HISTÓRICO."""
        if not self.best:
            return {"detected_style": "Desconocido", "dominant_mods": ["NM"]}
            
        mods_list = [m for p in self.best for m in p.get("mods", [])]
        if not mods_list: mods_list = ["NM"]
            
        mods_counter = Counter(mods_list)
        dominant_mods = [m for m, _ in mods_counter.most_common(3)]
        
        style = "Híbrido"
        if mods_counter['DT'] > 5 or mods_counter['NC'] > 5: style = "Velocidad (DT/NC)"
        elif mods_counter['HR'] > 5: style = "Precisión (HR)"
        elif mods_counter['HD'] > 10: style = "Lectura (HD)"
        
        return {"detected_style": style, "dominant_mods": dominant_mods}

    def _analyze_pp_spread(self) -> dict:
        """Analiza la diferencia de PP entre los 'best plays'."""
        if len(self.best) < 10:
            return {"spread_type": "Pocos Datos", "top_pp": 0, "50th_pp": 0}

        pp_values = sorted([p.get('pp', 0) for p in self.best if p.get('pp')], reverse=True)
        top_pp = pp_values[0]
        fiftieth_pp = pp_values[min(len(pp_values)-1, 49)] # Su 50º play
        
        spread_type = "Consistente"
        if top_pp > fiftieth_pp * 2:
            spread_type = "Farmer (Top-heavy)"
            
        return {"spread_type": spread_type, "top_pp": top_pp, "50th_pp": fiftieth_pp}

    def _analyze_best_beatmap_stats(self) -> dict:
        """Analiza las propiedades de los mapas en los 'best plays' (Top 50)."""
        bp_stats = {'ar': [], 'od': [], 'cs': [], 'length': []}
        
        for p in self.best:
            bm = p.get('beatmap')
            if bm:
                bp_stats['ar'].append(bm.get('ar', 9.0))
                bp_stats['od'].append(bm.get('accuracy', 7.0))
                bp_stats['cs'].append(bm.get('cs', 4.0))
                bp_stats['length'].append(bm.get('total_length', 180))

        if not bp_stats['ar']:
            return {'avg_ar': 9.0, 'avg_od': 7.0, 'avg_cs': 4.0, 'avg_length': 180}

        return {
            'avg_ar': statistics.mean(bp_stats['ar']),
            'avg_od': statistics.mean(bp_stats['od']),
            'avg_cs': statistics.mean(bp_stats['cs']),
            'avg_length': statistics.mean(bp_stats['length']),
        }

    # --- ANÁLISIS DE "RECENT PLAYS" (ÚLTIMAS 50) ---

    def _analyze_trends(self) -> dict:
        """
        Analiza los 'recent plays' para detectar la consistencia del accuracy.
        
        (BUG ARREGLADO v4.1): Maneja el caso de 'no partidas pasadas'.
        """
        # Filtramos solo las partidas que NO son 'pass: False'
        recent_accs = [
            p['accuracy'] * 100 for p in self.recent
            if p.get('pass') != False and 'accuracy' in p # Keep 'pass: True' and 'pass: None'
        ]
        
        # --- ¡FIX v4.1! ---
        # Si la lista está vacía, no devuelvas 0.0, devuélve None.
        if not recent_accs: 
            return {"trend": "Ninguna", "consistency": "Baja (Inconsistente)", "avg_recent_acc": None} 
        # --- FIN FIX ---
        
        avg_acc = statistics.mean(recent_accs)
        std_dev = statistics.pstdev(recent_accs) if len(recent_accs) > 1 else 0
        
        consistency = "Alta" if std_dev < 1.5 else "Media" if std_dev < 3.5 else "Baja (Inconsistente)"
        return {"trend": "Estable", "consistency": consistency, "avg_recent_acc": round(avg_acc, 2)}

    def _analyze_recent_playstyle(self) -> dict:
        """Analiza los 'recent plays' (Últimos 50) para detectar el estilo ACTUAL."""
        if not self.recent:
            return {"detected_style": "Ninguna", "dominant_mods": ["NM"]}
        
        passed_recent_plays = [p for p in self.recent if p.get('pass') != False]
        if not passed_recent_plays:
             return {"detected_style": "Ninguna", "dominant_mods": ["NM"]}

        mods_list = [m for p in passed_recent_plays for m in p.get('mods', [])]
        if not mods_list: mods_list = ["NM"]
        
        mods_counter = Counter(mods_list)
        dominant_mods = [m for m, _ in mods_counter.most_common(3)]
        
        style = "Híbrido"
        if mods_counter['DT'] > 3 or mods_counter['NC'] > 3: style = "Velocidad (DT/NC)"
        elif mods_counter['HR'] > 3: style = "Precisión (HR)"
        elif mods_counter['HD'] > 5: style = "Lectura (HD)"
            
        return {"detected_style": style, "dominant_mods": dominant_mods}

    def _analyze_recent_beatmap_stats(self) -> dict:
        """Analiza las propiedades de los mapas en los 'recent plays' (Últimos 50)."""
        passed_recent_plays = [p for p in self.recent if p.get('pass') != False]
        if not passed_recent_plays:
            return {'avg_ar': 9.0, 'avg_od': 7.0, 'avg_cs': 4.0, 'avg_length': 180}

        bp_stats = {'ar': [], 'od': [], 'cs': [], 'length': []}
        for p in passed_recent_plays:
            bm = p.get('beatmap')
            if bm:
                bp_stats['ar'].append(bm.get('ar', 9.0))
                bp_stats['od'].append(bm.get('accuracy', 7.0))
                bp_stats['cs'].append(bm.get('cs', 4.0))
                bp_stats['length'].append(bm.get('total_length', 180))
        
        if not bp_stats['ar']:
             return {'avg_ar': 9.0, 'avg_od': 7.0, 'avg_cs': 4.0, 'avg_length': 180}
        
        return {
            'avg_ar': statistics.mean(bp_stats['ar']),
            'avg_od': statistics.mean(bp_stats['od']),
            'avg_cs': statistics.mean(bp_stats['cs']),
            'avg_length': statistics.mean(bp_stats['length']),
        }

    # --- LÓGICA DE DECISIÓN Y BÚSQUEDA ---

    def _determine_focus(self, trends: dict, pp_spread: dict, recent_beatmap_stats: dict) -> str:
        """
        Determina el área de enfoque (debilidad) de manera inteligente.
        Calcula una puntuación de prioridad para cada área débil para evitar falsos positivos
        y que no siempre sea "consistencia".
        """
        if self.user_focus and self.user_focus in FOCUS_KEYWORDS:
            return self.user_focus

        # Extraer estadísticas base
        global_acc = self.stats.get("hit_accuracy", 96.0)
        total_s = self.grades.get('s', 0) + self.grades.get('sh', 0)
        total_ss = self.grades.get('ss', 0) + self.grades.get('ssh', 0)
        total_a = self.grades.get('a', 0)
        
        # Estadísticas de Best Plays
        bp_lengths = [p['beatmap'].get('total_length', 180) for p in self.best if 'beatmap' in p]
        avg_bp_length = statistics.mean(bp_lengths) if bp_lengths else 180
        
        bp_bpms = [p['beatmap'].get('bpm', 170) for p in self.best if 'beatmap' in p]
        avg_bp_bpm = statistics.mean(bp_bpms) if bp_bpms else 170

        bp_ars = [p['beatmap'].get('ar', 9.0) for p in self.best if 'beatmap' in p]
        avg_bp_ar = statistics.mean(bp_ars) if bp_ars else 9.0

        # Estadísticas de Recents
        avg_recent_acc = trends.get("avg_recent_acc") # accuracy promedio de pasados
        recent_acc_consistency = trends.get("consistency", "Media")
        
        # Inicializar pesos de debilidades
        scores = {
            "precisión": 0.0,
            "consistencia": 0.0,
            "lectura": 0.0,
            "velocidad": 0.0,
            "stamina": 0.0
        }

        # --- EVALUAR PRECISIÓN (ACCURACY) ---
        # Si la acc global es baja, es prioridad
        if global_acc < 95.0:
            scores["precisión"] += (97.0 - global_acc) * 1.5
        if avg_recent_acc is not None and avg_recent_acc < 96.0:
            scores["precisión"] += (96.0 - avg_recent_acc) * 1.2
        # Si tiene muchos rango A comparado con S/SS
        if total_a > (total_s + total_ss) * 0.7:
            scores["precisión"] += 2.0

        # --- EVALUAR CONSISTENCIA (COMBO / LARGOS) ---
        # Si la inconsistencia de acc es alta
        if recent_acc_consistency == "Baja (Inconsistente)":
            scores["consistencia"] += 2.5
        # Si la duración promedio de sus mejores jugadas es muy baja (farm short maps < 110s)
        if avg_bp_length < 110:
            scores["consistencia"] += (110 - avg_bp_length) * 0.05 + 1.5
        # Si es un farmer top-heavy (pocos scores altos y el resto basura)
        if pp_spread.get("spread_type") == "Farmer (Top-heavy)":
            scores["consistencia"] += 2.0

        # --- EVALUAR LECTURA (READING) ---
        # Si el AR promedio de sus mejores mapas es muy alto (>9.4) pero juega reciente en AR más bajo
        if avg_bp_ar > 9.4 and recent_beatmap_stats.get('avg_ar', 9.0) < 9.2:
            scores["lectura"] += 2.5
        # Si el AR promedio general es bajo pero tiene mala acc
        if recent_beatmap_stats.get('avg_ar', 9.0) < 9.0:
            scores["lectura"] += 1.5

        # --- EVALUAR VELOCIDAD (SPEED / HIGH BPM) ---
        # Si sus top plays son lentas (<165 bpm) y queremos empujarlo a mejorar velocidad
        if avg_bp_bpm < 165:
            scores["velocidad"] += (170 - avg_bp_bpm) * 0.1
        # Si juega reciente con DT pero su acc en recents es mala
        recent_mods = [m for p in self.recent for m in p.get('mods', [])]
        if any(m in ["DT", "NC"] for m in recent_mods):
            if avg_recent_acc is not None and avg_recent_acc < 94.0:
                scores["velocidad"] += 2.0

        # --- EVALUAR STAMINA (STREAMS / LONG MAPS) ---
        # Si juega mapas largos pero con muchos fails/misses
        recent_fails = sum(1 for p in self.recent if p.get('pass') == False)
        if recent_fails > 15 and avg_bp_length > 150:
            scores["stamina"] += 2.5
        # Si su BPM promedio es alto (>180) y la acc reciente baja
        if avg_bp_bpm > 185 and avg_recent_acc is not None and avg_recent_acc < 95.0:
            scores["stamina"] += 2.0

        # Encontrar el área de mayor puntaje
        best_focus = max(scores, key=scores.get)
        
        # Si el puntaje más alto es muy bajo, ir por consistencia general
        if scores[best_focus] < 1.0:
            return "consistencia general"
            
        return best_focus

    async def _search_recommended_maps(self, focus: str) -> list:
        """Busca 5 mapas recomendados de la base de datos (con fallback a la API de osu!)."""
        avg_stars = statistics.mean([p['beatmap']['difficulty_rating'] for p in self.best if 'beatmap' in p]) if self.best else 4.5
        
        min_s = avg_stars - 0.4
        max_s = avg_stars + 0.3
        
        if focus == "consistencia":
            min_s = avg_stars
            max_s = avg_stars + 0.5
        
        # 1. Intentar buscar en la Base de Datos local
        try:
            from database.repositories.osu_repository import OsuRepository
            repo = OsuRepository()
            db_maps = await repo.get_recommended_maps(min_s, max_s, focus, limit=5)
            if db_maps:
                formatted_maps = []
                for r in db_maps:
                    formatted_maps.append({
                        "title": r["title"],
                        "artist": r["artist"],
                        "stars": round(r["stars"], 2),
                        "url": f"https://osu.ppy.sh/beatmapsets/{r['beatmapsetid']}"
                    })
                return formatted_maps
        except Exception as e:
            logger.error(f"[OsuAnalyzer] Error en DB Map Search: {e}")

        # 2. Fallback a la API de osu! si la BD falla o no tiene mapas
        selected_keyword = random.choice(FOCUS_KEYWORDS.get(focus, ["osu"]))
        try:
            results = await self.osu_api.search_beatmaps(self.mode, min_s, max_s, keyword=selected_keyword)
            maps = []
            for m in results:
                bm = m.get("beatmaps", [{}])[0]
                maps.append({"title": m.get("title", "Desconocido"), "artist": m.get("artist", "Desconocido"),
                             "stars": round(bm.get("difficulty_rating", 0), 2), "url": f"https://osu.ppy.sh/beatmapsets/{m.get('id')}"})
            
            return random.sample(maps, k=min(5, len(maps)))
        except Exception as e:
            logger.error(f"[OsuAnalyzer] Error en API Map Search Fallback: {e}") 
            return []


    # --- GENERADOR DE PROMPT UNIFICADO (v5.0 - SUPER ANALYZE) ---

    async def generate_super_prompt(self) -> str:
        """
        Genera un prompt unificado que incluye Estadísticas, Análisis Profundo y Coaching.
        Estructurado para ser dividido en 3 páginas por el Bot.
        """
        # 1. Preparar Datos
        best_playstyle = self._analyze_best_playstyle()
        pp_spread = self._analyze_pp_spread()
        best_beatmap_stats = self._analyze_best_beatmap_stats()
        
        trends = self._analyze_trends()
        recent_playstyle = self._analyze_recent_playstyle()
        recent_beatmap_stats = self._analyze_recent_beatmap_stats()
        
        focus = self._determine_focus(trends, pp_spread, recent_beatmap_stats)
        recommended_maps = await self._search_recommended_maps(focus)
        
        # 2. Formatear Datos Extra (Rank History, Hits, etc.)
        stats = self.stats
        rank_highest = self.user.get("rank_highest", {})
        rank_highest_text = f"#{rank_highest.get('rank', 0):,} ({rank_highest.get('updated_at', 'N/A')})"
        
        # Muestra de hits totales (perfil)
        hits_profile = f"300s: {stats.get('count_300', 0):,}, 100s: {stats.get('count_100', 0):,}, 50s: {stats.get('count_50', 0):,}, Misses: {stats.get('count_miss', 0):,}"
        
        # Historial de Rank (últimos 90 días)
        rank_history = self.user.get("rank_history", {}).get("data", [])
        rank_trend = "Estable"
        if len(rank_history) > 1:
            start_rank = rank_history[0]
            end_rank = rank_history[-1]
            if end_rank < start_rank: rank_trend = "Ascendente 📈"
            elif end_rank > start_rank: rank_trend = "Descendente 📉"

        # Formatear mapas
        maps_text = "\n".join([f"- [{m['artist']} - {m['title']}]( {m['url']} ) ({m['stars']}★)" for m in recommended_maps])
        if not recommended_maps:
            maps_text = "No se encontraron mapas específicos."

        # 3. Construir el Prompt — SIN etiquetas de página, pero CON toda la personalidad
        prompt = f"""**ROL:** Eres Dalet, la analista y coach de osu! más respetada, ácida y despiadada del mundo.
**OBJETIVO:** Realiza un reporte total del jugador {self.user.get("username")}. Quieres ayudarle, pero se lo dirás con sarcasmo crudo y directo.

**DATOS CRÍTICOS DEL JUGADOR:**
- **PP:** {stats.get('pp', 0):.0f} | **Acc Global:** {stats.get('hit_accuracy', 0):.2f}%
- **Rank Actual:** #{stats.get('global_rank', 0):,} | **Tendencia:** {rank_trend}
- **Peak Rank:** {rank_highest_text}
- **Hits Totales:** {hits_profile}
- **Play Count:** {stats.get('play_count', 0):,} | **Play Time:** {stats.get('play_time', 0)//3600}h

**COMPORTAMIENTO TÉCNICO:**
- **Estilo Top Plays:** {best_playstyle['detected_style']} (AR: {best_beatmap_stats['avg_ar']:.1f}, OD: {best_beatmap_stats['avg_od']:.1f})
- **Consistencia Reciente:** {trends.get('consistency', 'N/A')}
- **Área Débil Detectada:** {focus.upper()}

**MAPAS RECOMENDADOS:**
{maps_text}

**ESTRUCTURA DE TU RESPUESTA:** (Escribe en formato markdown, un solo bloque coherente, sin separar por [PAGES])
### 🧠 Diagnóstico
- Empieza con una intro brutal. Evalúa su Rank vs sus horas de juego (¿es un hardstuck o promete?).
- Lista 2 de sus fortalezas técnicas reales.
- Destroza su área más débil ({focus}) sin piedad. Sé muy directa si su acc apesta o si pierde combo tontamente.

### 🎯 Plan de Acción
- Dale un consejo de coaching puro y duro sobre cómo arreglar su debilidad en {focus}.
- Añade una nota técnica exigiendo que juegue los **Mapas Recomendados** de arriba.
- Despídete con una sola frase cínica animándolo a mejorar.

[No uses roleplay ni asteriscos para acciones, solo habla directo]"""
        return prompt
    
async def setup(bot):
    """Función 'setup' vacía (este módulo no es un Cog)."""
    pass