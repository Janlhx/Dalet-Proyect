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
        "osu.recent_best_author": "Recent Best (24h) · {username} ({mode})",
        "osu.recent_pass_author": "Recent Pass · {username} ({mode})",
        "osu.no_recent": "**{username}** has no recent plays in {mode}.",
        "osu.no_recent_filtered": "**{username}** has no recent plays matching that filter in {mode}.",
        "osu.top_author": "osu! Profile for {username}",
        "osu.top_title": "Top Scores · {username} ({mode})",
        "osu.top_none": "No recorded plays found for this mode.",
        "osu.top_none_filtered": "**{username}** has no top plays matching that filter in {mode}.",
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
        "osu.compare_h2h_title": "Head-to-Head · {u1} vs {u2}",
        "osu.compare_score_lead": "**{winner}** leads **{wins1} - {wins2}** ({mode})",
        "osu.compare_score_tie": "Even match **{wins1} - {wins2}** ({mode})",
        "osu.compare_skills_title": "Skill Breakdown",
        "osu.compare_consistency_title": "Activity & Consistency",
        "osu.compare_need_link": "To compare against yourself, link your account with `/link <user>` or specify two players.",
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
        "osu.top_header": "Top 5 Scores",
        "osu.top_recent_header": "Recent Best (Top 5)",
        "osu.top_acc_header": "Highest Accuracy (Top 5)",
        "osu.chart_rank": "Play rank",
        "osu.chart_title": "PP Distribution — {username}",
        "osu.chart_summary": "Top 1: {top1:.0f}pp  │  Median: {median:.0f}pp  │  Top {last_idx}: {min_pp:.0f}pp  │  Δ: {delta:.0f}pp",
        "osu.profile_author": "osu! Profile · {username} ({mode})",
        "osu.peak_rank": "Peak Rank",
        "osu.ranked_score": "Ranked Score",
        "osu.max_combo": "Max Combo",
        "osu.progress_title": "PP Progress — {username} ({mode})",
        "osu.progress_summary": "Progress Summary",
        "osu.progress_current_pp": "Current PP",
        "osu.progress_change": "Total Change",
        "osu.progress_snapshots": "Snapshots",
        "osu.progress_need_snapshots": "Need at least 2 snapshots to plot progress. Check your profile regularly to record history.",
        "osu.firsts_title": "Global #1 Scores · {username} ({mode})",
        "osu.firsts_none": "**{username}** has no global #1 scores in {mode}.",
        "osu.map_not_found": "✕ Couldn't find a matching beatmap.",
        "osu.map_no_recent": "✕ Provide a beatmap link/ID or play/search one in this channel first.",
        "osu.map_mapper": "Mapper",
        "osu.map_status": "Status",
        "osu.map_objects": "Objects",
        "osu.map_pp_table": "PP Simulation (NM / Active Mods)",
        "osu.map_difficulty": "Difficulty & Rhythm",
        "osu.map_compare_author": "Scores on Beatmap · {username} ({mode})",
        "osu.map_compare_none": "No recorded scores found for **{username}** on this beatmap.",
        "osu.map_compare_none_filtered": "No scores matching `+{mods}` found for **{username}** on this beatmap (other mod combinations exist).",

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
        "info.changelog_hint": "Type `/changelog` or `d.changelog` to view version updates.",
        "info.help_hint": "Type `/help` or `d.help` to view the command list.",
        "info.feedback_hint": "Type `/feedback` to send suggestions or report bugs.",

        "changelog.title": "Updates — Dalet {version}",
        "changelog.milestone_title": "Milestone v3.1: Modular Auto-Moderation & Cognitive Memory",
        "changelog.milestone_desc": "• **Auto-Moderation Suite**: Gemini Vision multimodal image scanning, in-memory anti-flood, adult link & phishing heuristics, and granular channel exemptions (`/mod ignore`).\n• **Reflective Cognitive Memory**: Asynchronously infers user traits (`DaletThought`) to build natural, ongoing familiarity without robotic recitation.\n• **Dynamic Semantic Versioning**: Automated git commit release notes and real-time patch tracking (`/changelog`).",
        "changelog.skills_title": "5-Dimension Skill Analytics (`/skills`)",
        "changelog.skills_desc": "• Algorithmic radar across Aim, Speed, Accuracy, Stamina, and Reading with mod re-weighting and Dalet's biting AI verdict.",
        "changelog.i18n_title": "Multi-LLM Load Balancing & Full i18n",
        "changelog.i18n_desc": "• Smart routing across DeepSeek V3, Gemini 3.8 Flash, Groq (<200ms) with circuit breakers.\n• Native English default for new guilds, with Spanish configurable via `/language`.",

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
        "rank.error": "✕ Error fetching the leaderboard.",

        # --- Feedback ---
        "feedback.success": "✓ Thank you for your feedback! It has been sent directly to the developer.",
        "feedback.error": "✕ Could not send your feedback. Please try again later.",
        "feedback.dm_title": "✦ New Feedback Received",
        "feedback.author": "Author",
        "feedback.server": "Server",
        "feedback.channel": "Channel",
        "feedback.dm_alert": "▸ {mention}, you received a new feedback submission!",

        # --- Admin ---
        "admin.lock_success": "✓ Channel {channel} locked. Dalet commands are now disabled here.",
        "admin.lock_error": "✕ Error locking channel.",
        "admin.unlock_success": "✓ Channel {channel} unlocked.",
        "admin.unlock_error": "✕ Error unlocking channel.",
        "admin.proactive_status": "Proactive mode **{status}** in {channel}.",
        "admin.reactive_status": "Reactive mode **{status}** in this server.",
        "admin.enabled": "enabled ✓",
        "admin.disabled": "disabled ✕",
        "admin.setwelcome_success": "✓ Welcome channel set to {channel}.",
        "admin.setwelcome_error": "✕ Error configuring welcome channel.",
        "admin.removewelcome_success": "✓ Welcome channel removed. Greetings are now disabled.",
        "admin.removewelcome_error": "✕ Error removing welcome channel.",
        "admin.setname_success": "✓ My nickname in this server is now **{name}**.",
        "admin.setname_error": "✕ Error changing nickname.",
        "admin.name_too_long": "✕ Nickname cannot exceed 32 characters.",
        "admin.cs_title": "✦ Channel Status │ #{channel}",
        "admin.cs_commands": "Commands",
        "admin.cs_blocked": "✕ **BLOCKED** (Use `d.unlock`)",
        "admin.cs_active": "✓ **ACTIVE**",
        "admin.cs_proactive": "Proactive AI",
        "admin.cs_reactive": "Reactive AI (Mentions)",
        "admin.cs_on": "✓ **ACTIVE**",
        "admin.cs_off": "▫ **INACTIVE**"
    },
    "es": {
        # --- osu! cards ---
        "osu.recent_author": "Jugada Reciente · {username} ({mode})",
        "osu.recent_best_author": "Mejor Jugada Reciente (24h) · {username} ({mode})",
        "osu.recent_pass_author": "Último Pass Reciente · {username} ({mode})",
        "osu.no_recent": "**{username}** no tiene jugadas recientes en {mode}.",
        "osu.no_recent_filtered": "**{username}** no tiene jugadas recientes con ese filtro en {mode}.",
        "osu.top_author": "Perfil de osu! de {username}",
        "osu.top_title": "Top Scores · {username} ({mode})",
        "osu.top_none": "No se encontraron jugadas registradas en este modo.",
        "osu.top_none_filtered": "**{username}** no tiene top plays con ese filtro en {mode}.",
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
        "osu.compare_h2h_title": "Head-to-Head · {u1} vs {u2}",
        "osu.compare_score_lead": "**{winner}** lidera **{wins1} - {wins2}** ({mode})",
        "osu.compare_score_tie": "Duelo igualado **{wins1} - {wins2}** ({mode})",
        "osu.compare_skills_title": "Desglose de Habilidades",
        "osu.compare_consistency_title": "Actividad & Consistencia",
        "osu.compare_need_link": "Para comparar contra ti mismo, vincula tu cuenta con `/link <usuario>` o especifica dos jugadores.",
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
        "osu.top_header": "Mejores 5 Jugadas",
        "osu.top_recent_header": "Mejores Jugadas Recientes (Top 5)",
        "osu.top_acc_header": "Mayor Precisión (Top 5)",
        "osu.chart_rank": "Rank de la jugada",
        "osu.chart_title": "Distribución de PP — {username}",
        "osu.chart_summary": "Top 1: {top1:.0f}pp  │  Mediana: {median:.0f}pp  │  Top {last_idx}: {min_pp:.0f}pp  │  Δ: {delta:.0f}pp",
        "osu.profile_author": "Perfil de osu! · {username} ({mode})",
        "osu.peak_rank": "Récord Máximo",
        "osu.ranked_score": "Ranked Score",
        "osu.max_combo": "Combo Máximo",
        "osu.progress_title": "Progreso de PP — {username} ({mode})",
        "osu.progress_summary": "Resumen de Progreso",
        "osu.progress_current_pp": "PP Actual",
        "osu.progress_change": "Cambio Total",
        "osu.progress_snapshots": "Snapshots Registrados",
        "osu.progress_need_snapshots": "Necesito al menos 2 snapshots para hacer el gráfico. Consulta tu perfil seguido para guardar historial.",
        "osu.firsts_title": "Récords #1 Globales · {username} ({mode})",
        "osu.firsts_none": "**{username}** no tiene #1 globales en {mode}.",
        "osu.map_not_found": "✕ No encontré ningún beatmap con esa referencia.",
        "osu.map_no_recent": "✕ Pasa un link/ID de mapa, busca uno por nombre, o muestra un play antes en este canal.",
        "osu.map_mapper": "Mapper",
        "osu.map_status": "Estado",
        "osu.map_objects": "Objetos",
        "osu.map_pp_table": "Simulación de PP (Mods activos)",
        "osu.map_difficulty": "Dificultad & Ritmo",
        "osu.map_compare_author": "Jugadas en el Mapa · {username} ({mode})",
        "osu.map_compare_none": "No encontré jugadas guardadas de **{username}** en este beatmap.",
        "osu.map_compare_none_filtered": "No encontré jugadas con `+{mods}` para **{username}** en este mapa (sí tiene con otros mods).",

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
        "info.changelog_hint": "Escribe `/changelog` o `d.changelog` para ver las novedades de la versión.",
        "info.help_hint": "Escribe `/help` o `d.help` para consultar el menú de comandos.",
        "info.feedback_hint": "Escribe `/feedback` para enviar sugerencias o reportar errores.",

        "changelog.title": "Novedades — Dalet {version}",
        "changelog.milestone_title": "Hito v3.1: Auto-Moderación Modular & Memoria Cognitiva",
        "changelog.milestone_desc": "• **Auto-Moderación Modular**: Escaneo de imágenes con IA (Gemini Vision), Anti-Flood en memoria, filtros anti-phishing y exenciones granulares por canal (`/mod ignore`).\n• **Memoria Cognitiva Reflexiva**: Deducción psicológica en segundo plano (`DaletThought`) para conversaciones y familiaridad orgánica.\n• **Versionado Semántico Dinámico**: Registro automático de commits de Git y cálculo de parches en tiempo real (`/changelog`).",
        "changelog.skills_title": "Análisis de Habilidades en 5D (`/skills`)",
        "changelog.skills_desc": "• Radar heurístico en Aim, Speed, Accuracy, Stamina y Reading con re-ponderación de mods y veredicto mordaz con IA.",
        "changelog.i18n_title": "Balanceador Multi-LLM e Internacionalización",
        "changelog.i18n_desc": "• Enrutamiento inteligente entre DeepSeek V3, Gemini 3.8 Flash y Groq (<200ms) con disyuntores.\n• Soporte bilingüe completo (Inglés por defecto, Español configurable vía `/language`).",

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
        "rank.error": "✕ Error obteniendo el ranking.",

        # --- Feedback ---
        "feedback.success": "✓ ¡Muchas gracias por tu feedback! Ha sido enviado directamente al desarrollador.",
        "feedback.error": "✕ No se pudo enviar tu feedback. Inténtalo de nuevo más tarde.",
        "feedback.dm_title": "✦ Nuevo Feedback Recibido",
        "feedback.author": "Autor",
        "feedback.server": "Servidor",
        "feedback.channel": "Canal",
        "feedback.dm_alert": "▸ {mention}, ¡has recibido un nuevo mensaje de feedback!",

        # --- Admin ---
        "admin.lock_success": "✓ Canal {channel} bloqueado. Los comandos de Dalet están desactivados.",
        "admin.lock_error": "✕ Error al bloquear el canal.",
        "admin.unlock_success": "✓ Canal {channel} desbloqueado.",
        "admin.unlock_error": "✕ Error al desbloquear el canal.",
        "admin.proactive_status": "Modo proactivo **{status}** en {channel}.",
        "admin.reactive_status": "Modo reactivo **{status}** en este servidor.",
        "admin.enabled": "activado ✓",
        "admin.disabled": "desactivado ✕",
        "admin.setwelcome_success": "✓ Canal de bienvenida establecido en {channel}.",
        "admin.setwelcome_error": "✕ Error al configurar el canal de bienvenida.",
        "admin.removewelcome_success": "✓ Canal de bienvenida eliminado. Ya no se enviarán bienvenidas.",
        "admin.removewelcome_error": "✕ Error al eliminar el canal de bienvenida.",
        "admin.setname_success": "✓ Ahora me llamo **{name}** en este servidor.",
        "admin.setname_error": "✕ Error al cambiar el nombre.",
        "admin.name_too_long": "✕ El nombre no puede superar los 32 caracteres.",
        "admin.cs_title": "✦ Estado del Canal │ #{channel}",
        "admin.cs_commands": "Comandos",
        "admin.cs_blocked": "✕ **BLOQUEADOS** (Usa `d.unlock`)",
        "admin.cs_active": "✓ **ACTIVOS**",
        "admin.cs_proactive": "IA Proactiva",
        "admin.cs_reactive": "IA Reactiva (Menciones)",
        "admin.cs_on": "✓ **ACTIVA**",
        "admin.cs_off": "▫ **INACTIVA**"
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
