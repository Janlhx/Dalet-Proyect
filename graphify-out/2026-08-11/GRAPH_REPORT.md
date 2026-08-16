# Graph Report - .  (2026-08-11)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 523 nodes · 941 edges · 35 communities (32 shown, 3 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 40 edges (avg confidence: 0.5)
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
- SQLiteManager
- DaletAtoms
- CommandsHandler
- DatabasePool
- EventsHandler
- DaletNLPChat
- .is_available
- HelpPaginator
- AdminRepository
- ChatLogger
- dalet_main.py
- UniversalPaginator
- .fetch_all
- DaletGreetings
- ResumenInteligente
- MemoryService
- .add_standard_footer
- .send_bot_help
- PageInputModal
- .check_reminders
- .create_button
- .get_rank_color

## God Nodes (most connected - your core abstractions)
1. `SlashCommands` - 27 edges
2. `DaletAtoms` - 25 edges
3. `DaletReminders` - 23 edges
4. `UserRepository` - 22 edges
5. `OsuHandler` - 21 edges
6. `DaletOrganisms` - 20 edges
7. `AdminCommands` - 18 edges
8. `OsuService` - 17 edges
9. `SQLiteManager` - 17 edges
10. `DatabasePool` - 16 edges

## Surprising Connections (you probably didn't know these)
- `OsuHandler` --uses--> `DaletAtoms`  [INFERRED]
  handlers/dalet_osucommands.py → ui/atoms.py
- `OsuHandler` --uses--> `DaletOrganisms`  [INFERRED]
  handlers/dalet_osucommands.py → ui/organisms.py
- `SlashCommands` --uses--> `DatabasePool`  [INFERRED]
  handlers/dalet_slash_commands.py → database/pool.py
- `SlashCommands` --uses--> `DaletAtoms`  [INFERRED]
  handlers/dalet_slash_commands.py → ui/atoms.py
- `SlashCommands` --uses--> `DaletOrganisms`  [INFERRED]
  handlers/dalet_slash_commands.py → ui/organisms.py

## Import Cycles
- None detected.

## Communities (35 total, 3 thin omitted)

### Community 0 - "OsuHandler"
Cohesion: 0.08
Nodes (24): File, _acc_str(), _mods_str(), OsuHandler, command, Member, _rank_color(), Vincula tu cuenta de Discord con tu perfil de osu!. (+16 more)

### Community 1 - "SlashCommands"
Cohesion: 0.16
Nodes (13): choices, Bot, command, describe, has_permissions, Interaction, Member, TextChannel (+5 more)

### Community 2 - "DaletReminders"
Cohesion: 0.12
Nodes (20): autocomplete, Choice, DaletReminders, format_days_readable(), parse_date(), parse_days(), parse_days_or_date(), parse_time() (+12 more)

