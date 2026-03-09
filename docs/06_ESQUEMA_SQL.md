# 🗃️ Esquema SQL — Tablas, Vistas, Procedimientos y Funciones

> Todo lo que existe en la base de datos de Neon (PostgreSQL). Los scripts están en la carpeta `/sql/` y se numeran en orden de ejecución.

---

## 📋 Orden de los Scripts

| Script                        | Descripción                                 |
| ----------------------------- | ------------------------------------------- |
| `01_Schema.sql`               | Tablas base del sistema                     |
| `02_Data.sql`                 | Datos iniciales (si los hay)                |
| `03_Procedures_Functions.sql` | Procedimientos y funciones principales      |
| `04_Views.sql`                | Vistas de consulta                          |
| `05_Triggers.sql`             | Triggers de la BD                           |
| `06_Migration_LockSystem.sql` | Migración del sistema de bloqueo de canales |
| `07_Cleanup.sql`              | Eliminación de tablas o columnas obsoletas  |
| `08_Privacy_TTL.sql`          | Sistema de retención y purga de datos       |
| `09_Enhancements.sql`         | Mejoras de columnas existentes              |
| `10_New_Tables.sql`           | Tablas de analítica y métricas              |

---

## 🏛️ Tablas

### `Servers` — Servidores de Discord

```
ServerID    BIGINT  PK  → ID de Discord del servidor
ServerName  VARCHAR     → Nombre del servidor
IsReactive  BOOLEAN     → ¿Dalet responde a menciones? (defecto: TRUE)
```

### `Users` — Usuarios de Discord

```
UserID        BIGINT   PK → ID de Discord del usuario
UserName      VARCHAR     → Nombre del usuario
FirstSeen     TIMESTAMP   → Primera vez que habló (09_Enhancements)
LastSeen      TIMESTAMP   → Última vez que habló (09_Enhancements)
TotalMessages INT         → Contador total de mensajes (09_Enhancements)
```

### `Channels` — Canales de Discord

```
ChannelID       BIGINT   PK → ID de Discord del canal
ChannelName     VARCHAR     → Nombre del canal
ServerID        BIGINT   FK → A qué servidor pertenece
IsProactive     BOOLEAN     → ¿Dalet participa aquí automáticamente? (defecto: FALSE)
CommandsLocked  BOOLEAN     → ¿Están bloqueados los comandos aquí? (06_Migration)
TotalMessages   INT         → Contador de mensajes del canal (09_Enhancements)
LastActivity    TIMESTAMP   → Última actividad registrada (09_Enhancements)
```

### `Messages` — Historial de Mensajes

```
MessageID   SERIAL    PK → Auto-incremental
Content     TEXT         → Texto del mensaje
Timestamp   TIMESTAMP    → Cuándo se envió
UserID      BIGINT    FK → Quién lo envió
ChannelID   BIGINT    FK → En qué canal
ExpiresAt   TIMESTAMP    → Cuándo se puede eliminar (08_Privacy_TTL)
```

> Se purgan automáticamente mensajes con `ExpiresAt` en el pasado (TTL de 48h).

### `UserMemories` — Recuerdos Personales

```
MemoryID    SERIAL    PK → Auto-incremental
UserID      BIGINT    FK → A quién pertenece el recuerdo (CASCADE DELETE)
Topic       VARCHAR      → Categoría del recuerdo (defecto: 'general')
Content     TEXT         → Contenido del recuerdo
Timestamp   TIMESTAMP    → Cuándo se guardó
```

> Máximo 20 recuerdos por usuario (los más viejos se eliminan automáticamente).

### `Summaries` — Resúmenes de Chat

```
SummaryID      SERIAL    PK
GeneratedDate  TIMESTAMP    → Cuándo se generó
SummaryText    TEXT         → El resumen en texto
ChannelID      BIGINT    FK → Canal resumido
```

### `RolePermissions` — Roles con Permisos

```
PermissionID  SERIAL  PK
ServerID      BIGINT  FK  → En qué servidor
RoleID        BIGINT      → ID del rol de Discord
UNIQUE(ServerID, RoleID)
```

### `OsuAccounts` — Cuentas de osu! Vinculadas

