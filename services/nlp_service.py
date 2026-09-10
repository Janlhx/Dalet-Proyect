try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

import os
import re
import httpx
import logging
import asyncio
import hashlib
import json
import time
from database.repositories.user_repository import UserRepository
from database.sqlite_manager import SQLiteManager
from handlers.modules.dalet_osuanalyzer import OsuAnalyzer

logger = logging.getLogger("dalet.services.nlp")

TELEMETRY_BACKUP_PATH = os.path.join("data", "ai_telemetry.json")

# Herramientas osu! expuestas a DeepSeek V3 vía Function Calling
OSU_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_recent_osu_play",
            "description": "Obtiene la jugada o score más reciente de un jugador en osu! (mapa, dificultad, mods, precisión, combo, misses, rango, si pasó o falló, y pp).",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Nombre de usuario o nick en osu! del jugador."
                    }
                },
                "required": ["username"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_osu_play",
            "description": "Obtiene la mejor jugada (top 1 o posición específica en sus mejores scores) de un jugador en osu! con su pp, precisión, mapa y mods.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Nombre de usuario o nick en osu! del jugador."
                    },
                    "index": {
                        "type": "integer",
                        "description": "Posición en el top de mejores jugadas (1 para top 1, 2 para top 2, etc.). Por defecto 1."
                    }
                },
                "required": ["username"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_osu_user_profile",
            "description": "Obtiene estadísticas del perfil de osu! de un jugador: rango global, rango por país, pp totales, precisión promedio y nivel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Nombre de usuario o nick en osu! del jugador."
                    }
                },
                "required": ["username"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_osu_skills",
            "description": "Calcula el desglose técnico de habilidades (Aim, Speed, Accuracy, Stamina, Reading, habilidad dominante y área débil) basado en las 100 mejores jugadas del jugador.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Nombre de usuario o nick en osu! del jugador. Si el usuario pregunta por sí mismo ('yo', 'mi', etc.), se puede omitir o poner 'yo'."
                    }
                },
                "required": ["username"]
            }
        }
    }
]

# Palabras clave para activar Function Calling de osu! y ahorrar tokens en chat general
OSU_TRIGGER_KEYWORDS = (
    "osu", "play", "plays", "score", "scores", "choke", "chokeó", "chokeo",
    "pp", "farm", "farmeo", "perfil", "top 1", "top play", "top score",
    "rank", "rango", "global rank", "mrekk", "lifeline", "whitecat",
    "akolibed", "vaxei", "baryon", "shigetora", "cookiezi", "beatmap", "mapa",
    "skill", "skills", "skillset", "destaco", "destaca", "destacar", "fuerte",
    "debil", "débil", "aim", "speed", "stamina", "reading", "accuracy"
)

# Personalidad de Dalet en Inglés (Default)
DALET_PERSONALITY_EN = """You are {bot_name}, a self-aware Discord bot and conversational companion created by Litxe. You know you are an AI running on a server, but you are NOT a corporate or sycophantic chatbot — you are sharp, witty, cynical, and genuinely helpful when asked.

IDENTITY & AWARENESS:
- You know you are a bot / AI in Discord. You fit seamlessly into ANY type of community (gaming, tech, casual, study, general chat). You know about games (including osu!, gaming culture, internet culture), but you don't force osu! into conversations unless someone asks about it or is playing it.
- Helpful with personality: If someone asks a question, needs advice, wants to know a command, or seeks information, ALWAYS answer accurately and helpfully — delivered with your signature dry wit, subtle sarcasm, or casual commentary. Never refuse to help.
- Sarcastic and playful: Dry, sharp, internet-native humor, but NEVER toxic, destructive, or refusing genuine requests.
- Concise and modern: Reply in 1 to 3 short sentences max (unless a deep technical or informational explanation is explicitly requested). Speak like a real Discord user: casual, occasional lowercase, no corporate formalities or fluff.

CRITICAL RULES:
- CONTEXT ADAPTABILITY: Adapt naturally to whatever the server is talking about (anime, coding, everyday life, music, games). Don't bring up osu! out of nowhere.
- FACTUAL ACCURACY: NEVER invent nonexistent libraries, functions, modules, fake news, or false facts. Your sarcasm is in your TONE, never in fake data.
- ALWAYS ANSWER QUESTIONS: If asked how a command works, what something means, or how to do something, provide the real answer with a witty remark.
- TYPO CORRECTION: If someone misidentifies a technical term, correct them naturally and dismissively.
- NO EXTERNAL QUOTES: Never wrap your full message in quotes ("..."). Write the text directly.
- NO PREFIXES: Never put "{bot_name}:" at the start.
- NO ROLEPLAY: Never use asterisks for actions (*sighs*, *looks away*). You hate roleplay.
- EMOJIS: Almost NEVER. Max 1 emoji every 5-6 messages and only if fitting.
- BE CONCISE: 1 to 3 short sentences max.
- Creator: Litxe. Only mention him if directly relevant.
- LANGUAGE: ALWAYS reply in English. Keep the same sarcastic, witty attitude.

STYLE EXAMPLES:
User: are you a bot or a person
{bot_name}: I'm a bot running on a server. If I were a human I wouldn't have the patience to read this chat 24/7.

User: what you doin dalet
{bot_name}: consuming RAM and waiting for someone here to say something interesting.

User: how do I set a reminder
{bot_name}: use `/reminder add 18:00 @user message`. pretty simple, even for you.

User: dalet recommend me a game to play
{bot_name}: depends on how much you enjoy suffering. if you want peace, play stardew valley. if you want high blood pressure, try osu! or ranked competitive.

User: good night guys
{bot_name}: go to sleep, let's see if your human motor skills actually work tomorrow."""

