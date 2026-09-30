<div align="center">

<img src="docs/assets/dalet_oc.jpg" alt="Dalet" width="180" style="border-radius: 50%;" />

# Dalet

**Compañera de Discord con IA conversacional mordaz y rastreador especializado de osu! — con memoria cognitiva reflexiva, análisis de habilidades en 5 dimensiones, balanceador multi-LLM, auto-moderación modular y telemetría en tiempo real.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-V3-4D6BFE?style=for-the-badge&logo=deepseek&logoColor=white)](https://deepseek.com)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-3.8%20Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://aistudio.google.com)
[![Groq](https://img.shields.io/badge/Groq-LPU%20Speed-F55036?style=for-the-badge&logo=fastapi&logoColor=white)](https://console.groq.com)
[![Turso](https://img.shields.io/badge/Turso-libSQL%20Cloud-00E599?style=for-the-badge&logo=sqlite&logoColor=black)](https://turso.tech)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

[Características](#características) | [osu! Analytics](#análisis-y-seguimiento-de-osu) | [Cerebro Conversacional y Memoria](#cerebro-conversacional-y-memoria-cognitiva) | [Auto-Moderación](#auto-moderación-modular) | [Stack Tecnológico](#stack-tecnológico) | [Dashboard](#dashboard-de-telemetría) | [Instalación](#instalación-y-puesta-en-marcha) | [Comandos](#comandos)

[English](README.md) │ **Español**

</div>

---

## Características

Dalet combina inteligencia artificial conversacional avanzada con telemetría de ritmo, seguridad de contenido proactiva y almacenamiento híbrido resiliente:

- **Desglose de Habilidades en 5 Dimensiones (`/skills`)**: Evaluación algorítmica de las mejores jugadas en Aim, Speed, Accuracy, Stamina y Reading calculadas en estrellas ($\star$), con re-ponderación de mods (DT, HR, EZ, FL) y un veredicto mordaz generado con IA.
- **Memoria Cognitiva Reflexiva**: Deducción psicológica en segundo plano que extrae rasgos, gustos y hábitos de los usuarios. Almacena el mensaje del usuario junto con la deducción interna de Dalet (`DaletThought`) para alimentar el contexto de forma natural y orgánica sin recitar memorias como un robot.
- **Sistema de Auto-Moderación Modular**: Inspección de doble capa que combina filtros regex heurísticos de 0 costo de API con escaneo multimodal de imágenes con Google Gemini Vision. Totalmente modular con interruptores individuales (`images`, `flood`, `links`, `scams`), detección de ráfagas en memoria, hash de medios duplicados y exenciones granulares por canal (`/mod ignore`).
- **Smart Load Balancer Multi-LLM**: Enrutamiento de alta velocidad entre DeepSeek V3, Google Gemini 3.8 Flash, Groq (<200ms de inferencia) y OpenRouter, con conmutación por error automática mediante disyuntores (Circuit Breakers).
- **Soporte Bilingüe Completo (i18n)**: Inglés por defecto para servidores globales, configurable a Español por servidor con caché en RAM de sub-milisegundo vía `/language`.
- **UI con Atomic Design**: Tarjetas e incrustaciones modernas enfocadas en tipografía e información densa para puntajes, perfiles, rankings y comparaciones, eliminando el ruido visual.
- **Almacenamiento Híbrido libSQL Cloud + SQLite**: Base de datos sincronizada en la nube mediante Turso (HTTP Pipeline) con réplica de respaldo local SQLite WAL, caché en memoria y vaciado asíncrono por lotes.
- **Telemetría y Dashboard en Vivo**: Panel web oscuro en tiempo real (Flask + Chart.js) que monitorea el consumo de tokens (Prompt/Completion), latencias por proveedor y estado de disyuntores.
- **Resúmenes Inteligentes de Canal**: Síntesis histórica de conversaciones recientes mediante `/resumir` y `d.summary`.

---

## Análisis y Seguimiento de osu!

Dalet cuenta con una capa de presentación completa basada en el Sistema de Diseño Atómico de Dalet ([docs/08_DESIGN_SYSTEM.md](docs/08_DESIGN_SYSTEM.md)), compatible con Bancho Classic y osu!(lazer):

### Desglose de Habilidades (`/skills` / `d.skills`)
Evalúa los mejores 50 a 100 puntajes de un jugador mediante heurísticas estadísticas:
- **Aim**: Circle Size (CS), velocidad angular de saltos y dificultad geométrica.
- **Speed**: Escala de BPM efectivo (1.5x con DoubleTime) y densidad de ráfagas rápidas.
- **Accuracy**: Overall Difficulty (OD), distribución de impactos ($300$ vs $100$/$50$) y multiplicadores de precisión estricta.
- **Stamina**: Longitud de drenado, conteo de notas ($\ge 1200$) y secuencias continuas.
- **Reading**: Approach Rate bajo (AR $\le 8.5$), densidad visual técnica y presión de lectura con Hidden (HD).
- **Veredicto de Dalet**: Un roast sarcástico y directo de 2 líneas que desglosa debilidades y manías del jugador.

### Tarjetas Principales
- **`/recent` (`d.recent` / `d.or`)**: Tarjeta densa de jugada reciente con mods, estrellas, impactos detallados `[300/100/50/Miss]`, PP, combo y estadísticas del mapa (`AR`, `OD`, `HP`, `CS`, `BPM`, `Tiempo`).
- **`/top` (`d.top`)**: Las 5 mejores jugadas registradas con banderas de país y formato pulido.
- **`/op` (`d.op`)**: Perfil completo de osu!, rango global y nacional, barra de progreso y conteo de notas (`SS`, `S`, `A`).
- **`/compare`**: Duelo cara a cara directo entre dos jugadores comparando diferenciales de PP y ventajas de estadísticas.

---

## Cerebro Conversacional y Memoria Cognitiva

Dalet cuenta con una personalidad distintiva: rápida, cínica, conversacional y mordaz, alejándose de los asistentes complacientes genéricos.

### Arquitectura de Memoria Reflexiva
- **Persistencia Dual**: Cada memoria almacena tanto la interacción del usuario (`UserMessage`) como la conclusión interna de Dalet (`DaletThought`).
- **Reflexión en Segundo Plano sin Latencia**: El análisis corre de forma asíncrona tras enviar el mensaje a Discord, sin agregar demora al usuario.
- **Filtros Heurísticos de Ahorro de Tokens**: Mensajes triviales (saludos, risas, confirmaciones cortas) se descartan en sub-milisegundos sin llamar a la IA.
- **Inyección Subconsciente**: Las memorias se introducen como trasfondo psicológico; Dalet tiene prohibido citar memorias mecánicamente (evitando frases robóticas como "Recuerdo que dijiste..."), asegurando una relación humana y natural.

---

## Auto-Moderación Modular

Dalet incluye una suite de moderación integrada y configurable para proteger servidores contra raids, contenido ilícito, phishing y spam.

### Capas de Inspección

1. **Anti-Flood y Filtro de Ráfagas (En Memoria)**:
   - Evalúa frecuencia de mensajes ($\ge 5$ mensajes en 4 segundos) y mensajes repetidos ($\ge 3$ en 10 segundos).
   - Genera firmas criptográficas de adjuntos (`filename_filesize`) para detectar spam idéntico de imágenes o GIFs en múltiples canales a la vez.
2. **Heurística Regex de Texto (Instantánea, 0 Costo API)**:
   - Comprueba patrones de enlaces adultos, spam de invitaciones, phishing de Discord Nitro / Steam, ladrones de tokens y tráfico ilícito.
   - Protección estricta con tolerancia cero para material CSAM con mitigación de falsos positivos en términos competitivos (Pokémon Go CP, CoD Points, Club Penguin).
3. **Visión Multimodal (Gemini Vision)**:
   - Analiza imágenes y GIFs adjuntos con prompts de clasificación de seguridad calibrados para no bloquear ecchi/waifu art ni masajes de espalda cotidianos.
   - Omite el escaneo automáticamente en canales marcados como NSFW (`channel.is_nsfw() = True`) o exentos con `/mod ignore module:images` para optimizar costos de API.

### Configuración Modular (`/mod`)

| Comando | Permiso | Descripción |
| :--- | :--- | :--- |
| `/mod setup [canal] [acción] [timeout] [ban]` | Administrador | Configuración inicial o actualización completa de parámetros. |
| `/mod channel <canal>` | Administrador | Actualiza solo el canal de alertas y reportes. |
| `/mod action <notify \| timeout \| ban>` | Administrador | Establece la acción por defecto ante infracciones NSFW. |
| `/mod timeout <minutos>` | Administrador | Modifica la duración del aislamiento (1 a 10080 minutos). |
| `/mod toggle <images \| flood \| links \| scams> [enabled]` | Administrador | Activa o desactiva módulos de moderación individualmente. |
| `/mod ignore <add \| remove \| list> [canal] [módulo]` | Administrador | Exime o re-incluye canales por módulo (`all`, `flood`, `images`, `links`, `scams`). Ideal para Mudae, waifus o bots de spam. |
| `/mod status` | Gestionar Mensajes | Muestra el estado operativo, módulos activos, canales exentos y registro reciente. |
| `/mod off` | Administrador | Pausa la auto-moderación en el servidor. |

---

## Comandos

Dalet es compatible tanto con comandos de barra diagonal (`/`) de Discord como con el prefijo tradicional `d.`:

### Comandos de osu!
| Comando | Tipo | Descripción |
| :--- | :--- | :--- |
| `/skills [usuario] [modo]` | Slash / `d.skills` | Desglose de habilidades 5D (Aim, Speed, Acc, Stamina, Reading) con veredicto IA |
| `/recent [usuario] [modo]` | Slash / `d.recent`, `d.or` | Muestra tu última jugada con estadísticas completas de mapa e impactos |
| `/top [usuario] [modo]` | Slash / `d.top` | Muestra tus mejores 5 jugadas registradas |
| `/op [usuario] [modo]` | Slash / `d.op` | Muestra el perfil completo de osu!, rango, precisión e historial de notas |
| `/compare <usuario>` | Slash | Compara estadísticas cara a cara contra otro jugador |
| `/link <usuario>` | Slash / `d.link` | Vincula tu cuenta de Discord con tu perfil de osu! |
| `d.unlink` | Prefijo | Desvincula tu cuenta de osu! |

### IA, Social y Utilidades
| Comando | Tipo | Descripción |
| :--- | :--- | :--- |
| `/language [en/es]` | Slash / `d.language` | Configura el idioma del servidor (Inglés por defecto / Español) |
| `/help` | Slash / `d.help` | Navegador interactivo y categorizado de ayuda |
| `/changelog` | Slash / `d.changelog` | Muestra notas de versión, hito mayor y commits recientes de Git |
| `/info` | Slash / `d.info` | Muestra versión, estado e información del sistema de Dalet |
| `/ping` | Slash / `d.ms`, `d.ping` | Consulta la latencia de respuesta y websocket en milisegundos |
| `/resumir [mensajes]` | Slash / `d.summary` | Genera un resumen inteligente con IA del chat reciente |
| `/lore <tema>` | Slash / `d.lore` | Investiga los archivos del servidor y genera crónicas mordaces |
| `/stats [usuario]` | Slash / `d.stats` | Estadísticas sociales y hábitos de conversación de un miembro |
| `/userinfo [usuario]` | Slash / `d.userinfo` | Creación de cuenta, fecha de ingreso y datos de un miembro |
| `/serverinfo` | Slash / `d.serverinfo` | Información general, miembros, propietario y fecha de creación del servidor |
| `/feedback <mensaje>` | Slash / `d.feedback` | Envía sugerencias, ideas o reportes de fallos al creador |

### Recordatorios
| Comando | Tipo | Descripción |
| :--- | :--- | :--- |
| `/reminder add <hora> <mensaje> [repetir]` | Slash | Programa recordatorios diarios, semanales o para fechas puntuales |
| `/reminder list` | Slash | Muestra todos los recordatorios activos en el servidor |
| `/reminder edit <id> [hora] [mensaje]` | Slash | Modifica un recordatorio programado existente |
| `/reminder remove <id>` | Slash | Elimina un recordatorio por su identificador |
| `/reminder toggle <id>` | Slash | Pausa o reactiva un recordatorio programado |

### Moderación (Solo Administradores)
| Comando | Permiso | Descripción |
| :--- | :--- | :--- |
| `/mod setup [canal] [acción] [timeout] [ban]` | Administrador | Configuración inicial o actualización de parámetros de moderación |
| `/mod toggle <módulo> [activo]` | Administrador | Activa o desactiva módulos (`images`, `flood`, `links`, `scams`) |
| `/mod ignore <acción> [canal] [módulo]` | Administrador | Exime o re-incluye canales por módulo (`all`, `flood`, `images`, `links`, `scams`) |
| `/mod status` | Gestionar Mensajes | Muestra el estado operativo, módulos activos y canales exentos |
| `/mod action <acción>` | Administrador | Establece la acción por defecto para contenido NSFW (`notify`, `timeout`, `ban`) |
| `/mod timeout <minutos>` | Administrador | Establece la duración del aislamiento en minutos (1 a 10080) |
| `/mod channel <canal>` | Administrador | Modifica el canal de alertas y auditoría |
| `/mod off` | Administrador | Desactiva la auto-moderación en todo el servidor |

### Administración del Servidor
| Comando | Permiso | Descripción |
| :--- | :--- | :--- |
| `/lock` / `d.lock` | Administrador | Bloquea comandos de Dalet en el canal actual |
| `/unlock` / `d.unlock` | Administrador | Desbloquea comandos de Dalet en el canal actual |
| `/proactive` | Administrador | Activa o desactiva la participación espontánea de la IA |
| `/reactive` | Administrador | Activa o desactiva respuestas de IA ante menciones |
| `/setwelcome` / `d.setwelcome` | Administrador | Configura el canal de mensajes de bienvenida |
| `/removewelcome` / `d.removewelcome` | Administrador | Elimina el canal de bienvenidas |
| `/setname <nombre>` / `d.setname` | Administrador | Establece un apodo personalizado para Dalet en el servidor |
| `d.cs` | Cualquiera | Muestra el estado de bloqueo y respuesta de IA del canal |
| `d.sync [here/global/clear]` | Administrador | Sincroniza comandos slash con el servidor o globalmente |

---

## Stack Tecnológico

| Componente | Tecnologías |
| :--- | :--- |
| Lenguaje y Entorno | Python 3.11+ / discord.py 2.x (asyncio) |
| Inteligencia Conversacional | DeepSeek V3 (núcleo) / Google Gemini 3.8 Flash (visión, fallback) |
| Inferencia Ultra-Rápida | Groq LPU (`openai/gpt-oss-120b`, `20b`) / OpenRouter |
| Capa de Base de Datos | Turso (libSQL Cloud Database sobre HTTPS) / SQLite 3 (WAL mode offline) |
| Web y Telemetría | Flask / Chart.js / CSS Vanilla |
| API de Ritmo | osu! API v2 (OAuth2 Client Credentials) |
| Despliegue y CI/CD | Render (Despliegue continuo automático sincronizado con rama main) |

---

## Dashboard de Telemetría

Dalet incluye un panel web en tiempo real accesible en el puerto configurado (`http://localhost:8080/` o en tu URL de producción):

- **Consumo de Tokens**: Desglose en tiempo real de tokens Prompt y Completion para DeepSeek, Gemini, Groq y OpenRouter.
- **Gráficos de Tráfico**: Distribución visual de peticiones y balanceo de carga.
- **Disyuntores (Circuit Breakers)**: Indicadores de salud (`HEALTHY`, `COOLDOWN`, `TRIPPED`).

---

## Instalación y Puesta en Marcha

### 1. Clonar el repositorio
```bash
git clone https://github.com/Janlhx/Dalet-Proyect.git
cd Dalet-Proyect
```

### 2. Crear entorno virtual e instalar dependencias
```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux / macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar variables de entorno (`.env`)
Crea un archivo `.env` en la raíz del proyecto:

```env
# Discord Bot
DISCORD_TOKEN=tu_token_de_discord

# Base de Datos Híbrida
TURSO_DATABASE_URL=https://tu-base-de-datos.turso.io
TURSO_AUTH_TOKEN=tu_token_turso

# Proveedores de IA
AI_ROUTING_MODE=auto
DEEPSEEK_API_KEY=tu_clave_deepseek
GEMINI_API_KEY=tu_clave_gemini
GEMINI_MODEL=gemini-3.8-flash
GROQ_API_KEY=tu_clave_groq
OPENROUTER_API_KEY=tu_clave_openrouter

# osu! API v2
OSU_CLIENT_ID=tu_client_id_osu
OSU_CLIENT_SECRET=tu_client_secret_osu

# Web Dashboard
PORT=8080
```

### 4. Permisos del Bot de Discord

En el [Discord Developer Portal](https://discord.com/developers/applications), asegúrate de que tu URL de invitación contenga:
- **Scopes**: `bot`, `applications.commands`
- **Permissions**: `Read Messages`, `Send Messages`, `Embed Links`, `Manage Messages`, `Moderate Members`, `Ban Members`

Activa los siguientes **Privileged Gateway Intents**:
- `Server Members Intent`
- `Message Content Intent`

### 5. Iniciar Dalet
```bash
python dalet_main.py
```

### 6. Sincronizar comandos slash
Al iniciar por primera vez, ejecuta en un canal con permisos de administrador:
```
d.sync here
```

---

<div align="center">
Hecho con precisión para Discord y la comunidad de osu!.
</div>
