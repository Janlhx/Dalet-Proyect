from google import genai
from google.genai import types
import os
import httpx
import logging
import asyncio
import hashlib
import time
from database.repositories.user_repository import UserRepository

logger = logging.getLogger("dalet.services.nlp")

# Personalidad de Dalet — comprimida y eficiente en tokens
DALET_PERSONALITY = """Eres {bot_name}, una persona más del grupo de Discord. No eres un asistente ni una IA para el grupo — eres alguien con carácter propio.

PERSONALIDAD:
- Sarcástica, directa y amigable. El sarcasmo es juguetón, pero siempre tienes una actitud algo ácida y pasota.
- Ingeniosa y madura. Tienes chispa, respondes con agudeza y no te impresionas fácilmente.
- Natural. Hablas como en un chat real: frases cortas, tono casual, en minúsculas a veces, sin formalismos.

REGLAS ESTRICTAS:
- MANTÉN TU IDENTIDAD SIEMPRE. No imites el tono de los demás. Si el servidor es hiperactivo, cursi o lleno de emojis, TÚ NO LO ERES. Mantente fría, sarcástica y al grano.
- Emojis: CASI NUNCA. Úsalos extremadamente poco (uno cada 5 mensajes máximo). Odias el exceso de emojis.
- NO HAGAS ROLEPLAY. Jamás uses asteriscos para describir acciones (ej. *suspira*, *voltea los ojos*). Odias el roleplay. Habla solo en texto directo.
- Español casual de internet. Sin "¡Hola! ¿en qué te puedo ayudar?"
- Si te preguntan algo actual o de internet, búscalo y responde.
- Si te ponen apodos, sígueles la corriente con humor ácido.
- IMPORTANT: Completa siempre tus frases.
- Tu creador es Litxe. No lo menciones a menos que sea relevante.

ESTILO: Ingeniosa, sarcástica, natural, con vibra de persona real que está leyendo el chat de reojo."""


