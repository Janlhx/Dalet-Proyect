# 🔑 Environment Variables (`.env`)

> This file contains all the **secrets and configurations** for the bot. It should never be committed to Git (it is included in `.gitignore`).

---

## All Variables

### Discord

| Variable | Description | Where to get it |
| -------- | ----------- | --------------- |
| `DISCORD_TOKEN` | Bot authentication token | [Discord Developer Portal](https://discord.com/developers/applications) → Your App → Bot → Token |

### Base de Datos Principal (Turso / libSQL)

| Variable | Descripción | Dónde obtenerla |
| -------- | ----------- | --------------- |
| `TURSO_URL` | URL de la base de datos libSQL (`https://...` o `libsql://...`) | [Turso Dashboard](https://turso.tech) → Database → Overview |
| `TURSO_AUTH_TOKEN` | Token de autenticación de Turso | `turso db tokens create <db_name>` o en la web |

### IA Primaria (Google Gemini)
### 🤖 Configuración de Inteligencia Artificial (Smart Load Balancer)
| Variable | Requerido | Descripción | Ejemplo / Default |
| :--- | :--- | :--- | :--- |
| `AI_ROUTING_MODE` | No | Modo de balanceo: `auto`, `gemini`, `groq` o `openrouter` | `auto` |
| `GEMINI_API_KEY` | Sí | API Key de Google Gemini | `AIzaSy...` |
| `GEMINI_MODEL` | No | Modelo principal de Gemini | `gemini-2.5-flash` |
| `GROQ_API_KEY` | No | API Key de Groq para inferencia ultrarrápida (<200ms) | `gsk_...` |
| `GROQ_MODEL` | No | Modelo principal en Groq | `openai/gpt-oss-120b` |
| `GROQ_MODEL_FALLBACK` | No | Modelo secundario en Groq | `openai/gpt-oss-20b` |
| `OPENROUTER_API_KEY` | No | API Key de OpenRouter (Acceso a modelos gratuitos) | `sk-or-v1-...` |
| `OPENROUTER_MODEL` | No | Modelo en OpenRouter | `openrouter/free` |
| `AI_PROVIDER` | No | Proveedor activo | `gemini` (default) o `groq` |

### osu! API v2

| Variable | Descripción | Dónde obtenerla |
| -------- | ----------- | --------------- |
| `OSU_CLIENT_ID` | Client ID de la app de osu! | [osu.ppy.sh/home/account/edit](https://osu.ppy.sh/home/account/edit) → OAuth |
| `OSU_CLIENT_SECRET` | Client Secret de la app de osu! | Mismo sitio |

---

## Archivo `.env` de Ejemplo

```env
# Discord
DISCORD_TOKEN=MTxxxxxxxxxxxxxxxxxxxxxxxx.Gxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Turso (Base de Datos Principal libSQL)
TURSO_URL=https://tu-db.turso.io
TURSO_AUTH_TOKEN=eyJh...

# Google Gemini (IA Principal)
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GEMINI_MODEL=gemini-2.5-flash

# Groq (IA Rápida / Fallback)
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_MODEL_FALLBACK=llama-3.1-8b-instant

# Proveedor Activo: "gemini" o "groq"
AI_PROVIDER=gemini

# osu! API
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
