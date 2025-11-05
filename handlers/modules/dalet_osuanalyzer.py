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
        """Determina el área de enfoque basado en HÁBITOS RECIENTES."""
        if self.user_focus and self.user_focus in FOCUS_KEYWORDS:
            return self.user_focus
        
        if trends.get("consistency") == "Baja (Inconsistente)":
            return "consistencia"
        
        avg_acc = trends.get("avg_recent_acc")
        if avg_acc is not None and avg_acc < 96 and recent_beatmap_stats['avg_od'] > 8:
            return "precisión"
            
        if recent_beatmap_stats['avg_ar'] < 9.3:
            return "lectura"
        
        if pp_spread.get("spread_type") == "Farmer (Top-heavy)":
            return "consistencia"
            
        total_s_ranks = self.grades.get('s', 0) + self.grades.get('sh', 0)
        total_a_ranks = self.grades.get('a', 0)
        if total_a_ranks > total_s_ranks * 0.5:
            return "precisión"
            
        return "consistencia general"

    async def _search_recommended_maps(self, focus: str) -> list:
        """Busca 5 mapas recomendados (sin cambios v3.0)."""
        avg_stars = statistics.mean([p['beatmap']['difficulty_rating'] for p in self.best if 'beatmap' in p]) if self.best else 4.5
        
        min_s = avg_stars - 0.4
        max_s = avg_stars + 0.3
        
        if focus == "consistencia":
            min_s = avg_stars
            max_s = avg_stars + 0.5
        
        selected_keyword = random.choice(FOCUS_KEYWORDS.get(focus, ["osu"]))
        
        try:
            results = await self.osu_api.async_search_beatmaps(self.mode, min_s, max_s, keyword=selected_keyword)
            maps = []
            for m in results:
                bm = m.get("beatmaps", [{}])[0]
                maps.append({"title": m.get("title", "Desconocido"), "artist": m.get("artist", "Desconocido"),
                             "stars": round(bm.get("difficulty_rating", 0), 2), "url": f"https://osu_ppy_sh/beatmapsets/{m.get('id')}"})
            
            return random.sample(maps, k=min(5, len(maps)))
        except Exception as e:
            print(f"!!!!!! [OsuAnalyzer] Error en Map Search: {e}"); 
            return []

    # --- GENERADORES DE PROMPTS (v4.1) ---

    def generate_ai_analysis(self) -> str:
        """
        MEJORADO: El prompt ahora incluye la COMPARACIÓN y maneja el 'None' del acc.
        """
        # 1. Analizar Best Plays
        best_playstyle = self._analyze_best_playstyle()
        pp_spread = self._analyze_pp_spread()
        best_beatmap_stats = self._analyze_best_beatmap_stats()
        
        # 2. Analizar Recent Plays
        trends = self._analyze_trends()
        recent_playstyle = self._analyze_recent_playstyle()
        recent_beatmap_stats = self._analyze_recent_beatmap_stats()
        
        # --- ¡FIX v4.1! Manejar el None ---
        if trends['avg_recent_acc'] is not None:
            trends_text = f"""
            - **Acc Promedio Reciente:** {trends['avg_recent_acc']}% (¡Corregido!)
            - **Consistencia Reciente:** {trends['consistency']}
            """
        else:
            trends_text = """
            - **Acc Promedio Reciente:** N/A (No se encontraron partidas completadas en las últimas 50)
            - **Consistencia Reciente:** Baja (Inconsistente)
            """

        prompt = f"""
        **ROL:** Eres Dalet, una analista de osu! experta, sarcástica y brutalmente honesta.
        **TAREA:** Proporciona un análisis detallado comparando el historial (Top 50) vs. los hábitos (Recent 50).
        
        **DATOS DEL PERFIL:**
        - **Nombre:** {self.user.get("username")}
        - **PP Total:** {self.stats.get('pp', 0):.2f}
        - **Acc Global:** {self.stats.get('hit_accuracy', 0):.2f}%
        
        **ANÁLISIS DE POTENCIAL (Top 50 Plays):**
        - **Estilo Histórico:** {best_playstyle['detected_style']} (Mods: {', '.join(best_playstyle['dominant_mods'])})
        - **Perfil de PP:** {pp_spread['spread_type']} (Top: {pp_spread['top_pp']:.0f}pp vs 50vo: {pp_spread['50th_pp']:.0f}pp)
        - **Stats de Mapas (Top):** AR {best_beatmap_stats['avg_ar']:.1f}, OD {best_beatmap_stats['avg_od']:.1f}
        
        **ANÁLISIS DE HÁBITOS (Últimas 50 Partidas Pasadas):**
        - **Estilo Reciente:** {recent_playstyle['detected_style']} (Mods: {', '.join(recent_playstyle['dominant_mods'])})
        {trends_text}
        - **Stats de Mapas (Reciente):** AR {recent_beatmap_stats['avg_ar']:.1f}, OD {recent_beatmap_stats['avg_od']:.1f}
        
        **FORMATO OBLIGATORIO (SEPARA CADA SECCIÓN CLARAMENTE):**
        
        ### 🧠 Análisis (Potencial vs. Hábito)
        (Aquí está la clave. Compara ambos análisis. Ej: "Veo que tus mejores plays son de DT, pero recientemente no juegas DT para nada. Parece que estás cambiando tu estilo..." o "Tu potencial está en HR, pero tu acc reciente es N/A, lo que significa que estás fallando todo.")
        
        ### ✅ Fortalezas
        (Menciona 2-3 puntos fuertes claros basados en TODOS los datos.)
        
        ### ⚠️ A Mejorar
        (Menciona 2-3 debilidades claras. Si su AR reciente es bajo, está sesgado. Si su Acc Reciente es N/A, está jugando mapas muy difíciles o reiniciando mucho.)
        
        ### 💡 Consejo Rápido de Dalet
        (Basado en la comparación. Ej: "Ya demostraste que puedes jugar DT. Ahora aplica esa velocidad a mapas de 'stamina' (NM) para balancear tu perfil." o "Tu AR promedio reciente es 9.1. Deja de tenerle miedo a AR10.")
        
        ### 💬 Comentario Final
        (Una frase final, corta y sarcástica sobre su perfil.)
        """
        return prompt

    async def generate_coaching_prompt(self) -> str:
        """
        MEJORADO: El prompt de coaching ahora también se basa en la comparación
        y maneja el 'None' del acc.
        """
        # 1. Analizar Best Plays
        best_playstyle = self._analyze_best_playstyle()
        pp_spread = self._analyze_pp_spread()
        best_beatmap_stats = self._analyze_best_beatmap_stats()
        
        # 2. Analizar Recent Plays
        trends = self._analyze_trends()
        recent_playstyle = self._analyze_recent_playstyle()
        recent_beatmap_stats = self._analyze_recent_beatmap_stats()
        
        self.analysis_summary = {
            "username": self.user.get("username", "Desconocido"),
            "pp": round(self.stats.get("pp", 0), 2),
            "accuracy": round(self.stats.get("hit_accuracy", 0), 2),
        }

        # 3. Determinar Foco (basado en 'recents' y 'trends')
        focus = self._determine_focus(trends, pp_spread, recent_beatmap_stats)
        recommended_maps = await self._search_recommended_maps(focus)
 
        maps_text = "\n".join([f"- Título: {m['title']}, Artista: {m['artist']}, Estrellas: {m['stars']:.2f}, URL: {m['url']}" for m in recommended_maps])
        if not recommended_maps:
            maps_text = "No se encontraron mapas específicos con la búsqueda automática."

        # --- ¡FIX v4.1! Manejar el None ---
        if trends['avg_recent_acc'] is not None:
            trends_text = f"- **Tendencia Reciente:** Acc Promedio: {trends['avg_recent_acc']}% (Consistencia: {trends['consistency']})"
        else:
            trends_text = f"- **Tendencia Reciente:** N/A (No hay partidas completadas recientemente. Consistencia: Baja)"
        
        prompt = f"""
        **ROL Y OBJETIVO:** Eres Dalet, un coach de osu! de élite. Tu tono es sarcástico pero tus consejos son oro puro.
        **TAREA:** Crea un plan de coaching para el jugador, usando los datos y los mapas encontrados. Sigue el formato OBLIGATORIO.

        **DATOS DEL JUGADOR:**
        - **Nombre:** {self.analysis_summary['username']}
        - **Stats Clave:** {self.analysis_summary['pp']}pp, {self.analysis_summary['accuracy']}% acc
        - **Estilo Histórico (Top 50):** {best_playstyle['detected_style']} (Mods: {', '.join(best_playstyle['dominant_mods'])})
        - **Estilo Reciente (Últimos 50):** {recent_playstyle['detected_style']} (Mods: {', '.join(recent_playstyle['dominant_mods'])})
        {trends_text}
        - **Análisis de Mapas (Reciente):** AR Promedio: {recent_beatmap_stats['avg_ar']:.1f}, OD Promedio: {recent_beatmap_stats['avg_od']:.1f}
        - **ÁREA DE ENFOQUE (Deducida):** {focus.upper()}

        **MAPAS ENCONTRADOS (CON URL):**
        {maps_text}

        **FORMATO DE RESPUESTA OBLIGATORIO Y REGLAS:**
        Usa viñetas y frases cortas. No te repitas.

        ### 🎯 Foco Principal: {focus.capitalize()}
        (Explica en UNA SOLA frase por qué este enfoque es crucial. Ej: "Tu AR promedio reciente es 9.2, necesitas mejorar tu 'Lectura' con mapas más rápidos" o "Tu acc reciente es N/A, lo que significa que estás fallando todo. Enfócate en 'Consistencia' y completa mapas.")

        ### 💡 Observación Clave (Potencial vs. Hábito)
        (Compara su 'Estilo Histórico' con su 'Estilo Reciente'. Ej: "Tus mejores plays son DT, pero ya no lo juegas. Si quieres subir PP, vuelve a practicar velocidad, o si no, enfócate en tu nuevo estilo de NM".)

        ### ⚠️ A Mejorar
        (Menciona 1-2 debilidades que NO sean el Foco Principal.)

        ### 🗺️ Plan de Acción y Mapas
        (Para cada mapa de la lista (deben ser 4 o 5), crea un enlace Markdown. **Formato exacto:** `- [Título del Mapa](URL) ({'stars'}★)`.
        (Debajo de cada mapa, en una sub-viñeta, da un consejo técnico específico Y UNA RECOMENDACIÓN DE MOD. Ej: "Juega esto con Hidden para tu 'lectura'" o "Juega esto SIN MODS (NM) para enfocarte en el acc puro").
        (Si no hay mapas, recomienda 1-2 tipos de mapas a buscar manualmente).

        ### 💬 Comentario de Dalet
        (UNA frase final, sarcástica y motivadora).
        """
        return prompt
    
async def setup(bot):
    """Función 'setup' vacía (este módulo no es un Cog)."""
    pass