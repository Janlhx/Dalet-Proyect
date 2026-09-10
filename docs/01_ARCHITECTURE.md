# 🏗️ Dalet System Architecture

> Comprehensive technical blueprint detailing the high-level architecture, data flows, multi-LLM load balancer, hybrid persistence, and resilient execution patterns in Dalet.

---

## 🧠 System Overview

Dalet is an asynchronous Discord bot built with **discord.py 2.x**, engineered around a decoupled 3-tier architecture focused on low latency, resilience, and high visual density:

1. **Conversational AI Engine (Dalet Brain v3.0)**: Dynamic contextual replies powered by a multi-provider load balancer (DeepSeek V3, Google Gemini 2.5 Flash, Groq, OpenRouter) with automatic circuit breaker failover.
2. **Hybrid Cloud & Local Persistence**: Primary cloud database powered by **Turso (libSQL HTTP Pipeline)** with a seamless local fallback to **aiosqlite (WAL Mode)** and memory caches.
3. **Competitive osu! Analytics**: Native integration with the osu! API v2, extracting both Bancho Classic and Lazer score models, computing a 5-dimension skill radar, and delivering concise AI verdicts.
4. **Atomic Design System (UI & i18n)**: Decoupled presentation layer with typographic tokens, progress bars, and full bilingual internationalization (`ui/locales.py`) supporting English (default) and Spanish.

---

## ⚙️ Tech Stack & Dependencies

| Component | Technology | Role / Purpose |
| :--- | :--- | :--- |
| **Runtime & Framework** | Python 3.11+ · discord.py 2.x | Async gateway loop, slash commands, interaction events |
| **Conversational Models** | DeepSeek V3 · Google Gemini 2.5 Flash | High-quality reasoning, image vision, and contextual dialogue |
| **Fast Inference Engine** | Groq LPU (`openai/gpt-oss-120b`, `20b`) | Ultra-low latency responses (<200ms) for high-frequency chat |
| **Cloud Storage** | Turso (libSQL Cloud Database) | Stateless HTTP pipeline for global data replication |
| **Local Storage** | SQLite 3 (WAL Mode, aiosqlite) | Local analytics and instant offline fallback |
| **Web Telemetry** | Flask · Chart.js · Glassmorphism CSS | Live dashboard serving metrics and health checks on port 8080 |
| **Rhythm Game API** | osu! API v2 (OAuth2 Client Credentials) | Score extraction, user profiles, beatmap telemetry |

---

## 🔄 Interaction Flow: "What happens when someone mentions Dalet?"

```
User types "@Dalet ..." or interacts in an active room
                      │
                      ▼
        [DaletNLPChat (handlers/dalet_nlpchat.py)]
                      │
     ┌────────────────┴────────────────────────┐
     ▼                                         ▼
[Permission & Channel Check]          [Is Server Muted?]
(Checks if channel is locked)         (Checks AdminRepository)
     │                                         │
     └────────────────┬────────────────────────┘
                      ▼
            [Retrieve Server Language]
            (admin_repo.get_server_language -> "en" / "es")
                      │
                      ▼
         [Context & History Builder]
         (Fetches recent channel history + user memory)
                      │
                      ▼
          [NLPService Tri-Load Balancer]
          (services/nlp_service.py)
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
   [DeepSeek V3]  [Gemini Flash] [Groq Fast]
         │            │            │
         └────────────┴────────────┘
         (Auto-failover on 429/503 HTTP errors)
                      │
                      ▼
           [Filtered Response Generated]
                      │
                      ▼
           [Discord Message Dispatch]
                      │
                      ▼
          [Async Background Logging]
          (Saves user interactions & token counts to Turso/SQLite)
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
             (Fetches user profile, recent plays, top 100 plays)
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

## 📂 Visual Architecture Diagram

An interactive, visual architecture diagram is available at [`docs/architecture/dalet-architecture.html`](architecture/dalet-architecture.html), viewable in any modern web browser.