```
UserID        BIGINT    PK+FK → Usuario de Discord
OsuUsername   VARCHAR         → Nick en osu!
OsuUserID     INT             → ID en osu!
PlayMode      VARCHAR         → 'osu', 'taiko', 'fruits', 'mania'
PP            FLOAT           → Performance Points actuales
GlobalRank    INT             → Ranking global
CountryRank   INT             → Ranking por país
Accuracy      FLOAT           → Precisión media (%)
LastUpdated   TIMESTAMP       → Última actualización (09_Enhancements)
```

### `OsuScores` — Scores Notables

```
ScoreID    BIGINT    PK → ID del score en osu!
UserID     BIGINT    FK
BeatmapID  INT          → ID del mapa
Score      INT          → Puntuación
Accuracy   FLOAT        → Precisión del score
Mods       VARCHAR      → Mods usados ('HD', 'DT', etc.)
ScoreType  VARCHAR      → 'best' o 'recent'
Timestamp  TIMESTAMP
```

### `CommandUsage` — Estadísticas de Comandos _(10_New_Tables)_

```
UsageID      SERIAL    PK
CommandName  VARCHAR      → Nombre del comando ('ms', 'lore', etc.)
UserID       BIGINT    FK
ServerID     BIGINT    FK
ChannelID    BIGINT
Success      BOOLEAN      → ¿Se ejecutó correctamente?
ExecutedAt   TIMESTAMP
```

### `OsuHistory` — Historial de PP/Rank _(10_New_Tables)_

```
HistoryID   SERIAL  PK
UserID      BIGINT  FK
LogDate     DATE       → Fecha del snapshot (máximo 1 por día por usuario)
PP          FLOAT
GlobalRank  INT
CountryRank INT
Accuracy    FLOAT
PlayMode    VARCHAR
RecordedAt  TIMESTAMP
UNIQUE(UserID, LogDate)
```

### `AIInteractions` — Métricas de IA _(10_New_Tables)_

```
InteractionID   SERIAL    PK
ServerID        BIGINT    FK
ChannelID       BIGINT    FK
TriggerType     VARCHAR   → 'mention', 'proactive', 'name_trigger'
Provider        VARCHAR   → 'gemini', 'groq', 'groq_fallback'
ResponseTimeMs  INT       → Latencia de la respuesta en ms
Success         BOOLEAN
InteractedAt    TIMESTAMP
```

### `BotErrors` — Errores Persistentes _(10_New_Tables)_

```
ErrorID     SERIAL    PK
ErrorType   VARCHAR      → 'discord_429', 'gemini_quota', 'db_error', etc.
ErrorMsg    TEXT         → Mensaje de la excepción (máx 2000 chars)
Context     VARCHAR      → Módulo donde ocurrió ('dalet_nlpchat.send_message')
ServerID    BIGINT       → Opcional, puede ser NULL
OccurredAt  TIMESTAMP
```

---

## 👁️ Vistas (Views)

Las vistas son consultas SQL guardadas como "tablas virtuales". Facilitan queries complejas.

| Vista                 | Descripción                                               |
| --------------------- | --------------------------------------------------------- |
| `V_ChannelMessages`   | JOIN de Messages + Users. Devuelve `username` y `content` |
| `V_UserSummaries`     | JOIN de Summaries + Channels                              |
| `V_UsersWithoutOsu`   | Usuarios que no han vinculado osu!                        |
| `V_OsuRankingGlobal`  | Ranking de jugadores por PP con `RANK()`                  |
| `V_ActiveChannels`    | Canales con más actividad (09_Enhancements)               |
| `V_CommandStats`      | Top comandos con tasa de éxito (10_New_Tables)            |
| `V_OsuTopImprovers`   | Jugadores con mayor ganancia de PP en 30 días             |
| `V_AIActivitySummary` | Resumen de actividad de la IA por servidor                |
| `V_AIHourlyActivity`  | Horas pico de actividad de la IA                          |
| `V_RecentErrors`      | Errores más frecuentes de los últimos 7 días              |

---

## ⚙️ Procedimientos Almacenados

Los procedimientos encapsulan lógica de escritura en la BD. Se llaman con `CALL sp_nombre(...)`.

