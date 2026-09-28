# 🏗️ Dalet System Architecture

> Comprehensive technical blueprint detailing the high-level architecture, data flows, multi-LLM load balancer, content moderation pipeline, hybrid persistence, and resilient execution patterns in Dalet.

---

## 🧠 System Overview

Dalet is an asynchronous Discord bot built with **discord.py 2.x**, engineered around a decoupled 3-tier architecture focused on low latency, resilience, and high visual density:

1. **Conversational AI Engine (Dalet Brain v3.0)**: Dynamic contextual replies powered by a multi-provider load balancer (DeepSeek V3, Google Gemini 2.5 Flash, Groq, OpenRouter) with automatic circuit breaker failover.
2. **Content Auto-Moderation**: Two-layer NSFW and illegal content detection running before the conversation engine — instant regex text scanning and Google Gemini Vision image analysis.
3. **Hybrid Cloud & Local Persistence**: Primary cloud database powered by **Turso (libSQL HTTP Pipeline)** with a seamless local fallback to **aiosqlite (WAL Mode)** and memory caches.
4. **Competitive osu! Analytics**: Native integration with the osu! API v2, extracting both Bancho Classic and Lazer score models, computing a 5-dimension skill radar, and delivering concise AI verdicts.
5. **Atomic Design System (UI & i18n)**: Decoupled presentation layer with typographic tokens, progress bars, and full bilingual internationalization (`ui/locales.py`) supporting English (default) and Spanish.

---

## ⚙️ Tech Stack & Dependencies

| Component | Technology | Role / Purpose |
| :--- | :--- | :--- |
| **Runtime & Framework** | Python 3.11+ · discord.py 2.x | Async gateway loop, slash commands, interaction events |
| **Primary Conversational Model** | DeepSeek V3 | High-quality reasoning, contextual dialogue |
| **Vision & Fallback Model** | Google Gemini 2.5 Flash | Image understanding, content moderation, conversational fallback |
| **Fast Inference Engine** | Groq LPU (`openai/gpt-oss-120b`, `20b`) | Ultra-low latency responses (<200ms) for high-frequency chat |
| **Cloud Storage** | Turso (libSQL Cloud Database) | Stateless HTTP pipeline for global data replication |
| **Local Storage** | SQLite 3 (WAL Mode, aiosqlite) | Local analytics, moderation logs, and instant offline fallback |
| **Web Telemetry** | Flask · Chart.js · Glassmorphism CSS | Live dashboard serving metrics and health checks on port 8080 |
| **Rhythm Game API** | osu! API v2 (OAuth2 Client Credentials) | Score extraction, user profiles, beatmap telemetry |

---

## 🔄 Interaction Flow: Message Lifecycle

Every incoming message passes through moderation before reaching the conversational engine:

```
User message arrives in a guild channel
              │
              ▼
 [ModerationCog — on_message]  ← runs first (alphabetical cog load order)
              │
     ┌────────┴────────┐
     ▼                 ▼
[Text Regex Scan]  [Gemini Vision]   ← only if attachments present
     │                 │
     └────────┬────────┘
              │
       Flagged? ──Yes──► Delete + Notify/Timeout/Ban → log to DB
              │
             No
              │
              ▼
 [ChatLogger — on_message]          ← saves message to SQLite context buffer
              │
              ▼
 [DaletNLPChat — on_message]        ← determines if Dalet should respond
              │
     ┌────────┴──────────────┐
     ▼                       ▼
[Is Dalet mentioned?]  [Is channel proactive?]
     │                       │
     └──────────┬────────────┘
                │
                ▼
   [Retrieve Server Language + Config]
   (admin_repo.get_server_language → "en" / "es")
                │
                ▼
    [Context & History Builder]
    (MemoryService: RAM buffer + SQLite, last 6 messages)
                │
                ▼
     [NLPService Smart Load Balancer]
                │
       ┌────────┼────────┐
       ▼        ▼        ▼
 [DeepSeek]  [Gemini] [Groq]
       │        │        │
       └────────┴────────┘
       (Auto-failover on 429/503 errors)
                │
                ▼
     [Response dispatched to Discord]
                │
                ▼
  [Async Background Logging]
  (AIInteractions + token counts → Turso / SQLite)
```

