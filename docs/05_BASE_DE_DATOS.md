# 🗄️ Base de Datos — Pool y Repositorios

> Esta capa conecta el bot con PostgreSQL. Está diseñada para ser **rápida, resiliente y fácil de usar** desde el resto del código.

---

## 📐 Jerarquía de Clases

```
DatabasePool (Singleton)
      │
      └── asyncpg connection pool
               │
               ├── BaseRepository
               │     ├── UserRepository      (usuarios, mensajes, memorias)
               │     ├── AdminRepository     (bloqueo de canales)
               │     └── OsuRepository       (cuentas y scores de osu!)
               │
               └── AnalyticsRepository       (métricas — sin herencia de Base)
```

---

## 🔌 `database/pool.py` — El Pool de Conexiones

### ¿Qué es un "pool"?

En vez de abrir/cerrar una conexión a la BD en cada consulta (lo cual es lento), un "pool" mantiene un conjunto de conexiones **abiertas y listas** para usar.

```python
cls._pool = await asyncpg.create_pool(
    DATABASE_URL,
    min_size=1,   # Siempre habrá al menos 1 conexión abierta
    max_size=5,   # Máximo 5 conexiones simultáneas
    command_timeout=60  # Una consulta no puede tardar más de 60s
)
```

### `DatabasePool` (Singleton)

Es un **Singleton**: solo existe una instancia del pool en todo el proceso. La primera vez que se llama a `get_pool()`, crea el pool. Las siguientes veces, devuelve el mismo.

```python
pool = await DatabasePool.get_pool()  # Primer acceso: crea el pool
pool = await DatabasePool.get_pool()  # Accesos posteriores: retorna el mismo pool
```

### `get_db()`

Función de conveniencia. Es simplemente un alias de `DatabasePool.get_pool()`.

---

## 🏗️ `base_repository.py` — La Clase Base

Define los **4 métodos SQL fundamentales** que todos los repositorios comparten:

| Método                        | Equivalente SQL                 | Retorna                             |
| ----------------------------- | ------------------------------- | ----------------------------------- |
| `execute(query, *args)`       | INSERT, UPDATE, DELETE          | `None` (no devuelve filas)          |
| `fetch_one(query, *args)`     | SELECT ... LIMIT 1              | Un `Record` (como un dict) o `None` |
| `fetch_all(query, *args)`     | SELECT ...                      | Lista de `Record`s                  |
| `call_procedure(name, *args)` | `CALL procedimiento($1, $2...)` | —                                   |

### Parámetros con `$1`, `$2`...

asyncpg usa **parámetros posicionales** (`$1`, `$2`...) en vez de `?` o `%s`. Son más seguros y eficientes.

```python
# ✅ Correcto (parameterized, seguro contra SQL Injection)
await conn.fetch("SELECT * FROM Users WHERE UserID = $1", user_id)

# ❌ Nunca hacer esto
await conn.fetch(f"SELECT * FROM Users WHERE UserID = {user_id}")
```

---

## 👤 `user_repository.py` — El Repositorio Principal

El más complejo. Maneja usuarios, mensajes, memorias y configuración de proactividad.

### Sistema de Caché (`_get_cached`)

Para evitar consultar la BD en cada mensaje, algunas queries tienen caché en RAM con TTL de 5 minutos:

```python
_cache = {}      # {key: (valor, timestamp_expira)}
_cache_ttl = 300 # 5 minutos
```

Métodos cacheados:

- `is_server_reactive(server_id)` → clave: `reactive_{server_id}`
- `is_channel_proactive(channel_id)` → clave: `proactive_{channel_id}`
- `get_all_user_memories(user_id)` → clave: `memories_{user_id}`

### Sistema de Batch Logging (`_log_buffer` + `_flushing_logs`)

El guardado de mensajes es el punto con más tráfico. En vez de hacer una INSERT por cada mensaje, se acumulan y se guardan en lote:

```python
_log_buffer = []         # Buffer activo (se va llenando con mensajes nuevos)
_flushing_logs = []      # Buffer temporal durante la escritura en BD
_flush_interval = 60     # Cada 60 segundos
_max_buffer_size = 20    # O cuando llega a 20 mensajes
```

**¿Por qué dos buffers?**

