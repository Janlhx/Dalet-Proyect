<div align="center">

<img src="docs/assets/dalet_oc.jpg" alt="Dalet" width="180" style="border-radius: 50%;" />

# Dalet

**Witty AI companion and specialized osu! tracking bot for Discord — featuring cognitive reflective memory, 5-dimension skill analytics, multi-LLM load balancing, granular auto-moderation, and real-time telemetry.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-V3-4D6BFE?style=for-the-badge&logo=deepseek&logoColor=white)](https://deepseek.com)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-3.8%20Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://aistudio.google.com)
[![Groq](https://img.shields.io/badge/Groq-LPU%20Speed-F55036?style=for-the-badge&logo=fastapi&logoColor=white)](https://console.groq.com)
[![Turso](https://img.shields.io/badge/Turso-libSQL%20Cloud-00E599?style=for-the-badge&logo=sqlite&logoColor=black)](https://turso.tech)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

[Features](#features) | [osu! Analytics](#osu-tracking-and-skill-breakdown) | [Conversational Brain and Cognitive Memory](#conversational-brain-and-cognitive-memory) | [Auto-Moderation](#modular-auto-moderation) | [Tech Stack](#tech-stack) | [Web Dashboard](#telemetry-dashboard) | [Getting Started](#getting-started) | [Commands](#commands) | [Architecture](#architecture)

</div>

---

## Features

Dalet combines conversational AI with rhythm game telemetry, proactive content security, and resilient hybrid storage:

- **5-Dimension Skill Breakdown (`/skills`)**: Algorithmic evaluation of user top plays across Aim, Speed, Accuracy, Stamina, and Reading in star ratings ($\star$) with mod re-weighting (DT, HR, EZ, FL) and an AI verdict.
- **Cognitive Reflective Memory**: Background extraction of personal traits, preferences, and dynamics. Stores both user input and Dalet's internal deductions (`DaletThought`) to enrich context naturally without robotic recitation.
- **Granular Auto-Moderation System**: Dual-layer detection combining instant regex heuristic filters and Google Gemini Vision image scanning. Fully modular with individual toggles (`images`, `flood`, `links`, `scams`), multi-channel burst detection, duplicate media hashing, and high-priority alerts.
- **Smart Multi-LLM Load Balancer**: High-throughput routing across DeepSeek V3, Google Gemini 3.8 Flash, Groq (<200ms inference), and OpenRouter with automatic circuit breaker failover.
- **Full Bilingual Support (i18n)**: English by default for global communities, switchable to Spanish per guild with zero-overhead RAM caching via `/language`.
- **Atomic Design UI**: Modern, typography-focused Discord embeds for scores, user profiles, rankings, and comparisons without visual clutter.
- **Hybrid libSQL Cloud + SQLite Storage**: Cloud-synced database via Turso (HTTP Pipeline) with local SQLite WAL fallback, in-memory caching, and asynchronous log batching.
- **Live Telemetry and Dashboard**: Real-time dark-mode web panel (Flask + Chart.js) tracking Prompt/Completion token burn, provider latencies, and circuit breaker status.
- **Channel Digest Summaries**: Historical conversation synthesis via `/resumir` and `d.summary`.

---

## osu! Tracking and Skill Breakdown

Dalet features a complete presentation layer built on the Dalet Atomic Design System ([docs/08_DESIGN_SYSTEM.md](docs/08_DESIGN_SYSTEM.md)), extracting both Bancho Classic and Lazer score formats:

### Skill Breakdown (`/skills` / `d.skills`)
Evaluates a player's top 50/100 plays through mathematical heuristics:
- **Aim**: Circle Size (CS), jump velocity, and spatial pattern difficulty.
- **Speed**: Effective BPM scaling (1.5x with DoubleTime) and high-density burst analysis.
- **Accuracy**: Overall Difficulty (OD), hit distribution ($300$s vs $100$s/$50$s), and strict timing mod multipliers.
- **Stamina**: Drain length, note count ($\ge 1200$), and sustained streams.
- **Reading**: Low Approach Rate (AR $\le 8.5$), technical map patterns, and Hidden (HD) reading pressure.
- **Dalet's Verdict**: A sharp, 2-line AI roast dissecting player imbalances and choke habits.

### Core Cards
- **`/recent` (`d.recent` / `d.or`)**: High-density recent play card with mods, stars, detailed hits `[300/100/50/Miss]`, PP, combo, and technical map stats (`AR`, `OD`, `HP`, `CS`, `BPM`, `Length`).
- **`/top` (`d.top`)**: Top 5 ranked scores with country badges and clean formatting.
- **`/op` (`d.op`)**: Full user profile overview, global/country rank, progress bar, and grade counts (`SS`, `S`, `A`).
- **`/compare`**: Direct head-to-head comparison between two players displaying PP differentials and stat leads.

---

## Conversational Brain and Cognitive Memory

Dalet features a distinctive persona providing direct, witty, and contextual dialogue rather than generic assistant responses.

### Reflective Memory Architecture
- **Dual-Data Persistence**: Each memory captures the user context (`UserMessage`) paired with Dalet's internal deductive insight (`DaletThought`).
- **Zero-Latency Background Analysis**: Reflection runs asynchronously after delivering responses to Discord, imposing zero lag on user interactions.
- **Heuristic Token-Saving Filters**: Trivial interactions (greetings, laughter, short acknowledgments) are dismissed in sub-milliseconds without LLM calls.
- **Organic Contextual Injection**: Memories are injected as subconscious psychological background. Dalet is explicitly instructed never to quote memories mechanically (avoiding "I remember you said..."), ensuring human-like familiarity and tone modulation.

### Multi-LLM Routing
- **Dynamic Language Selection**: Adapts replies between English and Spanish based on guild settings.
- **Direct REST Integration**: Uses direct HTTP client connections for Google Gemini 3.8 Flash, bypassing Python SDK overhead.
- **Circuit Breakers**: Detects rate limits (`429`) and upstream errors (`503`), instantly shifting traffic across DeepSeek, Groq, and OpenRouter without dropping active user queries.

---

## Modular Auto-Moderation

Dalet provides an integrated, opt-in moderation suite designed to secure Discord communities against raids, illicit material, phishing, and spam.

### Inspection Layers

1. **Anti-Flood and Burst Filter (In-Memory)**:
   - Evaluates message frequency ($\ge 5$ messages in 4 seconds) and duplicate content ($\ge 3$ repeated messages in 10 seconds).
   - Generates attachment signatures (`filename_filesize`) to detect identical image or GIF spam launched across multiple channels simultaneously.
2. **Text Regex Heuristics (Instant, 0 API Cost)**:
   - Scans against categorized pattern libraries for adult links, invite spam, Discord Nitro/Steam phishing, token stealers, carding, and unauthorized data trade.
   - Strict, zero-tolerance CSAM contextual regex protection with false-positive mitigation (differentiating competitive terms like Pokemon Go CP, CoD Points, and Club Penguin).
3. **Multimodal Vision Layer (Gemini Vision)**:
   - Inspects attached images and GIFs using safety classification prompts.
   - Automatically bypasses scanning in native Discord NSFW channels (`channel.is_nsfw() = True`) to eliminate unnecessary API costs.

### Modular Administration (`/mod`)

Administrators can configure parameters individually without executing full setups:

| Command | Permission | Description |
| :--- | :--- | :--- |
| `/mod setup [log_channel] [action] [timeout_minutes] [auto_ban_on_illegal]` | Administrator | Initial configuration or full update. Parameters are optional. |
| `/mod channel <log_channel>` | Administrator | Updates only the alert and audit log channel. |
| `/mod action <notify \| timeout \| ban>` | Administrator | Sets the default enforcement action for adult content violations. |
| `/mod timeout <minutes>` | Administrator | Modifies timeout duration (1 to 10080 minutes). |
| `/mod toggle <images \| flood \| links \| scams> [enabled]` | Administrator | Enables or disables individual moderation modules on demand. |
| `/mod ignore <add \| remove \| list> [channel]` | Administrator | Exempts or re-includes channels from auto-moderation and anti-flood (e.g. bot or spam channels). |
| `/mod status` | Manage Messages | Displays current operational status, active modules, exempt channels, and recent enforcement log. |
| `/mod off` | Administrator | Pauses auto-moderation for the server. |

### Enforcement Actions

| Action | Execution Details |
| :--- | :--- |
| `notify` | Deletes violating content and sends an embed report to the log channel. |
| `timeout` | Deletes content, applies a member timeout, and logs the event. |
| `ban` | Deletes content and bans the user from the guild. |

Critical infractions (illegal content or cross-channel raid floods) prepend high-priority `@here` pings in the configured moderation channel for rapid staff intervention.

---

## Tech Stack

| Component | Technologies |
| :--- | :--- |
| Language and Runtime | Python 3.11+ / discord.py 2.x (asyncio) |
| Conversational AI | DeepSeek V3 (primary) / Google Gemini 3.8 Flash (vision, cognition, fallback) |
| High-Speed Inference | Groq LPU (`openai/gpt-oss-120b`, `20b`) / OpenRouter |
| Database Layer | Turso (libSQL Cloud Database over HTTPS) / SQLite 3 (WAL mode local fallback) |
| Web and Telemetry | Flask / Chart.js / Vanilla CSS |
| Rhythm Game API | osu! API v2 (OAuth2 Client Credentials) |
| Hosting and CI/CD | Render (Web Service deployment with automatic continuous deploy) |

---

## Telemetry Dashboard

Dalet includes a built-in real-time monitoring web dashboard hosted on the application port (`http://localhost:8080/` or your production URL):

- **Token Consumption**: Real-time breakdown of Prompt and Completion tokens for DeepSeek, Gemini, Groq, and OpenRouter.
- **Traffic Graphs**: Visual request distribution and provider load balancing.
- **Circuit Breaker Status**: Health indicators (`HEALTHY`, `COOLDOWN`, `TRIPPED`).
- **Gateway Metrics**: Discord API latency, connected guilds, total members, and uptime.
- **Live Event Feed**: Real-time log of AI queries, response latencies, and system events.

---

## Commands

Dalet supports both native Discord Slash Commands (`/`) and the traditional `d.` prefix:

### osu! Commands
| Command | Type | Description |
| :--- | :--- | :--- |
| `/skills [user] [mode]` | Slash / `d.skills` | 5-dimension skill breakdown (Aim, Speed, Acc, Stamina, Reading) with AI verdict |
| `/recent [user] [mode]` | Slash / `d.recent`, `d.or` | Displays your latest play with full hit and map stats |
| `/top [user] [mode]` | Slash / `d.top` | Shows your top 5 best registered scores |
| `/op [user] [mode]` | Slash / `d.op` | Displays complete osu! profile, rank, accuracy, and grade history |
| `/compare <user>` | Slash | Compares stats head-to-head against another player |
| `/link <username>` | Slash / `d.link` | Links your Discord account to your osu! profile |
| `d.unlink` | Prefix | Unlinks your osu! account |

### AI, Social and Utilities
| Command | Type | Description |
| :--- | :--- | :--- |
| `/language [en/es]` | Slash / `d.language` | Configures server language (English default / Espanol) |
| `/help` | Slash / `d.help` | Interactive categorized command navigator and overview |
| `/feedback <message>` | Slash / `d.feedback` | Sends feedback, suggestions, or bug reports directly to the developer |
| `/resumir [messages]` | Slash / `d.summary` | Generates a smart AI digest of recent channel conversations |
| `/lore <topic>` | Slash / `d.lore` | Researches server history and chat archives with cynical commentary |
| `/info` | Slash / `d.info` | Displays Dalet's version, status, and system information |
| `/changelog` | Slash / `d.changelog` | Displays version release notes, major milestone, and recent commits |
| `d.ms` | Prefix | Checks bot response latency in milliseconds |

### Moderation (Admin Only)
| Command | Permission | Description |
| :--- | :--- | :--- |
| `/mod setup` | Administrator | Initial setup with optional channel, action, timeout, and ban parameters |
| `/mod channel <channel>` | Administrator | Modifies the alert log channel |
| `/mod action <action>` | Administrator | Modifies the default violation action (notify, timeout, ban) |
| `/mod timeout <minutes>` | Administrator | Adjusts timeout length |
| `/mod toggle <module>` | Administrator | Enables or disables modules (images, flood, links, scams) |
| `/mod status` | Manage Messages | Shows granular module statuses and recent actions |
| `/mod off` | Administrator | Disables auto-moderation |

### Admin and Server Management
| Command | Permission | Description |
| :--- | :--- | :--- |
| `d.lock` / `d.unlock` | Administrator | Locks or unlocks Dalet commands in the current channel |
| `d.setname <name>` | Administrator | Sets a custom bot name for the server |
| `d.setwelcome` / `d.removewelcome` | Administrator | Configures or removes the welcome/farewell channel |
| `d.cs` | Any | Shows the current channel lock and AI responsiveness state |
| `d.sync [here/global/clear]` | Administrator | Synchronizes slash commands to the guild or globally |

---

## Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/Janlhx/Dalet-Proyect.git
cd Dalet-Proyect
```

### 2. Create virtual environment and install dependencies
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
# Discord Bot
DISCORD_TOKEN=your_discord_bot_token

# Hybrid Databases
TURSO_DATABASE_URL=https://your-database-name.turso.io
TURSO_AUTH_TOKEN=your_turso_auth_token

# AI Providers
AI_ROUTING_MODE=auto
DEEPSEEK_API_KEY=your_deepseek_api_key
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.8-flash
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key

# osu! API v2
OSU_CLIENT_ID=your_osu_client_id
OSU_CLIENT_SECRET=your_osu_client_secret

# Web Dashboard
PORT=8080
```

### 4. Discord Bot Permissions

In the [Discord Developer Portal](https://discord.com/developers/applications), ensure your application URL includes:
- **Scopes**: `bot`, `applications.commands`
- **Permissions**: `Read Messages`, `Send Messages`, `Embed Links`, `Manage Messages`, `Moderate Members`, `Ban Members`

Enable the following **Privileged Gateway Intents**:
- `Server Members Intent`
- `Message Content Intent`

### 5. Launch Dalet
```bash
python dalet_main.py
```

### 6. Synchronize slash commands
After initial startup, run in any authorized channel:
```
d.sync
```

---

## Architecture

```
Dalet-Proyect/
|-- dalet_main.py                    <- Bootstrap, cog loader, Flask dashboard, retry loop
|
|-- handlers/                        <- Discord Cogs
|   |-- dalet_slash_commands.py      <- Unified slash commands (osu!, utilities)
|   |-- dalet_osucommands.py         <- Prefix commands (d.skills, d.op, d.recent)
|   |-- dalet_osu_presenter.py       <- Atomic embed renderer for osu! cards
|   |-- dalet_nlpchat.py             <- Contextual conversation engine and memory hook
|   |-- dalet_moderation.py          <- Granular auto-moderation cog (/mod commands)
|   |-- dalet_chatlogger.py          <- Message logger for conversation context
|   |-- dalet_admcommands_handler.py <- Admin commands (lock, setname, sync, language)
|   |-- dalet_helpcommands_handlers.py <- Help menus and command documentation
|   |-- dalet_reminders.py           <- Scheduled reminders system
|   |-- dalet_greetings.py           <- Welcome and farewell dispatchers
|   |-- dalet_events_handlers.py     <- on_ready, on_command_error, presence rotation
|   `-- modules/
|       `-- dalet_osuanalyzer.py     <- 5-dimension skill calculation engine
|
|-- services/                        <- Business logic services
|   |-- nlp_service.py               <- Multi-LLM load balancer (DeepSeek, Gemini, Groq)
|   |-- moderation_service.py        <- Content moderation (regex, anti-flood, vision)
|   |-- osu_service.py               <- Async osu! API v2 client
|   |-- memory_service.py            <- Cognitive memory and reflection engine
|   `-- dashboard_service.py         <- Flask telemetry and metrics
|
|-- database/                        <- Hybrid persistence layer
|   |-- turso_client.py              <- libSQL HTTP Pipeline client (Turso Cloud)
|   |-- sqlite_manager.py            <- SQLite WAL fallback, schema, migrations
|   `-- repositories/
|       |-- admin_repository.py      <- Server config, moderation config, channel locks
|       |-- user_repository.py       <- User memories, message history, social stats
|       |-- osu_repository.py        <- osu! profiles, score snapshots, history
|       `-- analytics_repository.py  <- AI telemetry and error tracking
|
|-- ui/                              <- Atomic Design System and i18n
|   |-- locales.py                   <- Centralized string catalog (EN / ES) + t() helper
|   |-- atoms.py                     <- Design tokens: colors, glyphs, version constants
|   |-- molecules.py                 <- Progress bars, footers, field helpers
|   `-- organisms.py                 <- Composite embeds (user stats, skill cards)
|
`-- docs/                            <- Technical documentation
    |-- 01_ARCHITECTURE.md           <- System design and data flows
    |-- 07_VARIABLES_ENVIRONMENT.md  <- Environment variable reference
    `-- 08_DESIGN_SYSTEM.md          <- Atomic UI design tokens and embed layouts
```

---

## Documentation

| Document | Description |
| :--- | :--- |
| [01 - Architecture](docs/01_ARCHITECTURE.md) | High-level system design, data flows, and resilience patterns |
| [07 - Environment Variables](docs/07_VARIABLES_ENVIRONMENT.md) | Configuration guide for credentials and API keys |
| [08 - Design System](docs/08_DESIGN_SYSTEM.md) | Atomic UI design tokens, typography, and embed layouts |

---

<div align="center">

Crafted by **Litxe** · Colombia

</div>
