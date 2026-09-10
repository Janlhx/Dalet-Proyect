# Graph Report - Dalet-Proyect  (2026-09-09)

## Corpus Check
- 68 files · ~136,463 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 719 nodes · 1196 edges · 43 communities (39 shown, 4 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 50 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3f76e9d2`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- OsuHandler
- SlashCommands
- DaletReminders
- 🏛️ Tables
- AdminCommands
- AIConfigCommands
- OsuService
- .build_recent_card
- SQLiteManager
- UserRepository
- OsuPresenter
- NLPService
- EventsHandler
- DaletNLPChat
- .add_standard_footer
- 🗄️ Database — Connection Pool & Repositories
- docs/README.md
- ChatLogger
- DashboardService
- UniversalPaginator
- 📋 Components Explained
- DaletGreetings
- ResumenInteligente
- CommandsHandler
- Dalet
- HelpPaginator
- BaseRepository
- MemoryService
- .execute
- 🧩 Handlers (Cogs) — Command Modules
- 🤖 `nlp_service.py` — Response Generator
- .fetch_all
- .get_rank_color
- dalet_main.py
- rules/graphify.md
- workflows/graphify.md
- DaletAtoms
- archify.md

## God Nodes (most connected - your core abstractions)
1. `DaletAtoms` - 34 edges
2. `SlashCommands` - 28 edges
3. `UserRepository` - 23 edges
4. `DaletReminders` - 22 edges
5. `NLPService` - 21 edges
6. `DaletOrganisms` - 21 edges
7. `SQLiteManager` - 19 edges
8. `OsuHandler` - 19 edges
9. `AdminCommands` - 18 edges
10. `DaletMolecules` - 18 edges

## Surprising Connections (you probably didn't know these)
- `DaletReminders` --uses--> `ReminderRepository`  [INFERRED]
  handlers/dalet_reminders.py → database/repositories/reminder_repository.py
- `NLPService` --uses--> `UserRepository`  [INFERRED]
  services/nlp_service.py → database/repositories/user_repository.py
- `AdminCommands` --uses--> `SQLiteManager`  [INFERRED]
  handlers/dalet_admcommands_handler.py → database/sqlite_manager.py
- `DashboardService` --uses--> `SQLiteManager`  [INFERRED]
  services/dashboard_service.py → database/sqlite_manager.py
- `DaletReminders` --uses--> `TursoClient`  [INFERRED]
  handlers/dalet_reminders.py → database/turso_client.py

## Import Cycles
- None detected.

## Communities (43 total, 4 thin omitted)

### Community 0 - "OsuHandler"
Cohesion: 0.08
Nodes (23): File, _acc_str(), _create_progress_chart_sync(), _mods_str(), OsuHandler, command, Member, _rank_color() (+15 more)

### Community 1 - "SlashCommands"
Cohesion: 0.16
Nodes (12): choices, Bot, command, describe, has_permissions, Interaction, Member, TextChannel (+4 more)

### Community 2 - "DaletReminders"
Cohesion: 0.10
Nodes (23): autocomplete, Choice, DaletReminders, format_days_readable(), parse_date(), parse_days(), parse_days_or_date(), parse_time() (+15 more)

### Community 3 - "🏛️ Tables"
Cohesion: 0.13
Nodes (14): `AIInteractions` — AI Performance Metrics, `Channels` — Discord Channels, `Messages` — Message History, `OsuAccounts` — Linked osu! Accounts, 🔒 Privacy System (`08_Privacy_TTL.sql`), 📋 Script Execution Order, `Servers` — Discord Servers, 🔧 SQL Functions (+6 more)

### Community 4 - "AdminCommands"
Cohesion: 0.10
Nodes (18): AdminCommands, command, has_permissions, [ADMIN] Bloquea todos los comandos en este canal., [ADMIN] Desbloquea los comandos en este canal., [ADMIN] Cambia mi nombre en este servidor (máx 25 caracteres)., Comandos para administrar el bot y depurar la base de datos., [ADMIN] Establece el canal actual para las bienvenidas y despedidas. (+10 more)

### Community 5 - "AIConfigCommands"
Cohesion: 0.11
Nodes (17): group, AIConfigCommands, command, has_permissions, TextChannel, 🤖 [ADMIN] Configura en qué canales Dalet puede participar automáticamente en…, 💬 [ADMIN] Controla si Dalet responde cuando la mencionan en conversaciones., Activa la respuesta de Dalet a su nombre. (+9 more)

### Community 6 - "OsuService"
Cohesion: 0.12
Nodes (11): OsuService, Información de un beatmap específico., Top scores globales de un beatmap., Busca beatmaps con filtros., Perfil completo de un usuario., Perfil de un usuario por ID numérico., Top plays del usuario., Jugadas recientes del usuario. (+3 more)

### Community 7 - ".build_recent_card"
Cohesion: 0.19
Nodes (9): _format_acc(), _format_mods(), Construye un Embed estructurado con los Top Plays del usuario., Formatea la precisión (0.0 a 1.0) a porcentaje XX.XX%., Obtiene el puntaje formateado tanto para scores de Lazer como Classic/Bancho y…, Formatea la lista de mods en un string compacto tipo +HDDT o +NM., Construye una tarjeta de jugada reciente única, estructurada y sin ruido visual., Convierte segundos a formato MM:SS. (+1 more)

### Community 8 - "SQLiteManager"
Cohesion: 0.21
Nodes (5): Connection, Calcula estadísticas agregadas desde SQLite., Inserción masiva eficiente — usa una sola transacción., Crea las tablas si no existen. Se llama internamente con el lock activo., SQLiteManager

### Community 10 - "OsuPresenter"
Cohesion: 0.27
Nodes (5): OsuPresenter, Presentador de UI para osu! con la identidad visual única de Dalet., Slash Commands (Application Commands) de Dalet. Unifica y expone los comandos…, OsuAnalyzer, Calcula el desglose de habilidades tecnicas para osu!.

### Community 11 - "NLPService"
Cohesion: 0.18
Nodes (8): NLPService, Devuelve un snapshot de telemetría de IA listo para el Dashboard con costo y…, Cierra recursos del cliente HTTP., Limpia y sanea la respuesta generada por cualquier LLM: 1. Elimina etiquetas de…, Determina dinámicamente qué proveedor usar según intención, salud y balanceo.…, Servicio de Procesamiento de Lenguaje Natural para Dalet con Smart LLM Load…, Recorta el contexto de forma dinámica para optimizar consumo de tokens., Describe una imagen usando el modelo principal con timeout estricto y caché en…

### Community 12 - "EventsHandler"
Cohesion: 0.18
Nodes (9): Guild, EventsHandler, listener, Handler de Eventos Globales de Discord. Maneja: on_ready, on_command_error,…, Agrupa los listeners de eventos globales del bot., Se ejecuta cuando el bot está listo y conectado., Manejo global de errores de comandos., Envía presentación cuando el bot entra a un servidor nuevo. (+1 more)

### Community 13 - "DaletNLPChat"
Cohesion: 0.13
Nodes (12): DaletNLPChat, listener, loop, Message, Controla las sesiones reactive por usuario/servidor. Conversación continua y…, Centraliza el manejo de errores 429 con backoff exponencial., Decide si el bot debe responder proactivamente en este mensaje., Maneja el listener 'on_message' para las respuestas de IA. (+4 more)

### Community 14 - ".add_standard_footer"
Cohesion: 0.13
Nodes (12): _get_country_flag(), _mode_title(), Embed, Construye la tarjeta de perfil osu! limpia y estructurada., Convierte un código ISO de país (ej. 'CO', 'US') en su emoji de bandera., Construye una tarjeta comparativa limpia entre dos jugadores., Construye una tarjeta visual y detallada del desglose de habilidades (Skill…, Embed (+4 more)

### Community 15 - "🗄️ Database — Connection Pool & Repositories"
Cohesion: 0.13
Nodes (15): 🛡️ `admin_repository.py` — Channel Locks, 📊 `analytics_repository.py` — Metrics & Tracking, 🏗️ `base_repository.py` — The base class, Batch Logging System (`_log_buffer` + `_flushing_logs`), Caching System (`_get_cached`), 📐 Class Hierarchy, 🗄️ Database — Connection Pool & Repositories, 🔌 `database/pool.py` — The Connection Pool (+7 more)

### Community 16 - "docs/README.md"
Cohesion: 0.05
Nodes (37): 🧩 Design Pattern: Cogs, 🗺️ Design Pattern: Repository, 🏗️ General Architecture of Dalet, 🔄 Main Flow: "What happens when someone mentions Dalet?", 🗄️ Message Logging Flow (Batch Logging), 🧠 ¿Qué es Dalet?, 🔁 Resilience & Fallbacks, ⚙️ Tech Stack (+29 more)

### Community 17 - "ChatLogger"
Cohesion: 0.17
Nodes (9): ChatLogger, command, has_permissions, listener, Message, Guarda mensajes de usuarios (no comandos, no bots) en el buffer de SQLite., [ADMIN] Muestra los últimos mensajes guardados en este canal., Registra mensajes en SQLite para memoria de contexto e historial. El on_message… (+1 more)

### Community 18 - "DashboardService"
Cohesion: 0.14
Nodes (12): api_telemetry(), health(), home(), Sirve la interfaz web del Dashboard de telemetría., Devuelve métricas en tiempo real en formato JSON., Health check simple para Render., route, DashboardService (+4 more)

### Community 19 - "UniversalPaginator"
Cohesion: 0.29
Nodes (5): button, Interaction, Paginador definitivo para el Súper Análisis de Dalet (3 Páginas)., Re-añade los campos de stats que podrian haberse borrado al limpiar campos., UniversalPaginator

### Community 20 - "📋 Components Explained"
Cohesion: 0.15
Nodes (12): 📋 Components Explained, `DatabasePool.get_pool()` — Database Initialization, 🚀 Entry Point: `dalet_main.py`, Expired Message Purge (Privacy TTL), Flask Server (Health Check), Global Block Check (Security Middleware), Instantiating Repositories and Services, `load_extensions(bot)` — Dynamic Cog Loading (+4 more)

### Community 21 - "DaletGreetings"
Cohesion: 0.31
Nodes (5): DaletGreetings, listener, Member, Modulo predefinido para administrar saludos y despedidas., setup()

### Community 22 - "ResumenInteligente"
Cohesion: 0.24
Nodes (6): command, 📄 Genera un resumen de los últimos N mensajes del canal. Uso: `d.resumir…, 📜 Muestra los últimos resúmenes guardados para este canal. Uso:…, Comandos para generar y ver resúmenes de chat., ResumenInteligente, setup()

### Community 23 - "CommandsHandler"
Cohesion: 0.14
Nodes (12): cooldown, CommandsHandler, command, Member, Comandos básicos de Dalet (utilidades, info y herramientas generales)., 🏓 Muestra la latencia del bot en milisegundos., 📊 Muestra tus estadísticas sociales o las de otro usuario., Muestra información detallada de un usuario del servidor. (+4 more)

### Community 24 - "Dalet"
Cohesion: 0.13
Nodes (15): 1. Clonar el repositorio, 2. Crear entorno virtual e instalar dependencias, 3. Configurar variables de entorno (`.env`), 4. Ejecutar el Bot, 🏗️ Arquitectura, ✨ Características, 💬 Comandos, Dalet (+7 more)

### Community 25 - "HelpPaginator"
Cohesion: 0.13
Nodes (13): CategorySelect, HelpPaginator, PageInputModal, button, Embed, Interaction, Menú desplegable para saltar directamente a una categoría., Vista con botones de navegación y select menu de categorías. (+5 more)

### Community 26 - "BaseRepository"
Cohesion: 0.06
Nodes (25): DatabasePool, Bridge de compatibilidad hacia TursoClient., AdminRepository, Activa o desactiva el bloqueo de comandos en un canal., Obtiene el nombre personalizado del bot para un servidor., Establece un nombre personalizado para el bot en un servidor., Obtiene el ID del canal de bienvenida de un servidor., Establece o elimina el canal de bienvenida para un servidor. (+17 more)

### Community 27 - "MemoryService"
Cohesion: 0.25
Nodes (4): MemoryService, Construye el contexto de conversación optimizado combinando: 1. Historial…, Guarda una memoria sobre el usuario en la BD., Servicio de memoria que combina historial local (RAM) con historial de BD. Sin…

### Community 28 - ".execute"
Cohesion: 0.18
Nodes (8): Cursor, AnalyticsRepository, Registra la ejecución de un comando en SQLite., Registra una respuesta de la IA en SQLite., Registra un error crítico del bot en SQLite., Repositorio para escritura de datos analíticos: CommandUsage, AIInteractions,…, Guarda un snapshot del perfil osu! del jugador en SQLite., Elimina un recordatorio de la base de datos (Turso y SQLite fallback).

### Community 29 - "🧩 Handlers (Cogs) — Command Modules"
Cohesion: 0.09
Nodes (23): Behavioral Constants (at the top of the file), Command `d.chatlog [count]`, Components, 🛡️ `dalet_admcommands_handler.py` — Admin Commands, 📝 `dalet_chatlogger.py` — The Message Logger, 🔧 `dalet_commands_handlers.py` — General Commands, 📡 `dalet_events_handlers.py` — Global Events, ⚙️ `dalet_geminicommand.py` — AI Configuration (+15 more)

### Community 35 - "🤖 `nlp_service.py` — Response Generator"
Cohesion: 0.11
Nodes (17): AI Providers, Authentication, Core Methods, Dalet's Personality, Fallback Chain, 🗂️ Files, `get_relevant_context(channel_id, user_id, current_message)`, 💾 `memory_service.py` — Memory System (+9 more)

### Community 36 - ".fetch_all"
Cohesion: 0.29
Nodes (3): Obtiene el historial de PP de un jugador desde SQLite., Obtiene los últimos mensajes de un canal desde SQLite y el buffer de memoria., Busca fragmentos de mensajes pasados en SQLite.

### Community 37 - ".get_rank_color"
Cohesion: 0.29
Nodes (4): Color, Devuelve un color de acento basado en el rango global numérico., Devuelve el color correspondiente al grade de osu!., Organismo complejo para mostrar el perfil de osu!.

### Community 39 - "dalet_main.py"
Cohesion: 0.23
Nodes (5): keep_alive(), load_extensions(), main(), run_flask(), OsuRepository

### Community 46 - "DaletAtoms"
Cohesion: 0.17
Nodes (12): CustomHelpCommand, Handler (Cog) para el Comando de Ayuda Personalizado de Dalet. Sistema…, Reemplaza el comando de ayuda por defecto con un panel visual e interactivo., setup(), DaletAtoms, Design Tokens e Identidad Visual de Dalet., DaletMolecules, Crea un botón de Discord con el estilo Dalet. (+4 more)

## Knowledge Gaps
- **107 isolated node(s):** `archify`, `graphify`, `Workflow: graphify`, `✨ Características`, `🛠️ Stack Tecnológico` (+102 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaletAtoms` connect `DaletAtoms` to `OsuHandler`, `SlashCommands`, `DaletReminders`, `AdminCommands`, `AIConfigCommands`, `.get_rank_color`, `.build_recent_card`, `OsuPresenter`, `CommandsHandler`, `HelpPaginator`, `BaseRepository`?**
  _High betweenness centrality (0.209) - this node is a cross-community bridge._
- **Why does `SQLiteManager` connect `SQLiteManager` to `.fetch_all`, `AdminCommands`, `dalet_main.py`, `UserRepository`, `DashboardService`, `BaseRepository`, `.execute`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **Why does `DaletReminders` connect `DaletReminders` to `BaseRepository`, `DaletAtoms`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `DaletAtoms` (e.g. with `AdminCommands` and `CommandsHandler`) actually correct?**
  _`DaletAtoms` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `SlashCommands` (e.g. with `OsuPresenter` and `OsuAnalyzer`) actually correct?**
  _`SlashCommands` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `UserRepository` (e.g. with `BaseRepository` and `SQLiteManager`) actually correct?**
  _`UserRepository` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `DaletReminders` (e.g. with `ReminderRepository` and `TursoClient`) actually correct?**
  _`DaletReminders` has 4 INFERRED edges - model-reasoned connections that need verification._