"""
Módulo de Lógica de Análisis de osu! (v3.0)

Esta versión corrige el cálculo de 'acc promedio' (ignorando fails)
e introduce un análisis de beatmaps (BPM, AR, OD, CS) para
reducir el sesgo y dar recomendaciones más acertadas.
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
    """Analiza datos de osu! (v3.0) y genera prompts detallados para la IA."""

    def __init__(self, osu_api, user_data: dict, recent_plays: list = None, best_plays: list = None, user_focus: str = None):
        self.osu_api = osu_api
        self.user = user_data or {}
        self.recent = recent_plays or [] # Ahora 50
        self.best = best_plays or [] # Ahora 50
        self.mode = self.user.get("playmode", "osu")
        self.user_focus = user_focus
        
        self.stats = self.user.get("statistics", {})
        self.grades = self.stats.get("grade_counts", {})
        self.play_count = self.stats.get("play_count", 0)
        
        self.analysis_summary = {}

    def _analyze_playstyle(self) -> dict:
        """Analiza los 'best plays' para detectar el estilo de juego (mods dominantes)."""
        if not self.best:
            return {"detected_style": "Desconocido", "dominant_mods": ["NM"]}
            
        mods_list = [m for p in self.best for m in p.get("mods", [])]
        if not mods_list:
            mods_list = ["NM"]
            
        mods_counter = Counter(mods_list)
        dominant_mods = [m for m, _ in mods_counter.most_common(3)]
        
        style = "Híbrido"
        if mods_counter['DT'] > 5 or mods_counter['NC'] > 5: style = "Velocidad (DT/NC)"
        elif mods_counter['HR'] > 5: style = "Precisión (HR)"
        elif mods_counter['HD'] > 10: style = "Lectura (HD)"
        
        return {"detected_style": style, "dominant_mods": dominant_mods}

    def _analyze_pp_spread(self) -> dict:
        """Analiza la diferencia de PP entre los 'best plays'."""
        if len(self.best) < 10: # Necesitamos una buena muestra
            return {"spread_type": "Pocos Datos", "top_pp": 0, "50th_pp": 0}

        pp_values = sorted([p.get('pp', 0) for p in self.best if p.get('pp')], reverse=True)
        top_pp = pp_values[0]
        fiftieth_pp = pp_values[min(len(pp_values)-1, 49)] # Su 50º play
        
        spread_type = "Consistente"
        if top_pp > fiftieth_pp * 2: # Si el top play es el doble que el 50
            spread_type = "Farmer (Top-heavy)"
            
        return {"spread_type": spread_type, "top_pp": top_pp, "50th_pp": fiftieth_pp}

    def _analyze_trends(self) -> dict:
        """
        Analiza los 'recent plays' para detectar la consistencia del accuracy.
        
        (BUG ARREGLADO): Ahora solo incluye partidas con p.get('pass') == True.
        """
        # --- ¡FIX! Filtramos solo las partidas 'pass' (completadas) ---
        recent_accs = [
            p['accuracy'] * 100 for p in self.recent 
            if p.get('pass') == True and 'accuracy' in p
        ]
        
        if not recent_accs: 
            return {"trend": "Estable", "consistency": "Media", "avg_recent_acc": 0}
        
        avg_acc = statistics.mean(recent_accs)
        std_dev = statistics.pstdev(recent_accs) if len(recent_accs) > 1 else 0
        
        consistency = "Alta" if std_dev < 1.5 else "Media" if std_dev < 3.5 else "Baja (Inconsistente)"
        return {"trend": "Estable", "consistency": consistency, "avg_recent_acc": round(avg_acc, 2)}

    def _analyze_beatmap_stats(self) -> dict:
        """
        ¡NUEVO! Analiza las propiedades de los mapas en los 'best plays'.
        
        Esto nos dice si el jugador está sesgado a mapas de bajo AR, BPM, etc.
        """
        bp_stats = {'bpm': [], 'ar': [], 'od': [], 'cs': [], 'length': []}
        
        for p in self.best:
            bm = p.get('beatmap')
            if bm: # 'beatmap' es un objeto más pequeño dentro del 'score'
                # La API de 'best scores' no da BPM base, solo con mods.
                # 'beatmapset' (el objeto padre) no está en 'best_scores',
                # así que nos limitamos a lo que tenemos.
                # (Nota: la API de 'scores' es limitada, 'beatmap' no trae BPM)
                # (Obtenemos AR, OD, CS, Length de la dificultad del mapa jugado)
                bp_stats['ar'].append(bm.get('ar', 9.0))
                bp_stats['od'].append(bm.get('accuracy', 7.0)) # 'accuracy' es OD en el objeto beatmap
                bp_stats['cs'].append(bm.get('cs', 4.0))
                bp_stats['length'].append(bm.get('total_length', 180))

        if not bp_stats['ar']: # Si no hay datos, devolver default
            return {'avg_ar': 9.0, 'avg_od': 7.0, 'avg_cs': 4.0, 'avg_length': 180}

        return {
            'avg_ar': statistics.mean(bp_stats['ar']),
            'avg_od': statistics.mean(bp_stats['od']),
            'avg_cs': statistics.mean(bp_stats['cs']),
            'avg_length': statistics.mean(bp_stats['length']),
        }

    def _determine_focus(self, playstyle: dict, trends: dict, pp_spread: dict, beatmap_stats: dict) -> str:
        """
        MEJORADO: Determina el área de enfoque usando las estadísticas de mapas.
        """
        if self.user_focus and self.user_focus in FOCUS_KEYWORDS:
            return self.user_focus
        
        total_s_ranks = self.grades.get('s', 0) + self.grades.get('sh', 0)
        total_a_ranks = self.grades.get('a', 0)
        
        # Lógica de detección (ahora más inteligente)
        if trends.get("consistency") == "Baja (Inconsistente)":
            return "consistencia"
        
        if self.stats.get("hit_accuracy", 95) < 94 and beatmap_stats['avg_od'] > 8:
            return "precisión" # Falla en mapas de OD alto
            
        if beatmap_stats['avg_ar'] < 9.3 and playstyle.get("detected_style") != "Precisión (HR)":
            return "lectura" # Sesgado a mapas de AR bajo
        
        if pp_spread.get("spread_type") == "Farmer (Top-heavy)":
            return "consistencia" # Necesita más scores, no solo uno grande
            
        if total_a_ranks > total_s_ranks * 0.5: # Si tiene más del 50% de A's que S'
            return "precisión" # Demasiadas 'A', falta pulir
            
        if playstyle.get("detected_style") == "Velocidad (DT/NC)":
            return "stamina y control en velocidad"
            
        return "consistencia general" # Default

    async def _search_recommended_maps(self, focus: str) -> list:
        """Busca 5 mapas recomendados."""
        avg_stars = statistics.mean([p['beatmap']['difficulty_rating'] for p in self.best if 'beatmap' in p]) if self.best else 4.5
        
        # Ajustamos el rango de estrellas
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
                             "stars": round(bm.get("difficulty_rating", 0), 2), "url": f"https://osu.ppy.sh/beatmapsets/{m.get('id')}"})
            
            return random.sample(maps, k=min(5, len(maps))) # Pedimos 5 mapas
        except Exception as e:
            print(f"!!!!!! [OsuAnalyzer] Error en Map Search: {e}"); 
            return []

    def generate_ai_analysis(self) -> str:
        """
        MEJORADO: Genera un prompt para un análisis MÁS LARGO y con MÁS DATOS.
        """
        playstyle = self._analyze_playstyle()
        trends = self._analyze_trends()
        pp_spread = self._analyze_pp_spread()
        beatmap_stats = self._analyze_beatmap_stats()

        prompt = f"""
        **ROL:** Eres Dalet, una analista de osu! experta, sarcástica y brutalmente honesta.
        **TAREA:** Proporciona un análisis detallado del jugador. No seas breve. Quiero un análisis completo que llene la página.
        
        **DATOS DEL PERFIL:**
        - **Nombre:** {self.user.get("username")}
        - **PP Total:** {self.stats.get('pp', 0):.2f}
        - **Acc Global:** {self.stats.get('hit_accuracy', 0):.2f}%
        - **Grados (S/A):** {self.grades.get('s', 0) + self.grades.get('sh', 0)} S / {self.grades.get('a', 0)} A
        
        **DATOS DE ANÁLISIS (Top 50 Plays):**
        - **Estilo Detectado:** {playstyle['detected_style']} (Mods: {', '.join(playstyle['dominant_mods'])})
        - **Perfil de PP:** {pp_spread['spread_type']} (Top: {pp_spread['top_pp']:.0f}pp vs 50vo: {pp_spread['50th_pp']:.0f}pp)
        - **Análisis de Mapas:**
            - AR Promedio: {beatmap_stats['avg_ar']:.1f}
            - OD Promedio: {beatmap_stats['avg_od']:.1f}
            - CS Promedio: {beatmap_stats['avg_cs']:.1f}
            - Duración Promedio: {beatmap_stats['avg_length']:.0f}s
        
        **DATOS DE TENDENCIA (Últimas 50 Partidas Pasadas):**
        - **Consistencia Reciente:** {trends['consistency']}
        - **Acc Promedio Reciente:** {trends['avg_recent_acc']}% (¡Este es el dato corregido, sin fails!)
        
        **FORMATO OBLIGATORIO (SEPARA CADA SECCIÓN CLARAMENTE):**
        
        ### ✅ Fortalezas
        (Menciona 2-3 puntos fuertes claros basados en TODOS los datos. Ej: si su AR es alto, su lectura es buena. Si su OD es alto, su precisión es buena. Si 'dominant_mods' es HR, es bueno en precisión.)
        
        ### ⚠️ A Mejorar
        (Menciona 2-3 debilidades claras. Si es 'Farmer', su consistencia es baja. Si su AR promedio es bajo, está sesgado y debe mejorar su lectura. Si su Acc Reciente es baja, está jugando mapas muy difíciles.)
        
        ### 💡 Consejo Rápido de Dalet
        (Basado en las debilidades, da 1 o 2 consejos accionables y directos. Ej: "Tu AR promedio es 9.1. Deja de tenerle miedo a AR10." o "Tu perfil es 'Farmer'. Juega más mapas de tu rango para estabilizar tu habilidad.")
        
        ### 💬 Comentario Final
        (Una frase final, corta y sarcástica sobre su perfil.)
        """
        return prompt

    async def generate_coaching_prompt(self) -> str:
        """
        MEJORADO: Genera el prompt de coaching completo con MÁS DATOS.
        """
        stats = self.user.get("statistics", {})
        playstyle = self._analyze_playstyle()
        trends = self._analyze_trends()
        pp_spread = self._analyze_pp_spread()
        beatmap_stats = self._analyze_beatmap_stats()
        
        self.analysis_summary = {
            "username": self.user.get("username", "Desconocido"),
            "pp": round(stats.get("pp", 0), 2),
            "accuracy": round(stats.get("hit_accuracy", 0), 2),
        }

        focus = self._determine_focus(playstyle, trends, pp_spread, beatmap_stats)
        recommended_maps = await self._search_recommended_maps(focus) # Ahora trae 5
 
        maps_text = "\n".join([f"- Título: {m['title']}, Artista: {m['artist']}, Estrellas: {m['stars']:.2f}, URL: {m['url']}" for m in recommended_maps])
        if not recommended_maps:
            maps_text = "No se encontraron mapas específicos con la búsqueda automática."

        prompt = f"""
        **ROL Y OBJETIVO:** Eres Dalet, un coach de osu! de élite. Tu tono es sarcástico pero tus consejos son oro puro. Tu objetivo es crear un plan de entrenamiento CONCISO, COHERENTE y ACCIONABLE.

        **TAREA:** Crea un plan de coaching para el jugador, usando los datos y los mapas encontrados. Sigue el formato OBLIGATORIO.

        **DATOS DEL JUGADOR:**
        - **Nombre:** {self.analysis_summary['username']}
        - **Stats Clave:** {self.analysis_summary['pp']}pp, {self.analysis_summary['accuracy']}% acc
        - **Estilo Detectado:** {playstyle['detected_style']} (Mods: {', '.join(playstyle['dominant_mods'])})
        - **Perfil de PP:** {pp_spread['spread_type']}
        - **Análisis de Mapas (Top 50):** AR Promedio: {beatmap_stats['avg_ar']:.1f}, OD Promedio: {beatmap_stats['avg_od']:.1f}
        - **Tendencia Reciente:** Acc Promedio: {trends['avg_recent_acc']}% (Consistencia: {trends['consistency']})
        - **ÁREA DE ENFOQUE:** {focus.upper()}

        **MAPAS ENCONTRADOS (CON URL):**
        {maps_text}

        **FORMATO DE RESPESTA OBLIGATORIO Y REGLAS:**
        Usa viñetas y frases cortas. No te repitas.

        ### 🎯 Foco Principal: {focus.capitalize()}
        (Explica en UNA SOLA frase por qué este enfoque es crucial basado en los datos. Ej: "Tu AR promedio es 9.2, necesitas mejorar tu 'Lectura' con mapas más rápidos" o "Tu consistencia reciente es 'Baja', necesitas 'Consistencia' para dejar de fallar.")

        ### ✅ Fortalezas
        (Menciona 1-2 puntos fuertes claros. Sé breve).

        ### ⚠️ A Mejorar
        (Menciona 1-2 debilidades que NO sean el Foco Principal. Ej: "Tu dependencia de HD está ocultando tus problemas de lectura" o "Tu OD promedio es muy bajo").

        ### 🗺️ Plan de Acción y Mapas
        (Para cada mapa de la lista (deben ser 4 o 5), crea un enlace Markdown usando su URL y título, y añade la dificultad en estrellas. **Formato exacto:** `- [Título del Mapa](URL) ({'stars'}★)`.
        (Debajo de cada mapa, en una sub-viñeta, da un consejo técnico específico Y UNA RECOMENDACIÓN DE MOD. Ej: "Juega esto con Hidden para tu 'lectura'" o "Juega esto SIN MODS (NM) para enfocarte en el acc puro" o "Intenta esto con Hard Rock para practicar tu 'precisión'").
        (Si no hay mapas, recomienda 1-2 tipos de mapas a buscar manualmente).

        ### 💬 Comentario de Dalet
        (UNA frase final, sarcástica y motivadora).
        """
        return prompt
    
async def setup(bot):
    """Función 'setup' vacía (este módulo no es un Cog)."""
    pass