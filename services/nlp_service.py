from google import genai
from google.genai import types
import os
import httpx
import logging
import asyncio
from database.repositories.user_repository import UserRepository

logger = logging.getLogger("dalet.services.nlp")

# Líneas del historial de canal a incluir en respuestas reactive (canal completo, todos los usuarios)
REACTIVE_MAX_CONTEXT_LINES = 6

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
    def __init__(self, gemini_api_key: str, user_repo=None):
        from dotenv import load_dotenv
        load_dotenv(override=True)

        self.gemini_api_key = gemini_api_key
        if self.gemini_api_key:
            self.client = genai.Client(
                api_key=self.gemini_api_key,
                http_options={'api_version': 'v1beta'}
            )

        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.repo = user_repo or UserRepository()

        env_provider = os.getenv("AI_PROVIDER", "gemini").lower()
        self.active_provider = env_provider

        logger.info(f"NLPService iniciado. Proveedor: {self.active_provider}")

    async def generate_reply(
        self, trigger: str, context: str, username: str,
        bot_name: str = "Dalet", image_urls: list = None, is_reactive: bool = False, **kwargs
    ):
        logger.info(f"Generando respuesta para {username}. BotName: {bot_name}. Proveedor: {self.active_provider}")

        image_description = ""
        if image_urls:
            image_description = await self._get_images_description(image_urls)

        if is_reactive:
            context = self._trim_context_for_reactive(context)

        if self.active_provider == "groq" and self.groq_api_key:
            return await self._generate_groq_reply(
                trigger, context, username, bot_name, image_description,
                is_reactive=is_reactive, **kwargs
            )
        else:
            return await self._generate_gemini_reply(
                trigger, context, username, bot_name, image_description,
                is_reactive=is_reactive, **kwargs
            )

    async def _generate_gemini_reply(
        self, trigger: str, context: str, username: str,
        bot_name: str, image_description: str = "", is_reactive: bool = False, **kwargs
    ):
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

        try:
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            logger.info(f"Llamando Gemini: {model_name}")

            max_tokens = kwargs.get("max_tokens_override", 420 if is_reactive else 700)
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.85,
                max_output_tokens=max_tokens,  # Puede ser sobreescrito para análisis largos
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )

            response = await self.client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )

            if response and response.text:
                return response.text.strip()
            return None

        except Exception as e:
            logger.error(f"Error llamando Gemini: {e}")
            # Fallback a Groq si Gemini falla (cuota, etc.)
            if self.groq_api_key:
                logger.warning("Gemini falló, usando Groq como fallback...")
                return await self._generate_groq_reply(
                    trigger, context, username, bot_name, image_description,
                    is_fallback=True, is_reactive=is_reactive, **kwargs
                )
            return None

    async def _generate_groq_reply(
        self, trigger: str, context: str, username: str,
        bot_name: str, image_description: str = "", is_fallback: bool = False,
        is_reactive: bool = False, **kwargs
    ):
        active_room_users = kwargs.get("active_room_users", "")

        # Modelos desde .env, con valores por defecto de alta fidelidad (DeepSeek R1 Distill / Qwen Coder)
        model_primary = os.getenv("GROQ_MODEL", "deepseek-r1-distill-llama-70b")
        model_fallback = os.getenv("GROQ_MODEL_FALLBACK", "qwen-2.5-coder-32b")
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

        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"Llamando Groq: {model_name} (fallback={is_fallback})")
                response = await client.post(url, headers=headers, json=data, timeout=25.0)

                if response.status_code == 429:
                    if not is_fallback:
                        # Intentar con modelo más pequeño
                        return await self._generate_groq_reply(
                            trigger, context, username, bot_name, image_description,
                            is_fallback=True, is_reactive=is_reactive, **kwargs
                        )
                    else:
                        logger.warning("Groq también con rate limit. Silencio.")
                        return None

                response.raise_for_status()
                result = response.json()
                return result['choices'][0]['message']['content'].strip()

        except Exception as e:
            logger.error(f"Groq falló ({model_name}): {e}")
            return None

    def _trim_context_for_reactive(self, context: str) -> str:
        """
        Recorta el contexto a las últimas REACTIVE_MAX_CONTEXT_LINES líneas del canal.
        El historial siempre es del canal completo (todos los usuarios), no solo de quien habla,
        para que Dalet pueda seguir la conversación de forma natural.
        Preserva los datos de memoria del usuario si existen.
        """
        lines = context.split("\n")

        # Buscar el marcador del historial de chat
        chat_marker_idx = None
        for i, line in enumerate(lines):
            if "CHAT RECIENTE" in line:
                chat_marker_idx = i
                break

        if chat_marker_idx is None:
            # Sin marcador — recortar directamente las últimas N líneas
            return "\n".join(lines[-REACTIVE_MAX_CONTEXT_LINES:])

        user_data_lines = lines[:chat_marker_idx]   # Datos del usuario (memorias, si existen)
        chat_lines = lines[chat_marker_idx:]         # "CHAT RECIENTE:" + historial del canal

        # Mantener encabezado + últimas N líneas del canal
        if len(chat_lines) > REACTIVE_MAX_CONTEXT_LINES + 1:
            chat_lines = [chat_lines[0]] + chat_lines[-REACTIVE_MAX_CONTEXT_LINES:]

        return "\n".join(user_data_lines + chat_lines)

    async def _get_images_description(self, image_urls: list):
        """Describe brevemente una imagen usando Gemini (solo 1 para ahorrar cuota)."""
        if not self.gemini_api_key:
            return ""

        try:
            model_name = "gemini-2.0-flash"

            async with httpx.AsyncClient() as client:
                for url in image_urls[:1]:  # Solo 1 imagen
                    resp = await client.get(url, timeout=10.0)
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
                        return res.text.strip()

        except Exception as e:
            logger.error(f"Error en visión: {e}")

        return ""
