# 🏗️ General Architecture of Dalet

> This document explains the "big picture": how all the bot's pieces are connected and the data flow when someone interacts with Dalet.

---

## 🧠 What is Dalet?

Dalet is an asynchronous Discord bot built on top of **discord.py**. It has three main capabilities:

1. **Conversational AI**: Responds to messages using Google Gemini (or Groq as a fallback).
2. **Persistent Memory**: Remembers information about users and chat history using a PostgreSQL database hosted on Neon.
3. **osu! Integration**: Queries game statistics from osu! using its official API.

---

## ⚙️ Tech Stack

| Technology | Purpose |
| ---------- | ------- |
| **Python 3.x** | Primary language |
| **discord.py** | Library for interacting with the Discord API |
| **asyncpg** | Asynchronous driver for PostgreSQL (faster than psycopg2 for bots) |
| **PostgreSQL (Neon)** | Cloud database. Neon provides a free tier with automatic "sleep" |
| **Google Gemini API** | Primary AI model (Gemini 2.0 Flash) |
| **Groq API** | Fallback AI model (Llama 3.3 70B) |
| **Flask** | Minimal HTTP server for Render's Health Check |
| **Render** | Deployment platform for the bot in the cloud |

---

## 🔄 Main Flow: "What happens when someone mentions Dalet?"

```
User types "@Dalet hello"
          │
          ▼
[Discord API] ─── on_message event ──► [dalet_nlpchat.py]
                                               │
                                     ┌─────────┴────────────┐
                                     │  Is it on cooldown?  │
                                     │  Is it a mention?   │
                                     └─────────┬────────────┘
                                               │ Yes → Generate response
                                               ▼
                                     [memory_service.py]
                                     get_relevant_context()
                                     ┌────────────────────────────────┐
                                     │ 1. In-memory log buffer        │
                                     │ 2. Logs currently flushing     │
                                     │ 3. DB (V_ChannelMessages)      │
                                     │ 4. Cog local_history           │
                                     │ 5. User memories               │
                                     └──────────────┬─────────────────┘
                                                    │ context string
                                                    ▼
                                          [nlp_service.py]
                                          generate_reply()
                                          ┌──────────────────────────┐
                                          │  Is Gemini available?    │
                                          │  → Call Gemini 2.0 Flash │
                                          │  Quota exceeded?         │
                                          │  → Fallback to Groq      │
                                          └──────────┬───────────────┘
                                                     │ response text
                                                     ▼
                                          [dalet_nlpchat.py]
                                          ┌───────────────────────────┐
                                          │ Contains [SAVE_MEMORY:]?  │
                                          │ → Save to UserMemories    │
                                          │ Contains [ACTION:]?       │
                                          │ → Execute command         │
                                          └──────────┬────────────────┘
                                                     │
                                                     ▼
                                          message.channel.send(reply)
                                          [Discord API] → User
```

---

## 🗄️ Message Logging Flow (Batch Logging)

To avoid overloading the Neon database with a query for every single message, a **buffer + flush** system is used:

```
User sends a message
        │
        ▼
[dalet_chatlogger.py] on_message
        │
        ▼
user_repo.log_message()
        │
        ▼
[_log_buffer] ← Message is stored in RAM first
        │
        ├── Buffer full (≥20 msgs)? → Immediate flush_logs()
        │
        └── [_periodic_flush] (every 60s) → Scheduled flush_logs()
                │
                ▼
        sp_LogMessage() × N calls in ONE transaction → Neon DB
```

> **Why does this matter for the AI?**  
> While messages are in the buffer (before flushing), they are NOT in the database. Therefore, `get_channel_messages()` combines the buffer, the flushing state, AND the database to always provide full context.

---

## 🧩 Design Pattern: Cogs

discord.py uses the **Cog** concept. A Cog is simply a Python class that groups related commands and events. Dalet automatically loads all Cogs from the `/handlers/` folder at startup.

Advantages:

- You can **reload a single Cog** (`d.reload handlers.dalet_nlpchat`) without restarting the entire bot.
- Code is organized by responsibility.

---

## 🗺️ Design Pattern: Repository

The database layer follows the **Repository Pattern**:

```
Handlers/Services              Repository               Database
─────────────────             ────────────             ──────────────
bot.user_repo           →    UserRepository      →    asyncpg + Neon
bot.admin_repo          →    AdminRepository     →    asyncpg + Neon
bot.osu_repo            →    OsuRepository       →    asyncpg + Neon
bot.analytics_repo      →    AnalyticsRepository →    asyncpg + Neon
                               ↑ all inherit from ↑
                               BaseRepository
```

Advantages:

- Handler code **knows nothing about SQL**. It just calls methods like `repo.get_channel_messages()`.
- If you change the database engine, you only need to update the repository.

---

## 🔁 Resilience & Fallbacks

| Problem | Implemented Solution |
| ------- | -------------------- |
| Gemini quota reached | Automatic fallback to Groq |
| Groq quota reached | Groq Fallback (smaller model: llama-3.1-8b) |
| Neon DB sleeping/slow | In-RAM `local_history` as context fallback |
| Discord Rate Limit 429 | Exponential cooldown (`error_cooldown`) in `dalet_nlpchat` |
| Bot crashes on Render | Infinite `while True` loop in `main()` for auto-restart |
| Unsaved messages (buffer) | `_flushing_logs` state to prevent message loss during flush |
