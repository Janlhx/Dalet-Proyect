<div align="center">

<img src="docs/assets/dalet_oc.jpg" alt="Dalet" width="180" style="border-radius: 50%;" />

# Dalet

**Witty AI companion & specialized osu! tracking bot for Discord with context-aware memory, 5-dimension skill breakdowns, multi-LLM load balancing, and a real-time telemetry dashboard.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-V3-4D6BFE?style=for-the-badge&logo=deepseek&logoColor=white)](https://deepseek.com)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-2.5%20Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://aistudio.google.com)
[![Groq](https://img.shields.io/badge/Groq-LPU%20Speed-F55036?style=for-the-badge&logo=fastapi&logoColor=white)](https://console.groq.com)
[![Turso](https://img.shields.io/badge/Turso-libSQL%20Cloud-00E599?style=for-the-badge&logo=sqlite&logoColor=black)](https://turso.tech)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

[✨ Features](#-features) · [🎮 osu! System](#-osu-tracking--skill-breakdown) · [🧠 Conversational Brain](#-conversational-brain-v30) · [🛠️ Tech Stack](#️-tech-stack) · [🖥️ Web Dashboard](#-telemetry-dashboard) · [🚀 Getting Started](#-getting-started) · [💬 Commands](#-commands) · [🏗️ Architecture](#️-architecture) · [📚 Documentation](#-documentation)

</div>

---

## ✨ Features

Dalet bridges cutting-edge conversational AI with competitive rhythm game analytics and enterprise-grade resilience:

- 🎯 **5-Dimension Skill Breakdown (`/skills`)**: Algorithmic evaluation of user top plays across **Aim, Speed, Accuracy, Stamina, and Reading** in star ratings ($\star$) with mod re-weighting (DT, HR, EZ, FL) and a biting AI verdict.
- 🧠 **Smart Multi-LLM Load Balancer**: High-throughput routing across **DeepSeek V3**, **Google Gemini 2.5 Flash**, **Groq** (<200ms inference), and **OpenRouter** with automatic circuit breaker failover.
- 🌐 **Full Bilingual Support (i18n)**: English by default for global communities, switchable to Spanish per guild with zero-overhead RAM caching via `/language`.
- 🎨 **Atomic Design UI**: Modern, clean, and typographic Discord embeds for scores, user profiles, rankings, and comparisons without visual emoji clutter.
- 💾 **Hybrid libSQL Cloud + SQLite Storage**: Cloud-synced database via **Turso (HTTP Pipeline)** with an instant local **SQLite WAL** fallback and asynchronous batching.
- 🖥️ **Live Telemetry & Dashboard**: Real-time dark-mode web panel (Flask + Chart.js) tracking Prompt/Completion token burn, provider latencies, and circuit breaker status.
- 📝 **Smart Channel Summaries**: Intelligent historical digest generation via `/resumir` and `d.summary`.
- 🧠 **Persistent Long-Term Memory**: Explicit user preferences, facts, and conversation context retained across bot restarts.

---

## 🎮 osu! Tracking & Skill Breakdown

Dalet features a complete presentation layer built on the **Dalet Atomic Design System** ([docs/08_DESIGN_SYSTEM.md](docs/08_DESIGN_SYSTEM.md)), extracting both Bancho Classic and Lazer score formats:

### ✦ Skill Breakdown (`/skills` / `d.skills`)
Evaluates a player's top 50/100 plays through mathematical heuristics:
- **Aim**: Circle Size (CS), jump velocity, and spatial pattern difficulty.
- **Speed**: Effective BPM scaling (1.5x with DoubleTime) and high-density burst analysis.
- **Accuracy**: Overall Difficulty (OD), hit distribution ($300$s vs $100$s/$50$s), and strict timing mod multipliers.
- **Stamina**: Drain length, note count ($\ge 1200$), and sustained streams.
- **Reading**: Low Approach Rate (AR $\le 8.5$), technical map patterns, and Hidden (HD) reading pressure.
- **Dalet's Verdict**: A sharp, 2-line AI roast dissecting player imbalances and choke habits.

### ✦ Core Cards
- **`/recent` (`d.recent` / `d.or`)**: High-density recent play card with mods, stars, detailed hits `[300/100/50/Miss]`, PP, combo, and technical map stats (`AR`, `OD`, `HP`, `CS`, `BPM`, `Length`).
- **`/top` (`d.top`)**: Top 5 ranked scores with native country flags and clean formatting.
- **`/op` (`d.op`)**: Full user profile overview, global/country rank, progress bar, and grade counts (`SS`, `S`, `A`).
- **`/compare`**: Direct head-to-head comparison between two players displaying PP differentials and stat leads.

---

## 🧠 Conversational Brain v3.0

Dalet features a unique, cynical persona that provides witty, concise, and direct answers rather than generic AI responses.

- **Dynamic Persona Adaptation**: Responds in English or Spanish depending on guild configuration.
- **Micro-Prompt Architecture**: High token efficiency — prompts consume under 60 input tokens and produce focused ~40 token replies for game verdicts.
- **Auto-Failover Circuit Breakers**: If an LLM provider encounters rate limits (`429`) or downtime (`503`), requests instantly reroute to alternative providers without interrupting user sessions.

---

## 🛠️ Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Language & Core** | Python 3.11+ · discord.py 2.x (asyncio) |
| **AI Models** | DeepSeek V3 · Google Gemini (`gemini-2.5-flash`) · Groq (`openai/gpt-oss-120b`, `20b`) · OpenRouter |
| **Cloud Persistence** | [Turso](https://turso.tech) (libSQL Cloud Database over HTTP Pipeline) |
| **Local Persistence** | SQLite 3 (WAL mode, in-memory LRU caching & async log batching) |
| **Web & Telemetry** | Flask · Chart.js · Glassmorphism CSS |
| **Rhythm Game API** | [osu! API v2](https://osu.ppy.sh/docs/index.html) (OAuth2 Client Credentials) |
| **Deployment** | [Render](https://render.com) (Web Service with Health Check on `:8080`) |

---

## 🖥️ Telemetry Dashboard

Dalet includes a built-in real-time monitoring web dashboard hosted on the application port (`http://localhost:8080/` or your production URL):

- **Token Consumption**: Real-time breakdown of Prompt and Completion tokens for DeepSeek, Gemini, Groq, and OpenRouter.
- **Traffic Graphs**: Visual request distribution and provider load balancing.
- **Circuit Breaker Status**: Health indicators (`HEALTHY`, `COOLDOWN`, `TRIPPED`).
- **Gateway Metrics**: Discord API latency, connected guilds, total members, and uptime.
- **Live Event Feed**: Real-time log of AI queries, response latencies, and system events.

---

## 💬 Commands

Dalet supports both **native Discord Slash Commands (`/`)** and the traditional `d.` prefix:

### 🎮 osu! Commands
| Command | Type | Description |
| :--- | :--- | :--- |
| `/skills [user] [mode]` | Slash / `d.skills` | 5-dimension skill radar (Aim, Speed, Acc, Stamina, Reading) with AI verdict |
| `/recent [user] [mode]` | Slash / `d.recent`, `d.or` | Displays your latest play with full hit and map stats |
| `/top [user] [mode]` | Slash / `d.top` | Shows your top 5 best registered scores |
| `/op [user] [mode]` | Slash / `d.op` | Displays complete osu! profile, rank, accuracy, and grade history |
| `/compare <user>` | Slash | Compares your stats head-to-head against another player |
| `/link <username>` | Slash / `d.link` | Links your Discord account to your osu! profile |
| `d.unlink` | Prefix | Unlinks your osu! account |

### 🤖 AI, Social & Utilities
| Command | Type | Description |
| :--- | :--- | :--- |
| `/language [en/es]` | Slash / `d.language` | Configures server language (English default / Español) |
| `/resumir [messages]` | Slash / `d.summary` | Generates a smart AI digest of recent channel conversations |
| `/lore <topic>` | Slash / `d.lore` | Researches server history and chat archives with cynical commentary |
| `/info` | Slash / `d.info` | Displays Dalet's version, status, and system information |
| `d.changelog` | Prefix | Displays version release notes and recent updates |
| `d.ms` | Prefix | Checks bot response latency in milliseconds |

---

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/Janlhx/Dalet-Proyect.git
cd Dalet-Proyect
```

### 2. Create virtual environment & install dependencies
```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux / macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure environment variables (`.env`)
Create a `.env` file in the project root:

```env
# --- Discord Bot ---
DISCORD_TOKEN=your_discord_bot_token

# --- Hybrid Databases (Turso libSQL Cloud + Local SQLite) ---
TURSO_DATABASE_URL=https://your-database-name.turso.io
TURSO_AUTH_TOKEN=your_turso_auth_token

# --- Artificial Intelligence (Smart Tri-Load Balancer) ---
AI_ROUTING_MODE=auto

# 1. DeepSeek V3
DEEPSEEK_API_KEY=your_deepseek_api_key

# 2. Google Gemini (Vision & Context)
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash

# 3. Groq (Ultra-low latency <200ms)
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b

# 4. OpenRouter (Fallback & Free Tier)
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=openrouter/free

# --- osu! API v2 ---
OSU_CLIENT_ID=your_osu_client_id
OSU_CLIENT_SECRET=your_osu_client_secret

# --- Web Dashboard Port ---
PORT=8080
```

### 4. Launch Dalet
```bash
python dalet_main.py
```

---

## 🏗️ Architecture

```
Dalet-Proyect/
├── dalet_main.py                  ← Application bootstrap, task runner & Flask dashboard
│
├── handlers/                      ← Discord Cogs and command handlers
│   ├── dalet_slash_commands.py    ← Unified application slash commands (/)
│   ├── dalet_osucommands.py       ← Traditional prefix commands (d.skills, d.op, d.recent)
│   ├── dalet_osu_presenter.py     ← High-density visual card presenter
│   ├── dalet_nlpchat.py           ← Contextual conversation engine
│   ├── dalet_commands_handlers.py ← Utility commands (info, changelog, latency, stats)
│   ├── dalet_admcommands_handler.py ← Admin controls (d.language, channel blocking)
│   ├── dalet_helpcommands_handlers.py ← Help menus and documentation cards
│   └── modules/
│       └── dalet_osuanalyzer.py   ← 5-dimension skill calculation engine
│
├── services/                      ← Business logic layer
│   ├── nlp_service.py             ← Multi-LLM load balancer (DeepSeek, Gemini, Groq)
│   ├── osu_service.py             ← Async osu! API v2 client
│   ├── memory_service.py          ← Conversation context and user memory
│   └── dashboard_service.py       ← Flask telemetry dashboard & metrics
│
├── database/                      ← Hybrid persistence layer
│   ├── turso_client.py            ← libSQL HTTP Pipeline client for Turso Cloud
│   ├── sqlite_manager.py          ← SQLite (WAL) fallback and local analytics
│   └── repositories/              ← Data access repositories (Admin, User, Osu, Analytics)
│
├── ui/                            ← Atomic Design System & Localization
│   ├── locales.py                 ← Centralized i18n string catalog (EN / ES) & t() helper
│   ├── atoms.py                   ← Visual design tokens, glyphs, and grade colors
│   ├── molecules.py               ← Progress bars, footers, and field helpers
│   └── organisms.py               ← Composite embeds
│
└── docs/                          ← Architecture specifications & technical documentation
```

---

## 📚 Documentation

| Document | Description |
| :--- | :--- |
| [01 — Architecture](docs/01_ARCHITECTURE.md) | High-level system design and abstraction layers |
| [07 — Environment Variables](docs/07_VARIABLES_ENVIRONMENT.md) | Complete guide to configuring credentials and API keys |
| [08 — Design System](docs/08_DESIGN_SYSTEM.md) | Atomic UI design tokens, typography, and embed layouts |

---

<div align="center">

Crafted with ❤️ by **Litxe** · Colombia 🇨🇴

</div>
