# 🔑 Environment Variables (`.env`)

> This file contains all the **secrets and configurations** for the bot. It should never be committed to Git (it is included in `.gitignore`).

---

## All Variables

### Discord

| Variable | Description | Where to get it |
| -------- | ----------- | --------------- |
| `DISCORD_TOKEN` | Bot authentication token | [Discord Developer Portal](https://discord.com/developers/applications) → Your App → Bot → Token |

### Primary AI (Gemini)

| Variable | Description | Where to get it |
| -------- | ----------- | --------------- |
| `GEMINI_API_KEY` | Google Gemini API key | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `GEMINI_MODEL` | AI model to use _(optional)_ | Default: `gemini-2.0-flash`. Alternatives: `gemini-1.5-pro` |

### Alternative AI (Groq)

| Variable | Description | Where to get it |
| -------- | ----------- | --------------- |
| `GROQ_API_KEY` | Groq API key | [console.groq.com](https://console.groq.com) |
| `GROQ_MODEL` | Primary Groq model _(optional)_ | Default: `llama-3.3-70b-versatile` |
| `GROQ_MODEL_FALLBACK` | Emergency Groq model _(optional)_ | Default: `llama-3.1-8b-instant` |
| `AI_PROVIDER` | Active provider _(optional)_ | `gemini` (default) or `groq` |

### Database (Neon)

| Variable | Description | Where to get it |
| -------- | ----------- | --------------- |
| `DATABASE_URL` | PostgreSQL connection URL | [console.neon.tech](https://console.neon.tech) → Project → Connection string |

> Expected format: `postgresql://user:password@host/database?sslmode=require`

### osu! API

| Variable | Description | Where to get it |
| -------- | ----------- | --------------- |
| `OSU_CLIENT_ID` | osu! application client ID | [osu.ppy.sh/home/account/edit](https://osu.ppy.sh/home/account/edit) → OAuth → New Application |
| `OSU_CLIENT_SECRET` | osu! application client secret | Same as above |

---

## Example `.env` file

```env
# Discord
DISCORD_TOKEN=MTxxxxxxxxxxxxxxxxxxxxxxxx.Gxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Gemini (Primary AI)
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GEMINI_MODEL=gemini-2.0-flash

# Groq (Fallback AI)
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_MODEL_FALLBACK=llama-3.1-8b-instant

# Active Provider: "gemini" or "groq"
AI_PROVIDER=gemini

# Neon (PostgreSQL)
DATABASE_URL=postgresql://dalet_owner:password@ep-xxx.us-east-2.aws.neon.tech/dalet?sslmode=require

# osu!
OSU_CLIENT_ID=12345
OSU_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## How are these variables loaded in the code?

```python
from dotenv import load_dotenv
import os

load_dotenv()  # Reads the .env file and injects variables into the environment

DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
```

The `python-dotenv` library is used for this purpose. In production environments (like Render), variables are configured directly in the deployment dashboard as "Environment Variables," and a physical `.env` file is not required.

---

## On Render (Production)

Variables should be configured in:  
`Render Dashboard → Your Service → Environment → Environment Variables`

They are the exact same variables but managed by the platform instead of a local file.