Cuando `flush_logs()` empieza a escribir en la BD, mueve `_log_buffer` a `_flushing_logs` y limpia el activo. Durante esa escritura, `get_channel_messages()` puede ver AMBOS buffers, garantizando que ningún mensaje se pierda.

```
Estado normal:      Estado durante flush:
_log_buffer = [A,B,C]      _log_buffer = [D,E] (nuevos)
_flushing_logs = []         _flushing_logs = [A,B,C] (escribiendo en BD)
```

### `get_channel_messages(channel_id, limit=20)`

Combina tres fuentes, de más reciente a más antigua:

```
1. _log_buffer     (mensajes recién llegados, sin persistir)
2. _flushing_logs  (mensajes en proceso de escritura)
3. BD              (mensajes ya guardados)
```

El resultado se devuelve como lista de dicts: `[{'username': str, 'content': str}]`

### Métodos Principales

| Método                                    | Descripción                                          |
| ----------------------------------------- | ---------------------------------------------------- |
| `log_message(...)`                        | Añade un mensaje al buffer (no escribe directamente) |
| `flush_logs()`                            | Vacía el buffer → escribe en BD con `sp_LogMessage`  |
| `_periodic_flush()`                       | Tarea asyncio que llama `flush_logs()` cada 60s      |
| `get_channel_messages(channel_id, limit)` | Historial del canal (buffer + BD)                    |
| `is_server_reactive(server_id)`           | ¿El servidor tiene IA reactiva? (con caché)          |
| `is_channel_proactive(channel_id)`        | ¿El canal tiene IA proactiva? (con caché)            |
| `add_user_memory(user_id, ...)`           | Guarda un recuerdo en `UserMemories`                 |
| `get_all_user_memories(user_id)`          | Todos los recuerdos del usuario (con caché)          |
| `search_lore(query, channel_id)`          | Búsqueda de texto en `Messages` (para `d.lore`)      |

---

## 🛡️ `admin_repository.py` — Bloqueo de Canales

Repositorio muy sencillo, solo dos métodos:

| Método                              | Descripción                                            |
| ----------------------------------- | ------------------------------------------------------ |
| `is_channel_locked(channel_id)`     | ¿Está bloqueado el canal? → `fn_IsChannelLocked($1)`   |
| `set_channel_lock(channel_id, ...)` | Activa/desactiva el bloqueo → `sp_SetChannelLock(...)` |

---

## 🎮 `osu_repository.py` — Datos de osu!

| Método                         | Descripción                                                 |
| ------------------------------ | ----------------------------------------------------------- |
| `get_linked_username(user_id)` | Obtiene el username de osu! vinculado al usuario de Discord |
| `link_account(...)`            | Vincula/actualiza una cuenta de osu! → `sp_LinkOsuAccount`  |
| `unlink_account(user_id)`      | Desvincula la cuenta de osu! → `sp_UnlinkOsuAccount`        |
| `save_score(...)`              | Guarda un score notable → `sp_SaveOrUpdateOsuScore`         |
| `get_ranking(limit)`           | Top jugadores por PP → `V_OsuRankingGlobal`                 |
| `get_score_history(user_id)`   | Historial de accuracy/scores → `fn_GetScoreHistory`         |

---

## 📊 `analytics_repository.py` — Métricas y Errores

Diseñado para ser **fire-and-forget**: si una escritura de analítica falla, se registra un WARNING en los logs pero **nunca lanza una excepción** ni interrumpe el bot.

| Método                      | Descripción                      | Tabla/Procedimiento                      |
| --------------------------- | -------------------------------- | ---------------------------------------- |
| `log_command(...)`          | Registra uso de un comando       | `sp_LogCommandUsage` → `CommandUsage`    |
| `log_ai_interaction(...)`   | Registra una respuesta de la IA  | `sp_LogAIInteraction` → `AIInteractions` |
| `log_error(...)`            | Registra un error crítico        | `sp_LogBotError` → `BotErrors`           |
| `record_osu_snapshot(...)`  | Guarda snapshot de stats de osu! | `sp_RecordOsuSnapshot` → `OsuHistory`    |
| `get_osu_progress(user_id)` | Historial de PP de un jugador    | `fn_GetOsuProgress`                      |

### Parámetros de `log_ai_interaction`

- `trigger_type`: `"mention"` | `"proactive"` | `"name_trigger"`
- `provider`: `"gemini"` | `"groq"` | `"groq_fallback"`
