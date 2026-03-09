<div align="center">

<img src="docs/assets/dalet_oc.jpg" alt="Dalet" width="180" />

# Dalet

**A conversational AI Discord bot with persistent memory, osu! integration, and a PostgreSQL backbone.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![Google Gemini](https://img.shields.io/badge/Gemini-AI-4285F4?style=flat-square&logo=google&logoColor=white)](https://aistudio.google.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-336791?style=flat-square&logo=postgresql&logoColor=white)](https://neon.tech)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[Features](#-features) · [Tech Stack](#-tech-stack) · [Getting Started](#-getting-started) · [Commands](#-commands) · [Architecture](#-architecture) · [Docs](#-documentation)

</div>

---

## ✨ Features

Dalet is more than a chatbot. It's a full-featured Discord companion designed to feel genuinely present in your server.

- 🤖 **Conversational AI** — Powered by Google Gemini. Talks naturally, remembers context, and has its own personality.
- 🧠 **Persistent Memory** — Dalet remembers things users explicitly ask it to. Memories survive restarts and persist across sessions.
- 📝 **Smart Chat Summaries** — Can read a channel's history and generate an AI-powered summary on demand.
- 🎮 **osu! Integration** — Link your osu! profile, fetch your top scores, and get personalised AI coaching and performance analysis.
- 📊 **Analytics & Logging** — Tracks usage metrics and logs errors to the database for monitoring and insights.
- ⚙️ **Admin Controls** — Configure proactive/reactive modes, restrict channels, and manage bot behaviour per-server.
- 🔒 **Privacy-first** — Includes a data retention policy (TTL) that automatically purges old messages from the database.

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Discord Library | discord.py 2.x |
| AI / NLP | Google Gemini (`google-genai`) + Groq (fallback) |
| Database | PostgreSQL on [Neon](https://neon.tech) |
| DB Driver | `asyncpg` (async connection pool) |
| Hosting | [Render](https://render.com) (Web Service) |
| Keep-alive | [UptimeRobot](https://uptimerobot.com) |
| osu! Data | [osu! API v2](https://osu.ppy.sh/docs/index.html) |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- A PostgreSQL database (we recommend [Neon](https://neon.tech) — free tier works great)
- API keys for: Discord, Google Gemini, and osu!

### Step 1 — Get your API Keys

You'll need the following credentials before anything else:

| Variable | Where to get it |
|---|---|
| `DISCORD_TOKEN` | [Discord Developer Portal](https://discord.com/developers/applications) → Bot → Reset Token. Enable **Message Content Intent**. |
| `DATABASE_URL` | [Neon](https://neon.tech) → Create project → copy the `postgres://...` connection string. |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) → Create API Key. |
| `OSU_CLIENT_ID` | [osu! Settings](https://osu.ppy.sh/home/account/edit) → OAuth → New OAuth Application. |
| `OSU_CLIENT_SECRET` | Same as above — generated alongside the Client ID. |
| `GROQ_API_KEY` *(optional)* | [Groq Cloud](https://console.groq.com) — used as an AI fallback. |

### Step 2 — Set up the Database

Run the SQL scripts inside the `/sql` folder **in order** against your PostgreSQL database:

```
01_Schema.sql               ← Creates all tables
03_Procedures_Functions.sql ← Stored procedures & functions
04_Views.sql                ← Useful views (e.g. V_ChannelMessages)
08_Privacy_TTL.sql          ← Data retention policy
09_Enhancements.sql         ← Column additions & improvements
10_New_Tables.sql           ← Analytics tables
```

You can use Neon's built-in SQL editor, DBeaver, or PgAdmin.

### Step 3 — Configure Environment

Clone the repo and create a `.env` file in the root:

```bash
git clone https://github.com/YOUR_USERNAME/Dalet-Proyect.git
cd Dalet-Proyect
```

```env
# .env
DISCORD_TOKEN=your_discord_token
GEMINI_API_KEY=your_gemini_key
DATABASE_URL=postgres://user:pass@host/dbname
OSU_CLIENT_ID=your_osu_client_id
OSU_CLIENT_SECRET=your_osu_client_secret
GROQ_API_KEY=your_groq_key   # optional
```

### Step 4 — Install & Run

```bash
# Create and activate a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run the bot
python dalet_main.py
```

### Step 5 — Deploy to Production (Render)

1. Push the repo to GitHub.
2. Go to [Render](https://render.com) → **New Web Service** → connect your GitHub repo.
3. Set the following:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python dalet_main.py`
4. Add all your `.env` variables in the **Environment** tab.
5. Click **Create Web Service**. Render will deploy and restart automatically on crashes.
6. *(Optional)* Set up a [UptimeRobot](https://uptimerobot.com) HTTP monitor pointing at your Render URL to prevent cold starts.

---

## 💬 Commands

Dalet uses the prefix `d.` by default.

| Command | Description |
|---|---|
| `d.help` | Shows all available commands |
| `d.osuLink <username>` | Link your osu! account to Dalet |
| `d.osuProfile` | View your linked osu! profile stats |
| `d.osuScores` | Fetch and store your top osu! scores |
| `d.osuAnalyze` | Get an AI analysis of your osu! performance |
| `d.osuCoach` | Get a personalised osu! training plan from the AI |
| `d.summary` | Generate an AI summary of the current channel |
| `d.gemini proactive` | Switch Dalet to proactive mode (talks freely) |
| `d.gemini reactive` | Switch Dalet to reactive mode (only on mention) |
| `d.admin blockChannel` | Prevent Dalet from talking in a channel |
| `d.admin unblockChannel` | Re-enable Dalet in a channel |

> Dalet also responds naturally when **mentioned** (`@Dalet`) or when it detects it's being talked to, depending on the configured mode.

---

## 🏗 Architecture

Dalet follows a layered architecture separating concerns cleanly:

```
Dalet-Proyect/
├── dalet_main.py           ← Bot entry point & Flask keep-alive server
│
├── handlers/               ← discord.py Cogs (one per feature domain)
│   ├── dalet_nlpchat.py        ← Core conversational AI engine
│   ├── dalet_smartresume.py    ← AI-powered chat summaries
│   ├── dalet_osucommands.py    ← osu! commands
│   ├── dalet_chatlogger.py     ← Message logging to DB
│   ├── dalet_geminicommand.py  ← AI mode configuration
│   ├── dalet_commands_handlers.py
│   ├── dalet_helpcommands_handlers.py
│   ├── dalet_admcommands_handler.py
│   └── dalet_events_handlers.py
│
├── services/               ← Business logic layer
│   ├── nlp_service.py          ← Gemini/Groq response generation
│   ├── memory_service.py       ← Context & persistent memory management
│   └── osu_service.py          ← osu! API client
│
├── database/               ← Data access layer
│   ├── pool.py                 ← asyncpg connection pool
│   └── repositories/
│       ├── base_repository.py
│       ├── user_repository.py      ← Users, messages, memories
│       ├── admin_repository.py     ← Channel blocks
│       ├── osu_repository.py       ← osu! scores & accounts
│       └── analytics_repository.py ← Metrics & error logs
│
├── sql/                    ← Database schema & migration scripts
└── docs/                   ← Full technical documentation
```

For a deeper dive into how each layer works, see the [docs folder](docs/README.md).

---

## 📚 Documentation

Technical documentation lives in the [`/docs`](docs/) folder:

| Doc | Contents |
|---|---|
| [01 — Architecture](docs/01_ARQUITECTURA.md) | System overview and data flow |
| [02 — Entry Point](docs/02_PUNTO_DE_ENTRADA.md) | How `dalet_main.py` bootstraps the bot |
| [03 — Handlers](docs/03_HANDLERS.md) | Every Cog explained |
| [04 — Services](docs/04_SERVICIOS.md) | NLPService and MemoryService |
| [05 — Database](docs/05_BASE_DE_DATOS.md) | Pool, repositories, and the Repository pattern |
| [06 — SQL Schema](docs/06_ESQUEMA_SQL.md) | All tables, views, procedures, and functions |
| [07 — Environment Variables](docs/07_VARIABLES_ENTORNO.md) | Full `.env` reference |

---

## 🤝 Contributing

Contributions, issues and feature requests are welcome!

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'feat: add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

Made with ❤️ by **Litxe** · Colombia 🇨🇴

</div>
