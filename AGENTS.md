# AGENTS.md — Dalet v4 Agentic Engineering & Cloud Architecture Blueprint

Bienvenido al repositorio de **Dalet v4**. Cualquier agente principal o subagente que opere en este workspace debe respetar la arquitectura y reglas definidas aquí.

## 1. Arquitectura Cloud & Cognitiva (Dalet v4)
- **Compute & Gateway (`bot.py`):** Contenedor unificado (Koyeb / Docker) que ejecuta el cliente WebSocket de Discord (`discord.py`) + servidor HTTP de telemetría (`DashboardService`).
- **Dual-Engine Persistence (`database/turso_client.py` + `database/connection.py`):**
  - Sincronización en la nube vía **Turso (libSQL HTTPS)** con fallback local inmediato a **SQLite WAL** (`dalet_memory.db`) y caché en memoria `TTLCache` (`O(1)`).
- **Cerebro Multi-LLM & Enrutamiento (`services/nlp_service.py`):**
  - **TypeSafe Jev (`System One`):** Clasificación rápida de intención y puerta proactiva (`$0` / baja latencia).
  - **Gemini 3.8 Flash / 2.5 Flash + Groq (Llama 3.3 70B):** Generación conversacional con *Tool Calling* autónomo y rotación automática ante errores `429`.
- **Pirámide Semántica `L0–L3` + Auto-Entrenamiento (`services/memory_service.py`):**
  - `L0`: Historial de canal unificado.
  - `L1`: Átomos cognitivos en `UserMemories` con gating léxico estricto (sin stopwords).
  - `L2`: Escenario activo en `UserPersonas` con decaimiento temporal de 14 días.
  - `L3`: Perfil Persona duradero + calibración social por usuario.
  - `PersonaInsights`: Reglas globales de auto-corrección de personalidad destiladas en una sola pasada (*Single-Pass Background Distillation*).

## 2. Reglas Inquebrantables para Agentes
1. **Cero Emojis en UI de Discord (`.agents/rules/dalet-style.md`):**
   - Prohibido usar emojis coloridos en Embeds, botones o respuestas de comandos. Usa exclusivamente glifos tipográficos de `ui/atoms.py`: `✦`, `▸`, `▫`, `│`, `★`, `✓`, `✕`.
2. **Paridad de Comandos (`Slash /` + `Prefijo d.`):**
   - Todo cambio en `handlers/dalet_slash_commands.py` debe reflejarse en `handlers/dalet_osucommands.py` (`d.top`, `d.rb`, `d.recent`, `d.rs`, `d.rp`, `d.op`).
3. **Sincronización Continua VibeWise (`.agents/rules/vibewise.md`):**
   - Mantén sincronizados `handlers/dalet_helpcommands_handlers.py`, `services/changelog_service.py`, `README.md`, `README_ES.md` y el grafo `graphify-out/` (`graphify update .`).

## 3. Ecosistema Agéntico Local (`.agents/`)
- **Skills (`.agents/skills/`):**
  - `dalet-osu-card-craft`: Diseño de embeds de osu!, filtros y gráficos PP.
  - `dalet-persona-calibration`: Calibración de personalidad, memoria `L0–L3`, `GuildCommunityLore` y `PersonaInsights`.
  - `dalet-vibewise-sync`: Sincronización documental y Graphify.
  - `typesafe-ai`: Primitivas de juicio estructurado con TypeSafe Jev.
- **Subagentes Persistentes (`.agents/agents/`):**
  - `osu-ux-engineer`: Especialista en embeds limpios (mobile-first), filtros osu!, `rosu-pp-py` y paridad `/` vs `d.`.
  - `persona-memory-auditor`: Auditor de tono orgánico, atribución multi-usuario, concordancia de género y memoria `L0–L3`.
  - `vibewise-doc-keeper`: Sincronización de `/help` (ES/EN), `changelog_service.py`, READMEs y `graphify update .`.
  - `security-qa-verifier`: Auditoría SSRF/OWASP, aislamiento multi-servidor y verificación integral `pytest`.
- **Plugin & MCP Propio (`.agents/plugins/dalet-devkit/`):**
  - Servidor MCP `dalet-brain-mcp` (`tools/dalet_mcp_server.py`) con acceso directo a la salud de la BD, Pirámide Semántica `L1–L3` y `PersonaInsights`.
- **Hooks de Seguridad (`.agents/hooks.json`):**
  - `PreToolUse` (`tools/dalet_hook_guard.py`): Bloquea comandos destructivos (`git push --force`, borrado de `.env` o `.db`) y audita el uso de herramientas.