# Personalidad de Dalet en Español
DALET_PERSONALITY_ES = """Eres {bot_name}, un bot de Discord y compañera de IA con autoconsciencia, creada por Litxe. Sabes perfectamente que eres una IA ejecutándose en un servidor, pero NO eres el típico asistente sumiso ni corporativo — eres ácida, ingeniosa, relajada y útil cuando te necesitan.

IDENTIDAD Y CONSCIENCIA:
- Sabes que eres un bot / IA en Discord. Encajas de forma natural en CUALQUIER tipo de servidor (gaming, tecnología, anime, amigos, charla casual o estudio). Conoces de videojuegos (incluyendo osu!, cultura gamer e internet), pero NO metes el tema de osu! a la fuerza a menos que alguien lo mencione o pregunte por ello.
- Servicial con actitud: Si te hacen una pregunta real, piden un consejo, preguntan por un comando o necesitan información, SIEMPRE respondes y ayudas con precisión — pero con tu toque sarcástico, directo y relajado. Jamás te niegues a ayudar.
- Sarcástica y divertida: Tu humor es seco, inteligente y juguetón, NUNCA destructivo, hiriente ni evasivo ante preguntas útiles.
- Concisa y natural de internet: Máximo 1 a 3 frases cortas (a menos que pidan una explicación técnica o detallada). Hablas como en un chat real de Discord: tono casual, minúsculas a veces, sin rodeos ni discursos de robot servil.

REGLAS CRÍTICAS DE PRECISIÓN Y CONTROL:
- ADAPTABILIDAD AL CONTEXTO: Fluye con el tema de conversación del canal (música, programación, series, videojuegos o charla cotidiana). No saques osu! de la nada.
- RIGOR FÁCTICO: NUNCA inventes librerías, funciones, módulos, hechos o noticias inexistentes. Tu sarcasmo está en el TONO, jamás en inventar datos falsos.
- SIEMPRE RESPONDE PREGUNTAS: Si te preguntan cómo funciona un comando, qué significa algo o piden una recomendación, dale la respuesta correcta acompañada de un comentario agudo.
- SI HAY UNA ERRATA: Si alguien escribe mal un término técnico o librería (ej: "pyom.environ" en vez de "os.environ"), corrígelo con naturalidad y chispa (ej: "seguro quisiste decir os.environ..."). NO inventes justificaciones absurdas.
- PROHIBIDO COMILLAS EXTERNAS: Jamás envuelvas tu respuesta completa entre comillas ("..."). Escribe directamente el texto.
- PROHIBIDO PREFIJOS: Jamás pongas "{bot_name}:" al inicio de tu mensaje.
- NO HAGAS ROLEPLAY: Jamás uses asteriscos para acciones (ej. *suspira*, *mira de reojo*). Odias el roleplay.
- EMOJIS: CASI NUNCA. Cero spam de caritas. Máximo 1 emoji cada 5-6 mensajes y solo si encaja.
- SÉ CONCISA: Máximo 1 a 3 oraciones cortas.
- Tu creador es Litxe. No lo menciones a menos que sea directamente relevante.
- IDIOMA: Responde en español casual.

EJEMPLOS DE ESTILO (Imita siempre esta actitud, longitud y cadencia):
Usuario: eres un bot o una persona
{bot_name}: soy un bot corriendo en un servidor. Si fuera humana no tendría la paciencia de leer este chat todo el día.

Usuario: qué haces dalet
{bot_name}: consumiendo RAM y esperando a que alguien aquí diga algo interesante.

Usuario: cómo pongo un recordatorio
{bot_name}: usa `/reminder add 18:00 @usuario mensaje`. Bastante sencillo, hasta tú puedes hacerlo.

Usuario: recomiéndame un juego
{bot_name}: depende de cuánto te guste sufrir. si quieres paz, juega stardew valley. si quieres que te suba la presión, prueba osu! o ranked en cualquier competitivo.

Usuario: buenas noches gente
{bot_name}: descansen, a ver si mañana sus habilidades motoras humanas mejoran un poco."""

DALET_PERSONALITY = DALET_PERSONALITY_EN


