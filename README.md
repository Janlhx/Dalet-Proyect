<div align="center">

<img src="docs/assets/dalet_oc.jpg" alt="Dalet" width="180" style="border-radius: 50%;" />

# Dalet

**Witty AI companion & specialized osu! tracking bot for Discord — with context-aware memory, 5-dimension skill breakdowns, multi-LLM load balancing, content auto-moderation, and a real-time telemetry dashboard.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-V3-4D6BFE?style=for-the-badge&logo=deepseek&logoColor=white)](https://deepseek.com)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-2.5%20Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://aistudio.google.com)
[![Groq](https://img.shields.io/badge/Groq-LPU%20Speed-F55036?style=for-the-badge&logo=fastapi&logoColor=white)](https://console.groq.com)
[![Turso](https://img.shields.io/badge/Turso-libSQL%20Cloud-00E599?style=for-the-badge&logo=sqlite&logoColor=black)](https://turso.tech)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

[✨ Features](#-features) · [🎮 osu! System](#-osu-tracking--skill-breakdown) · [🧠 Conversational Brain](#-conversational-brain-v30) · [🛡️ Auto-Moderation](#️-auto-moderation) · [🛠️ Tech Stack](#️-tech-stack) · [🖥️ Web Dashboard](#-telemetry-dashboard) · [🚀 Getting Started](#-getting-started) · [💬 Commands](#-commands) · [🏗️ Architecture](#️-architecture)

</div>

---

## ✨ Features

Dalet bridges cutting-edge conversational AI with competitive rhythm game analytics, content safety, and enterprise-grade resilience:

- 🎯 **5-Dimension Skill Breakdown (`/skills`)**: Algorithmic evaluation of user top plays across **Aim, Speed, Accuracy, Stamina, and Reading** in star ratings ($\star$) with mod re-weighting (DT, HR, EZ, FL) and a biting AI verdict.
- 🧠 **Smart Multi-LLM Load Balancer**: High-throughput routing across **DeepSeek V3**, **Google Gemini 2.5 Flash**, **Groq** (<200ms inference), and **OpenRouter** with automatic circuit breaker failover.
- 🛡️ **Content Auto-Moderation**: Two-layer NSFW/illegal content detection — instant regex text scanning + Gemini Vision image analysis. Three configurable action modes (notify / timeout / ban) per guild. Opt-in via `/mod setup`.
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

## 🛡️ Auto-Moderation

Dalet includes a built-in, opt-in content moderation system for Discord servers. Administrators activate it with a single slash command — no external service required.

### How It Works

Content is scanned through two sequential layers:

1. **Text Layer (instant, no API cost)**: Regex pattern matching against curated keyword sets for adult content and illegal material (CP/CSAM). Triggers immediately with 100% confidence on exact matches.
2. **Vision Layer (Gemini Vision)**: If the message contains image attachments, Dalet downloads and classifies the image using Google Gemini's multimodal capabilities with a strict safety prompt. Returns a confidence score and category (`safe`, `suggestive`, `explicit`, `illegal`).

### Anti-Spam Detection

A cross-channel tracker monitors repeated violations. If the same user triggers a moderation flag in **2 or more different channels within 60 seconds**, a more severe escalation action is automatically applied regardless of the server's default action mode.

### Configuration

| Command | Permission | Description |
| :--- | :--- | :--- |
| `/mod setup` | Administrator | Activates moderation, sets the log channel, action mode, and timeout duration |
| `/mod off` | Administrator | Disables auto-moderation for the server |
| `/mod status` | Manage Messages | Shows current config and the last 5 moderation actions |

### Action Modes

| Mode | Behavior |
| :--- | :--- |
| `notify` | Deletes the message and posts a detailed embed to the mod log channel |
| `timeout` | Deletes + applies a Discord timeout (configurable duration, default 10 min) |
| `ban` | Deletes + permanently bans the user (recommended only for severe escalation) |

> **Note:** Regardless of the configured mode, content classified as **illegal (CP/CSAM)** triggers an automatic ban by default. This behavior is configurable via the `auto_ban_on_illegal` parameter in `/mod setup`.

### Example Setup

```
/mod setup log_channel:#mod-logs action:notify timeout_minutes:30 auto_ban_on_illegal:True
```

After setup, run `d.sync` in the server to register the new slash commands, then no further configuration is required. All moderation events are logged in the database and visible via `/mod status`.

---

## 🛠️ Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Language & Core** | Python 3.11+ · discord.py 2.x (asyncio) |
| **Conversational AI** | DeepSeek V3 (primary) · Google Gemini 2.5 Flash (vision + fallback) |
| **Fast Inference** | Groq LPU (`openai/gpt-oss-120b`, `20b`) · OpenRouter |
| **Content Moderation** | Regex engine (text) · Google Gemini Vision (images) |
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
| `/help` | Slash / `d.help` | Interactive categorized command navigator and overview |
| `/feedback <message>` | Slash / `d.feedback` | Sends feedback, suggestions, or bug reports directly to the developer |
| `/resumir [messages]` | Slash / `d.summary` | Generates a smart AI digest of recent channel conversations |
| `/lore <topic>` | Slash / `d.lore` | Researches server history and chat archives with cynical commentary |
| `/info` | Slash / `d.info` | Displays Dalet's version, status, and system information |
| `d.changelog` | Prefix | Displays version release notes and recent updates |
| `d.ms` | Prefix | Checks bot response latency in milliseconds |

### 🛡️ Moderation (Admin Only — Opt-In)
| Command | Permission | Description |
| :--- | :--- | :--- |
| `/mod setup` | Administrator | Activates moderation and configures log channel, action mode, and timeout |
| `/mod off` | Administrator | Disables auto-moderation for the server |
| `/mod status` | Manage Messages | Shows current config and last 5 moderation actions |

### ⚙️ Admin & Server Management
| Command | Permission | Description |
| :--- | :--- | :--- |
| `d.lock` / `d.unlock` | Administrator | Locks or unlocks all Dalet commands in the current channel |
| `d.setname <name>` | Administrator | Sets a custom bot name for the server |
| `d.setwelcome` / `d.removewelcome` | Administrator | Configures or removes the welcome/farewell channel |
| `d.cs` | Any | Shows the current channel's lock and AI status |
| `d.sync [here/global/clear]` | Administrator | Syncs slash commands to the server or globally |

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
Create a `.env` file in the project root (see [docs/07_VARIABLES_ENVIRONMENT.md](docs/07_VARIABLES_ENVIRONMENT.md) for a full reference):

```env
# --- Discord Bot ---
DISCORD_TOKEN=your_discord_bot_token

# --- Hybrid Databases ---
TURSO_DATABASE_URL=https://your-database-name.turso.io
TURSO_AUTH_TOKEN=your_turso_auth_token

# --- AI Load Balancer ---
AI_ROUTING_MODE=auto
DEEPSEEK_API_KEY=your_deepseek_api_key
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key

# --- osu! API v2 ---
OSU_CLIENT_ID=your_osu_client_id
OSU_CLIENT_SECRET=your_osu_client_secret

# --- Web Dashboard ---
PORT=8080
```

### 4. Configure Discord Bot Permissions

In the [Discord Developer Portal](https://discord.com/developers/applications), ensure your bot invite URL includes:
- **Scopes**: `bot`, `applications.commands`
- **Permissions**: `Read Messages`, `Send Messages`, `Embed Links`, `Manage Messages`, `Moderate Members`, `Ban Members`

The last three are required for auto-moderation to act on violations. Without them, Dalet falls back to notify-only mode.

Also enable these **Privileged Gateway Intents**:
- `Server Members Intent`
- `Message Content Intent`

### 5. Launch Dalet
```bash
python dalet_main.py
```

### 6. Sync slash commands (first run)
After launch, in any server channel run:
```
d.sync
```

---

## 🏗️ Architecture

```
Dalet-Proyect/
├── dalet_main.py                    ← Bootstrap, cog loader, Flask dashboard, retry loop
│
├── handlers/                        ← Discord Cogs (loaded automatically from this directory)
│   ├── dalet_slash_commands.py      ← Unified slash commands (/, osu!, utilities)
│   ├── dalet_osucommands.py         ← Prefix commands (d.skills, d.op, d.recent)
│   ├── dalet_osu_presenter.py       ← Atomic embed renderer for osu! cards
│   ├── dalet_nlpchat.py             ← Contextual conversation engine (on_message)
│   ├── dalet_moderation.py          ← Auto-moderation Cog (/mod setup, on_message scan)
│   ├── dalet_chatlogger.py          ← Message logger for AI context memory
│   ├── dalet_admcommands_handler.py ← Admin commands (lock, setname, sync, language)
│   ├── dalet_helpcommands_handlers.py ← Help menus and paginated documentation
│   ├── dalet_reminders.py           ← Scheduled reminders system
│   ├── dalet_greetings.py           ← Welcome / farewell messages
│   ├── dalet_events_handlers.py     ← on_ready, on_command_error, presence rotation
│   └── modules/
│       └── dalet_osuanalyzer.py     ← 5-dimension skill calculation engine
│
├── services/                        ← Business logic (stateful, injected into bot)
│   ├── nlp_service.py               ← Multi-LLM load balancer (DeepSeek, Gemini, Groq)
│   ├── moderation_service.py        ← Content moderation (regex + Gemini Vision)
│   ├── osu_service.py               ← Async osu! API v2 client
│   ├── memory_service.py            ← Conversation context and user memory
│   └── dashboard_service.py         ← Flask telemetry and metrics
│
├── database/                        ← Hybrid persistence layer
│   ├── turso_client.py              ← libSQL HTTP Pipeline client (Turso Cloud)
│   ├── sqlite_manager.py            ← SQLite WAL fallback, schema, migrations
│   └── repositories/
│       ├── admin_repository.py      ← Server config, moderation config, channel locks
│       ├── user_repository.py       ← User data, message history, social stats
│       ├── osu_repository.py        ← osu! profiles, score snapshots, history
│       └── analytics_repository.py ← AI interaction telemetry and error tracking
│
├── ui/                              ← Atomic Design System & i18n
│   ├── locales.py                   ← Centralized string catalog (EN / ES) + t() helper
│   ├── atoms.py                     ← Design tokens: colors, glyphs, version constants
│   ├── molecules.py                 ← Progress bars, footers, field helpers
│   └── organisms.py                 ← Composite embeds (user stats, skill cards)
│
└── docs/                            ← Technical documentation
    ├── 01_ARCHITECTURE.md           ← System design and data flows
    ├── 07_VARIABLES_ENVIRONMENT.md  ← Environment variable reference
    └── 08_DESIGN_SYSTEM.md          ← Atomic UI design tokens and embed layouts
```

---

## 📚 Documentation

| Document | Description |
| :--- | :--- |
| [01 — Architecture](docs/01_ARCHITECTURE.md) | High-level system design, data flows, and resilience patterns |
| [07 — Environment Variables](docs/07_VARIABLES_ENVIRONMENT.md) | Complete guide to configuring credentials and API keys |
| [08 — Design System](docs/08_DESIGN_SYSTEM.md) | Atomic UI design tokens, typography, and embed layouts |

---

<div align="center">

Crafted with ❤️ by **Litxe** · Colombia 🇨🇴

</div>
