# 🔑 Environment Variables Reference (`.env`)

> Complete reference for all configuration keys used by Dalet. Never commit the `.env` file to source control — it is excluded via `.gitignore`.

---

## 📋 Configuration Keys

### 1. Discord Gateway

| Variable | Required | Description | Where to obtain |
| :--- | :--- | :--- | :--- |
| `DISCORD_TOKEN` | **Yes** | Authentication token for your Discord bot application | [Discord Developer Portal](https://discord.com/developers/applications) → Your App → Bot → Reset Token |

> **Privileged Intents Required:** In the Developer Portal, enable **Server Members Intent** and **Message Content Intent** under Bot → Privileged Gateway Intents.

> **Bot Permissions:** Your invite URL must include: `Read Messages`, `Send Messages`, `Embed Links`, `Manage Messages`, `Moderate Members`, `Ban Members`. The last three are required for auto-moderation to apply actions beyond notify-only.

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
| `DEEPSEEK_API_KEY` | No | DeepSeek API key — primary conversational model | `sk-...` |
| `DEEPSEEK_MODEL` | No | DeepSeek model identifier | `deepseek-flash` |
| `GEMINI_API_KEY` | **Yes** | Google Gemini API key — vision, moderation, and conversational fallback | [Google AI Studio](https://aistudio.google.com) |
| `GEMINI_MODEL` | No | Active Gemini model name | `gemini-2.5-flash` |
| `GROQ_API_KEY` | No | Groq API key for ultra-fast low-latency inference (<200ms) | [Groq Console](https://console.groq.com) |
| `GROQ_MODEL` | No | Primary model hosted on Groq LPU | `openai/gpt-oss-120b` |
| `GROQ_MODEL_FALLBACK` | No | Fallback model on Groq | `openai/gpt-oss-20b` |
| `OPENROUTER_API_KEY` | No | OpenRouter API key for free-tier and diverse open-source models | [OpenRouter](https://openrouter.ai) |
| `OPENROUTER_MODEL` | No | Model slug on OpenRouter | `openrouter/free` |

> **Note on `GEMINI_API_KEY`:** Gemini is used for two independent purposes — image vision in conversations and image scanning in the content moderation pipeline. A paid-tier API key (Google AI Studio with billing enabled) is recommended for production, as it provides higher rate limits and ensures moderation image scans don't consume the free-tier quota. The `GEMINI_MODEL` variable controls which model is used for both tasks.

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
| `DASHBOARD_SECRET` | No | Bearer token to protect the `/api/telemetry` and `/api/feedbacks` endpoints | Any random string; omit to allow open access in local development |
| `OWNER_ID` | No | Discord User ID of the bot creator (grants administrative override) | Numeric Discord Snowflake (e.g. `293847582910293847`) |

---

## 📝 Minimal `.env` Example

```env
# Required for core functionality
DISCORD_TOKEN=your_discord_bot_token
TURSO_DATABASE_URL=https://your-db-name.turso.io
TURSO_AUTH_TOKEN=your_turso_auth_token
GEMINI_API_KEY=your_gemini_api_key
OSU_CLIENT_ID=12345
OSU_CLIENT_SECRET=your_osu_client_secret

# Recommended for full functionality
AI_ROUTING_MODE=auto
DEEPSEEK_API_KEY=sk-your_deepseek_key
GEMINI_MODEL=gemini-2.5-flash
GROQ_API_KEY=gsk_your_groq_key
OPENROUTER_API_KEY=sk-or-your_openrouter_key

# Optional
PORT=8080
DASHBOARD_SECRET=your_random_secret
```
