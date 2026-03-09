# 🔑 Variables de Entorno (`.env`)

> Este archivo contiene todos los **secretos y configuraciones** del bot. Nunca debe subirse a Git (está en `.gitignore`).

---

## Todas las Variables

### Discord

| Variable        | Descripción                    | Cómo obtenerla                                                                                 |
| --------------- | ------------------------------ | ---------------------------------------------------------------------------------------------- |
| `DISCORD_TOKEN` | Token de autenticación del bot | [Discord Developer Portal](https://discord.com/developers/applications) → Tu app → Bot → Token |

### IA Principal (Gemini)

| Variable         | Descripción                      | Cómo obtenerla                                                                |
| ---------------- | -------------------------------- | ----------------------------------------------------------------------------- |
| `GEMINI_API_KEY` | Clave de la API de Google Gemini | [Google AI Studio](https://aistudio.google.com/app/apikey)                    |
| `GEMINI_MODEL`   | Modelo a usar _(opcional)_       | Defecto: `gemini-2.0-flash`. Otros: `gemini-1.5-pro`, `gemini-2.0-flash-lite` |

### IA Alternativa (Groq)

| Variable              | Descripción                               | Cómo obtenerla                               |
| --------------------- | ----------------------------------------- | -------------------------------------------- |
| `GROQ_API_KEY`        | Clave de la API de Groq                   | [console.groq.com](https://console.groq.com) |
| `GROQ_MODEL`          | Modelo principal de Groq _(opcional)_     | Defecto: `llama-3.3-70b-versatile`           |
| `GROQ_MODEL_FALLBACK` | Modelo de emergencia de Groq _(opcional)_ | Defecto: `llama-3.1-8b-instant`              |
| `AI_PROVIDER`         | Proveedor activo _(opcional)_             | `gemini` (defecto) o `groq`                  |

### Base de Datos (Neon)

| Variable       | Descripción                  | Cómo obtenerla                                                                   |
| -------------- | ---------------------------- | -------------------------------------------------------------------------------- |
| `DATABASE_URL` | URL de conexión a PostgreSQL | [console.neon.tech](https://console.neon.tech) → Tu proyecto → Connection string |

> Formato esperado: `postgresql://user:password@host/database?sslmode=require`

### osu! API

| Variable            | Descripción                     | Cómo obtenerla                                                                                  |
| ------------------- | ------------------------------- | ----------------------------------------------------------------------------------------------- |
| `OSU_CLIENT_ID`     | ID de cliente de la app de osu! | [osu.ppy.sh/home/account/edit](https://osu.ppy.sh/home/account/edit) → OAuth → Nueva Aplicación |
| `OSU_CLIENT_SECRET` | Secreto del cliente de osu!     | El mismo lugar que el CLIENT_ID                                                                 |

---

## Ejemplo de archivo `.env`

```env
# Discord
DISCORD_TOKEN=MTxxxxxxxxxxxxxxxxxxxxxxxx.Gxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Gemini (IA Principal)
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GEMINI_MODEL=gemini-2.0-flash

# Groq (IA de Respaldo)
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_MODEL_FALLBACK=llama-3.1-8b-instant

# Proveedor activo: "gemini" o "groq"
AI_PROVIDER=gemini

# Neon (PostgreSQL)
DATABASE_URL=postgresql://dalet_owner:password@ep-xxx.us-east-2.aws.neon.tech/dalet?sslmode=require

# osu!
OSU_CLIENT_ID=12345
OSU_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## ¿Cómo se cargan estas variables en el código?

```python
from dotenv import load_dotenv
import os

load_dotenv()  # Lee el archivo .env y pone las variables en el entorno del sistema

DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
```

Se usa la librería `python-dotenv`. En producción (Render), las variables se configuran directamente en el dashboard de Render como "Environment Variables" y no se necesita el archivo `.env`.

---

## En Render (Producción)

Las variables se configuran en:  
`Dashboard de Render → Tu servicio → Environment → Environment Variables`

Son exactamente las mismas variables pero gestionadas por la plataforma en vez de un archivo local.
