"""Módulo central de localización e internacionalización (i18n) para Dalet.

Define el catálogo bilingüe (en/es) y provee la función helper `t()` con
mecanismo de fallback seguro a inglés y formateo dinámico de variables.
"""

from typing import Any

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ("en", "es")

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # --- osu! cards ---
        "osu.recent_author": "Recent Play · {username} ({mode})",
        "osu.no_recent": "**{username}** has no recent plays in {mode}.",
        "osu.top_author": "osu! Profile for {username}",
        "osu.top_title": "Top Scores · {username} ({mode})",
        "osu.top_none": "No recorded plays found for this mode.",
        "osu.performance": "Performance",
        "osu.score_hits": "Score & Hits",
        "osu.score": "Score",
        "osu.hits": "Hits",
        "osu.misses": "Misses",
        "osu.map": "Beatmap",
        "osu.length": "Length",
        "osu.unranked": "Unranked",
        "osu.failed": "Failed",
        "osu.no_pp": "No PP",
        "osu.accuracy_level": "Accuracy & Level",
        "osu.accuracy": "Accuracy",
        "osu.level": "Level",
        "osu.activity": "Activity",
        "osu.plays": "Plays",
        "osu.play_time": "Play Time",
        "osu.grade_history": "Grade History",
        "osu.global_rank": "Global",
        "osu.country_rank": "Country ({code})",
        "osu.comparison_title": "osu! {mode} Comparison",
        "osu.leads_pp": "PP Leader: **{winner}** (`+{diff_pp:,.2f}pp`)",
        "osu.skills_overall": "Overall Rating",
        "osu.skills_strength": "Primary Strength",
        "osu.skills_weakness": "Weakest Area",
        "osu.skills_verdict": "Dalet's Verdict",
        "osu.skills_no_data": "Not enough play data.",

        # --- General Commands ---
        "general.latency_title": "Latency",
        "general.latency_desc": "My response takes about `{latency}ms`. Don't rush me.",
        "general.user_stats_fail": "Couldn't compute your social habits today.",
        "general.lore_empty": "No clue what '{query}' is. Either you made that up or it's too boring to archive.",
        "general.lore_busy": "Got too lazy to finish reading the logs. Ask me again.",
        "general.lore_error": "The archives are dusty and unreadable right now.",

        # --- Info & Changelog ---
        "info.title": "Dalet {version}",
        "info.tagline": "> *\"searching who asked\"*",
        "info.creator": "Creator",
        "info.status": "Status",
        "info.status_desc": "Online and judging your plays",
        "info.prefix": "Prefix",
        "info.prefix_desc": "`d.` or mention `@Dalet`",
        "info.changelog_hint": "Type `d.changelog` to view version updates.",
        "info.help_hint": "Type `d.help` to view the command list.",

        "changelog.title": "Updates — Dalet {version}",
        "changelog.brain_title": "Brain v3.0",
        "changelog.brain_desc": "• Faster conversational responsiveness and fluid context recall.\n• Cynical persona calibrated for direct, razor-sharp replies.",
        "changelog.skills_title": "Skill Breakdown (`d.skills`)",
        "changelog.skills_desc": "• Visual radar across 5 core skills (Aim, Speed, Accuracy, Stamina, Reading).\n• Real difficulty scaling with mod weighting (DT, HR, EZ, FL) and biting AI verdict.",
        "changelog.i18n_title": "Performance & Full Bilingual Support",
        "changelog.i18n_desc": "• Global response time optimizations across all servers.\n• Default English language for new servers with Spanish configurable via `d.language` / `/language`."
    },
    "es": {
        # --- osu! cards ---
        "osu.recent_author": "Jugada Reciente · {username} ({mode})",
        "osu.no_recent": "**{username}** no tiene jugadas recientes en {mode}.",
        "osu.top_author": "Perfil de osu! de {username}",
        "osu.top_title": "Top Scores · {username} ({mode})",
        "osu.top_none": "No se encontraron jugadas registradas en este modo.",
        "osu.performance": "Rendimiento",
        "osu.score_hits": "Puntuación & Hits",
        "osu.score": "Score",
        "osu.hits": "Hits",
        "osu.misses": "Misses",
        "osu.map": "Mapa",
        "osu.length": "Tiempo",
        "osu.unranked": "Sin rank",
        "osu.failed": "Fallido",
        "osu.no_pp": "Sin PP",
        "osu.accuracy_level": "Precisión & Nivel",
        "osu.accuracy": "Precisión",
        "osu.level": "Nivel",
        "osu.activity": "Actividad",
        "osu.plays": "Partidas",
        "osu.play_time": "Tiempo de juego",
        "osu.grade_history": "Récords Obtenidos",
        "osu.global_rank": "Global",
        "osu.country_rank": "País ({code})",
        "osu.comparison_title": "Comparación osu! {mode}",
        "osu.leads_pp": "Lidera en PP: **{winner}** (`+{diff_pp:,.2f}pp`)",
        "osu.skills_overall": "Promedio General",
        "osu.skills_strength": "Fuerza Principal",
        "osu.skills_weakness": "Área Débil",
        "osu.skills_verdict": "Veredicto de Dalet",
        "osu.skills_no_data": "Sin suficientes datos.",

        # --- General Commands ---
        "general.latency_title": "Latencia",
        "general.latency_desc": "Mi respuesta está tardando unos `{latency}ms`. No me presiones.",
        "general.user_stats_fail": "No pude calcular tus vicios sociales hoy.",
        "general.lore_empty": "Ni idea de qué es '{query}'. Ese lore te lo has inventado tú o es demasiado aburrido para que lo guarde.",
        "general.lore_busy": "Me dio pereza terminar de leer los archivos. Pregúntame otra vez.",
        "general.lore_error": "Se me han empolvado los archivos y no puedo leer nada ahora mismo.",

        # --- Info & Changelog ---
        "info.title": "Dalet {version}",
        "info.tagline": "> *\"searching who asked\"*",
        "info.creator": "Creador",
        "info.status": "Estado",
        "info.status_desc": "En línea y juzgando tus jugadas",
        "info.prefix": "Prefijo",
        "info.prefix_desc": "`d.` o mención `@Dalet`",
        "info.changelog_hint": "Escribe `d.changelog` para ver las novedades de la versión.",
        "info.help_hint": "Escribe `d.help` para consultar el menú de comandos.",

        "changelog.title": "Novedades — Dalet {version}",
        "changelog.brain_title": "Cerebro v3.0",
        "changelog.brain_desc": "• Mayor agilidad conversacional y fluidez de memoria.\n• Personalidad ácida calibrada para respuestas directas y contundentes.",
        "changelog.skills_title": "Desglose de Habilidades (`d.skills`)",
        "changelog.skills_desc": "• Evaluación visual en 5 áreas (Aim, Speed, Accuracy, Stamina, Reading).\n• Calibración de dificultad real en mods (DT, HR, EZ, FL) y veredicto mordaz.",
        "changelog.i18n_title": "Rendimiento e Internacionalización",
        "changelog.i18n_desc": "• Optimización de tiempos de respuesta en todos los servidores.\n• Soporte bilingüe completo (Inglés por defecto, Español configurable con `d.language`)."
    }
}


def t(key: str, lang: str = "en", **kwargs: Any) -> str:
    """Busca la traducción correspondiente a `key` en `lang`.
    
    Si `lang` no está soportado o la clave no existe en ese idioma,
    hace fallback automático al inglés ('en'). Si tampoco existe en 'en',
    devuelve la clave original. Si se pasan kwargs, formatea la cadena con ellos.
    """
    clean_lang = (lang or DEFAULT_LANGUAGE).lower().strip()
    if clean_lang not in SUPPORTED_LANGUAGES:
        clean_lang = DEFAULT_LANGUAGE

    text = STRINGS.get(clean_lang, {}).get(key)
    if text is None:
        text = STRINGS.get(DEFAULT_LANGUAGE, {}).get(key, key)

    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text

    return text