| Procedimiento                                                                                 | Descripción                                                                |
| --------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `sp_RegisterOrUpdateUser(id, name)`                                                           | INSERT o UPDATE en Users                                                   |
| `sp_RegisterOrUpdateServer(id, name)`                                                         | INSERT o UPDATE en Servers                                                 |
| `sp_RegisterOrUpdateChannel(id, name, server_id)`                                             | INSERT o UPDATE en Channels                                                |
| `sp_LogMessage(user_id, username, server_id, server_name, channel_id, channel_name, content)` | Guarda un mensaje completo (llama a los 3 anteriores + INSERT en Messages) |
| `sp_LinkOsuAccount(user_id, ...)`                                                             | Vincula/actualiza cuenta de osu!                                           |
| `sp_UnlinkOsuAccount(user_id)`                                                                | Elimina la vinculación de osu!                                             |
| `sp_AddUserMemory(user_id, username, content, topic, max_memories)`                           | Añade recuerdo y elimina el más viejo si supera el límite                  |
| `sp_SetChannelProactive(channel_id, ..., is_proactive)`                                       | Activa/desactiva modo proactivo                                            |
| `sp_ClearProactiveChannels(server_id)`                                                        | Desactiva todos los canales proactivos                                     |
| `sp_SetServerReactive(server_id, ..., is_reactive)`                                           | Activa/desactiva modo reactivo                                             |
| `sp_SetChannelLock(channel_id, ..., is_locked)`                                               | Bloquea/desbloquea comandos en canal                                       |
| `sp_SaveSummary(channel_id, text, n_msgs)`                                                    | Guarda un resumen de chat                                                  |
| `sp_SaveOrUpdateOsuScore(...)`                                                                | Guarda un score de osu!                                                    |
| `sp_LogCommandUsage(...)`                                                                     | Registra uso de comando                                                    |
| `sp_LogAIInteraction(...)`                                                                    | Registra respuesta de IA                                                   |
| `sp_LogBotError(...)`                                                                         | Registra error crítico                                                     |
| `sp_RecordOsuSnapshot(...)`                                                                   | Guarda snapshot diario de osu!                                             |

---

## 🔧 Funciones SQL

Las funciones devuelven datos. Se llaman con `SELECT fn_nombre(...)`.

| Función                                         | Devuelve                    | Descripción                                  |
| ----------------------------------------------- | --------------------------- | -------------------------------------------- |
| `fn_GetOsuUsername(user_id)`                    | `VARCHAR`                   | Username de osu! vinculado                   |
| `fn_IsServerReactive(server_id)`                | `BOOLEAN`                   | ¿El servidor tiene IA reactiva?              |
| `fn_IsChannelProactive(channel_id)`             | `BOOLEAN`                   | ¿El canal tiene IA proactiva?                |
| `fn_IsChannelLocked(channel_id)`                | `BOOLEAN`                   | ¿Están bloqueados los comandos?              |
| `fn_GetRolePermissions(server_id)`              | `BIGINT[]`                  | Array de IDs de roles permitidos             |
| `fn_CheckRolePermission(server_id, role_ids[])` | `BOOLEAN`                   | ¿Alguno de esos roles tiene permiso?         |
| `fn_GetProactiveChannels(server_id)`            | `BIGINT[]`                  | Canales con IA proactiva                     |
| `fn_GetAllUserMemories(user_id)`                | Tabla de `(topic, content)` | Todos los recuerdos del usuario              |
| `fn_GetRecentSummaries(channel_id, limit)`      | Tabla de `(date, text)`     | Últimos N resúmenes                          |
| `fn_GetSummaryByIndex(channel_id, index)`       | `TEXT`                      | Resumen por índice (1 = más reciente)        |
| `fn_GetUserStats(user_id)`                      | Tabla de stats              | Contador de mensajes y scores                |
| `fn_GetScoreHistory(user_id, limit)`            | Tabla de scores             | Historial de accuracy                        |
| `fn_PurgeExpiredMessages()`                     | `INT`                       | Elimina mensajes expirados, devuelve cuántos |
| `fn_GetOsuProgress(user_id, limit)`             | Tabla con PP histórico      | Progreso de PP con diferencia diaria         |

---

## 🔒 Sistema de Privacidad (`08_Privacy_TTL.sql`)

Los mensajes tienen una columna `ExpiresAt` que se calcula como `Timestamp + INTERVAL '48 hours'`.

La función `fn_PurgeExpiredMessages()` elimina todos los mensajes donde `ExpiresAt < NOW()`.

Se ejecuta automáticamente cada hora desde `dalet_main.py`. Esto asegura que el historial de mensajes nunca tenga más de 48 horas de antigüedad.

> **¿Por qué 48h?** Es suficiente para el contexto de IA (nadie necesita que el bot recuerde una conversación de hace 3 días) y protege la privacidad de los usuarios.
