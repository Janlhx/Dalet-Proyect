# 🔑 Environment Variables Reference (`.env`)

> This document provides a complete reference for all required and optional configuration keys used by Dalet. Secrets should never be committed to source control (the `.env` file is excluded via `.gitignore`).

---

## 📋 Configuration Keys

### 1. Discord Gateway
| Variable | Required | Description | Where to obtain |
| :--- | :--- | :--- | :--- |
| `DISCORD_TOKEN` | **Yes** | Authentication token for your Discord bot application | [Discord Developer Portal](https://discord.com/developers/applications) → Your App → Bot → Reset Token |

---

### 2. Hybrid Persistence (Turso Cloud + Local SQLite)
| Variable | Required | Description | Default / Example |
| :--- | :--- | :--- | :--- |
| `TURSO_DATABASE_URL` | **Yes** | HTTP/libSQL endpoint for your cloud database | `https://your-db-name.turso.io` |
| `TURSO_AUTH_TOKEN` | **Yes** | JWT authorization token issued by Turso | Generated via `turso db tokens create <name>` |
| `LOCAL_DB_PATH` | No | Path to local SQLite WAL fallback database | `dalet_local.db` |

---

### 3. Artificial Intelligence & Multi-LLM Load Balancer
| Variable | Required | Description | Default / Example |
| :--- | :--- | :--- | :--- |
| `AI_ROUTING_MODE` | No | Routing strategy: `auto`, `deepseek`, `gemini`, `groq`, or `openrouter` | `auto` |
| `DEEPSEEK_API_KEY` | No | DeepSeek API key for conversational reasoning | `sk-...` |
| `DEEPSEEK_MODEL` | No | DeepSeek model identifier | `deepseek-chat` |
| `GEMINI_API_KEY` | **Yes** | Google Gemini API key (primary for vision and fallback) | [Google AI Studio](https://aistudio.google.com) |
| `GEMINI_MODEL` | No | Active Gemini model name | `gemini-2.5-flash` |
| `GROQ_API_KEY` | No | Groq API key for ultra-fast low-latency inference (<200ms) | [Groq Console](https://console.groq.com) |
| `GROQ_MODEL` | No | Primary model hosted on Groq LPU | `openai/gpt-oss-120b` |
| `GROQ_MODEL_FALLBACK` | No | Fallback model on Groq | `openai/gpt-oss-20b` |
| `OPENROUTER_API_KEY` | No | OpenRouter API key for free-tier and diverse open-source models | [OpenRouter](https://openrouter.ai) |
| `OPENROUTER_MODEL` | No | Model slug on OpenRouter | `openrouter/free` |

---

### 4. osu! API v2
| Variable | Required | Description | Where to obtain |
| :--- | :--- | :--- | :--- |
| `OSU_CLIENT_ID` | **Yes** | OAuth2 Client ID from osu! account settings | [osu.ppy.sh Account Settings](https://osu.ppy.sh/home/account/edit) → OAuth |
| `OSU_CLIENT_SECRET` | **Yes** | OAuth2 Client Secret from osu! account settings | Generated upon registering application |

---

### 5. Web Telemetry Dashboard & Hosting
| Variable | Required | Description | Default / Example |
| :--- | :--- | :--- | :--- |
| `PORT` | No | Port for the live Flask web dashboard and Render health checks | `8080` |
| `OWNER_ID` | No | Discord User ID of the bot creator (grants administrative override) | Numeric Discord Snowflake (e.g. `293847582910293847`) |
