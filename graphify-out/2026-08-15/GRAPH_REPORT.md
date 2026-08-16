# Graph Report - Dalet-Proyect  (2026-08-15)

## Corpus Check
- 64 files · ~71,011 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 682 nodes · 1118 edges · 36 communities (34 shown, 2 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 45 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a626a078`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- OsuHandler
- SlashCommands
- DaletReminders
- OsuAnalyzer
- AdminCommands
- AIConfigCommands
- OsuService
- UserRepository
- .is_available
- 📋 Components Explained
- DaletAtoms
- SQLiteManager
- EventsHandler
- DaletNLPChat
- AdminRepository
- ChatLogger
- dalet_main.py
- UniversalPaginator
- .fetch_all
- DaletGreetings
- ResumenInteligente
- MemoryService
- docs/README.md
- 🧩 Handlers (Cogs) — Command Modules
- 🤖 `nlp_service.py` — Response Generator
- 🗄️ Database — Connection Pool & Repositories
- 🏛️ Tables
- .get_connection
- BaseRepository
- rules/graphify.md
- workflows/graphify.md

## God Nodes (most connected - your core abstractions)
1. `SlashCommands` - 28 edges
2. `DaletAtoms` - 27 edges
3. `DaletReminders` - 23 edges
4. `UserRepository` - 22 edges
5. `DaletOrganisms` - 22 edges
6. `AdminCommands` - 18 edges
7. `OsuHandler` - 18 edges
8. `DaletMolecules` - 18 edges
9. `SQLiteManager` - 17 edges
10. `OsuService` - 17 edges

## Surprising Connections (you probably didn't know these)
- `AdminCommands` --uses--> `DatabasePool`  [INFERRED]
  handlers/dalet_admcommands_handler.py → database/pool.py
- `DaletReminders` --uses--> `DatabasePool`  [INFERRED]
  handlers/dalet_reminders.py → database/pool.py
- `SlashCommands` --uses--> `DatabasePool`  [INFERRED]
  handlers/dalet_slash_commands.py → database/pool.py
- `DaletReminders` --uses--> `ReminderRepository`  [INFERRED]
  handlers/dalet_reminders.py → database/repositories/reminder_repository.py
- `AdminCommands` --uses--> `SQLiteManager`  [INFERRED]
  handlers/dalet_admcommands_handler.py → database/sqlite_manager.py

## Import Cycles
- None detected.

## Communities (36 total, 2 thin omitted)

### Community 0 - "OsuHandler"
Cohesion: 0.08
Nodes (23): File, _acc_str(), _create_progress_chart_sync(), _mods_str(), OsuHandler, command, Member, _rank_color() (+15 more)

### Community 1 - "SlashCommands"
Cohesion: 0.09
Nodes (23): choices, Embed, _acc_str(), _mods_str(), Construye la tarjeta principal de perfil., Construye un Embed para la jugada más reciente de un usuario., Construye un Embed con las mejores jugadas (Top Plays) de un usuario., Construye una tarjeta comparativa entre dos jugadores. (+15 more)

### Community 2 - "DaletReminders"
Cohesion: 0.12
Nodes (20): autocomplete, Choice, DaletReminders, format_days_readable(), parse_date(), parse_days(), parse_days_or_date(), parse_time() (+12 more)

### Community 3 - "OsuAnalyzer"
Cohesion: 0.08
Nodes (15): OsuRepository, OsuAnalyzer, Módulo de Lógica de Análisis de osu! (v4.1) Esta versión corrige el 'edge case'…, Analiza los 'recent plays' para detectar la consistencia del accuracy. (BUG…, Analiza los 'recent plays' (Últimos 50) para detectar el estilo ACTUAL., Analiza las propiedades de los mapas en los 'recent plays' (Últimos 50)., Determina el área de enfoque (debilidad) de manera inteligente. Calcula una…, Analiza datos de osu! (v4.1) y genera prompts detallados para la IA. (+7 more)

### Community 4 - "AdminCommands"
Cohesion: 0.10
Nodes (18): AdminCommands, command, has_permissions, [ADMIN] Cambia mi nombre en este servidor (máx 25 caracteres)., Comandos para administrar el bot y depurar la base de datos., [ADMIN] Establece el canal actual para las bienvenidas y despedidas., [ADMIN] Desactiva las bienvenidas y despedidas en el servidor., Muestra el estado de seguridad y IA del canal actual. (+10 more)

### Community 5 - "AIConfigCommands"
Cohesion: 0.11
Nodes (17): group, AIConfigCommands, command, has_permissions, TextChannel, 🤖 [ADMIN] Configura en qué canales Dalet puede participar automáticamente en…, 💬 [ADMIN] Controla si Dalet responde cuando la mencionan en conversaciones., Activa la respuesta de Dalet a su nombre. (+9 more)

### Community 6 - "OsuService"
Cohesion: 0.12
Nodes (11): OsuService, Información de un beatmap específico., Top scores globales de un beatmap., Busca beatmaps con filtros., Perfil completo de un usuario., Perfil de un usuario por ID numérico., Top plays del usuario., Jugadas recientes del usuario. (+3 more)

### Community 7 - "UserRepository"
Cohesion: 0.13
Nodes (6): Inicia la tarea de vaciado del buffer si no está activa., UserRepository, NLPService, Recorta el contexto de forma dinámica para optimizar consumo de tokens. -…, Describe una imagen usando el modelo principal con caché en RAM., Cierra recursos del cliente HTTP.

### Community 8 - ".is_available"
Cohesion: 0.10
Nodes (14): Cursor, Devuelve True si la BD está conectada y disponible., AnalyticsRepository, Registra la ejecución de un comando en SQLite., Registra una respuesta de la IA en SQLite., Registra un error crítico del bot en SQLite., Repositorio para escritura de datos analíticos: CommandUsage, AIInteractions,…, Guarda un snapshot del perfil osu! del jugador en SQLite. (+6 more)

### Community 9 - "📋 Components Explained"
Cohesion: 0.15
Nodes (12): 📋 Components Explained, `DatabasePool.get_pool()` — Database Initialization, 🚀 Entry Point: `dalet_main.py`, Expired Message Purge (Privacy TTL), Flask Server (Health Check), Global Block Check (Security Middleware), Instantiating Repositories and Services, `load_extensions(bot)` — Dynamic Cog Loading (+4 more)

### Community 10 - "DaletAtoms"
Cohesion: 0.05
Nodes (43): cooldown, CommandsHandler, command, Member, Comandos básicos de Dalet (utilidades, info y herramientas generales)., 🏓 Muestra la latencia del bot en milisegundos., 📊 Muestra tus estadísticas sociales o las de otro usuario., Muestra información detallada de un usuario del servidor. (+35 more)

### Community 11 - "SQLiteManager"
Cohesion: 0.24
Nodes (7): DatabasePool, get_db(), Devuelve el pool de conexiones. Si la BD no está disponible, devuelve None.…, Devuelve el pool. Puede devolver None si la BD no está disponible., ReminderRepository, SQLiteManager, main()

### Community 12 - "EventsHandler"
Cohesion: 0.18
Nodes (9): Guild, EventsHandler, listener, Handler de Eventos Globales de Discord. Maneja: on_ready, on_command_error,…, Agrupa los listeners de eventos globales del bot., Se ejecuta cuando el bot está listo y conectado., Manejo global de errores de comandos., Envía presentación cuando el bot entra a un servidor nuevo. (+1 more)

### Community 13 - "DaletNLPChat"
Cohesion: 0.13
Nodes (12): DaletNLPChat, listener, loop, Message, Controla las sesiones reactive por usuario/servidor. Retorna: 'ok' → responder…, Centraliza el manejo de errores 429 con backoff exponencial., Decide si el bot debe responder proactivamente en este mensaje., Maneja el listener 'on_message' para las respuestas de IA. (+4 more)

### Community 16 - "AdminRepository"
Cohesion: 0.14
Nodes (7): AdminRepository, Activa o desactiva el bloqueo de comandos en un canal., Obtiene el nombre personalizado del bot para un servidor., Establece un nombre personalizado para el bot en un servidor., Obtiene el ID del canal de bienvenida de un servidor., Establece o elimina el canal de bienvenida para un servidor., Verifica si los comandos están bloqueados en un canal.

### Community 17 - "ChatLogger"
Cohesion: 0.17
Nodes (9): ChatLogger, command, has_permissions, listener, Message, Guarda mensajes de usuarios (no comandos, no bots) en el buffer de SQLite., [ADMIN] Muestra los últimos mensajes guardados en este canal., Registra mensajes en SQLite para memoria de contexto e historial. El on_message… (+1 more)

### Community 18 - "dalet_main.py"
Cohesion: 0.21
Nodes (9): home(), keep_alive(), load_extensions(), main(), run_flask(), Devuelve el cliente de Turso. Si la BD no está disponible, devuelve None. NUNCA…, Devuelve True si la BD está conectada y disponible., TursoClient (+1 more)

### Community 19 - "UniversalPaginator"
Cohesion: 0.29
Nodes (5): button, Interaction, Paginador definitivo para el Súper Análisis de Dalet (3 Páginas)., Re-añade los campos de stats que podrian haberse borrado al limpiar campos., UniversalPaginator

### Community 20 - ".fetch_all"
Cohesion: 0.18
Nodes (5): Obtiene el historial de PP de un jugador desde SQLite., Retorna los recordatorios creados por un usuario en un servidor específico., Retorna todos los recordatorios activos en todo el sistema. Busca tanto en…, Obtiene los últimos mensajes de un canal desde SQLite y el buffer de memoria., Busca fragmentos de mensajes pasados en SQLite.

### Community 21 - "DaletGreetings"
Cohesion: 0.31
Nodes (5): DaletGreetings, listener, Member, Modulo predefinido para administrar saludos y despedidas., setup()

### Community 22 - "ResumenInteligente"
Cohesion: 0.24
Nodes (6): command, 📄 Genera un resumen de los últimos N mensajes del canal. Uso: `d.resumir…, 📜 Muestra los últimos resúmenes guardados para este canal. Uso:…, Comandos para generar y ver resúmenes de chat., ResumenInteligente, setup()

### Community 23 - "MemoryService"
Cohesion: 0.25
Nodes (4): MemoryService, Construye el contexto de conversación combinando: 1. Historial reciente del…, Guarda una memoria sobre el usuario en la BD., Servicio de memoria que combina historial local (RAM) con historial de BD. Sin…

### Community 27 - "docs/README.md"
Cohesion: 0.04
Nodes (41): 🧩 Design Pattern: Cogs, 🗺️ Design Pattern: Repository, 🏗️ General Architecture of Dalet, 🔄 Main Flow: "What happens when someone mentions Dalet?", 🗄️ Message Logging Flow (Batch Logging), 🔁 Resilience & Fallbacks, ⚙️ Tech Stack, 🧠 What is Dalet? (+33 more)

### Community 29 - "🧩 Handlers (Cogs) — Command Modules"
Cohesion: 0.09
Nodes (23): Behavioral Constants (at the top of the file), Command `d.chatlog [count]`, Components, 🛡️ `dalet_admcommands_handler.py` — Admin Commands, 📝 `dalet_chatlogger.py` — The Message Logger, 🔧 `dalet_commands_handlers.py` — General Commands, 📡 `dalet_events_handlers.py` — Global Events, ⚙️ `dalet_geminicommand.py` — AI Configuration (+15 more)

### Community 35 - "🤖 `nlp_service.py` — Response Generator"
Cohesion: 0.11
Nodes (17): AI Providers, Authentication, Core Methods, Dalet's Personality, Fallback Chain, 🗂️ Files, `get_relevant_context(channel_id, user_id, current_message)`, 💾 `memory_service.py` — Memory System (+9 more)

### Community 36 - "🗄️ Database — Connection Pool & Repositories"
Cohesion: 0.12
Nodes (15): 🛡️ `admin_repository.py` — Channel Locks, 📊 `analytics_repository.py` — Metrics & Tracking, 🏗️ `base_repository.py` — The base class, Batch Logging System (`_log_buffer` + `_flushing_logs`), Caching System (`_get_cached`), 📐 Class Hierarchy, 🗄️ Database — Connection Pool & Repositories, 🔌 `database/pool.py` — The Connection Pool (+7 more)

### Community 37 - "🏛️ Tables"
Cohesion: 0.13
Nodes (14): `AIInteractions` — AI Performance Metrics, `Channels` — Discord Channels, `Messages` — Message History, `OsuAccounts` — Linked osu! Accounts, 🔒 Privacy System (`08_Privacy_TTL.sql`), 📋 Script Execution Order, `Servers` — Discord Servers, 🔧 SQL Functions (+6 more)

### Community 39 - ".get_connection"
Cohesion: 0.15
Nodes (6): Connection, Obtiene un recordatorio específico por su ID., Activa/desactiva un recordatorio. Retorna el nuevo estado., Calcula estadísticas agregadas desde SQLite., Inserción masiva eficiente — usa una sola transacción., Crea las tablas si no existen. Se llama internamente con el lock activo.

### Community 40 - "BaseRepository"
Cohesion: 0.23
Nodes (5): BaseRepository, Convierte parámetros de PostgreSQL ($1, $2) a SQLite (?), Turso (SQLite) no soporta stored procedures, solo logueamos o pasamos., get_db(), Devuelve el cliente. Puede devolver None si la BD no está disponible.

## Knowledge Gaps
- **99 isolated node(s):** `graphify`, `Workflow: graphify`, `✨ Features`, `🛠 Tech Stack`, `Prerequisites` (+94 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaletAtoms` connect `DaletAtoms` to `OsuHandler`, `SlashCommands`, `DaletReminders`, `AIConfigCommands`, `SQLiteManager`?**
  _High betweenness centrality (0.130) - this node is a cross-community bridge._
- **Why does `DaletOrganisms` connect `DaletAtoms` to `OsuHandler`, `SlashCommands`, `DaletReminders`, `SQLiteManager`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Why does `DaletReminders` connect `DaletReminders` to `.is_available`, `DaletAtoms`, `SQLiteManager`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `SlashCommands` (e.g. with `DatabasePool` and `OsuPresenter`) actually correct?**
  _`SlashCommands` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `DaletAtoms` (e.g. with `CommandsHandler` and `AIConfigCommands`) actually correct?**
  _`DaletAtoms` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `DaletReminders` (e.g. with `DatabasePool` and `ReminderRepository`) actually correct?**
  _`DaletReminders` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `UserRepository` (e.g. with `BaseRepository` and `SQLiteManager`) actually correct?**
  _`UserRepository` has 3 INFERRED edges - model-reasoned connections that need verification._