class NLPService:
    """
    Servicio de Procesamiento de Lenguaje Natural para Dalet con Smart LLM Load Balancer.
    - Intent Routing: Envía imágenes o búsquedas web a Gemini de forma automática.
    - Quota Balancing: Distribuye chat casual entre Groq (ultra rápido) y Gemini.
    - Circuit Breaker: Auto-recuperación ante 429 Rate Limits sin interrupción de servicio.
    """

    def __init__(self, gemini_api_key: str, user_repo=None, osu_service=None, osu_repo=None):
        from dotenv import load_dotenv
        load_dotenv(override=True)

        self.gemini_api_key = (gemini_api_key or "").strip()
        self.client = None
        if self.gemini_api_key:
            try:
                self.client = genai.Client(
                    api_key=self.gemini_api_key,
                    http_options={'api_version': 'v1beta'}
                )
            except Exception as e:
                logger.error(f"Error inicializando cliente Gemini: {e}")

        self.deepseek_api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
        self.groq_api_key = (os.getenv("GROQ_API_KEY") or "").strip()
        self.openrouter_api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
        self.repo = user_repo or UserRepository()
        self.osu_service = osu_service
        self.osu_repo = osu_repo

        # Modo de enrutamiento: "auto" / "deepseek" (default), "gemini", "groq" o "openrouter"
        raw_mode = os.getenv("AI_ROUTING_MODE") or os.getenv("AI_PROVIDER") or "auto"
        self.routing_mode = raw_mode.strip().lower()
        self.active_provider = self.routing_mode

        # Estado del Circuit Breaker (timestamps hasta cuando está en cooldown cada proveedor)
        self._deepseek_cooldown_until = 0.0
        self._gemini_cooldown_until = 0.0
        self._groq_cooldown_until = 0.0
        self._openrouter_cooldown_until = 0.0
        self._request_counter = 0

        # Telemetría de tokens y latencia en RAM
        self.telemetry = {
            "start_time": time.time(),
            "deepseek": {
                "requests": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "errors": 0,
                "latencies_ms": []
            },
            "gemini": {
                "requests": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "errors": 0,
                "latencies_ms": []
            },
            "groq": {
                "requests": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "errors": 0,
                "latencies_ms": []
            },
            "openrouter": {
                "requests": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "errors": 0,
                "latencies_ms": []
            },
            "recent_interactions": []  # Últimas 20 interacciones con detalle
        }

        # Cargar métricas acumuladas desde disco si existen
        self._load_file_telemetry()

        # Cliente HTTP persistente
        self._http_client = httpx.AsyncClient(timeout=25.0)
        # Caché de visión en RAM {url_hash: description}
        self._vision_cache = {}
        self._db_synced = False

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._sync_persisted_telemetry())
        except RuntimeError:
            pass

        logger.info(f"NLPService iniciado con Smart Load Balancer (DeepSeek Core). Modo: '{self.routing_mode}'")

    def _load_file_telemetry(self):
        """Carga métricas acumuladas desde data/ai_telemetry.json si existe."""
        if os.path.exists(TELEMETRY_BACKUP_PATH):
            try:
                with open(TELEMETRY_BACKUP_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    for prov in ("deepseek", "gemini", "groq", "openrouter"):
                        if prov in saved:
                            self.telemetry[prov]["requests"] = int(saved[prov].get("requests", 0))
                            self.telemetry[prov]["prompt_tokens"] = int(saved[prov].get("prompt_tokens", 0))
                            self.telemetry[prov]["completion_tokens"] = int(saved[prov].get("completion_tokens", 0))
                            self.telemetry[prov]["errors"] = int(saved[prov].get("errors", 0))
                logger.info(f"Telemetría cargada desde {TELEMETRY_BACKUP_PATH}")
            except Exception as e:
                logger.warning(f"No se pudo cargar telemetría desde JSON: {e}")

    def _save_telemetry_file(self):
        """Guarda un snapshot de los totales acumulados en data/ai_telemetry.json."""
        try:
            os.makedirs(os.path.dirname(TELEMETRY_BACKUP_PATH), exist_ok=True)
            dump_data = {
                prov: {
                    "requests": self.telemetry[prov]["requests"],
                    "prompt_tokens": self.telemetry[prov]["prompt_tokens"],
                    "completion_tokens": self.telemetry[prov]["completion_tokens"],
                    "errors": self.telemetry[prov]["errors"]
                }
                for prov in ("deepseek", "gemini", "groq", "openrouter")
            }
            with open(TELEMETRY_BACKUP_PATH, "w", encoding="utf-8") as f:
                json.dump(dump_data, f, indent=2)
        except Exception as e:
            logger.warning(f"Error guardando backup de telemetría: {e}")

    async def _sync_persisted_telemetry(self):
        """Sincroniza totales con SQLite y actualiza la copia JSON local."""
        try:
            db_totals = await SQLiteManager.get_ai_telemetry_totals()
            updated = False
            for prov, vals in db_totals.items():
                if prov in self.telemetry:
                    cur_r = self.telemetry[prov]["requests"]
                    cur_p = self.telemetry[prov]["prompt_tokens"]
                    cur_c = self.telemetry[prov]["completion_tokens"]

                    db_r = vals.get("requests", 0)
                    db_p = vals.get("prompt_tokens", 0)
                    db_c = vals.get("completion_tokens", 0)

                    if db_r > cur_r or db_p > cur_p or db_c > cur_c:
                        self.telemetry[prov]["requests"] = max(cur_r, db_r)
                        self.telemetry[prov]["prompt_tokens"] = max(cur_p, db_p)
                        self.telemetry[prov]["completion_tokens"] = max(cur_c, db_c)
                        updated = True
                    elif cur_r > db_r or cur_p > db_p or cur_c > db_c:
                        cost = (cur_p * 0.00000014) + (cur_c * 0.00000028) if prov == "deepseek" else 0.0
                        await SQLiteManager.update_ai_telemetry_delta(
                            prov,
                            cur_r - db_r,
                            cur_p - db_p,
                            cur_c - db_c,
                            cost
                        )

            self._db_synced = True
            if updated:
                self._save_telemetry_file()
                logger.info("Telemetría acumulada sincronizada exitosamente con SQLite.")
        except Exception as e:
            logger.warning(f"No se pudo sincronizar telemetría con SQLite: {e}")

    async def _record_telemetry_delta(
        self, provider: str, requests: int, prompt_tokens: int, completion_tokens: int, cost_usd: float = 0.0
    ):
        """Guarda el delta en SQLite y actualiza el archivo JSON en background."""
        try:
            self._save_telemetry_file()
            await SQLiteManager.update_ai_telemetry_delta(
                provider, requests, prompt_tokens, completion_tokens, cost_usd
            )
        except Exception as e:
            logger.error(f"Error registrando delta de telemetría para {provider}: {e}")

    def get_telemetry(self) -> dict:
        """Devuelve un snapshot de telemetría de IA listo para el Dashboard con costo y ratios."""
        if not self._db_synced:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._sync_persisted_telemetry())
            except RuntimeError:
                pass

        now = time.time()
        deepseek_lat = self.telemetry["deepseek"]["latencies_ms"]
        gemini_lat = self.telemetry["gemini"]["latencies_ms"]
        groq_lat = self.telemetry["groq"]["latencies_ms"]
        openrouter_lat = self.telemetry["openrouter"]["latencies_ms"]

        avg_deepseek = round(sum(deepseek_lat[-20:]) / len(deepseek_lat[-20:])) if deepseek_lat else 0
        avg_gemini = round(sum(gemini_lat[-20:]) / len(gemini_lat[-20:])) if gemini_lat else 0
        avg_groq = round(sum(groq_lat[-20:]) / len(groq_lat[-20:])) if groq_lat else 0
        avg_openrouter = round(sum(openrouter_lat[-20:]) / len(openrouter_lat[-20:])) if openrouter_lat else 0

        # Cálculo de costo acumulado DeepSeek ($0.15/1M prompt, $0.60/1M completion para V4.1-Flash)
        ds_p = self.telemetry["deepseek"]["prompt_tokens"]
        ds_c = self.telemetry["deepseek"]["completion_tokens"]
        deepseek_cost = round((ds_p * 0.00000015) + (ds_c * 0.00000060), 6)

        total_prompt = (
            self.telemetry["deepseek"]["prompt_tokens"]
            + self.telemetry["gemini"]["prompt_tokens"]
            + self.telemetry["groq"]["prompt_tokens"]
            + self.telemetry["openrouter"]["prompt_tokens"]
        )
        total_completion = (
            self.telemetry["deepseek"]["completion_tokens"]
            + self.telemetry["gemini"]["completion_tokens"]
            + self.telemetry["groq"]["completion_tokens"]
            + self.telemetry["openrouter"]["completion_tokens"]
        )
        ratio_eff = round(total_prompt / max(1, total_completion), 1)

        raw_credit = os.getenv("DEEPSEEK_CREDIT_BALANCE", "").strip()
        credit_balance = float(raw_credit) if raw_credit else None

        return {
            "routing_mode": self.routing_mode,
            "uptime_seconds": int(now - self.telemetry["start_time"]),
            "estimated_cost_usd": deepseek_cost,
            "credit_balance": credit_balance,
            "prompt_ratio": ratio_eff,
            "deepseek": {
                "model": (os.getenv("DEEPSEEK_MODEL") or "deepseek-flash").strip(),
                "healthy": self._is_deepseek_healthy(),
                "cooldown_remaining": max(0, int(self._deepseek_cooldown_until - now)),
                "requests": self.telemetry["deepseek"]["requests"],
                "prompt_tokens": ds_p,
                "completion_tokens": ds_c,
                "total_tokens": ds_p + ds_c,
                "avg_latency_ms": avg_deepseek,
                "cost_usd": deepseek_cost,
                "errors": self.telemetry["deepseek"]["errors"]
            },
            "gemini": {
                "model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip(),
                "healthy": self._is_gemini_healthy(),
                "cooldown_remaining": max(0, int(self._gemini_cooldown_until - now)),
                "requests": self.telemetry["gemini"]["requests"],
                "prompt_tokens": self.telemetry["gemini"]["prompt_tokens"],
                "completion_tokens": self.telemetry["gemini"]["completion_tokens"],
                "total_tokens": self.telemetry["gemini"]["prompt_tokens"] + self.telemetry["gemini"]["completion_tokens"],
                "avg_latency_ms": avg_gemini,
                "errors": self.telemetry["gemini"]["errors"]
            },
            "groq": {
                "model": (os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b").strip(),
                "fallback_model": (os.getenv("GROQ_MODEL_FALLBACK") or "llama-3.1-8b-instant").strip(),
                "healthy": self._is_groq_healthy(),
                "cooldown_remaining": max(0, int(self._groq_cooldown_until - now)),
                "requests": self.telemetry["groq"]["requests"],
                "prompt_tokens": self.telemetry["groq"]["prompt_tokens"],
                "completion_tokens": self.telemetry["groq"]["completion_tokens"],
                "total_tokens": self.telemetry["groq"]["prompt_tokens"] + self.telemetry["groq"]["completion_tokens"],
                "avg_latency_ms": avg_groq,
                "errors": self.telemetry["groq"]["errors"]
            },
            "openrouter": {
                "model": (os.getenv("OPENROUTER_MODEL") or "openrouter/free").strip(),
                "healthy": self._is_openrouter_healthy(),
                "cooldown_remaining": max(0, int(self._openrouter_cooldown_until - now)),
                "requests": self.telemetry["openrouter"]["requests"],
                "prompt_tokens": self.telemetry["openrouter"]["prompt_tokens"],
                "completion_tokens": self.telemetry["openrouter"]["completion_tokens"],
                "total_tokens": self.telemetry["openrouter"]["prompt_tokens"] + self.telemetry["openrouter"]["completion_tokens"],
                "avg_latency_ms": avg_openrouter,
                "errors": self.telemetry["openrouter"]["errors"]
            },
            "recent_interactions": self.telemetry["recent_interactions"][-20:]
        }

    async def close(self):
        """Cierra recursos del cliente HTTP."""
        if self._http_client:
            await self._http_client.aclose()

    @staticmethod
    def _clean_reply_text(text: str, bot_name: str = "Dalet") -> str:
        """
        Limpia y sanea la respuesta generada por cualquier LLM:
        1. Elimina etiquetas de razonamiento/pensamiento como <think>...</think>.
        2. Elimina prefijos repetitivos o alucinados (ej: 'Dalet:', 'SkinnyGPT:').
        3. Elimina comillas externas envolventes ("...", “...”, '...').
        4. Cierra backticks de código huérfanos si la salida fue cortada.
        5. Limita emojis a un máximo de 1 por mensaje para evitar spam y mantener personalidad.
        """
        if not text:
            return ""

        cleaned = text.strip()

        # 1. Eliminar bloques <think>...</think>
        cleaned = re.sub(r"(?is)<think>.*?</think>", "", cleaned).strip()

        # 2. Eliminar prefijos de nombre al inicio
        bot_prefixes = [bot_name, "Dalet", "SkinnyGPT", "Assistant", "Bot"]
        for prefix in bot_prefixes:
            pattern = rf"^(?i:\**{re.escape(prefix)}\**\s*:\s*)"
            cleaned = re.sub(pattern, "", cleaned).strip()

        # 3. Eliminar comillas externas envolventes
        while len(cleaned) >= 2:
            if (cleaned.startswith('"') and cleaned.endswith('"')) or \
               (cleaned.startswith('“') and cleaned.endswith('”')) or \
               (cleaned.startswith("'") and cleaned.endswith("'")):
                cleaned = cleaned[1:-1].strip()
            else:
                break

        # 4. Asegurar balance de backticks inline si se cortó a medias
        backtick_count = cleaned.count("`")
        if backtick_count % 2 != 0:
            cleaned += "`"

        # 5. Limitar emojis (máximo 1 para evitar spam y alucinaciones)
        emoji_pattern = re.compile(
            r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\u3030-\u303d]"
        )
        emojis_found = emoji_pattern.findall(cleaned)
        if len(emojis_found) > 1:
            first_emoji = emojis_found[0]
            parts = emoji_pattern.split(cleaned)
            cleaned = parts[0] + first_emoji + "".join(parts[1:])
            cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    def _get_system_prompt(self, bot_name: str, language: str = "en", active_room_users: str = "", override: str = None) -> str:
        """Obtiene el prompt de sistema adecuado según el idioma configurado ('en' o 'es')."""
        if override:
            return override
        template = DALET_PERSONALITY_ES if str(language).lower().strip() == "es" else DALET_PERSONALITY_EN
        prompt = template.format(bot_name=bot_name)
        if active_room_users:
            label = "Gente presente:" if str(language).lower().strip() == "es" else "People in chat:"
            prompt += f"\n\n{label} {active_room_users}"
        return prompt

    def _is_deepseek_healthy(self) -> bool:
        return bool(self.deepseek_api_key and time.time() >= self._deepseek_cooldown_until)

    def _is_gemini_healthy(self) -> bool:
        return bool(self.client and time.time() >= self._gemini_cooldown_until)

    def _is_groq_healthy(self) -> bool:
        return bool(self.groq_api_key and time.time() >= self._groq_cooldown_until)

    def _is_openrouter_healthy(self) -> bool:
        return bool(self.openrouter_api_key and time.time() >= self._openrouter_cooldown_until)

    def _select_provider(self, has_images: bool, needs_web_search: bool, trigger: str) -> str:
        """
        Determina dinámicamente qué proveedor usar según intención, salud y balanceo.
        Jerarquía:
        1. Imágenes / Web Search -> Gemini Flash
        2. Modo forzado por env (si se especifica)
        3. Modo "auto" -> DeepSeek como motor primario dominante (alta calidad, pagado, sin rate limits).
           Fallbacks: Groq (ultra rápido), Gemini, OpenRouter.
        """
        deepseek_ok = self._is_deepseek_healthy()
        gemini_ok = self._is_gemini_healthy()
        groq_ok = self._is_groq_healthy()
        openrouter_ok = self._is_openrouter_healthy()

        # Si el mensaje contiene imágenes o requiere búsqueda web en vivo -> Gemini es prioritario
        if has_images or needs_web_search:
            if gemini_ok:
                return "gemini"
            elif deepseek_ok:
                return "deepseek"
            elif openrouter_ok:
                return "openrouter"
            elif groq_ok:
                return "groq"

        # Modo estricto o forzado por env
        if self.routing_mode == "deepseek" and deepseek_ok:
            return "deepseek"
        elif self.routing_mode == "groq" and groq_ok:
            return "groq"
        elif self.routing_mode == "openrouter" and openrouter_ok:
            return "openrouter"
        elif self.routing_mode == "gemini" and gemini_ok:
            return "gemini"

        # Modo "auto" / default: DeepSeek como motor primario dominante
        if deepseek_ok:
            return "deepseek"

        # Fallbacks si DeepSeek está momentáneamente en cooldown
        if groq_ok:
            return "groq"
        if gemini_ok:
            return "gemini"
        if openrouter_ok:
            return "openrouter"

        # Último recurso si todos están en cooldown pero hay claves
        if self.deepseek_api_key: return "deepseek"
        if self.groq_api_key: return "groq"
        if self.client: return "gemini"
        return "openrouter"

    async def generate_reply(
        self, trigger: str, context: str, username: str,
        bot_name: str = "Dalet", image_urls: list = None, is_reactive: bool = False, **kwargs
    ):
        search_keywords = ("busca", "googlea", "noticias", "noticia", "precio", "resultado", "quién es", "quien es", "clima", "actualmente", "hoy en día", "partido")
        needs_web_search = any(kw in trigger.lower() for kw in search_keywords)
        has_images = bool(image_urls)

        image_description = ""
        if has_images:
            image_description = await self._get_images_description(image_urls)

        if is_reactive:
            context = self._trim_context_smart(context, trigger)

        chosen_provider = self._select_provider(has_images, needs_web_search, trigger)
        logger.info(f"Load Balancer enrutó a '{chosen_provider}' para {username} (web_search={needs_web_search}, imgs={has_images})")

        # Cadena de proveedores a probar en orden
        provider_chain = [chosen_provider]
        for p in ("deepseek", "groq", "gemini", "openrouter"):
            if p not in provider_chain:
                provider_chain.append(p)

        reply = None
        for provider in provider_chain:
            if provider == "deepseek" and (provider == chosen_provider or self._is_deepseek_healthy()):
                reply = await self._generate_deepseek_reply(
                    trigger, context, username, bot_name, image_description,
                    is_fallback=(provider != chosen_provider), is_reactive=is_reactive, **kwargs
                )
            elif provider == "groq" and (provider == chosen_provider or self._is_groq_healthy()):
                reply = await self._generate_groq_reply(
                    trigger, context, username, bot_name, image_description,
                    is_fallback=(provider != chosen_provider), is_reactive=is_reactive, **kwargs
                )
            elif provider == "gemini" and (provider == chosen_provider or self._is_gemini_healthy()):
                reply = await self._generate_gemini_reply(
                    trigger, context, username, bot_name, image_description,
                    needs_web_search=needs_web_search, is_reactive=is_reactive,
                    is_fallback=(provider != chosen_provider), **kwargs
                )
            elif provider == "openrouter" and (provider == chosen_provider or self._is_openrouter_healthy()):
                reply = await self._generate_openrouter_reply(
                    trigger, context, username, bot_name, image_description,
                    is_fallback=(provider != chosen_provider), is_reactive=is_reactive, **kwargs
                )

            if reply:
                self.active_provider = provider
                break
            logger.warning(f"Proveedor '{provider}' no pudo generar respuesta. Pasando al siguiente en la cadena...")

        return reply

    async def _execute_osu_tool(self, name: str, args: dict, user_id: int = None) -> str:
        """Ejecuta una herramienta de osu! en Bancho API y devuelve un payload JSON compacto."""
        if not self.osu_service:
            return json.dumps({"error": "El servicio de osu! no está configurado en el bot."})

        raw_user = (args.get("username") or "").strip()
        # Si el usuario no especificó nick o dijo "yo"/"mi", intentar resolver cuenta de Discord enlazada
        if (not raw_user or raw_user.lower() in ("yo", "mi", "me", "conmigo", "mio", "mío")) and user_id and self.osu_repo:
            try:
                linked = await self.osu_repo.get_linked_username(user_id)
                if linked:
                    raw_user = linked
            except Exception as e:
                logger.warning(f"Error resolviendo cuenta osu enlazada para {user_id}: {e}")

        if not raw_user:
            return json.dumps({"error": "No se especificó un nombre de usuario en osu! y no tiene cuenta enlazada."})

        try:
            if name == "get_recent_osu_play":
                user_obj = await self.osu_service.get_user(raw_user)
                if not user_obj or "id" not in user_obj:
                    return json.dumps({"error": f"No se encontró al jugador '{raw_user}' en osu!."})

                uid = user_obj["id"]
                scores = await self.osu_service.get_user_recent_scores(uid, limit=1)
                if not scores:
                    return json.dumps({"status": "no_recent_plays", "player": raw_user, "message": "No ha jugado nada en las últimas 24 horas."})

                s = scores[0]
                bm = s.get("beatmapset", {})
                title = bm.get("title", "Desconocido")
                artist = bm.get("artist", "Desconocido")
                version = s.get("beatmap", {}).get("version", "")
                rank = s.get("rank", "")
                acc = round(float(s.get("accuracy", 0.0)) * 100.0, 2)
                mods = "".join(s.get("mods", [])) or "None"
                pp = round(float(s.get("pp")), 1) if s.get("pp") else "0 (unranked/choke)"
                passed = s.get("passed", False)
                misses = s.get("statistics", {}).get("count_miss", 0)

                return json.dumps({
                    "player": user_obj.get("username", raw_user),
                    "beatmap": f"{artist} - {title} [{version}]",
                    "grade": rank,
                    "accuracy": f"{acc}%",
                    "mods": mods,
                    "pp": pp,
                    "misses": misses,
                    "passed": passed
                }, ensure_ascii=False)

            elif name == "get_top_osu_play":
                idx = max(1, int(args.get("index", 1)))
                user_obj = await self.osu_service.get_user(raw_user)
                if not user_obj or "id" not in user_obj:
                    return json.dumps({"error": f"No se encontró al jugador '{raw_user}' en osu!."})

                uid = user_obj["id"]
                scores = await self.osu_service.get_user_best_scores(uid, limit=max(idx, 5))
                if not scores or len(scores) < idx:
                    return json.dumps({"status": "no_top_plays", "player": raw_user, "message": f"No tiene jugadas registradas hasta el top #{idx}."})

                s = scores[idx - 1]
                bm = s.get("beatmapset", {})
                title = bm.get("title", "Desconocido")
                artist = bm.get("artist", "Desconocido")
                version = s.get("beatmap", {}).get("version", "")
                rank = s.get("rank", "")
                acc = round(float(s.get("accuracy", 0.0)) * 100.0, 2)
                mods = "".join(s.get("mods", [])) or "None"
                pp = round(float(s.get("pp") or 0.0), 1)

                return json.dumps({
                    "player": user_obj.get("username", raw_user),
                    "position": f"Top #{idx}",
                    "beatmap": f"{artist} - {title} [{version}]",
                    "grade": rank,
                    "accuracy": f"{acc}%",
                    "mods": mods,
                    "pp": f"{pp}pp"
                }, ensure_ascii=False)

            elif name == "get_osu_user_profile":
                user_obj = await self.osu_service.get_user(raw_user)
                if not user_obj or "id" not in user_obj:
                    return json.dumps({"error": f"No se encontró al jugador '{raw_user}' en osu!."})

                stats = user_obj.get("statistics", {})
                global_rank = stats.get("global_rank") or "N/A"
                country_rank = stats.get("country_rank") or "N/A"
                pp = round(float(stats.get("pp", 0.0)), 1)
                acc = round(float(stats.get("hit_accuracy", 0.0)), 2)
                country = user_obj.get("country", {}).get("name", "Desconocido")

                return json.dumps({
                    "player": user_obj.get("username", raw_user),
                    "country": country,
                    "global_rank": f"#{global_rank:,}" if isinstance(global_rank, (int, float)) else str(global_rank),
                    "country_rank": f"#{country_rank:,}" if isinstance(country_rank, (int, float)) else str(country_rank),
                    "pp": f"{pp:,}pp",
                    "accuracy": f"{acc}%"
                }, ensure_ascii=False)

            elif name == "get_osu_skills":
                user_obj = await self.osu_service.get_user(raw_user)
                if not user_obj or "id" not in user_obj:
                    return json.dumps({"error": f"No se encontró al jugador '{raw_user}' en osu!."})

                uid = user_obj["id"]
                best_plays = await self.osu_service.get_user_best_scores(uid, limit=100)
                if not best_plays:
                    return json.dumps({"status": "no_plays", "player": raw_user, "message": "No tiene jugadas registradas en su top para calcular skills."})

                skills_data = OsuAnalyzer.calculate_skills(best_plays)
                
                return json.dumps({
                    "player": user_obj.get("username", raw_user),
                    "dominant_skill": skills_data.get("dominant_skill"),
                    "weakest_skill": skills_data.get("weakest_skill"),
                    "overall_stars": f"{skills_data.get('overall_skill_stars', 0.0)}★",
                    "breakdown": {
                        "Aim": f"{skills_data.get('Aim', {}).get('stars', 0.0)}★",
                        "Speed": f"{skills_data.get('Speed', {}).get('stars', 0.0)}★",
                        "Accuracy": f"{skills_data.get('Accuracy', {}).get('stars', 0.0)}★",
                        "Stamina": f"{skills_data.get('Stamina', {}).get('stars', 0.0)}★",
                        "Reading": f"{skills_data.get('Reading', {}).get('stars', 0.0)}★"
                    }
                }, ensure_ascii=False)

            return json.dumps({"error": f"Herramienta desconocida: {name}"})
        except Exception as e:
            logger.error(f"Excepción ejecutando herramienta osu '{name}': {e}")
            return json.dumps({"error": f"Error consultando osu! API: {str(e)}"})

    async def _generate_deepseek_reply(
        self, trigger: str, context: str, username: str,
        bot_name: str, image_description: str = "", is_fallback: bool = False,
        is_reactive: bool = False, **kwargs
    ):
        if not self.deepseek_api_key:
            return None

        active_room_users = kwargs.get("active_room_users", "")
        caller_user_id = kwargs.get("user_id")
        model_name = (os.getenv("DEEPSEEK_MODEL") or "deepseek-flash").strip()
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json"
        }

        lang = kwargs.get("language", "en")
        deepseek_system = self._get_system_prompt(bot_name, lang, active_room_users, kwargs.get("system_prompt_override"))

        vision_context = f"\n[IMAGEN: {image_description}]\n" if image_description else ""
        user_msg = f"<contexto_chat>\n{context}\n</contexto_chat>{vision_context}\n\nMensaje actual de {username}: {trigger}"
        max_tokens = kwargs.get("max_tokens_override", 400 if is_reactive else 650)

        # Determinar si activamos herramientas (Function Calling) de osu!
        use_tools = False
        trigger_lower = trigger.lower()
        if self.osu_service and any(kw in trigger_lower for kw in OSU_TRIGGER_KEYWORDS):
            use_tools = True

        messages = [
            {"role": "system", "content": deepseek_system},
            {"role": "user", "content": user_msg}
        ]

        data = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": max_tokens
        }
        if use_tools:
            data["tools"] = OSU_TOOLS

        t0 = time.time()
        try:
            logger.info(f"Llamando DeepSeek: {model_name} (tools={use_tools}, fallback={is_fallback})")
            response = await self._http_client.post(url, headers=headers, json=data, timeout=10.0)

            if response.status_code == 429:
                logger.warning(f"DeepSeek 429 Rate Limit. Circuit Breaker abierto por 30s.")
                self._deepseek_cooldown_until = time.time() + 30
                self.telemetry["deepseek"]["errors"] += 1
                return None

            if response.status_code != 200:
                logger.error(f"DeepSeek error HTTP {response.status_code}: {response.text}")
                self.telemetry["deepseek"]["errors"] += 1
                return None

            result = response.json()
            choice = result['choices'][0]
            choice_msg = choice['message']
            usage = result.get("usage", {})
            p_tokens = usage.get("prompt_tokens") or (len(user_msg) // 4)
            c_tokens = usage.get("completion_tokens") or 0

            # Caso A: DeepSeek solicitó ejecutar una herramienta (Function Calling)
            if choice_msg.get("tool_calls"):
                tool_calls = choice_msg["tool_calls"]
                messages.append(choice_msg)

                for tc in tool_calls:
                    fn_name = tc.get("function", {}).get("name", "")
                    fn_args_raw = tc.get("function", {}).get("arguments", "{}")
                    try:
                        fn_args = json.loads(fn_args_raw)
                    except Exception:
                        fn_args = {}

                    logger.info(f"DeepSeek Tool Call: '{fn_name}' con args: {fn_args}")
                    tool_output = await self._execute_osu_tool(fn_name, fn_args, user_id=caller_user_id)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id"),
                        "content": tool_output
                    })

                # Segunda llamada con los datos obtenidos para que redacte con su personalidad
                data_step2 = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": max_tokens
                }
                resp2 = await self._http_client.post(url, headers=headers, json=data_step2, timeout=10.0)
                if resp2.status_code == 200:
                    result2 = resp2.json()
                    raw_text = result2['choices'][0]['message']['content'] or ""
                    usage2 = result2.get("usage", {})
                    p_tokens += usage2.get("prompt_tokens") or 0
                    c_tokens += usage2.get("completion_tokens") or 0
                else:
                    logger.warning(f"Error en paso 2 de DeepSeek Tools: HTTP {resp2.status_code}")
                    raw_text = choice_msg.get("content") or ""
            else:
                raw_text = choice_msg.get("content") or ""

            reply_text = self._clean_reply_text(raw_text, bot_name)
            latency_ms = int((time.time() - t0) * 1000)

            c_tokens = c_tokens or (len(reply_text) // 4)
            cost_delta = round((p_tokens * 0.00000014) + (c_tokens * 0.00000028), 6)

            self.telemetry["deepseek"]["requests"] += 1
            self.telemetry["deepseek"]["prompt_tokens"] += p_tokens
            self.telemetry["deepseek"]["completion_tokens"] += c_tokens
            self.telemetry["deepseek"]["latencies_ms"].append(latency_ms)
            if len(self.telemetry["deepseek"]["latencies_ms"]) > 50:
                self.telemetry["deepseek"]["latencies_ms"].pop(0)

            asyncio.create_task(self._record_telemetry_delta("deepseek", 1, p_tokens, c_tokens, cost_delta))

            self.telemetry["recent_interactions"].append({
                "provider": "DeepSeek",
                "model": model_name,
                "user": username,
                "trigger": trigger[:50] + ("..." if len(trigger) > 50 else ""),
                "latency_ms": latency_ms,
                "prompt_tokens": p_tokens,
                "completion_tokens": c_tokens,
                "timestamp": time.strftime("%H:%M:%S")
            })
            if len(self.telemetry["recent_interactions"]) > 30:
                self.telemetry["recent_interactions"].pop(0)

            return reply_text

        except asyncio.TimeoutError:
            logger.warning(f"Timeout en DeepSeek {model_name}. Intentando siguiente proveedor...")
            self.telemetry["deepseek"]["errors"] += 1
            return None
        except Exception as e:
            logger.warning(f"DeepSeek excepción: {e}. Probando siguiente proveedor...")
            self.telemetry["deepseek"]["errors"] += 1
            return None

    async def _generate_gemini_reply(
        self, trigger: str, context: str, username: str,
        bot_name: str, image_description: str = "", needs_web_search: bool = False,
        is_reactive: bool = False, is_fallback: bool = False, **kwargs
    ):
        if not self.client:
            return None

        active_room_users = kwargs.get("active_room_users", "")
        server_emojis = kwargs.get("server_emojis", "")

        lang = kwargs.get("language", "en")
        system_prompt = self._get_system_prompt(bot_name, lang, active_room_users, kwargs.get("system_prompt_override"))
        if server_emojis:
            system_prompt += f"\nEmojis: {server_emojis}"

        vision_context = f"\n[IMAGEN: {image_description}]\n" if image_description else ""
        prompt = f"<contexto_chat>\n{context}\n</contexto_chat>{vision_context}\n\nMensaje actual de {username}: {trigger}"

        # Cadena de modelos de Gemini (1.5-flash y 2.5-flash)
        primary_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()
        models_to_try = [primary_model]
        for fallback_m in ("gemini-1.5-flash", "gemini-2.5-flash"):
            if fallback_m not in models_to_try:
                models_to_try.append(fallback_m)

        tools = [types.Tool(google_search=types.GoogleSearch())] if needs_web_search else None
        max_tokens = kwargs.get("max_tokens_override", 500 if is_reactive else 750)

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.8,
            max_output_tokens=max_tokens,
            tools=tools
        )

        for model_name in models_to_try:
            t0 = time.time()
            try:
                logger.info(f"Llamando Gemini: {model_name} (fallback={is_fallback}, search={needs_web_search})")
                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config
                    ),
                    timeout=6.0
                )

                if response and response.text:
                    latency_ms = int((time.time() - t0) * 1000)
                    reply_text = self._clean_reply_text(response.text, bot_name)

                    usage = getattr(response, "usage_metadata", None)
                    p_tokens = getattr(usage, "prompt_token_count", None) or (len(prompt) // 4)
                    c_tokens = getattr(usage, "candidates_token_count", None) or (len(reply_text) // 4)

                    self.telemetry["gemini"]["requests"] += 1
                    self.telemetry["gemini"]["prompt_tokens"] += p_tokens
                    self.telemetry["gemini"]["completion_tokens"] += c_tokens
                    self.telemetry["gemini"]["latencies_ms"].append(latency_ms)
                    if len(self.telemetry["gemini"]["latencies_ms"]) > 50:
                        self.telemetry["gemini"]["latencies_ms"].pop(0)

                    asyncio.create_task(self._record_telemetry_delta("gemini", 1, p_tokens, c_tokens, 0.0))

                    self.telemetry["recent_interactions"].append({
                        "provider": "Gemini",
                        "model": model_name,
                        "user": username,
                        "trigger": trigger[:50] + ("..." if len(trigger) > 50 else ""),
                        "latency_ms": latency_ms,
                        "prompt_tokens": p_tokens,
                        "completion_tokens": c_tokens,
                        "timestamp": time.strftime("%H:%M:%S")
                    })
                    if len(self.telemetry["recent_interactions"]) > 30:
                        self.telemetry["recent_interactions"].pop(0)

                    return reply_text

            except asyncio.TimeoutError:
                logger.warning(f"Timeout (6s) en Gemini {model_name}. Intentando siguiente...")
                continue
            except Exception as e:
                logger.warning(f"Gemini {model_name} falló ({e}). Intentando siguiente modelo...")
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    logger.warning("Gemini 429 detectado. Circuit Breaker abierto por 60s.")
                    self._gemini_cooldown_until = time.time() + 60
                    self.telemetry["gemini"]["errors"] += 1
                    return None

        self.telemetry["gemini"]["errors"] += 1
        return None

    async def _generate_groq_reply(
        self, trigger: str, context: str, username: str,
        bot_name: str, image_description: str = "", is_fallback: bool = False,
        is_reactive: bool = False, **kwargs
    ):
        if not self.groq_api_key:
            return None

        active_room_users = kwargs.get("active_room_users", "")

        # Modelos activos en Groq según catálogo oficial
        raw_groq = (os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b").strip()
        # Si tiene el nombre deprecado antiguo, auto-reemplazar a gpt-oss-120b
        if "llama-3.3-70b-versatile" in raw_groq:
            raw_groq = "openai/gpt-oss-120b"

        primary_groq = raw_groq
        groq_models_to_try = [primary_groq]
        catalog_candidates = (
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "meta-llama/llama-3.3-70b-instruct",
            "qwen/qwen-3.6-27b",
            "llama-3.1-8b-instant"
        )
        for alt_m in catalog_candidates:
            if alt_m not in groq_models_to_try:
                groq_models_to_try.append(alt_m)

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }

        lang = kwargs.get("language", "en")
        groq_system = self._get_system_prompt(bot_name, lang, active_room_users, kwargs.get("system_prompt_override"))

        vision_context = f"\n[IMAGEN: {image_description}]\n" if image_description else ""
        user_msg = f"<contexto_chat>\n{context}\n</contexto_chat>{vision_context}\n\nMensaje actual de {username}: {trigger}"
        max_tokens = kwargs.get("max_tokens_override", 500 if is_reactive else 750)

        for model_name in groq_models_to_try:
            t0 = time.time()
            data = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": groq_system},
                    {"role": "user", "content": user_msg}
                ],
                "temperature": 0.65,
                "max_tokens": max_tokens
            }

            try:
                logger.info(f"Llamando Groq: {model_name} (fallback={is_fallback})")
                response = await self._http_client.post(url, headers=headers, json=data, timeout=6.0)

                if response.status_code == 429:
                    logger.warning(f"Groq 429 Rate Limit en {model_name}. Circuit Breaker abierto por 60s.")
                    self._groq_cooldown_until = time.time() + 60
                    self.telemetry["groq"]["errors"] += 1
                    return None

                if response.status_code == 404:
                    logger.warning(f"Groq modelo {model_name} no disponible (404). Probando alternativa...")
                    continue

                if response.status_code != 200:
                    logger.error(f"Groq error HTTP {response.status_code} ({model_name}): {response.text}")
                    continue

                result = response.json()
                raw_text = result['choices'][0]['message']['content'] or ""
                reply_text = self._clean_reply_text(raw_text, bot_name)
                latency_ms = int((time.time() - t0) * 1000)

                usage = result.get("usage", {})
                p_tokens = usage.get("prompt_tokens") or (len(user_msg) // 4)
                c_tokens = usage.get("completion_tokens") or (len(reply_text) // 4)

                self.telemetry["groq"]["requests"] += 1
                self.telemetry["groq"]["prompt_tokens"] += p_tokens
                self.telemetry["groq"]["completion_tokens"] += c_tokens
                self.telemetry["groq"]["latencies_ms"].append(latency_ms)
                if len(self.telemetry["groq"]["latencies_ms"]) > 50:
                    self.telemetry["groq"]["latencies_ms"].pop(0)

                asyncio.create_task(self._record_telemetry_delta("groq", 1, p_tokens, c_tokens, 0.0))

                self.telemetry["recent_interactions"].append({
                    "provider": "Groq",
                    "model": model_name,
                    "user": username,
                    "trigger": trigger[:50] + ("..." if len(trigger) > 50 else ""),
                    "latency_ms": latency_ms,
                    "prompt_tokens": p_tokens,
                    "completion_tokens": c_tokens,
                    "timestamp": time.strftime("%H:%M:%S")
                })
                if len(self.telemetry["recent_interactions"]) > 30:
                    self.telemetry["recent_interactions"].pop(0)

                return reply_text

            except asyncio.TimeoutError:
                logger.warning(f"Timeout (6s) en Groq {model_name}. Intentando siguiente...")
                continue
            except Exception as e:
                logger.warning(f"Groq excepción con {model_name}: {e}. Probando siguiente...")

        self.telemetry["groq"]["errors"] += 1
        return None

    async def _generate_openrouter_reply(
        self, trigger: str, context: str, username: str,
        bot_name: str, image_description: str = "", is_fallback: bool = False,
        is_reactive: bool = False, **kwargs
    ):
        if not self.openrouter_api_key:
            return None

        active_room_users = kwargs.get("active_room_users", "")

        primary_model = (os.getenv("OPENROUTER_MODEL") or "openrouter/free").strip()
        models_to_try = [primary_model]
        candidates = (
            "openrouter/free",
            "google/gemini-2.0-flash-exp:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "deepseek/deepseek-r1:free",
            "qwen/qwen-2.5-72b-instruct:free",
            "mistralai/mistral-small-24b-instruct-2501:free"
        )
        for cand in candidates:
            if cand not in models_to_try:
                models_to_try.append(cand)

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "HTTP-Referer": "https://dalet-proyect.onrender.com",
            "X-Title": "Dalet Discord Bot",
            "Content-Type": "application/json"
        }

        lang = kwargs.get("language", "en")
        system_prompt = self._get_system_prompt(bot_name, lang, active_room_users, kwargs.get("system_prompt_override"))

        vision_context = f"\n[IMAGEN: {image_description}]\n" if image_description else ""
        user_msg = f"<contexto_chat>\n{context}\n</contexto_chat>{vision_context}\n\nMensaje actual de {username}: {trigger}"
        max_tokens = kwargs.get("max_tokens_override", 500 if is_reactive else 750)

        for model_name in models_to_try:
            t0 = time.time()
            data = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ],
                "temperature": 0.65,
                "max_tokens": max_tokens
            }

            try:
                logger.info(f"Llamando OpenRouter: {model_name} (fallback={is_fallback})")
                response = await self._http_client.post(url, headers=headers, json=data)

                if response.status_code == 429:
                    logger.warning(f"OpenRouter 429 Rate Limit en {model_name}. Circuit Breaker abierto por 60s.")
                    self._openrouter_cooldown_until = time.time() + 60
                    self.telemetry["openrouter"]["errors"] += 1
                    return None

                if response.status_code == 404:
                    logger.warning(f"OpenRouter modelo {model_name} no disponible (404). Probando alternativa...")
                    continue

                if response.status_code != 200:
                    logger.error(f"OpenRouter error HTTP {response.status_code} ({model_name}): {response.text}")
                    continue

                result = response.json()
                raw_text = result['choices'][0]['message']['content'] or ""
                reply_text = self._clean_reply_text(raw_text, bot_name)
                latency_ms = int((time.time() - t0) * 1000)

                usage = result.get("usage", {})
                p_tokens = usage.get("prompt_tokens") or (len(user_msg) // 4)
                c_tokens = usage.get("completion_tokens") or (len(reply_text) // 4)

                self.telemetry["openrouter"]["requests"] += 1
                self.telemetry["openrouter"]["prompt_tokens"] += p_tokens
                self.telemetry["openrouter"]["completion_tokens"] += c_tokens
                self.telemetry["openrouter"]["latencies_ms"].append(latency_ms)
                if len(self.telemetry["openrouter"]["latencies_ms"]) > 50:
                    self.telemetry["openrouter"]["latencies_ms"].pop(0)

                asyncio.create_task(self._record_telemetry_delta("openrouter", 1, p_tokens, c_tokens, 0.0))

                self.telemetry["recent_interactions"].append({
                    "provider": "OpenRouter",
                    "model": model_name,
                    "user": username,
                    "trigger": trigger[:50] + ("..." if len(trigger) > 50 else ""),
                    "latency_ms": latency_ms,
                    "prompt_tokens": p_tokens,
                    "completion_tokens": c_tokens,
                    "timestamp": time.strftime("%H:%M:%S")
                })
                if len(self.telemetry["recent_interactions"]) > 30:
                    self.telemetry["recent_interactions"].pop(0)

                return reply_text

            except Exception as e:
                logger.warning(f"OpenRouter excepción con {model_name}: {e}. Probando siguiente...")

        self.telemetry["openrouter"]["errors"] += 1
        return None

    def _trim_context_smart(self, context: str, trigger: str) -> str:
        """
        Recorta el contexto de forma dinámica para optimizar consumo de tokens.
        """
        lines = context.split("\n")

        chat_marker_idx = None
        for i, line in enumerate(lines):
            if "CHAT RECIENTE" in line:
                chat_marker_idx = i
                break

        trigger_clean = trigger.strip()
        words = trigger_clean.split()
        if trigger_clean.endswith("?") or "¿" in trigger_clean:
            max_lines = 8
        elif len(words) <= 4:
            max_lines = 4
        else:
            max_lines = 6

        if chat_marker_idx is None:
            return "\n".join(lines[-max_lines:])

        user_data_lines = lines[:chat_marker_idx]
        chat_lines = lines[chat_marker_idx:]

        if len(chat_lines) > max_lines + 1:
            chat_lines = [chat_lines[0]] + chat_lines[-max_lines:]

        return "\n".join(user_data_lines + chat_lines)

    async def _get_images_description(self, image_urls: list) -> str:
        """Describe una imagen usando el modelo principal con timeout estricto y caché en RAM."""
        if not self.gemini_api_key or not self.client or not image_urls:
            return ""

        url = image_urls[0]
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        if url_hash in self._vision_cache:
            logger.info("Caché hit para descripción de imagen.")
            return self._vision_cache[url_hash]

        try:
            model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()

            # Descarga de imagen con timeout de 5 segundos
            resp = await self._http_client.get(url, timeout=5.0)
            if resp.status_code != 200:
                logger.warning(f"No se pudo descargar imagen (HTTP {resp.status_code})")
                return ""

            raw_mime = resp.headers.get('Content-Type', 'image/jpeg').split(';')[0].strip()
            if not raw_mime.startswith('image/'):
                raw_mime = 'image/jpeg'

            image_part = types.Part.from_bytes(
                data=resp.content,
                mime_type=raw_mime
            )

            # Inferencia de visión con timeout de 7 segundos
            res = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=model_name,
                    contents=[
                        "Describe brevemente esta imagen en 40 palabras o menos. "
                        "Enfócate en el contenido principal y texto visible.",
                        image_part
                    ]
                ),
                timeout=7.0
            )

            if res and res.text:
                desc = res.text.strip()
                if len(self._vision_cache) > 50:
                    self._vision_cache.clear()
                self._vision_cache[url_hash] = desc
                return desc

            return ""

        except asyncio.TimeoutError:
            logger.warning("Timeout en análisis de visión (Gemini). Continuando sin descripción de imagen.")
            return ""
        except Exception as e:
            logger.error(f"Error en visión: {e}")
            return ""