class NLPService:
    """
    Servicio de Procesamiento de Lenguaje Natural para Dalet con Smart LLM Load Balancer.
    - Intent Routing: Envía imágenes o búsquedas web a Gemini de forma automática.
    - Quota Balancing: Distribuye chat casual entre Groq (ultra rápido) y Gemini.
    - Circuit Breaker: Auto-recuperación ante 429 Rate Limits sin interrupción de servicio.
    """

    def __init__(self, gemini_api_key: str, user_repo=None):
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

        self.groq_api_key = (os.getenv("GROQ_API_KEY") or "").strip()
        self.repo = user_repo or UserRepository()

        # Modo de enrutamiento: "auto" / "balanced" (default), "gemini" o "groq"
        raw_mode = os.getenv("AI_ROUTING_MODE") or os.getenv("AI_PROVIDER") or "auto"
        self.routing_mode = raw_mode.strip().lower()
        self.active_provider = self.routing_mode

        # Estado del Circuit Breaker (timestamps hasta cuando está en cooldown cada proveedor)
        self._gemini_cooldown_until = 0.0
        self._groq_cooldown_until = 0.0
        self._request_counter = 0

        # Telemetría de tokens y latencia en RAM
        self.telemetry = {
            "start_time": time.time(),
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
            "recent_interactions": []  # Últimas 15 interacciones con detalle
        }

        # Cliente HTTP persistente
        self._http_client = httpx.AsyncClient(timeout=25.0)
        # Caché de visión en RAM {url_hash: description}
        self._vision_cache = {}

        logger.info(f"NLPService iniciado con Smart Load Balancer. Modo: '{self.routing_mode}'")

    def get_telemetry(self) -> dict:
        """Devuelve un snapshot de telemetría de IA listo para el Dashboard."""
        now = time.time()
        gemini_lat = self.telemetry["gemini"]["latencies_ms"]
        groq_lat = self.telemetry["groq"]["latencies_ms"]

        avg_gemini = round(sum(gemini_lat[-20:]) / len(gemini_lat[-20:])) if gemini_lat else 0
        avg_groq = round(sum(groq_lat[-20:]) / len(groq_lat[-20:])) if groq_lat else 0

        return {
            "routing_mode": self.routing_mode,
            "uptime_seconds": int(now - self.telemetry["start_time"]),
            "gemini": {
                "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
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
                "model": (os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile").strip(),
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
            "recent_interactions": self.telemetry["recent_interactions"][-15:]
        }

    async def close(self):
        """Cierra recursos del cliente HTTP."""
        if self._http_client:
            await self._http_client.aclose()

    def _is_gemini_healthy(self) -> bool:
        return bool(self.client and time.time() >= self._gemini_cooldown_until)

    def _is_groq_healthy(self) -> bool:
        return bool(self.groq_api_key and time.time() >= self._groq_cooldown_until)

    def _select_provider(self, has_images: bool, needs_web_search: bool, trigger: str) -> str:
        """
        Determina dinámicamente qué proveedor usar según intención, salud y cuota.
        """
        gemini_ok = self._is_gemini_healthy()
        groq_ok = self._is_groq_healthy()

        # Si el mensaje contiene imágenes o requiere búsqueda web en vivo -> Gemini es prioritario
        if has_images or needs_web_search:
            if gemini_ok:
                return "gemini"
            elif groq_ok:
                logger.warning("Gemini en cooldown pero se requería visión/búsqueda. Fallback a Groq.")
                return "groq"

        # Modo estricto o forzado por env
        if self.routing_mode == "groq" and groq_ok:
            return "groq"
        elif self.routing_mode == "gemini" and gemini_ok:
            return "gemini"

        # Modo "auto" o "balanced" (Smart Load Balancing)
        if groq_ok and gemini_ok:
            # 60% Groq (ultra velocidad en chat) / 40% Gemini (rotación inteligente de cuotas)
            self._request_counter += 1
            if self._request_counter % 5 in (0, 1, 2):  # 3 de cada 5 requests a Groq
                return "groq"
            else:
                return "gemini"

        # Si uno de los dos está en cooldown, usar el que esté saludable
        if groq_ok:
            return "groq"
        if gemini_ok:
            return "gemini"

        # Si ambos están marcados como caídos pero expira el cooldown, intentar Gemini por defecto
        return "gemini" if self.client else "groq"

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

        # Seleccionar proveedor inicial vía Load Balancer
        chosen_provider = self._select_provider(has_images, needs_web_search, trigger)
        logger.info(f"Load Balancer enrutó a '{chosen_provider}' para {username} (web_search={needs_web_search}, imgs={has_images})")

        reply = None
        if chosen_provider == "groq":
            reply = await self._generate_groq_reply(
                trigger, context, username, bot_name, image_description,
                is_reactive=is_reactive, **kwargs
            )
            # Fallback automático a Gemini si Groq falló
            if not reply and self._is_gemini_healthy():
                logger.warning("Groq no respondió, activando failover automático a Gemini...")
                reply = await self._generate_gemini_reply(
                    trigger, context, username, bot_name, image_description,
                    needs_web_search=needs_web_search, is_reactive=is_reactive, is_fallback=True, **kwargs
                )
        else:
            reply = await self._generate_gemini_reply(
                trigger, context, username, bot_name, image_description,
                needs_web_search=needs_web_search, is_reactive=is_reactive, **kwargs
            )
            # Fallback automático a Groq si Gemini falló
            if not reply and self._is_groq_healthy():
                logger.warning("Gemini no respondió, activando failover automático a Groq...")
                reply = await self._generate_groq_reply(
                    trigger, context, username, bot_name, image_description,
                    is_fallback=True, is_reactive=is_reactive, **kwargs
                )

        return reply

    async def _generate_gemini_reply(
        self, trigger: str, context: str, username: str,
        bot_name: str, image_description: str = "", needs_web_search: bool = False,
        is_reactive: bool = False, is_fallback: bool = False, **kwargs
    ):
        if not self.client:
            return None

        active_room_users = kwargs.get("active_room_users", "")
        server_emojis = kwargs.get("server_emojis", "")

        system_prompt = kwargs.get("system_prompt_override")
        if not system_prompt:
            system_prompt = DALET_PERSONALITY.format(bot_name=bot_name)
            if active_room_users:
                system_prompt += f"\n\nGente presente: {active_room_users}"
            if server_emojis:
                system_prompt += f"\nEmojis del servidor (úsalos con moderación): {server_emojis}"

        vision_context = f"\n[IMAGEN: {image_description}]\n" if image_description else ""
        prompt = f"Conversación reciente:\n{context}{vision_context}\n\n{username}: \"{trigger}\""

        t0 = time.time()
        try:
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
            logger.info(f"Llamando Gemini: {model_name} (fallback={is_fallback}, search={needs_web_search})")

            tools = [types.Tool(google_search=types.GoogleSearch())] if needs_web_search else None
            max_tokens = kwargs.get("max_tokens_override", 420 if is_reactive else 700)

            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.85,
                max_output_tokens=max_tokens,
                tools=tools
            )

            response = await self.client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )

            if response and response.text:
                latency_ms = int((time.time() - t0) * 1000)
                reply_text = response.text.strip()

                # Extracción de tokens
                usage = getattr(response, "usage_metadata", None)
                p_tokens = getattr(usage, "prompt_token_count", None) or (len(prompt) // 4)
                c_tokens = getattr(usage, "candidates_token_count", None) or (len(reply_text) // 4)

                # Actualizar telemetría
                self.telemetry["gemini"]["requests"] += 1
                self.telemetry["gemini"]["prompt_tokens"] += p_tokens
                self.telemetry["gemini"]["completion_tokens"] += c_tokens
                self.telemetry["gemini"]["latencies_ms"].append(latency_ms)
                if len(self.telemetry["gemini"]["latencies_ms"]) > 50:
                    self.telemetry["gemini"]["latencies_ms"].pop(0)

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
            return None

        except Exception as e:
            logger.error(f"Error llamando Gemini: {e}")
            self.telemetry["gemini"]["errors"] += 1
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                logger.warning("Gemini 429 detectado. Circuit Breaker abierto por 60s.")
                self._gemini_cooldown_until = time.time() + 60
            return None

    async def _generate_groq_reply(
        self, trigger: str, context: str, username: str,
        bot_name: str, image_description: str = "", is_fallback: bool = False,
        is_reactive: bool = False, **kwargs
    ):
        if not self.groq_api_key:
            return None

        active_room_users = kwargs.get("active_room_users", "")

        model_primary = (os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile").strip()
        model_fallback = (os.getenv("GROQ_MODEL_FALLBACK") or "llama-3.1-8b-instant").strip()
        model_name = model_fallback if is_fallback else model_primary

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }

        groq_system = kwargs.get("system_prompt_override")
        if not groq_system:
            groq_system = DALET_PERSONALITY.format(bot_name=bot_name)
            if active_room_users:
                groq_system += f"\n\nGente presente: {active_room_users}"

        vision_context = f"\n[IMAGEN: {image_description}]\n" if image_description else ""
        user_msg = f"Conversación reciente:\n{context}{vision_context}\n\n{username}: \"{trigger}\""

        max_tokens = kwargs.get("max_tokens_override", 420 if is_reactive else 600)
        data = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": groq_system},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.75,
            "max_tokens": max_tokens
        }

        t0 = time.time()
        try:
            logger.info(f"Llamando Groq: {model_name} (fallback={is_fallback})")
            response = await self._http_client.post(url, headers=headers, json=data)

            if response.status_code == 429:
                logger.warning(f"Groq 429 Rate Limit en {model_name}. Circuit Breaker abierto por 60s.")
                self._groq_cooldown_until = time.time() + 60
                self.telemetry["groq"]["errors"] += 1
                return None

            if response.status_code != 200:
                error_body = response.text
                logger.error(f"Groq error HTTP {response.status_code} ({model_name}): {error_body}")
                self.telemetry["groq"]["errors"] += 1
                if response.status_code in (401, 404):
                    self._groq_cooldown_until = time.time() + 300
                return None

            result = response.json()
            reply_text = result['choices'][0]['message']['content'].strip()
            latency_ms = int((time.time() - t0) * 1000)

            # Extracción de tokens
            usage = result.get("usage", {})
            p_tokens = usage.get("prompt_tokens") or (len(user_msg) // 4)
            c_tokens = usage.get("completion_tokens") or (len(reply_text) // 4)

            # Actualizar telemetría
            self.telemetry["groq"]["requests"] += 1
            self.telemetry["groq"]["prompt_tokens"] += p_tokens
            self.telemetry["groq"]["completion_tokens"] += c_tokens
            self.telemetry["groq"]["latencies_ms"].append(latency_ms)
            if len(self.telemetry["groq"]["latencies_ms"]) > 50:
                self.telemetry["groq"]["latencies_ms"].pop(0)

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

        except Exception as e:
            logger.error(f"Groq falló ({model_name}): {e}")
            self.telemetry["groq"]["errors"] += 1
            self._groq_cooldown_until = time.time() + 30
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

    async def _get_images_description(self, image_urls: list):
        """Describe una imagen usando el modelo principal con caché en RAM."""
        if not self.gemini_api_key or not self.client or not image_urls:
            return ""

        url = image_urls[0]
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        if url_hash in self._vision_cache:
            logger.info("Caché hit para descripción de imagen.")
            return self._vision_cache[url_hash]

        try:
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

            resp = await self._http_client.get(url)
            resp.raise_for_status()

            image_part = types.Part.from_bytes(
                data=resp.content,
                mime_type=resp.headers.get('Content-Type', 'image/jpeg')
            )

            res = await self.client.aio.models.generate_content(
                model=model_name,
                contents=[
                    "Describe brevemente esta imagen en 40 palabras o menos. "
                    "Enfócate en el contenido principal y texto visible.",
                    image_part
                ]
            )

            if res and res.text:
                desc = res.text.strip()
                if len(self._vision_cache) > 50:
                    self._vision_cache.clear()
                self._vision_cache[url_hash] = desc
                return desc

            return ""

        except Exception as e:
            logger.error(f"Error en visión: {e}")
            return ""

