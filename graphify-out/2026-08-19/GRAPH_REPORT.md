# Graph Report - Dalet-Proyect  (2026-08-19)

## Corpus Check
- 65 files · ~73,592 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 702 nodes · 1138 edges · 44 communities (41 shown, 3 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 46 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `eee1ffab`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- OsuHandler
- SlashCommands
- DaletReminders
- 🗄️ Database — Connection Pool & Repositories
- AdminCommands
- AIConfigCommands
- OsuService
- UserRepository
- AdminRepository
- OsuAnalyzer
- DaletAtoms
- BaseRepository
- EventsHandler
- DaletNLPChat
- .build_recent_card
- Dalet
- 🎨 Dalet Design System (Atomic UI)
- ChatLogger
- MemoryService
- UniversalPaginator
- .fetch_all
- DaletGreetings
- ResumenInteligente
- NLPService
- dalet_main.py
- 🏗️ General Architecture of Dalet
- docs/README.md
- 📋 Components Explained
- 🤖 `dalet_nlpchat.py` — The Conversational Brain
- 🧩 Handlers (Cogs) — Command Modules
- 🤖 `nlp_service.py` — Response Generator
- All Variables
- 🏛️ Tables
- SQL Migration Guide for Neon (Dalet Restructuring)
- SQLiteManager
- 🔑 Environment Variables (`.env`)
- rules/graphify.md
- workflows/graphify.md
- 📝 `dalet_chatlogger.py` — The Message Logger

## God Nodes (most connected - your core abstractions)
1. `DaletAtoms` - 32 edges
2. `SlashCommands` - 26 edges
3. `UserRepository` - 23 edges
4. `DaletReminders` - 22 edges
5. `DaletOrganisms` - 21 edges
6. `OsuHandler` - 18 edges
7. `DaletMolecules` - 18 edges
8. `SQLiteManager` - 17 edges
9. `OsuService` - 17 edges
10. `BaseRepository` - 16 edges

## Surprising Connections (you probably didn't know these)
- `OsuAnalyzer` --uses--> `OsuRepository`  [INFERRED]
  handlers/modules/dalet_osuanalyzer.py → database/repositories/osu_repository.py
- `DaletReminders` --uses--> `ReminderRepository`  [INFERRED]
  handlers/dalet_reminders.py → database/repositories/reminder_repository.py
- `NLPService` --uses--> `UserRepository`  [INFERRED]
  services/nlp_service.py → database/repositories/user_repository.py
- `AdminCommands` --uses--> `SQLiteManager`  [INFERRED]
  handlers/dalet_admcommands_handler.py → database/sqlite_manager.py
- `DaletReminders` --uses--> `TursoClient`  [INFERRED]
  handlers/dalet_reminders.py → database/turso_client.py

## Import Cycles
- None detected.

## Communities (44 total, 3 thin omitted)

### Community 0 - "OsuHandler"
Cohesion: 0.08
Nodes (24): File, _acc_str(), _create_progress_chart_sync(), _mods_str(), OsuHandler, command, Member, _rank_color() (+16 more)

### Community 1 - "SlashCommands"
Cohesion: 0.17
Nodes (12): choices, Bot, command, describe, has_permissions, Interaction, Member, TextChannel (+4 more)

### Community 2 - "DaletReminders"
Cohesion: 0.10
Nodes (23): autocomplete, Choice, DaletReminders, format_days_readable(), parse_date(), parse_days(), parse_days_or_date(), parse_time() (+15 more)

### Community 3 - "🗄️ Database — Connection Pool & Repositories"
Cohesion: 0.12
Nodes (15): 🛡️ `admin_repository.py` — Channel Locks, 📊 `analytics_repository.py` — Metrics & Tracking, 🏗️ `base_repository.py` — The base class, Batch Logging System (`_log_buffer` + `_flushing_logs`), Caching System (`_get_cached`), 📐 Class Hierarchy, 🗄️ Database — Connection Pool & Repositories, 🔌 `database/pool.py` — The Connection Pool (+7 more)

### Community 4 - "AdminCommands"
Cohesion: 0.11
Nodes (17): AdminCommands, command, has_permissions, Comandos para administrar el bot y depurar la base de datos., [ADMIN] Desbloquea los comandos en este canal., [ADMIN] Cambia mi nombre en este servidor (máx 25 caracteres)., [ADMIN] Establece el canal actual para las bienvenidas y despedidas., [ADMIN] Desactiva las bienvenidas y despedidas en el servidor. (+9 more)

### Community 5 - "AIConfigCommands"
Cohesion: 0.11
Nodes (17): group, AIConfigCommands, command, has_permissions, TextChannel, 🤖 [ADMIN] Configura en qué canales Dalet puede participar automáticamente en…, 💬 [ADMIN] Controla si Dalet responde cuando la mencionan en conversaciones., Activa la respuesta de Dalet a su nombre. (+9 more)

### Community 6 - "OsuService"
Cohesion: 0.12
Nodes (11): OsuService, Información de un beatmap específico., Top scores globales de un beatmap., Busca beatmaps con filtros., Perfil completo de un usuario., Perfil de un usuario por ID numérico., Top plays del usuario., Jugadas recientes del usuario. (+3 more)

### Community 8 - "AdminRepository"
Cohesion: 0.14
Nodes (7): AdminRepository, Activa o desactiva el bloqueo de comandos en un canal., Obtiene el nombre personalizado del bot para un servidor., Establece un nombre personalizado para el bot en un servidor., Obtiene el ID del canal de bienvenida de un servidor., Establece o elimina el canal de bienvenida para un servidor., Verifica si los comandos están bloqueados en un canal.

### Community 9 - "OsuAnalyzer"
Cohesion: 0.11
Nodes (14): OsuAnalyzer, Módulo de Lógica de Análisis de osu! (v4.1) Esta versión corrige el 'edge case'…, Analiza los 'recent plays' para detectar la consistencia del accuracy. (BUG…, Analiza los 'recent plays' (Últimos 50) para detectar el estilo ACTUAL., Analiza las propiedades de los mapas en los 'recent plays' (Últimos 50)., Determina el área de enfoque (debilidad) de manera inteligente. Calcula una…, Analiza datos de osu! (v4.1) y genera prompts detallados para la IA., Busca 5 mapas recomendados de la base de datos (con fallback a la API de osu!). (+6 more)

### Community 10 - "DaletAtoms"
Cohesion: 0.05
Nodes (41): cooldown, CommandsHandler, command, Member, Comandos básicos de Dalet (utilidades, info y herramientas generales)., 🏓 Muestra la latencia del bot en milisegundos., 📊 Muestra tus estadísticas sociales o las de otro usuario., Muestra información detallada de un usuario del servidor. (+33 more)

### Community 11 - "BaseRepository"
Cohesion: 0.06
Nodes (23): Cursor, DatabasePool, Bridge de compatibilidad hacia TursoClient., Registra la ejecución de un comando en SQLite., Registra una respuesta de la IA en SQLite., Registra un error crítico del bot en SQLite., Guarda un snapshot del perfil osu! del jugador en SQLite., BaseRepository (+15 more)

### Community 12 - "EventsHandler"
Cohesion: 0.18
Nodes (9): Guild, EventsHandler, listener, Handler de Eventos Globales de Discord. Maneja: on_ready, on_command_error,…, Agrupa los listeners de eventos globales del bot., Se ejecuta cuando el bot está listo y conectado., Manejo global de errores de comandos., Envía presentación cuando el bot entra a un servidor nuevo. (+1 more)

### Community 13 - "DaletNLPChat"
Cohesion: 0.13
Nodes (12): DaletNLPChat, listener, loop, Message, Controla las sesiones reactive por usuario/servidor. Retorna: 'ok' → responder…, Centraliza el manejo de errores 429 con backoff exponencial., Decide si el bot debe responder proactivamente en este mensaje., Maneja el listener 'on_message' para las respuestas de IA. (+4 more)

### Community 14 - ".build_recent_card"
Cohesion: 0.09
Nodes (21): Color, _format_acc(), _format_mods(), _get_country_flag(), _mode_title(), Embed, Construye un Embed de alta densidad con los Top Plays del usuario., Formatea la precisión (0.0 a 1.0) a porcentaje XX.XX%. (+13 more)

### Community 15 - "Dalet"
Cohesion: 0.13
Nodes (15): 🏗 Architecture, 💬 Commands, 🤝 Contributing, Dalet, 📚 Documentation, ✨ Features, 🚀 Getting Started, 📄 License (+7 more)

### Community 16 - "🎨 Dalet Design System (Atomic UI)"
Cohesion: 0.17
Nodes (11): 🧱 1. Átomos (`ui/atoms.py`), 🧪 2. Moléculas (`ui/molecules.py`), 🫀 3. Organismos (`ui/organisms.py` & `OsuPresenter`), A. Jugada Reciente (`/recent`), B. Top Scores (`/top`), C. Perfil de Usuario (`/op`), Colores de Rango y Tiers (osu!), 🎨 Dalet Design System (Atomic UI) (+3 more)

### Community 17 - "ChatLogger"
Cohesion: 0.17
Nodes (9): ChatLogger, command, has_permissions, listener, Message, Guarda mensajes de usuarios (no comandos, no bots) en el buffer de SQLite., [ADMIN] Muestra los últimos mensajes guardados en este canal., Registra mensajes en SQLite para memoria de contexto e historial. El on_message… (+1 more)

### Community 18 - "MemoryService"
Cohesion: 0.25
Nodes (4): MemoryService, Construye el contexto de conversación combinando: 1. Historial reciente del…, Guarda una memoria sobre el usuario en la BD., Servicio de memoria que combina historial local (RAM) con historial de BD. Sin…

### Community 19 - "UniversalPaginator"
Cohesion: 0.29
Nodes (5): button, Interaction, Paginador definitivo para el Súper Análisis de Dalet (3 Páginas)., Re-añade los campos de stats que podrian haberse borrado al limpiar campos., UniversalPaginator

### Community 20 - ".fetch_all"
Cohesion: 0.18
Nodes (5): Obtiene el historial de PP de un jugador desde SQLite., Retorna los recordatorios creados por un usuario en un servidor específico., Retorna todos los recordatorios activos en todo el sistema., Obtiene los últimos mensajes de un canal desde SQLite y el buffer de memoria., Busca fragmentos de mensajes pasados en SQLite.

### Community 21 - "DaletGreetings"
Cohesion: 0.31
Nodes (5): DaletGreetings, listener, Member, Modulo predefinido para administrar saludos y despedidas., setup()

### Community 22 - "ResumenInteligente"
Cohesion: 0.24
Nodes (6): command, 📄 Genera un resumen de los últimos N mensajes del canal. Uso: `d.resumir…, 📜 Muestra los últimos resúmenes guardados para este canal. Uso:…, Comandos para generar y ver resúmenes de chat., ResumenInteligente, setup()

### Community 23 - "NLPService"
Cohesion: 0.31
Nodes (4): NLPService, Recorta el contexto de forma dinámica para optimizar consumo de tokens. -…, Describe una imagen usando el modelo principal con caché en RAM., Cierra recursos del cliente HTTP.

### Community 24 - "dalet_main.py"
Cohesion: 0.36
Nodes (6): home(), keep_alive(), load_extensions(), main(), run_flask(), route

### Community 25 - "🏗️ General Architecture of Dalet"
Cohesion: 0.25
Nodes (8): 🧩 Design Pattern: Cogs, 🗺️ Design Pattern: Repository, 🏗️ General Architecture of Dalet, 🔄 Main Flow: "What happens when someone mentions Dalet?", 🗄️ Message Logging Flow (Batch Logging), 🧠 ¿Qué es Dalet?, 🔁 Resilience & Fallbacks, ⚙️ Tech Stack

### Community 26 - "docs/README.md"
Cohesion: 0.33
Nodes (3): 📂 Documentation Sections, 📖 Project Documentation Index, 🗺️ Project Structure

### Community 27 - "📋 Components Explained"
Cohesion: 0.15
Nodes (12): 📋 Components Explained, `DatabasePool.get_pool()` — Database Initialization, 🚀 Entry Point: `dalet_main.py`, Expired Message Purge (Privacy TTL), Flask Server (Health Check), Global Block Check (Security Middleware), Instantiating Repositories and Services, `load_extensions(bot)` — Dynamic Cog Loading (+4 more)

### Community 28 - "🤖 `dalet_nlpchat.py` — The Conversational Brain"
Cohesion: 0.29
Nodes (7): Behavioral Constants (at the top of the file), 🤖 `dalet_nlpchat.py` — The Conversational Brain, `generate_response()` — The response process, `_handle_429()` — Rate Limit Management, `on_message` Flow (triggered per message), `_should_respond()` — Proactivity logic, What does it do?

### Community 29 - "🧩 Handlers (Cogs) — Command Modules"
Cohesion: 0.17
Nodes (12): Components, 🛡️ `dalet_admcommands_handler.py` — Admin Commands, 🔧 `dalet_commands_handlers.py` — General Commands, 📡 `dalet_events_handlers.py` — Global Events, ⚙️ `dalet_geminicommand.py` — AI Configuration, ❓ `dalet_helpcommands_handlers.py` — Help System, 📊 `dalet_smartresume.py` — AI Summaries, Handler Overview (+4 more)

### Community 35 - "🤖 `nlp_service.py` — Response Generator"
Cohesion: 0.11
Nodes (17): AI Providers, Authentication, Core Methods, Dalet's Personality, Fallback Chain, 🗂️ Files, `get_relevant_context(channel_id, user_id, current_message)`, 💾 `memory_service.py` — Memory System (+9 more)

### Community 36 - "All Variables"
Cohesion: 0.33
Nodes (6): All Variables, Base de Datos Principal (Turso / libSQL), Discord, IA de Alta Velocidad / Fallback (Groq), IA Primaria (Google Gemini), osu! API v2

### Community 37 - "🏛️ Tables"
Cohesion: 0.13
Nodes (14): `AIInteractions` — AI Performance Metrics, `Channels` — Discord Channels, `Messages` — Message History, `OsuAccounts` — Linked osu! Accounts, 🔒 Privacy System (`08_Privacy_TTL.sql`), 📋 Script Execution Order, `Servers` — Discord Servers, 🔧 SQL Functions (+6 more)

### Community 38 - "SQL Migration Guide for Neon (Dalet Restructuring)"
Cohesion: 0.33
Nodes (5): 1. Cleanup of Obsolete Audit Fragments (Optional but recommended), 2. View Updates, 3. Procedure and Function Update (CRITICAL), 4. Trigger Update, SQL Migration Guide for Neon (Dalet Restructuring)

### Community 39 - "SQLiteManager"
Cohesion: 0.19
Nodes (7): Connection, AnalyticsRepository, Repositorio para escritura de datos analíticos: CommandUsage, AIInteractions,…, Calcula estadísticas agregadas desde SQLite., Inserción masiva eficiente — usa una sola transacción., Crea las tablas si no existen. Se llama internamente con el lock activo., SQLiteManager

### Community 40 - "🔑 Environment Variables (`.env`)"
Cohesion: 0.40
Nodes (4): Archivo `.env` de Ejemplo, 🔑 Environment Variables (`.env`), How are these variables loaded in the code?, On Render (Production)

### Community 43 - "📝 `dalet_chatlogger.py` — The Message Logger"
Cohesion: 0.50
Nodes (4): Command `d.chatlog [count]`, 📝 `dalet_chatlogger.py` — The Message Logger, `on_message`, What does it do?

## Knowledge Gaps
- **107 isolated node(s):** `graphify`, `Workflow: graphify`, `✨ Features`, `🛠 Tech Stack`, `Prerequisites` (+102 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaletAtoms` connect `DaletAtoms` to `OsuHandler`, `SlashCommands`, `DaletReminders`, `AIConfigCommands`, `BaseRepository`, `.build_recent_card`?**
  _High betweenness centrality (0.166) - this node is a cross-community bridge._
- **Why does `DaletReminders` connect `DaletReminders` to `DaletAtoms`, `BaseRepository`?**
  _High betweenness centrality (0.099) - this node is a cross-community bridge._
- **Why does `DaletOrganisms` connect `DaletAtoms` to `OsuHandler`, `SlashCommands`, `DaletReminders`, `BaseRepository`, `.build_recent_card`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `DaletAtoms` (e.g. with `CommandsHandler` and `AIConfigCommands`) actually correct?**
  _`DaletAtoms` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `SlashCommands` (e.g. with `OsuPresenter` and `DaletAtoms`) actually correct?**
  _`SlashCommands` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `UserRepository` (e.g. with `BaseRepository` and `SQLiteManager`) actually correct?**
  _`UserRepository` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `DaletReminders` (e.g. with `ReminderRepository` and `TursoClient`) actually correct?**
  _`DaletReminders` has 4 INFERRED edges - model-reasoned connections that need verification._