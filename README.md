<div align="center">

<img src="docs/assets/dalet_oc.jpg" alt="Dalet" width="180" style="border-radius: 50%;" />

# Dalet

**Bot conversacional inteligente para Discord con memoria persistente, integración avanzada de osu!, balanceador de carga multi-IA y Dashboard web de telemetría en tiempo real.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-2.5%20Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://aistudio.google.com)
[![Groq](https://img.shields.io/badge/Groq-LPU%20Speed-F55036?style=for-the-badge&logo=fastapi&logoColor=white)](https://console.groq.com)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-Free%20Tier-6366F1?style=for-the-badge&logo=openai&logoColor=white)](https://openrouter.ai)
[![Turso](https://img.shields.io/badge/Turso-libSQL%20Cloud-00E599?style=for-the-badge&logo=sqlite&logoColor=black)](https://turso.tech)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

[✨ Características](#-características) · [🛠️ Stack Tecnológico](#️-stack-tecnológico) · [🖥️ Web Dashboard](#-web-dashboard--telemetría) · [🎮 osu! UI System](#-integración-y-diseño-de-osu) · [🚀 Instalación](#-instalación-y-despliegue) · [💬 Comandos](#-comandos) · [🏗️ Arquitectura](#️-arquitectura) · [📚 Docs](#-documentación)

</div>

---

## ✨ Características

Dalet combina inteligencia artificial conversacional, análisis en tiempo real y persistencia híbrida:

- 🧠 **Smart Tri-Load Balancer**: Distribución inteligente de tráfico entre **Google Gemini** (calidad y visión), **Groq** (inferencia ultrarrápida <200ms) y **OpenRouter** (catálogo libre de cuotas).
- 🛡️ **Circuit Breakers y Auto-Failover**: Tolerancia total a fallos. Si una API alcanza su límite de tasa (`429`) o saturación (`503`), el bot desvía el 100% del tráfico automáticamente sin interrupción de servicio.
- 🖥️ **Web Dashboard en Vivo**: Panel web oscuro con gráficos interactivos (Chart.js), conteo en tiempo real de **Prompt y Completion Tokens**, latencias y estado de salud de los modelos.
- 💾 **Persistencia Híbrida libSQL + SQLite**: Base de datos en la nube con **Turso (libSQL HTTP Pipeline)** y fallback local instantáneo con **SQLite en modo WAL** y buffers de escritura por lotes.
- 🎮 **osu! Atomic UI System**: Tarjetas rediseñadas de alta densidad para `/recent`, `/top`, `/profile` y `/compare` con compatibilidad para scores de Lazer y Classic, banderas nativas y telemetría completa.
- 📝 **Smart Channel Summaries**: Lectura de historial y generación de resúmenes contextuales inteligentes mediante `/resumir` y `d.summary`.
- 🧠 **Memoria Contextual a Largo Plazo**: Recuerda detalles y preferencias explícitas de los usuarios a través de reinicios.

---

## 🛠️ Stack Tecnológico

| Capa | Tecnologías |
| :--- | :--- |
| **Lenguaje & Core** | Python 3.11+ · discord.py 2.x (asyncio) |
| **Modelos de IA** | Google Gemini (`gemini-2.5-flash` / `2.0`) · Groq (`openai/gpt-oss-120b`, `20b`) · OpenRouter (`openrouter/free`, `deepseek-r1:free`, `llama-3.3:free`) |
| **Persistencia Cloud** | [Turso](https://turso.tech) (libSQL Database over HTTP Pipeline) |
| **Persistencia Local** | SQLite 3 (WAL Mode, in-memory LRU caching & async log batching) |
| **Dashboard & Web** | Flask · Chart.js · CSS Grid Glassmorphism |
| **osu! API** | [osu! API v2](https://osu.ppy.sh/docs/index.html) (OAuth2 Client Credentials) |
| **Hosting & Deploy** | [Render](https://render.com) (Web Service con Health Check en `:8080`) |

---

## 🖥️ Web Dashboard & Telemetría

Dalet incluye un panel web en tiempo real accesible directamente en el puerto del servicio (por ejemplo `https://dalet-proyect.onrender.com/` o `http://localhost:8080/`):

- **Tokens Consumidos**: Desglose exacto de Prompt / Completion Tokens para Gemini, Groq y OpenRouter.
- **Gráficos de Tráfico**: Comparativa visual en tiempo real de carga de trabajo entre modelos.
- **Estado de Circuit Breakers**: Indicadores de salud (`HEALTHY` / `COOLDOWN`).
- **Gateway & Uptime**: Latencia de Discord, servidores conectados, miembros y tiempo activo.
- **Feed en Vivo**: Registro en vivo con las últimas interacciones de IA y latencias.

---

## 🎮 Integración y Diseño de osu!

Las tarjetas de osu! fueron desarrolladas bajo el **Sistema de Diseño Atómico de Dalet** ([docs/08_DESIGN_SYSTEM.md](docs/08_DESIGN_SYSTEM.md)):

- **`/recent`**: Tarjeta estructurada con mods (`+HDDT`), dificultad `[6.52★]`, desglose de aciertos `[300/100/50/Miss]`, PP, precisión, duración `MM:SS`, BPM y atributos `AR / OD / HP / CS`.
- **`/top`**: Top 5 mejores puntuaciones del jugador en un formato compacto con banderas nativas.
- **`/profile` & `/compare`**: Perfil global, rangos de país y comparación directa entre jugadores.
- **Lazer & Classic Support**: Extracción correcta de scores estandarizados de Lazer y cálculo estimado para partidas fallidas (`Rank: F`).

---

## 🚀 Instalación y Despliegue

### 1. Clonar el repositorio
```bash
git clone https://github.com/Janlhx/Dalet-Proyect.git
cd Dalet-Proyect
```

### 2. Crear entorno virtual e instalar dependencias
```bash
python -m venv venv
# En Windows:
venv\Scripts\activate
# En Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar variables de entorno (`.env`)
Crea un archivo `.env` en la raíz del proyecto:

```env
# --- Discord Bot ---
DISCORD_TOKEN=tu_discord_bot_token

# --- Bases de Datos (Turso libSQL Cloud + SQLite Local) ---
TURSO_DATABASE_URL=https://tu-db-nombre.turso.io
TURSO_AUTH_TOKEN=tu_turso_auth_token

# --- Inteligencia Artificial (Smart Tri-Load Balancer) ---
AI_ROUTING_MODE=auto

# 1. Google Gemini (Primario para Visión y Búsquedas Web)
GEMINI_API_KEY=tu_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash

# 2. Groq (Ultra Velocidad <200ms)
GROQ_API_KEY=tu_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
GROQ_MODEL_FALLBACK=openai/gpt-oss-20b

# 3. OpenRouter (Modelos Gratuitos & Variedad)
OPENROUTER_API_KEY=tu_openrouter_api_key
OPENROUTER_MODEL=openrouter/free

# --- osu! API v2 ---
OSU_CLIENT_ID=tu_osu_client_id
OSU_CLIENT_SECRET=tu_osu_client_secret

# --- Web Dashboard Port ---
PORT=8080
```

### 4. Ejecutar el Bot
```bash
python dalet_main.py
```

---

## 💬 Comandos

Dalet soporta **Slash Commands nativos (`/`)** y el prefijo tradicional `d.`:

### 🎮 osu! Commands
| Comando | Tipo | Descripción |
| :--- | :--- | :--- |
| `/recent` o `d.recent` | Slash / Prefijo | Muestra tu última jugada en osu! con diseño estructurado |
| `/top` o `d.top` | Slash / Prefijo | Muestra tus 5 mejores jugadas registradas |
| `/profile` o `d.profile` | Slash / Prefijo | Muestra tu perfil de jugador, rango y estadísticas |
| `/compare` | Slash | Compara tu récord en el mapa actual contra otro jugador |
| `d.osuLink <user>` | Prefijo | Vincula tu cuenta de osu! a tu Discord |
| `d.osuAnalyze` | Prefijo | Análisis con IA sobre tu estilo de juego y áreas de mejora |
| `d.osuCoach` | Prefijo | Plan de entrenamiento personalizado generado por la IA |

### 🤖 Inteligencia Artificial & Utilidades
| Comando | Tipo | Descripción |
| :--- | :--- | :--- |
| `/resumir [mensajes]` | Slash | Genera un resumen inteligente de los últimos mensajes del canal |
| `/lore` | Slash | Cuenta la historia y personalidad de Dalet |
| `/gemini <proactive/reactive>`| Slash | Configura si Dalet habla libremente o solo por mención |
| `/help` | Slash | Menú interactivo de ayuda categorizado |
| `d.admin blockChannel` | Prefijo | Bloquea la interacción de Dalet en un canal específico |
| `d.admin unblockChannel` | Prefijo | Desbloquea un canal para permitir interacción |

---

## 🏗️ Arquitectura

```
Dalet-Proyect/
├── dalet_main.py                  ← Bootstrap del bot, semáforos y servidor Flask
│
├── handlers/                      ← Discord Cogs y controladores de eventos
│   ├── dalet_nlpchat.py           ← Motor de conversación reactivo/proactivo
│   ├── dalet_slash_commands.py    ← Slash commands nativos de Discord
│   ├── dalet_osu_presenter.py     ← Presentador visual de tarjetas de osu!
│   ├── dalet_smartresume.py       ← Generador de resúmenes con IA
│   ├── dalet_osucommands.py       ← Comandos tradicionales de osu!
│   ├── dalet_helpcommands_handlers.py
│   └── dalet_events_handlers.py
│
├── services/                      ← Capa de Lógica de Negocio
│   ├── nlp_service.py             ← Smart Tri-Load Balancer (Gemini + Groq + OpenRouter)
│   ├── dashboard_service.py       ← Servidor web del Dashboard & API de telemetría
│   ├── memory_service.py          ← Gestión de memoria y contexto de chat
│   └── osu_service.py             ← Cliente async de la API v2 de osu!
│
├── database/                      ← Persistencia Híbrida
│   ├── turso_client.py            ← Cliente libSQL HTTP Pipeline para Turso Cloud
│   ├── sqlite_manager.py          ← SQLite local (WAL) para analíticas y fallback
│   └── repositories/              ← Repositorios de datos (User, Osu, Admin, Analytics)
│
├── ui/                            ← Atomic Design System
│   ├── atoms.py                   ← Tokens de color, badges de rango y glifos
│   ├── molecules.py               ← Barras de progreso ASCII y footers
│   └── organisms.py               ← Embeds compuestos
│
└── docs/                          ← Documentación técnica completa
```

---

## 📚 Documentación

| Documento | Descripción |
| :--- | :--- |
| [01 — Arquitectura](docs/01_ARCHITECTURE.md) | Flujo general del sistema y capas de abstracción |
| [07 — Variables de Entorno](docs/07_VARIABLES_ENVIRONMENT.md) | Guía completa de configuración de variables |
| [08 — Sistema de Diseño](docs/08_DESIGN_SYSTEM.md) | Tokens de diseño, tipografía y Atomic UI |

---

<div align="center">

Hecho con ❤️ por **Litxe** · Colombia 🇨🇴

</div>
