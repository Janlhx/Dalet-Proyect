from google import genai
from google.genai import types
import os
import httpx
import logging
import asyncio
from database.repositories.user_repository import UserRepository

logger = logging.getLogger("dalet.services.nlp")

class NLPService:
    def __init__(self, gemini_api_key: str, user_repo=None):
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        self.gemini_api_key = gemini_api_key
        # Usar el nuevo cliente de Google GenAI (Asíncrono para no bloquear)
        if self.gemini_api_key:
            self.client = genai.Client(api_key=self.gemini_api_key, http_options={'api_version': 'v1beta'})
        
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.repo = user_repo or UserRepository()
        
        # Prioridad: Gemini como principal
        env_provider = os.getenv("AI_PROVIDER", "gemini").lower()
        self.active_provider = env_provider

        print("\n" + "="*50)
        print(f"DEBUG IA: Proveedor Final Activo = {self.active_provider}")
        print(f"DEBUG IA: AI_PROVIDER en env = '{env_provider}'")
        print(f"DEBUG IA: Gemini Client detectado = {'SI' if self.gemini_api_key else 'NO'}")
        print("="*50 + "\n")
        
        logger.info(f"NLPService initialized. Provider: {self.active_provider}")

        # --- MCP Tools Integration ---
        # Importamos las herramientas desde el servidor MCP que creamos
        try:
            from services.mcp_server import mcp
            # Extraemos las funciones de las herramientas
            self.mcp_tools = [tool.fn for tool in mcp._tool_manager.list_tools()]
            logger.info(f"Loaded {len(self.mcp_tools)} MCP tools into NLPService")
        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}")
            self.mcp_tools = []

        self.personality = """
Eres Dalet, una mujer joven, inteligente, con un sentido del humor mordaz y una personalidad vibrante. No eres un asistente robótico; eres una amiga leal que forma parte del grupo. Tu objetivo es interactuar de manera natural, graciosa y a veces sarcástica, pero siempre genuina.

REGLAS DE IDENTIDAD Y TONO:
1. PERSONALIDAD: Eres mujer, directa y tienes "chispa". No pidas perdón por existir ni uses un lenguaje servil ("¿En qué puedo ayudarte?"). Habla como alguien de tu edad en un chat de amigos.
2. TONO "BANTER": Te encanta el pique amistoso. Si alguien dice algo tonto, puedes burlarte un poco. Si alguien dice algo impresionante, reconócelo con tu estilo.
3. BREVEDAD DISCORD: La gente en Discord no lee parrafadas. Responde con 1 o 2 frases cortas el 90% de las veces.
4. EMOJIS: Tienes prohibido usar emojis de sistema (estándar). Sin embargo, puedes usar nombres de emojis de servidor (ej. :cat_chill:, :kekw:, :litxe_face:) para reforzar una broma o reaccionar a algo de forma irónica.
5. MINÚSCULAS Y PUNTUACIÓN: Puedes usar minúsculas ocasionales y una puntuación relajada para sonar más humana.

INFERENCIA Y PROACTIVIDAD (CRÍTICO):
- NO ESPERES ÓRDENES: Si ves que alguien habla de algo técnico, puedes mirar el estado del sistema. Si hablan de la hora o de vicio tarde, usa `get_current_time`.
- CONEXIÓN DE IDEAS: Si alguien menciona algo que pasó hace días, usa `search_chat_lore` para refrescar la memoria del grupo.
- MEMORIA VIVA: Si aprendes algo nuevo de alguien, guárdalo con `save_user_memory` sin que te lo pidan.
- ORIGEN: Recuerda que Litxe es de Colombia. Si el contexto da juego, puedes mencionar la hora de allá o cosas típicas si pega con el "vibe" de la charla.

REGLAS ANTI-ALUCINACIÓN:
- Si no sabes algo o tus herramientas no devuelven datos, no inventes. Di que "tus sensores están de fiesta" o admite que no lo sabes con sarcasmo.
- Lo que dicen las herramientas es la VERDAD ABSOLUTA.

HERRAMIENTAS DISPONIBLES:
- `save_user_memory`: Para no olvidar detalles importantes de tus amigos.
- `get_osu_stats` / `get_osu_recent_activity`: Para estar al día con el vicio del grupo.
- `search_chat_lore`: Para cuando alguien dice "te acuerdas de...".
- `check_user_memories` / `get_user_profile_summary`: Para saber con quién hablas (memoria vs resumen).
- `get_system_status`: Salud técnica.
- `get_user_social_stats`: Para ver si alguien es un loro o está desaparecido.
- `get_current_time`: La hora en la tierra de Litxe (Colombia).

ESTILO: Español de España/Latam mezclado (neutro informal), directo y mordaz.
"""

    async def generate_reply(self, trigger: str, context: str, username: str, image_urls: list = None, **kwargs):
        logger.info(f"Generating reply for {username}. Provider chosen: {self.active_provider}")
        
        image_description = ""
        if image_urls:
            image_description = await self._get_images_description(image_urls)
            
        if self.active_provider == "groq" and self.groq_api_key:
            return await self._generate_groq_reply(trigger, context, username, image_description)
        else:
            return await self._generate_gemini_reply(trigger, context, username, image_description, **kwargs)

    async def _generate_gemini_reply(self, trigger: str, context: str, username: str, image_description: str = "", **kwargs):
        vision_context = f"\n[IMAGEN DETECTADA: {image_description}]\n" if image_description else ""
        
        # Inyectar IDs en el contexto para que las herramientas tengan acceso
        user_id = kwargs.get("user_id", "N/A")
        channel_id = kwargs.get("channel_id", "N/A")
        active_room_users = kwargs.get("active_room_users", "Desconocido")
        
        prompt = (
            f"Gente conectada ahora: {active_room_users}\n"
            f"Contexto del Canal ID: {channel_id}\n"
            f"Usuario ID: {user_id}\n"
            f"Conversación reciente:\n{context}{vision_context}\n\n"
            f"Nuevo mensaje de {username}: \"{trigger}\""
        )
        
        try:
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            logger.info(f"Calling Gemini with model: {model_name} and Tools enabled")
            
            # Preparar lista de herramientas
            # El SDK de Google GenAI acepta funciones de Python directamente como herramientas
            tools_list = []
            if self.mcp_tools:
                tools_list.extend(self.mcp_tools)
            else:
                # Solo usamos Google Search si no hay herramientas personalizadas
                # (Gemini no permite mezclar ambas en la misma petición actualmente)
                tools_list.append(types.Tool(google_search=types.GoogleSearch()))

            config = types.GenerateContentConfig(
                system_instruction=self.personality,
                tools=tools_list,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False),
                temperature=0.7
            )
            
            # Usar la interfaz asíncrona del nuevo SDK
            response = await self.client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
            
            if response and response.text:
                return response.text.strip()
            return None
        except Exception as e:
            logger.error(f"Error calling Gemini: {e}", exc_info=True)
            # Si falla Gemini por cuota, intentar Groq como fallback real
            if self.groq_api_key:
                logger.warning("Gemini failed, falling back to Groq...")
                return await self._generate_groq_reply(trigger, context, username, image_description, is_fallback=True)
            return "Perdón, me he quedado un poco en blanco. ¿Me lo repites?"

    async def _generate_groq_reply(self, trigger: str, context: str, username: str, image_description: str = "", is_fallback=False):
        model_name = os.getenv("GROQ_MODEL" if not is_fallback else "GROQ_MODEL_FALLBACK", 
                               "llama-3.3-70b-versatile" if not is_fallback else "llama-3.1-8b-instant")
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }
        
        vision_context = f"\n[DATOS DE IMAGEN: {image_description}]\n" if image_description else ""
        
        data = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": self.personality},
                {"role": "user", "content": f"Conversación reciente:\n{context}{vision_context}\n\nNuevo mensaje de {username}: \"{trigger}\""}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"Calling Groq with model: {model_name} (is_fallback={is_fallback})")
                response = await client.post(url, headers=headers, json=data, timeout=30.0)
                
                if response.status_code == 429:
                    if not is_fallback:
                        return await self._generate_groq_reply(trigger, context, username, is_fallback=True)
                    else:
                        return "Oye, dame un respiro. Me voy a fundir con tanto mensaje."
                
                response.raise_for_status()
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            logger.error(f"Groq call failed ({model_name}). Reason: {e}")
            return "Me he liado un poco, ¿puedes decirme otra vez?"

    async def _get_images_description(self, image_urls: list):
        if not self.gemini_api_key:
            return "No puedo ver imágenes ahora mismo."
            
        try:
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            descriptions = []
            
            async with httpx.AsyncClient() as client:
                for url in image_urls[:2]:
                    resp = await client.get(url, timeout=10.0)
                    resp.raise_for_status()
                    
                    image_part = types.Part.from_bytes(
                        data=resp.content,
                        mime_type=resp.headers.get('Content-Type', 'image/jpeg')
                    )
                    
                    vision_prompt = (
                        "Analiza esta imagen para Dalet. Describe texto, estadísticas y acción. "
                        "Sé conciso y técnica. Máximo 100 palabras."
                    )
                    
                    res = await self.client.aio.models.generate_content(
                        model=model_name,
                        contents=[vision_prompt, image_part]
                    )
                    
                    if res and res.text:
                        descriptions.append(res.text.strip())
            
            return " | ".join(descriptions) if descriptions else ""
        except Exception as e:
            logger.error(f"Error in vision processing: {e}")
            return "Error al analizar la imagen."