---

## 🛡️ Content Moderation Pipeline

```
Message with content or image attachment
              │
              ▼
   [ModerationService.scan_message()]
              │
     ┌────────┴────────┐
     ▼                 ▼
[_scan_text()]    [_scan_image()]   ← skipped if no image URLs
 Regex match       Gemini Vision
 ILLEGAL_RE        Safety prompt
 ADULT_RE          → JSON response
     │                 │
     └────────┬────────┘
              ▼
   ModerationResult(flagged, severity, confidence, method)
              │
     flagged? ─── No ──► pass through
              │
             Yes
              │
              ▼
  [track_flag(user_id, channel_id)]   ← cross-channel spam tracker
              │
   is_spam? (≥2 channels in 60s) ─── Yes ──► escalate action
              │
             No
              ▼
   [_handle_violation()]
     1. message.delete()
     2. _apply_action()  → notify | timeout | ban
     3. _log_to_channel() → embed to mod log channel
     4. admin_repo.log_mod_action() → ModActions table
```

---

## 🎮 osu! Analytics & Skill Breakdown Pipeline

```
User executes `/skills [username]` or `/recent`
              │
              ▼
   [Slash Command / Prefix Cog]
   (dalet_slash_commands.py / dalet_osucommands.py)
              │
              ▼
      [OsuService Query]
      (Fetches user profile, recent plays, top 100 plays via osu! API v2)
              │
              ▼
   [OsuAnalyzer Calculation]
   (handlers/modules/dalet_osuanalyzer.py)
   ├── Computes Aim, Speed, Accuracy, Stamina, Reading
   ├── Re-weights difficulty across mods (DT, HR, EZ, FL)
   └── Identifies primary strength and choke bottlenecks
              │
              ▼
     [Dalet AI Verdict]
     (NLPService sends a ~50 token micro-prompt
      and receives a concise 2-sentence roast)
              │
              ▼
       [OsuPresenter]
       (handlers/dalet_osu_presenter.py)
       └── Applies ui/locales.py tokens (English or Spanish)
           and renders the clean atomic embed
```

---

## 🛡️ Resilience & Circuit Breaker Pattern

To prevent downtimes caused by third-party API rate limits, `NLPService` wraps each AI provider in a self-healing **Circuit Breaker**:

- **Closed State (Healthy)**: Normal execution. Requests are dispatched according to the configured routing strategy.
- **Open State (Tripped)**: Triggered when rate limits (`429`) or server errors (`503`) are returned. The provider enters a cooldown period (e.g. 60 seconds), and 100% of traffic is transparently diverted to the next available healthy model.
- **Half-Open State (Recovery)**: A test probe checks if the service has stabilized before restoring normal load.

---

## 🗄️ Database Schema (SQLite — Key Tables)

| Table | Purpose |
| :--- | :--- |
| `Messages` | Chat history buffer for AI context (6 messages per channel) |
| `Servers` | Guild config: language, custom name, welcome channel, reactivity |
| `Channels` | Per-channel settings: lock state, proactive AI toggle |
| `ModerationConfig` | Per-guild moderation settings: enabled, log channel, action mode, timeout duration |
| `ModActions` | Audit log of every moderation action taken (severity, method, user, action applied) |
| `AIInteractions` | Telemetry: provider, latency, trigger type per AI response |
| `CommandUsage` | Usage frequency and success rate per command |
| `OsuHistory` | Daily PP/rank snapshots per linked user |
| `Reminders` | Scheduled recurring reminders |
| `Feedbacks` | User-submitted feedback entries |

---

## 📂 Visual Architecture Diagram

An interactive, visual architecture diagram is available at [`docs/architecture/dalet-architecture.html`](architecture/dalet-architecture.html), viewable in any modern web browser.
