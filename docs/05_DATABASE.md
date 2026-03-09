# 🗄️ Database — Connection Pool & Repositories

> This layer connects the bot to PostgreSQL. It is built to be **fast, resilient, and easy to use** throughout the codebase.

---

## 📐 Class Hierarchy

```
DatabasePool (Singleton)
      │
      └── asyncpg connection pool
               │
               ├── BaseRepository
               │     ├── UserRepository      (users, messages, memories)
               │     ├── AdminRepository     (channel locks)
               │     └── OsuRepository       (osu! accounts and scores)
               │
               └── AnalyticsRepository       (metrics — separate from Base)
```

---

## 🔌 `database/pool.py` — The Connection Pool

### What is a "pool"?

Instead of opening and closing a database connection for every single query (which is slow), a "pool" maintains a set of **open and ready-to-use** connections.

```python
cls._pool = await asyncpg.create_pool(
    DATABASE_URL,
    min_size=1,   # Always keeps at least 1 connection open
    max_size=5,   # Maximum of 5 simultaneous connections
    command_timeout=60  # Any single query is capped at 60s
)
```

### `DatabasePool` (Singleton)

Implemented as a **Singleton**: only one pool instance exists across the entire process. The first call to `get_pool()` initializes the pool, while subsequent calls return the same instance.

```python
pool = await DatabasePool.get_pool()  # First access: initializes pool
pool = await DatabasePool.get_pool()  # Subsequent accesses: returns existing pool
```

### `get_db()`

A convenience function acting as an alias for `DatabasePool.get_pool()`.

---

## 🏗️ `base_repository.py` — The base class

Defines **4 core SQL methods** used by all repositories:

| Method | SQL Equivalent | Returns |
| ------ | -------------- | ------- |
| `execute(query, *args)` | INSERT, UPDATE, DELETE | `None` (no rows) |
| `fetch_one(query, *args)` | SELECT ... LIMIT 1 | A `Record` object (dict-like) or `None` |
| `fetch_all(query, *args)` | SELECT ... | A list of `Record` objects |
| `call_procedure(name, *args)` | `CALL procedure($1, $2...)` | — |

### Parameters using `$1`, `$2`...

`asyncpg` uses **positional parameters** (`$1`, `$2`, etc.) instead of `?` or `%s`. This is both more secure and efficient.

```python
# ✅ Correct (parameterized, safe from SQL Injection)
await conn.fetch("SELECT * FROM Users WHERE UserID = $1", user_id)

# ❌ Never do this
await conn.fetch(f"SELECT * FROM Users WHERE UserID = {user_id}")
```

---

## 👤 `user_repository.py` — Main Repository

The most complex repository. It handles users, messages, memories, and proactive AI settings.

### Caching System (`_get_cached`)

To prevent excessive database calls for every message, some common queries are cached in RAM with a 5-minute TTL:

```python
_cache = {}      # {key: (value, expiration_timestamp)}
_cache_ttl = 300 # 5 minutes
```

Cached methods include:

- `is_server_reactive(server_id)` → key: `reactive_{server_id}`
- `is_channel_proactive(channel_id)` → key: `proactive_{channel_id}`
- `get_all_user_memories(user_id)` → key: `memories_{user_id}`

### Batch Logging System (`_log_buffer` + `_flushing_logs`)

Message logging handles the highest traffic. Instead of one INSERT per message, they are gathered and stored in batches:

```python
_log_buffer = []         # Active buffer (fills up as new messages arrive)
_flushing_logs = []      # Temporary buffer during database write
_flush_interval = 60     # Every 60 seconds
_max_buffer_size = 20    # Or whenever 20 messages are reached
```

**Why two buffers?**

When `flush_logs()` starts writing to the database, it moves the contents of `_log_buffer` to `_flushing_logs` and clears the active buffer. During this write, `get_channel_messages()` can look into BOTH buffers, ensuring no messages are missed.

### `get_channel_messages(channel_id, limit=20)`

Combines three sources, from newest to oldest:

1. **`_log_buffer`** (brand new, non-persisted messages)
2. **`_flushing_logs`** (messages in the middle of being written)
3. **Database** (previously persisted messages)

---

## 🛡️ `admin_repository.py` — Channel Locks

A straightforward repository with two primary methods:

- `is_channel_locked(channel_id)`: Checks if the channel is currently locked.
- `set_channel_lock(channel_id, ...)`: Enables or disables the channel lock via the `sp_SetChannelLock` procedure.

---

## 🎮 `osu_repository.py` — osu! Data

- `get_linked_username(user_id)`: Retrieves the osu! username linked to a Discord ID.
- `link_account(...)`: Links or updates an osu! account.
- `unlink_account(user_id)`: Unlinks an osu! account.
- `save_score(...)`: Persists a notable score.
- `get_ranking(limit)`: Fetches top players by PP via `V_OsuRankingGlobal`.

---

## 📊 `analytics_repository.py` — Metrics & Tracking

Designed as **fire-and-forget**: if an analytical write fails, it logs a WARNING but **never throws an exception** that would interrupt the bot's core functionality.

- `log_command(...)`: Tracks bot command usage.
- `log_ai_interaction(...)`: Records an AI response (includes trigger type and provider).
- `log_error(...)`: Logs serious bot errors to the database.
- `record_osu_snapshot(...)`: Saves a snapshot of osu! statistics for historical tracking.
