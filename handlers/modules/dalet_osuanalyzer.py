"""
Módulo de Lógica de Análisis de osu! (v2.0)

Esta clase es el "cerebro" de los comandos 'osuAnalyze' y 'osuCoach'.
Toma los datos crudos de la API de osu! y los procesa para:
1. Analizar estilo, PP spread, grades y actividad reciente.
2. Determinar un área de enfoque inteligente.
3. Buscar 5 mapas recomendados.
4. Generar prompts de IA detallados para análisis y coaching.
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
    """Analiza datos de osu! y genera prompts detallados para la IA."""

    def __init__(self, osu_api, user_data: dict, recent_plays: list = None, best_plays: list = None, user_focus: str = None):
        self.osu_api = osu_api
        self.user = user_data or {}
        self.recent = recent_plays or []
        self.best = best_plays or []
        self.mode = self.user.get("playmode", "osu")
        self.user_focus = user_focus
        
        # --- NUEVAS ESTADÍSTICAS INVESTIGADAS ---
        self.stats = self.user.get("statistics", {})
        self.grades = self.stats.get("grade_counts", {})
        self.play_count = self.stats.get("play_count", 0)
        
        self.analysis_summary = {} # Se llenará después

    def _analyze_playstyle(self) -> dict:
        """Analiza los 'best plays' para detectar el estilo de juego (mods dominantes)."""
        if not self.best:
            return {"detected_style": "Desconocido", "dominant_mods": ["NM"]}
            
        mods_list = [m for p in self.best for m in p.get("mods", [])]
        if not mods_list:
            mods_list = ["NM"] # No Mod
            
        mods_counter = Counter(mods_list)
        dominant_mods = [m for m, _ in mods_counter.most_common(3)]
        
        style = "Híbrido"
        if mods_counter['DT'] > 2 or mods_counter['NC'] > 2: style = "Velocidad (DT/NC)"
        elif mods_counter['HR'] > 2: style = "Precisión (HR)"
        elif mods_counter['HD'] > 3: style = "Lectura (HD)"
        
        return {"detected_style": style, "dominant_mods": dominant_mods}

    def _analyze_pp_spread(self) -> dict:
        """
        NUEVO: Analiza la diferencia de PP entre los mejores 'best plays'.
        Detecta si el usuario es un 'farmer' de un solo score.
        """
        if len(self.best) < 5:
            return {"spread_type": "Pocos Datos", "top_pp": 0, "10th_pp": 0}

        pp_values = sorted([p.get('pp', 0) for p in self.best if p.get('pp')], reverse=True)
        top_pp = pp_values[0]
        tenth_pp = pp_values[min(len(pp_values)-1, 9)] # Su 10º play o el último si tiene menos de 10
        
        spread_type = "Consistente"
        if top_pp > tenth_pp * 1.5: # Si el top play es 50% más grande que el 10mo
            spread_type = "Farmer (Top-heavy)"
            
        return {"spread_type": spread_type, "top_pp": top_pp, "10th_pp": tenth_pp}

    def _analyze_trends(self) -> dict:
        """Analiza los 'recent plays' para detectar la consistencia del accuracy."""
        recent_accs = [p['accuracy'] * 100 for p in self.recent if 'accuracy' in p]
        if not recent_accs: return {"trend": "Estable", "consistency": "Media", "avg_recent_acc": 0}
        
        avg_acc = statistics.mean(recent_accs)
        std_dev = statistics.pstdev(recent_accs) if len(recent_accs) > 1 else 0
        
        consistency = "Alta" if std_dev < 1.5 else "Media" if std_dev < 3.5 else "Baja"
        return {"trend": "Estable", "consistency": consistency, "avg_recent_acc": round(avg_acc, 2)}

    def _determine_focus(self, playstyle: dict, trends: dict, pp_spread: dict) -> str:
        """
        MEJORADO: Determina el área de enfoque usando las nuevas estadísticas.
        """
        # 1. Prioridad: El focus que pidió el usuario
        if self.user_focus and self.user_focus in FOCUS_KEYWORDS:
            return self.user_focus
        
        # 2. Lógica de Detección Automática
        total_s_ranks = self.grades.get('s', 0) + self.grades.get('sh', 0)
        total_a_ranks = self.grades.get('a', 0)
        
        if self.stats.get("hit_accuracy", 95) < 94:
            return "precisión"
        if trends.get("consistency") == "Baja":
            return "consistencia"
        if pp_spread.get("spread_type") == "Farmer (Top-heavy)":
            return "consistencia" # Necesita más scores, no solo uno grande
        if total_a_ranks > total_s_ranks:
            return "precisión" # Demasiadas 'A', falta pulir
        if playstyle.get("detected_style") == "Velocidad (DT/NC)":
            return "stamina y control en velocidad"
        if playstyle.get("detected_style") == "Precisión (HR)":
            return "lectura y aim complejo"
            
        return "consistencia general" # Default

    async def _search_recommended_maps(self, focus: str) -> list:
        """
        MEJORADO: Busca 5 mapas recomendados en lugar de 3.
        """
        avg_stars = statistics.mean([p['beatmap']['difficulty_rating'] for p in self.best if 'beatmap' in p]) if self.best else 4.5
        star_ranges = {
            "precisión": (avg_stars - 0.3, avg_stars + 0.2), "consistencia": (avg_stars, avg_stars + 0.4),
            "stamina y control en velocidad": (avg_stars - 0.2, avg_stars + 0.3), "lectura y aim complejo": (avg_stars - 0.4, avg_stars + 0.1),
            "velocidad": (avg_stars - 0.2, avg_stars + 0.3), "lectura": (avg_stars - 0.4, avg_stars + 0.1),
            "stamina": (avg_stars, avg_stars + 0.5)
        }
        min_s, max_s = star_ranges.get(focus, (avg_stars - 0.1, avg_stars + 0.3))
        
        selected_keyword = random.choice(FOCUS_KEYWORDS.get(focus, ["osu"]))
        
        try:
            results = await self.osu_api.async_search_beatmaps(self.mode, min_s, max_s, keyword=selected_keyword)
            maps = []
            for m in results:
                bm = m.get("beatmaps", [{}])[0]
                maps.append({"title": m.get("title", "Desconocido"), "artist": m.get("artist", "Desconocido"),
                             "stars": round(bm.get("difficulty_rating", 0), 2), "url": f"https://osu.ppy.sh/beatmapsets/{m.get('id')}"})
            
            # --- CAMBIO IMPORTANTE: Pedimos 5 mapas ---
            return random.sample(maps, k=min(5, len(maps))) 
        except Exception as e:
            print(f"!!!!!! [OsuAnalyzer] Error en Map Search: {e}"); 
            return []

    def generate_ai_analysis(self) -> str:
        """
        MEJORADO: Genera un prompt para un análisis MÁS LARGO y detallado.
        Esto forzará el uso del paginador en 'd.osuAnalyze'.
        """
        playstyle = self._analyze_playstyle()
        trends = self._analyze_trends()
        pp_spread = self._analyze_pp_spread()

        prompt = f"""
        **ROL:** Eres Dalet, una analista de osu! experta, sarcástica y brutalmente honesta.
        **TAREA:** Proporciona un análisis detallado del jugador. No seas breve. Quiero un análisis completo que llene la página.
        
        **DATOS:**
        - **Nombre:** {self.user.get("username")}
        - **Estilo Detectado:** {playstyle['detected_style']} (Mods: {', '.join(playstyle['dominant_mods'])})
        - **Consistencia Reciente:** {trends['consistency']} (Acc Promedio: {trends['avg_recent_acc']}%)
        - **Perfil de PP:** {pp_spread['spread_type']} (Top: {pp_spread['top_pp']}pp vs 10mo: {pp_spread['10th_pp']}pp)
        - **Grados:** {self.grades.get('ss', 0) + self.grades.get('ssh', 0)} SS, {self.grades.get('s', 0) + self.grades.get('sh', 0)} S, {self.grades.get('a', 0)} A
        
        **FORMATO OBLIGATORIO (SEPARA CADA SECCIÓN CLARAMENTE):**
        
        ### ✅ Fortalezas
        (Menciona 2-3 puntos fuertes claros basados en los datos. Por ejemplo, si sus mods dominantes son HD, su lectura es buena. Si su consistencia es Alta, su control de aim es bueno.)
        
        ### ⚠️ A Mejorar
        (Menciona 2-3 debilidades claras. Si es 'Farmer', su consistencia es baja. Si tiene muchas 'A', su precisión falla al final. Si su 'avg_recent_acc' es baja, está jugando mapas muy difíciles.)
        
        ### 💡 Consejo Rápido de Dalet
        (Basado en las debilidades, da 1 o 2 consejos accionables y directos. Por ejemplo: "Deja de jugar mapas de 7 estrellas si tu acc promedio es 92%. Baja a 6 estrellas y saca 98%." o "Tu PP viene de un solo score. Juega más mapas de tu rango para estabilizar tu habilidad.")
        
        ### 💬 Comentario Final
        (Una frase final, corta y sarcástica sobre su perfil.)
        """
        return prompt

    async def generate_coaching_prompt(self) -> str:
        """
        MEJORADO: Genera el prompt de coaching completo.
        
        Ahora incluye más estadísticas y pide recomendaciones de MODS específicas.
        """
        stats = self.user.get("statistics", {})
        playstyle = self._analyze_playstyle()
        trends = self._analyze_trends()
        pp_spread = self._analyze_pp_spread()
        
        self.analysis_summary = {
            "username": self.user.get("username", "Desconocido"),
            "pp": round(stats.get("pp", 0), 2),
            "accuracy": round(stats.get("hit_accuracy", 0), 2),
        }

        focus = self._determine_focus(playstyle, trends, pp_spread)
        recommended_maps = await self._search_recommended_maps(focus) # Ahora trae 5
 
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
        - **Mods Dominantes:** {', '.join(playstyle['dominant_mods'])}
        - **Perfil de PP:** {pp_spread['spread_type']}
        - **Grados (S/A):** {self.grades.get('s', 0) + self.grades.get('sh', 0)} S / {self.grades.get('a', 0)} A
        - **ÁREA DE ENFOQUE:** {focus.upper()}

        **MAPAS ENCONTRADOS (CON URL):**
        {maps_text}

        **FORMATO DE RESPUESTA OBLIGATORIO Y REGLAS:**
        Usa viñetas y frases cortas. No te repitas.

        ### 🎯 Foco Principal: {focus.capitalize()}
        (Explica en UNA SOLA frase por qué este enfoque es crucial basado en los datos. Ej: "Tu perfil de PP es 'Farmer', así que necesitas 'Consistencia' para construir una base sólida.")

        ### ✅ Fortalezas
        (Menciona 1-2 puntos fuertes claros. Sé breve).

        ### ⚠️ A Mejorar
        (Menciona 1-2 debilidades que NO sean el Foco Principal. Ej: "Tu dependencia de HD está ocultando tus problemas de lectura de 'aim' simple" o "Tienes demasiadas 'A'").

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