### Community 3 - "OsuAnalyzer"
Cohesion: 0.08
Nodes (15): OsuRepository, OsuAnalyzer, Módulo de Lógica de Análisis de osu! (v4.1) Esta versión corrige el 'edge case'…, Analiza los 'recent plays' para detectar la consistencia del accuracy. (BUG…, Analiza los 'recent plays' (Últimos 50) para detectar el estilo ACTUAL., Analiza las propiedades de los mapas en los 'recent plays' (Últimos 50)., Determina el área de enfoque (debilidad) de manera inteligente. Calcula una…, Analiza datos de osu! (v4.1) y genera prompts detallados para la IA. (+7 more)

### Community 4 - "AdminCommands"
Cohesion: 0.11
Nodes (17): AdminCommands, command, has_permissions, [ADMIN] Cambia mi nombre en este servidor (máx 25 caracteres)., Comandos para administrar el bot y depurar la base de datos., [ADMIN] Establece el canal actual para las bienvenidas y despedidas., [ADMIN] Desactiva las bienvenidas y despedidas en el servidor., Muestra el estado de seguridad y IA del canal actual. (+9 more)

### Community 5 - "AIConfigCommands"
Cohesion: 0.11
Nodes (17): group, AIConfigCommands, command, has_permissions, TextChannel, 🤖 [ADMIN] Configura en qué canales Dalet puede participar automáticamente en…, 💬 [ADMIN] Controla si Dalet responde cuando la mencionan en conversaciones., Activa la respuesta de Dalet a su nombre. (+9 more)

### Community 6 - "OsuService"
Cohesion: 0.12
Nodes (11): OsuService, Información de un beatmap específico., Top scores globales de un beatmap., Busca beatmaps con filtros., Perfil completo de un usuario., Perfil de un usuario por ID numérico., Top plays del usuario., Jugadas recientes del usuario. (+3 more)

### Community 7 - "UserRepository"
Cohesion: 0.14
Nodes (5): Inicia la tarea de vaciado del buffer si no está activa., UserRepository, NLPService, Recorta el contexto a las últimas REACTIVE_MAX_CONTEXT_LINES líneas del canal.…, Describe brevemente una imagen usando Gemini (solo 1 para ahorrar cuota).

### Community 8 - "SQLiteManager"
Cohesion: 0.14
Nodes (11): Connection, Cursor, AnalyticsRepository, Registra la ejecución de un comando en SQLite., Registra una respuesta de la IA en SQLite., Registra un error crítico del bot en SQLite., Repositorio para escritura de datos analíticos: CommandUsage, AIInteractions,…, Guarda un snapshot del perfil osu! del jugador en SQLite. (+3 more)

### Community 9 - "DaletAtoms"
Cohesion: 0.21
Nodes (12): CustomHelpCommand, Handler (Cog) para el Comando de Ayuda Personalizado. Este archivo reemplaza el…, Clase que sobreescribe el comando de ayuda por defecto de Discord. Genera una…, setup(), Slash Commands (Application Commands) de Dalet. Duplica los comandos de prefijo…, DaletAtoms, Los ladrillos básicos de la identidad visual de Dalet., DaletMolecules (+4 more)

### Community 10 - "CommandsHandler"
Cohesion: 0.14
Nodes (12): cooldown, CommandsHandler, command, Member, Comandos básicos de Dalet (utilidades, info y herramientas generales)., 🏓 Muestra la latencia del bot en milisegundos., 📊 Muestra tus estadísticas sociales o las de otro usuario., Muestra información detallada de un usuario del servidor. (+4 more)

### Community 11 - "DatabasePool"
Cohesion: 0.23
Nodes (5): DatabasePool, get_db(), Devuelve el pool. Puede devolver None si la BD no está disponible., BaseRepository, ReminderRepository

### Community 12 - "EventsHandler"
Cohesion: 0.14
Nodes (12): Guild, EventsHandler, listener, Member, Handler de Eventos Globales de Discord. Maneja: on_ready, on_command_error,…, Saluda a los nuevos miembros con personalidad de Dalet., Despide a quien se va con el tono característico de Dalet., Agrupa los listeners de eventos globales del bot. (+4 more)

### Community 13 - "DaletNLPChat"
Cohesion: 0.16
Nodes (10): DaletNLPChat, listener, Message, Centraliza el manejo de errores 429 con backoff exponencial., Decide si el bot debe responder proactivamente en este mensaje., Maneja el listener 'on_message' para las respuestas de IA., Registra la interacción de IA en BD de forma no-bloqueante., Aplica un rate limiter usando Token Bucket. Límite por canal: máx 5 tokens, se… (+2 more)

### Community 14 - ".is_available"
Cohesion: 0.14
Nodes (7): Devuelve True si la BD está conectada y disponible., Obtiene un recordatorio específico por su ID., Elimina un recordatorio de la base de datos (Postgres y SQLite fallback)., Guarda un nuevo recordatorio en la base de datos remota PostgreSQL (Neon) o…, Activa/desactiva un recordatorio. Retorna el nuevo estado., Actualiza los campos especificados en `updates` para el recordatorio…, Calcula estadísticas agregadas desde SQLite.

### Community 15 - "HelpPaginator"
Cohesion: 0.25
Nodes (8): HelpPaginator, button, Interaction, Una Vista de Discord (UI) que maneja los botones de paginación. Controla los…, Activa o desactiva los botones según la página actual., Edita el mensaje de Discord para mostrar la página actual., Abre el Modal 'PageInputModal'., View

### Community 16 - "AdminRepository"
Cohesion: 0.15
Nodes (7): AdminRepository, Activa o desactiva el bloqueo de comandos en un canal., Obtiene el nombre personalizado del bot para un servidor., Establece un nombre personalizado para el bot en un servidor., Obtiene el ID del canal de bienvenida de un servidor., Establece o elimina el canal de bienvenida para un servidor., Verifica si los comandos están bloqueados en un canal.

### Community 17 - "ChatLogger"
Cohesion: 0.17
Nodes (9): ChatLogger, command, has_permissions, listener, Message, Guarda mensajes de usuarios (no comandos, no bots) en el buffer de SQLite., [ADMIN] Muestra los últimos mensajes guardados en este canal., Registra mensajes en SQLite para memoria de contexto e historial. El on_message… (+1 more)

### Community 18 - "dalet_main.py"
Cohesion: 0.23
Nodes (8): home(), keep_alive(), load_extensions(), main(), run_flask(), Devuelve el pool de conexiones. Si la BD no está disponible, devuelve None.…, main(), route

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

### Community 24 - ".add_standard_footer"
Cohesion: 0.25
Nodes (4): Añade el footer característico de Dalet a un embed., Organismo para mostrar estadísticas sociales del usuario., Organismo complejo para mostrar el perfil de osu!., Organismo para visualizar los recuerdos guardados.

### Community 26 - "PageInputModal"
Cohesion: 0.33
Nodes (4): PageInputModal, Un Modal (ventana emergente) que pide al usuario un número de página., Valida el número y salta a la página de categoría correspondiente., Modal

### Community 27 - ".check_reminders"
Cohesion: 0.40
Nodes (3): Tarea en segundo plano que revisa y dispara los recordatorios., Envía el mensaje de recordatorio al canal correspondiente., loop

## Knowledge Gaps
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DaletAtoms` connect `DaletAtoms` to `OsuHandler`, `SlashCommands`, `DaletReminders`, `AIConfigCommands`, `CommandsHandler`, `DatabasePool`, `HelpPaginator`, `.send_bot_help`, `PageInputModal`, `.get_rank_color`?**
  _High betweenness centrality (0.207) - this node is a cross-community bridge._
- **Why does `DatabasePool` connect `DatabasePool` to `SlashCommands`, `DaletReminders`, `AdminCommands`, `DaletAtoms`, `.is_available`, `dalet_main.py`?**
  _High betweenness centrality (0.190) - this node is a cross-community bridge._
- **Why does `DaletReminders` connect `DaletReminders` to `.check_reminders`, `DaletAtoms`, `DatabasePool`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `SlashCommands` (e.g. with `DatabasePool` and `DaletAtoms`) actually correct?**
  _`SlashCommands` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `DaletAtoms` (e.g. with `CommandsHandler` and `AIConfigCommands`) actually correct?**
  _`DaletAtoms` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `DaletReminders` (e.g. with `DatabasePool` and `ReminderRepository`) actually correct?**
  _`DaletReminders` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `UserRepository` (e.g. with `BaseRepository` and `SQLiteManager`) actually correct?**
  _`UserRepository` has 3 INFERRED edges - model-reasoned connections that need verification._