# 📖 Dalet Documentation Index

Welcome to the technical documentation for **Dalet**, a witty, conversational Discord bot featuring multi-LLM load balancing, specialized osu! analytics, a 5-dimension skill radar, and a hybrid cloud/local persistence layer.

---

## 📂 Documentation Directory

| Document | Description |
| :--- | :--- |
| [01 — Architecture](./01_ARCHITECTURE.md) | High-level system architecture, data flows, and multi-LLM circuit breakers |
| [07 — Environment Variables](./07_VARIABLES_ENVIRONMENT.md) | Comprehensive reference for all `.env` secrets and credentials |
| [08 — Design System](./08_DESIGN_SYSTEM.md) | Dalet Atomic UI design standards, color tokens, and embed layouts |
| [Interactive Architecture](./architecture/dalet-architecture.html) | Standalone interactive visual architecture diagram (open in browser) |
| [Privacy Policy](./PRIVACY_POLICY.md) | User data privacy disclosures (required for Discord App Directory) |
| [Terms of Service](./TERMS_OF_SERVICE.md) | End-user terms and guidelines (required for Discord App Directory) |

---

## 🗺️ Project Architecture Overview

```
Dalet-Proyect/
├── dalet_main.py                  ← Entry point, event loop & web dashboard
│
├── handlers/                      ← Discord command modules (Cogs)
│   ├── dalet_slash_commands.py    ← Unified application slash commands (/)
│   ├── dalet_osucommands.py       ← Traditional prefix commands (d.skills, d.op, d.recent)
│   ├── dalet_osu_presenter.py     ← High-density visual card presenter
│   ├── dalet_nlpchat.py           ← Contextual conversational engine
│   ├── dalet_commands_handlers.py ← Utility commands (info, changelog, latency, stats)
│   ├── dalet_admcommands_handler.py ← Administrative controls (d.language, channel blocking)
│   ├── dalet_helpcommands_handlers.py ← Interactive help menus
│   └── modules/
│       └── dalet_osuanalyzer.py   ← 5-dimension skill calculation engine
│
├── services/                      ← Business logic layer
│   ├── nlp_service.py             ← Multi-LLM load balancer (DeepSeek, Gemini, Groq)
│   ├── osu_service.py             ← Async osu! API v2 client
│   ├── memory_service.py          ← Conversation context & user memory
│   └── dashboard_service.py       ← Flask telemetry metrics & dashboard
│
├── database/                      ← Hybrid persistence layer
│   ├── turso_client.py            ← libSQL HTTP Pipeline client for Turso Cloud
│   ├── sqlite_manager.py          ← SQLite (WAL mode) fallback & local analytics
│   └── repositories/              ← Data access repositories (Admin, User, Osu, Analytics)
│
├── ui/                            ← Atomic Design System & Localization
│   ├── locales.py                 ← Centralized i18n string catalog (EN / ES) & t() helper
│   ├── atoms.py                   ← Visual design tokens, glyphs, and grade colors
│   ├── molecules.py               ← Progress bars, footers, and field helpers
│   └── organisms.py               ← Composite embeds
│
└── docs/                          ← Technical specifications & guides
```
