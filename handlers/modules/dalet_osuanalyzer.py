from collections import Counter
import statistics
import random

# --- Diccionario de Palabras Clave por Enfoque ---
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
    """Analiza datos de osu! y genera un prompt de coaching completo para la IA."""

    def __init__(self, osu_api, user_data: dict, recent_plays: list = None, best_plays: list = None, user_focus: str = None):
        self.osu_api = osu_api
        self.user = user_data or {}
        self.recent = recent_plays or []
        self.best = best_plays or []
        self.mode = self.user.get("playmode", "osu")
        self.user_focus = user_focus
        self.analysis_summary = {}

    def _analyze_playstyle(self) -> dict:
        mods = Counter(m for p in self.best for m in p.get("mods", []))
        style = "Híbrido"
        if mods['DT'] > 2 or mods['NC'] > 2: style = "Velocidad"
        elif mods['HR'] > 2: style = "Precisión"
        elif mods['HD'] > 3: style = "Lectura"
        return {"detected_style": style, "dominant_mods": [m for m, _ in mods.most_common(3)]}

    def _analyze_trends(self) -> dict:
        recent_accs = [p['accuracy'] * 100 for p in self.recent if 'accuracy' in p]
        if not recent_accs: return {"trend": "Estable", "consistency": "Media"}
        avg_acc = statistics.mean(recent_accs)
        std_dev = statistics.pstdev(recent_accs) if len(recent_accs) > 1 else 0
        consistency = "Alta" if std_dev < 1.5 else "Media" if std_dev < 3.5 else "Baja"
        return {"trend": "Estable", "consistency": consistency, "avg_recent_acc": round(avg_acc, 2)}

    def _determine_focus(self, playstyle: dict, trends: dict) -> str:
        if self.user_focus and self.user_focus in ["precisión", "consistencia", "velocidad", "lectura", "stamina"]:
            return self.user_focus
        stats = self.user.get("statistics", {})
        if stats.get("hit_accuracy", 95) < 94: return "precisión"
        if trends.get("consistency") == "Baja": return "consistencia"
        if playstyle.get("detected_style") == "Velocidad": return "stamina y control en velocidad"
        if playstyle.get("detected_style") == "Precisión": return "lectura y aim complejo"
        return "consistencia general"

    async def _search_recommended_maps(self, focus: str) -> list:
        avg_stars = statistics.mean([p['beatmap']['difficulty_rating'] for p in self.best if 'beatmap' in p]) if self.best else 4.5
        star_ranges = {
            "precisión": (avg_stars - 0.3, avg_stars + 0.2), "consistencia": (avg_stars, avg_stars + 0.4),
            "stamina y control en velocidad": (avg_stars - 0.2, avg_stars + 0.3), "lectura y aim complejo": (avg_stars - 0.4, avg_stars + 0.1),
            "velocidad": (avg_stars - 0.2, avg_stars + 0.3), "lectura": (avg_stars - 0.4, avg_stars + 0.1),
            "stamina": (avg_stars, avg_stars + 0.5)
        }
        min_s, max_s = star_ranges.get(focus, (avg_stars - 0.1, avg_stars + 0.3))
        
        # --- CORRECCIÓN 1: Pasar la palabra clave a la API ---
        keyword_options = FOCUS_KEYWORDS.get(focus, ["osu"])
        selected_keyword = random.choice(keyword_options)
        
        try:
            results = await self.osu_api.async_search_beatmaps(self.mode, min_s, max_s, keyword=selected_keyword)
            maps = []
            for m in results:
                bm = m.get("beatmaps", [{}])[0]
                maps.append({"title": m.get("title", "Desconocido"), "artist": m.get("artist", "Desconocido"),
                             "stars": round(bm.get("difficulty_rating", 0), 2), "url": f"https://osu.ppy.sh/beatmapsets/{m.get('id')}"})
            return random.sample(maps, k=min(3, len(maps)))
        except Exception as e:
            print(f"[Map Search] Error: {e}"); return []

    def generate_ai_analysis(self) -> str:
        """Genera un prompt para un análisis general (fortalezas/debilidades)."""
        playstyle = self._analyze_playstyle()
        trends = self._analyze_trends()
        prompt = f"""
        **ROL:** Eres Dalet, una analista de osu! sarcástica y directa.
        **TAREA:** Proporciona un análisis rápido de fortalezas y debilidades basado en los datos.
        
        **DATOS:**
        - **Nombre:** {self.user.get("username")}
        - **Estilo:** {playstyle['detected_style']}
        - **Consistencia Reciente:** {trends['consistency']}
        
        **FORMATO OBLIGATORIO:**
        ### ✅ Fortalezas
        (Menciona 1-2 puntos fuertes claros).
        ### ⚠️ A Mejorar
        (Menciona 1-2 debilidades claras).
        ### 💬 Comentario de Dalet
        (Una frase final, corta y sarcástica).
        """
        return prompt

    async def generate_coaching_prompt(self) -> str:
        """El método principal que consolida todo y genera el prompt final."""
        stats = self.user.get("statistics", {})
        playstyle = self._analyze_playstyle()
        trends = self._analyze_trends()
        
        # --- CORRECCIÓN 2: Poblar el resumen ANTES de usarlo ---
        self.analysis_summary = {
            "username": self.user.get("username", "Desconocido"),
            "pp": round(stats.get("pp", 0), 2),
            "accuracy": round(stats.get("hit_accuracy", 0), 2),
        }

        focus = self._determine_focus(playstyle, trends)
        recommended_maps = await self._search_recommended_maps(focus)
 
        maps_text = "\n".join([f"- Título: {m['title']}, Artista: {m['artist']}, Estrellas: {m['stars']}, URL: {m['url']}" for m in recommended_maps])
        if not recommended_maps:
            maps_text = "No se encontraron mapas específicos con la búsqueda automática."

        prompt = f"""
        **ROL Y OBJETIVO:** Eres Dalet, un coach de osu! de élite. Tu tono es sarcástico pero tus consejos son oro puro. Tu objetivo es crear un plan de entrenamiento CONCISO, COHERENTE y ACCIONABLE.

        **TAREA:** Crea un plan de coaching para el jugador, usando los datos y los mapas encontrados. Sigue el formato OBLIGATORIO.

        **DATOS DEL JUGADOR:**
        - **Nombre:** {self.analysis_summary['username']}
        - **Stats Clave:** {self.analysis_summary['pp']}pp, {self.analysis_summary['accuracy']}% acc
        - **Estilo Detectado:** {playstyle['detected_style']}
        - **ÁREA DE ENFOQUE:** {focus.upper()}

        **MAPAS ENCONTRADOS (CON URL):**
        {maps_text}

        **FORMATO DE RESPUESTA OBLIGATORIO Y REGLAS:**
        Usa viñetas y frases cortas. No te repitas.

        ### 🎯 Foco Principal: {focus.capitalize()}
        (Explica en UNA SOLA frase por qué este enfoque es crucial).

        ### ✅ Fortalezas
        (Menciona 1-2 puntos fuertes claros. Sé breve).

        ### ⚠️ A Mejorar
        (Menciona 1-2 debilidades que NO sean el Foco Principal).

        ### 🗺️ Plan de Acción y Mapas
        (Para cada mapa de la lista, crea un enlace Markdown usando su URL y título, y añade la dificultad en estrellas. **Formato exacto:** `- [Título del Mapa](URL) ({'stars'}★)`.
        (Debajo de cada mapa, en una sub-viñeta, da un consejo técnico específico y sugiere si se debe jugar con algún MOD como `HD` o `HR`).
        (Si no hay mapas, recomienda 1-2 tipos de mapas a buscar manualmente, ej: "Busca mapas de 'streams' de 5.5★").

        ### 💬 Comentario de Dalet
        (UNA frase final, sarcástica y motivadora).
        """
        return prompt
    
async def setup(bot):
    pass