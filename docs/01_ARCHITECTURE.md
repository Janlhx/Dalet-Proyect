# 🏗️ General Architecture of Dalet

> Este documento detalla la arquitectura global del sistema: cómo se conectan todas las piezas, los flujos de datos y los patrones arquitectónicos aplicados en Dalet.

---

## 🧠 ¿Qué es Dalet?

Dalet es un bot asíncrono para Discord construido sobre **discord.py 2.x**, diseñado con una arquitectura en 3 capas y patrones de resiliencia:

1. **IA Conversacional con Personalidad Propia**: Respuestas dinámicas usando Google Gemini (con fallback a Groq Llama 3.3/3.1), control de sesiones de chat y memoria contextual adaptativa.
2. **Persistencia Híbrida Cloud + Local**: Base de datos principal en la nube con **Turso (libSQL)** vía HTTP Pipeline API y fallback local en **SQLite (WAL Mode)**.
3. **Integración Completa con osu!**: Consultas a la API v2 de osu!, cálculo de PP, spreads de dificultad y presentación visual de alta densidad informativa.
4. **Sistema de Diseño Atómico (UI)**: Interfaz de usuario desacoplada construida en átomos, moléculas y organismos para garantizar consistencia visual en todos los comandos.

---

## ⚙️ Tech Stack

| Tecnología | Propósito |
| ---------- | --------- |
| **Python 3.10+** | Lenguaje principal |
| **discord.py 2.x** | SDK oficial para Discord Gateway, Slash Commands e Interacciones |
| **libsql-client** | Cliente asíncrono sobre HTTP Pipeline para Turso (SQLite Cloud) |
| **Turso (libSQL)** | Base de datos principal distribuida y stateless |
| **aiosqlite (Local)** | Fallback de persistencia local en modo WAL de alto rendimiento |
| **Google GenAI SDK** | Modelo primario de IA (Gemini 2.5 Flash) con context trimming |
| **Groq Cloud API** | Fallback y procesamiento ultrarrápido (Llama 3.3 70B / Llama 3.1 8B) |
| **Flask** | Servidor HTTP minimalista para el Health Check de Render |
| **Matplotlib** | Generación de gráficos de progreso en hilos secundarios (run_in_executor) |


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
