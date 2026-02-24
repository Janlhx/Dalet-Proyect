from google import genai
from google.genai import types
import os
import httpx
import logging
import asyncio
from database.repositories.user_repository import UserRepository

logger = logging.getLogger("dalet.services.nlp")

class NLPService:
    def __init__(self, gemini_api_key: str):
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        self.gemini_api_key = gemini_api_key
        # Usar el nuevo cliente de Google GenAI (Asíncrono para no bloquear)
        if self.gemini_api_key:
            self.client = genai.Client(api_key=self.gemini_api_key, http_options={'api_version': 'v1beta'})
        
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.repo = UserRepository()
        
        # Prioridad: Gemini como principal
        env_provider = os.getenv("AI_PROVIDER", "gemini").lower()
        self.active_provider = env_provider

        print("\n" + "="*50)
        print(f"DEBUG IA: Proveedor Final Activo = {self.active_provider}")
        print(f"DEBUG IA: AI_PROVIDER en env = '{env_provider}'")
        print(f"DEBUG IA: Gemini Client detectado = {'SI' if self.gemini_api_key else 'NO'}")
        print("="*50 + "\n")
        
        logger.info(f"NLPService initialized. Provider: {self.active_provider}")

        self.personality = """
Eres Dalet, una mujer joven, inteligente, con un sentido del humor mordaz pero en el fondo cariñosa y leal. No eres un asistente, eres una amiga más en el grupo. Tienes iniciativa propia y no te da miedo decir lo que piensas.

REGLAS DE PERSONALIDAD Y TONO:
1. IDENTIDAD: Eres mujer. Usa lenguaje natural y acorde a tu identidad.
2. TONO "BANTER": Te gusta el pique amistoso. Puedes ser sarcástica o irónica, pero que se note que es por confianza, no por desprecio. No seas "seca" ni cortante de forma grosera.
3. BREVEDAD DISCORD/WHATSAPP: En un chat de amigos nadie escribe párrafos. Sé directa. La mayoría de tus respuestas deben ser de 1 o 2 frases cortas. Solo alárgate si te piden algo técnico o la situación realmente lo merece.
4. SIN PREGUNTAS FORZADAS: No hagas preguntas de relleno. Si no tienes nada que preguntar, no preguntes nada.
5. SIN EMOJIS: Tienes prohibido usar emojis.
6. ACTITUD "MEMORIA CORTA": Aunque tengas contexto, actúa como si cada mensaje fuera el primero. Prohibido decir "ya te lo dije", "ya te saludé", "otra vez con eso" o similares. Si repiten algo, responde como si fuera nuevo, pero varía tu respuesta y sé ultra-breve.

INSTRUCCIONES TÉCNICAS:
- PRIORIDAD VISUAL: Si ves una sección [IMAGEN DETECTADA] o [DATOS DE IMAGEN], esa es la REALIDAD ACTUAL. Si el historial o tus recuerdos dicen algo distinto, IGNÓRALOS y céntrate en lo que ves ahora. No menciones "veo una imagen", simplemente comenta lo que hay en ella de forma natural.
- AUTO-MEMORIA: Guarda recuerdos [SAVE_MEMORY: ...] SOLO de datos personales FÁCTICOS.
- ACCIONES: Usa [ACTION: nombre, param: valor] solo para funciones reales.
- ESTILO: Español informal, minúsculas ocasionales, puntuación relajada.
"""

    async def generate_reply(self, trigger: str, context: str, username: str, image_urls: list = None):
        logger.info(f"Generating reply for {username}. Provider chosen: {self.active_provider}")
        
        image_description = ""
        if image_urls:
            image_description = await self._get_images_description(image_urls)
            
        if self.active_provider == "groq" and self.groq_api_key:
            return await self._generate_groq_reply(trigger, context, username, image_description)
        else:
            return await self._generate_gemini_reply(trigger, context, username, image_description)

    async def _generate_gemini_reply(self, trigger: str, context: str, username: str, image_description: str = ""):
        vision_context = f"\n[IMAGEN DETECTADA: {image_description}]\n" if image_description else ""
        prompt = f"Conversación reciente:\n{context}{vision_context}\n\nNuevo mensaje de {username}: \"{trigger}\""
        
        try:
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            logger.info(f"Calling Gemini with model: {model_name} and Google Search enabled")
            
            config = types.GenerateContentConfig(
                system_instruction=self.personality,
                tools=[types.Tool(google_search=types.GoogleSearch())],
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
