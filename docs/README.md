# 📖 Project Documentation Index

Welcome to the technical documentation for **Dalet**, a conversational Discord bot featuring AI-driven dialogue, osu! integration, and a persistent memory system.

---

## 📂 Documentation Sections

| File | Description |
| ---- | ----------- |
| [01 — Architecture](./01_ARCHITECTURE.md) | High-level system overview, data flow, and core logic patterns. |
| [02 — Entry Point](./02_ENTRY_POINT.md) | Deep dive into `dalet_main.py` — how the bot starts and the keep-alive server. |
| [03 — Handlers](./03_HANDLERS.md) | Cog breakdown — every command module and how they interact with users. |
| [04 — Services](./04_SERVICES.md) | `NLPService` and `MemoryService` — the AI engine and persistent context logic. |
| [05 — Database](./05_DATABASE.md) | Connection pooling, repositories, and the Repository Pattern implementation. |
| [06 — SQL Schema](./06_SQL_SCHEMA.md) | Complete database reference: tables, views, procedures, and triggers. |
| [07 — Environment Variables](./07_VARIABLES_ENVIRONMENT.md) | Reference for `.env` secrets and configurations. |
| [Neon Migration Guide](./NEON_MIGRATION.md) | Step-by-step guide for cloud deployment on Neon.tech. |

---

## 🗺️ Project Structure

```
Dalet-Proyect/
├── dalet_main.py           ← Main entry point
├── .env                    ← Environment variables (secrets)
├── requirements.txt        ← Python dependencies
│
├── handlers/               ← Feature modules (discord.py Cogs)
│   ├── dalet_nlpchat.py        ← Conversational AI engine
│   ├── dalet_chatlogger.py     ← Database message logging
│   ├── dalet_admcommands_handler.py  ← Admin utility commands
│   ├── dalet_geminicommand.py  ← AI mode config (proactive/reactive)
│   ├── dalet_commands_handlers.py    ← General user commands
│   ├── dalet_helpcommands_handlers.py ← Help system
│   ├── dalet_events_handlers.py      ← Discord event listeners
│   ├── dalet_osucommands.py    ← osu! API commands
│   └── dalet_smartresume.py    ← AI chat summarization
│
├── services/               ← Core business logic
│   ├── nlp_service.py          ← Response generation (Gemini/Groq)
│   ├── memory_service.py       ← Persistent context & memories
│   └── osu_service.py          ← osu! API integration client
│
├── database/               ← Data Access Layer (DAL)
│   ├── pool.py                 ← PostgreSQL connection pooling
│   └── repositories/
│       ├── base_repository.py      ← Generic SQL execution
│       ├── user_repository.py      ← User, message, and memory data
│       ├── admin_repository.py     ← Server & channel settings
│       ├── osu_repository.py       ← osu! accounts and scores
│       └── analytics_repository.py ← Performance metrics & logs
│
├── sql/                    ← Database schema & migration scripts
│   ├── 01_Schema.sql           ← Base tables
│   ├── 03_Procedures_Functions.sql ← Business logic in SQL
│   ├── 04_Views.sql            ← Efficient data views
│   ├── 08_Privacy_TTL.sql      ← Automated data retention policy
│   ├── 09_Enhancements.sql     ← Table improvements
│   └── 10_New_Tables.sql       ← Analytics & tracking tables
│
└── docs/                   ← Technical documentation (This folder)
```
