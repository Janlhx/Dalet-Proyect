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
        "osu.skills_no_qualifying": "No qualified maps found in top plays.",
        "osu.tier_unranked": "Unranked",
        "osu.tier_elite": "Elite",
        "osu.tier_master": "Master",
        "osu.tier_advanced": "Advanced",
        "osu.tier_competent": "Competent",
        "osu.tier_novice": "Novice",
        "osu.weighted_pp": "Weighted PP",
        "osu.raw_pp": "Raw PP",
        "osu.plays_analyzed": "Analyzed Plays",

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
        "info.feedback_hint": "Type `/feedback` to send suggestions or report bugs.",

        "changelog.title": "Updates — Dalet {version}",
        "changelog.brain_title": "Brain v3.0",
        "changelog.brain_desc": "• Faster conversational responsiveness and fluid context recall.\n• Cynical persona calibrated for direct, razor-sharp replies.",
        "changelog.skills_title": "Skill Breakdown (`d.skills`)",
        "changelog.skills_desc": "• Visual radar across 5 core skills (Aim, Speed, Accuracy, Stamina, Reading).\n• Real difficulty scaling with mod weighting (DT, HR, EZ, FL) and biting AI verdict.",
        "changelog.i18n_title": "Performance & Full Bilingual Support",
        "changelog.i18n_desc": "• Global response time optimizations across all servers.\n• Default English language for new servers with Spanish configurable via `d.language` / `/language`.",

        # --- Stats ---
        "stats.title": "Social Activity · {username}",
        "stats.desc": "Activity summary recorded in database.",
        "stats.messages": "Messages",
        "stats.active_days": "Active Days",
        "stats.chars_per_msg": "Chars/Msg",

        # --- Userinfo ---
        "userinfo.title": "Record: {username}",
        "userinfo.id": "ID",
        "userinfo.created": "Account created",
        "userinfo.joined": "Joined server",

        # --- Serverinfo ---
        "serverinfo.title": "Server Territory: {name}",
        "serverinfo.members": "Members",
        "serverinfo.owner": "Owner",
        "serverinfo.created": "Founded",

        # --- Rank ---
        "rank.title": "Server osu! Leaderboard",
        "rank.empty": "No one in this server has linked their osu! account yet. Use `/link` to join the leaderboard.",
        "rank.error": "⚠️ Error fetching the leaderboard.",

        # --- Feedback ---
        "feedback.success": "✅ Thank you for your feedback! It has been sent directly to the developer.",
        "feedback.error": "❌ Could not send your feedback. Please try again later.",
        "feedback.dm_title": "📬 New Feedback Received",
        "feedback.author": "Author",
        "feedback.server": "Server",
        "feedback.channel": "Channel",
        "feedback.dm_alert": "🔔 {mention}, you received a new feedback submission!",

        # --- Admin ---
        "admin.lock_success": "🔒 Channel {channel} locked. Dalet commands are now disabled here.",
        "admin.lock_error": "❌ Error locking channel.",
        "admin.unlock_success": "🔓 Channel {channel} unlocked.",
        "admin.unlock_error": "❌ Error unlocking channel.",
        "admin.proactive_status": "Proactive mode **{status}** in {channel}.",
        "admin.reactive_status": "Reactive mode **{status}** in this server.",
        "admin.enabled": "enabled ✅",
        "admin.disabled": "disabled 🛑",
        "admin.setwelcome_success": "✅ Welcome channel set to {channel}.",
        "admin.setwelcome_error": "❌ Error configuring welcome channel.",
        "admin.removewelcome_success": "🗑️ Welcome channel removed. Greetings are now disabled.",
        "admin.removewelcome_error": "❌ Error removing welcome channel.",
        "admin.setname_success": "✅ My nickname in this server is now **{name}**.",
        "admin.setname_error": "❌ Error changing nickname.",
        "admin.name_too_long": "❌ Nickname cannot exceed 32 characters."
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
        "osu.skills_no_qualifying": "Sin mapas representativos en el top.",
        "osu.tier_unranked": "Sin calibrar",
        "osu.tier_elite": "Élite",
        "osu.tier_master": "Maestro",
        "osu.tier_advanced": "Avanzado",
        "osu.tier_competent": "Competente",
        "osu.tier_novice": "Aprendiz",
        "osu.weighted_pp": "PP Ponderado",
        "osu.raw_pp": "PP Real",
        "osu.plays_analyzed": "Jugadas Analizadas",

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
        "info.feedback_hint": "Escribe `/feedback` para enviar sugerencias o reportar errores.",

        "changelog.title": "Novedades — Dalet {version}",
        "changelog.brain_title": "Cerebro v3.0",
        "changelog.brain_desc": "• Mayor agilidad conversacional y fluidez de memoria.\n• Personalidad ácida calibrada para respuestas directas y contundentes.",
        "changelog.skills_title": "Desglose de Habilidades (`d.skills`)",
        "changelog.skills_desc": "• Evaluación visual en 5 áreas (Aim, Speed, Accuracy, Stamina, Reading).\n• Calibración de dificultad real en mods (DT, HR, EZ, FL) y veredicto mordaz.",
        "changelog.i18n_title": "Rendimiento e Internacionalización",
        "changelog.i18n_desc": "• Optimización de tiempos de respuesta en todos los servidores.\n• Soporte bilingüe completo (Inglés por defecto, Español configurable con `d.language`).",

        # --- Stats ---
        "stats.title": "Actividad Social · {username}",
        "stats.desc": "Resumen de actividad registrada en mis bases de datos.",
        "stats.messages": "Mensajes",
        "stats.active_days": "Días Activo",
        "stats.chars_per_msg": "Letras/Msg",

        # --- Userinfo ---
        "userinfo.title": "Expediente: {username}",
        "userinfo.id": "ID",
        "userinfo.created": "Cuenta creada",
        "userinfo.joined": "Se unió al grupo",

        # --- Serverinfo ---
        "serverinfo.title": "Territorio: {name}",
        "serverinfo.members": "Miembros",
        "serverinfo.owner": "Propietario",
        "serverinfo.created": "Fundación",

        # --- Rank ---
        "rank.title": "Ranking osu! del Servidor",
        "rank.empty": "Nadie en este servidor tiene cuenta vinculada aún. Usa `/link` para entrar al ranking.",
        "rank.error": "⚠️ Error obteniendo el ranking.",

        # --- Feedback ---
        "feedback.success": "✅ ¡Muchas gracias por tu feedback! Ha sido enviado directamente al desarrollador.",
        "feedback.error": "❌ No se pudo enviar tu feedback. Inténtalo de nuevo más tarde.",
        "feedback.dm_title": "📬 Nuevo Feedback Recibido",
        "feedback.author": "Autor",
        "feedback.server": "Servidor",
        "feedback.channel": "Canal",
        "feedback.dm_alert": "🔔 {mention}, ¡has recibido un nuevo mensaje de feedback!",

        # --- Admin ---
        "admin.lock_success": "🔒 Canal {channel} bloqueado. Los comandos de Dalet están desactivados.",
        "admin.lock_error": "❌ Error al bloquear el canal.",
        "admin.unlock_success": "🔓 Canal {channel} desbloqueado.",
        "admin.unlock_error": "❌ Error al desbloquear el canal.",
        "admin.proactive_status": "Modo proactivo **{status}** en {channel}.",
        "admin.reactive_status": "Modo reactivo **{status}** en este servidor.",
        "admin.enabled": "activado ✅",
        "admin.disabled": "desactivado 🛑",
        "admin.setwelcome_success": "✅ Canal de bienvenida establecido en {channel}.",
        "admin.setwelcome_error": "❌ Error al configurar el canal de bienvenida.",
        "admin.removewelcome_success": "🗑️ Canal de bienvenida eliminado. Ya no se enviarán bienvenidas.",
        "admin.removewelcome_error": "❌ Error al eliminar el canal de bienvenida.",
        "admin.setname_success": "✅ Ahora me llamo **{name}** en este servidor.",
        "admin.setname_error": "❌ Error al cambiar el nombre.",
        "admin.name_too_long": "❌ El nombre no puede superar los 32 caracteres."
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
