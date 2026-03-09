# 🗃️ SQL Schema — Tables, Views, Procedures, & Functions

> Everything that exists in the Neon PostgreSQL database. Scripts are located in the `/sql/` folder and numbered in execution order.

---

## 📋 Script Execution Order

| Script | Description |
| ------ | ----------- |
| `01_Schema.sql` | Base system tables |
| `02_Data.sql` | Initial seed data (if applicable) |
| `03_Procedures_Functions.sql` | Core stored procedures and functions |
| `04_Views.sql` | Query views |
| `05_Triggers.sql` | Database triggers |
| `06_Migration_LockSystem.sql` | Channel locking system migration |
| `07_Cleanup.sql` | Removal of obsolete tables or columns |
| `08_Privacy_TTL.sql` | Automated data retention and purge system |
| `09_Enhancements.sql` | Improvements to existing columns |
| `10_New_Tables.sql` | Analytics and metrics tables |

---

## 🏛️ Tables

### `Servers` — Discord Servers

- `ServerID` (BIGINT PK): Discord status ID.
- `ServerName` (VARCHAR): Server name.
- `IsReactive` (BOOLEAN): Does Dalet reply to mentions? (Default: TRUE).

### `Users` — Discord Users

- `UserID` (BIGINT PK): Discord user ID.
- `UserName` (VARCHAR): User's current name.
- `FirstSeen` (TIMESTAMP): Date of first interaction.
- `LastSeen` (TIMESTAMP): Date of last interaction.
- `TotalMessages` (INT): Lifetime message counter.

### `Channels` — Discord Channels

- `ChannelID` (BIGINT PK): Discord channel ID.
- `ChannelName` (VARCHAR): Channel name.
- `ServerID` (BIGINT FK): Parent server.
- `IsProactive` (BOOLEAN): Does Dalet participate automatically? (Default: FALSE).
- `CommandsLocked` (BOOLEAN): Are commands disabled here?

### `Messages` — Message History

- `MessageID` (SERIAL PK): Auto-incrementing ID.
- `Content` (TEXT): Message content.
- `Timestamp` (TIMESTAMP): Sent-at date.
- `UserID` (BIGINT FK): Message author.
- `ChannelID` (BIGINT FK): Origin channel.
- `ExpiresAt` (TIMESTAMP): When the message can be deleted (Privacy system).

> Messages older than 48 hours are automatically purged to protect user privacy.

### `UserMemories` — Personal Memories

- `MemoryID` (SERIAL PK): Auto-incrementing ID.
- `UserID` (BIGINT FK): Owner of the memory (CASCADE DELETE).
- `Topic` (VARCHAR): Memory category (Default: 'general').
- `Content` (TEXT): Memory content.
- `Timestamp` (TIMESTAMP): Date saved.

> Limit: Maximum 20 memories per user; oldest memories are automatically removed.

### `OsuAccounts` — Linked osu! Accounts

- `UserID` (BIGINT PK+FK): Linked Discord user.
- `OsuUsername` (VARCHAR): osu! handle.
- `PP` (FLOAT): Current Performance Points.
- `GlobalRank` (INT): Global standing.
- `Accuracy` (FLOAT): Average hits (%) accuracy.

### `AIInteractions` — AI Performance Metrics

- `InteractionID` (SERIAL PK): Auto-incrementing ID.
- `TriggerType` (VARCHAR): 'mention', 'proactive', or 'name_trigger'.
- `Provider` (VARCHAR): 'gemini', 'groq', or 'groq_fallback'.
- `ResponseTimeMs` (INT): Generation latency in milliseconds.
- `InteractedAt` (TIMESTAMP): Timestamp of the interaction.

---

## 👁️ Views

Views simplify complex queries into developer-friendly "virtual tables."

| View | Description |
| ---- | ----------- |
| `V_ChannelMessages` | JOIN of Messages + Users. Returns `username` and `content`. |
| `V_OsuRankingGlobal` | Global leaderboard of linked accounts ranked by PP. |
| `V_CommandStats` | Command usage metrics with success rates. |
| `V_AIActivitySummary` | AI interaction breakdown per server. |
| `V_RecentErrors` | Frequent bot errors from the last 7 days. |

---

## ⚙️ Stored Procedures

Procedures encapsulate write logic. They are called using `CALL sp_name(...)`.

- `sp_LogMessage(...)`: Records a message (updates User, Server, and Channel info).
- `sp_LinkOsuAccount(...)`: Atomically links/updates an osu! profile.
- `sp_AddUserMemory(...)`: Saves a memory while maintaining the 20-count limit.
- `sp_SetChannelProactive(...)`: Configures proactive AI status.
- `sp_LogCommandUsage(...)`: Records command execution metrics.
- `sp_LogAIInteraction(...)`: Records AI latency and status.

---

## 🔧 SQL Functions

Functions return data and are typically called via `SELECT fn_name(...)`.

- `fn_IsServerReactive(server_id)`: Returns if mentions are enabled.
- `fn_IsChannelLocked(channel_id)`: Returns if bot commands are disabled.
- `fn_GetAllUserMemories(user_id)`: Returns all memories for semantic search.
- `fn_PurgeExpiredMessages()`: Deletes messages older than 48h; returns deleted count.
- `fn_GetOsuProgress(user_id)`: Returns historical PP data for progress tracking.

---

## 🔒 Privacy System (`08_Privacy_TTL.sql`)

Messages include an `ExpiresAt` column calculated as `Timestamp + INTERVAL '48 hours'`.

The `fn_PurgeExpiredMessages()` function deletes all entries where `ExpiresAt < NOW()`.

This is triggered hourly by `dalet_main.py` to ensure that conversational history never persists beyond 48 hours.

> **Why 48h?** It's the ideal window for AI conversational context (no one needs the bot to remember a 3-day-old casual chat) while strictly adhering to user privacy standards.
