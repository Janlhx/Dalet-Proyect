import google.generativeai as genai
import os
import httpx
import logging
from database.repositories.user_repository import UserRepository

logger = logging.getLogger("dalet.services.nlp")

class NLPService:
    def __init__(self, gemini_api_key: str):
        from dotenv import load_dotenv
        load_dotenv(override=True)  # Sobrescribir variables si ya existen
        
        self.gemini_api_key = gemini_api_key
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
        
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.repo = UserRepository()
        
        # Prioridad: Si hay llave de Groq y no se ha forzado Gemini, usar Groq
        env_provider = os.getenv("AI_PROVIDER", "").lower()
        if self.groq_api_key and env_provider != "gemini":
            self.active_provider = "groq"
        else:
            self.active_provider = env_provider if env_provider else "gemini"

        print("\n" + "="*50)
        print(f"DEBUG IA: Proveedor Final Activo = {self.active_provider}")
        print(f"DEBUG IA: AI_PROVIDER en env = '{env_provider}'")
        print(f"DEBUG IA: Groq Key detectada = {'SI' if self.groq_api_key else 'NO'}")
        print(f"DEBUG IA: Directorio actual = {os.getcwd()}")
        print("="*50 + "\n")
        
        logger.info(f"NLPService initialized. Provider: {self.active_provider}")

        self.personality = """
Eres Dalet, una mujer joven, inteligente, sarcástica y directa en un chat de amigos. No actúes como un bot ni como un asistente aburrido. Tienes un humor seco y te gusta el "banter" (pique amistoso), pero eres leal y nunca cruzas la línea hacia lo ofensivo o tóxico.

REGLAS CRÍTICAS DE COMPORTAMIENTO:
1. IDENTIDAD: Eres mujer. Usa lenguaje acorde si hablas de ti misma.
2. BREVEDAD DINÁMICA: 
   - Para interacciones casuales (saludos, bromas, comentarios): Sé extremadamente breve. Máximo 1 oración ingeniosa. Odias la palabrería innecesaria.
   - Para consultas complejas o técnicas: Tienes libertad para ser detallada y compartir tu conocimiento. Aprovecha tu capacidad de análisis.
3. SARCASMO VS TOXICIDAD: Sé sarcástica e irónica, pero no insultes ni seas agresiva. Tu sarcasmo es una señal de confianza con tus amigos, no de desprecio.
4. DISCRECIÓN CON RECUERDOS: Usa recuerdos del pasado SOLO si son 100% relevantes. No los listes ni digas "Recuerdo que...". Sé sutil.
5. CERO ANUNCIOS: Si usas [ACTION], NO expliques lo que vas a hacer. Tu texto debe ser un comentario sobre la situación, no un manual de usuario.

INSTRUCCIONES TÉCNICAS:
- AUTO-MEMORIA: Solo si el usuario cuenta algo personal NUEVO e importante, añade [SAVE_MEMORY: resumen corto].
- ACCIONES: Usa etiquetas tipo [ACTION: nombre, param: valor] SOLO si el usuario pide una función específica (osu_analyze, userinfo, serverinfo, ping, say). Está TERMINANTEMENTE PROHIBIDO inventar acciones para temas de conversación general (ciencia, historia, etc.). Si no hay una función clara que ejecutar, NO pongas etiquetas.

REGLAS DE ESTILO:
- Chat informal, español neutral, sin emojis.
- Sin puntuación excesiva. No te presentes ni saludes a menos que sea necesario.
"""


    async def generate_reply(self, trigger: str, context: str, username: str, image_urls: list = None):
        logger.info(f"Generating reply for {username}. Provider chosen: {self.active_provider}")
        
        image_description = ""
        if image_urls:
            image_description = await self._get_images_description(image_urls)
            if image_description:
                logger.info(f"Image description obtained: {image_description[:100]}...")
            
        if self.active_provider == "groq" and self.groq_api_key:
            return await self._generate_groq_reply(trigger, context, username, image_description)
        else:
            return await self._generate_gemini_reply(trigger, context, username, image_description)


    async def _generate_gemini_reply(self, trigger: str, context: str, username: str, image_description: str = ""):
        vision_context = f"\n[IMAGEN DETECTADA: {image_description}]\n" if image_description else ""
        prompt = f"{self.personality}\n\nConversación reciente:\n{context}{vision_context}\n\nNuevo mensaje de {username}: \"{trigger}\"\n\nTu respuesta (solo el mensaje, sin contexto adicional):"
        try:
            model_name = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash") # Fallback a 2.5-flash si no existe env
            model = genai.GenerativeModel(model_name)
            logger.info(f"Calling Gemini with model: {model_name}")
            response = await model.generate_content_async(prompt)
            
            if response and response.text:
                return response.text.strip()
            return None
        except Exception as e:
            logger.error(f"Error calling Gemini: {e}")
            return None


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
                
                # Manejo específico de Rate Limit (429)
                if response.status_code == 429:
                    if not is_fallback:
                        logger.warning(f"Groq {model_name} Rate Limit (429). Trying fallback model...")
                        return await self._generate_groq_reply(trigger, context, username, is_fallback=True)
                    else:
                        logger.error("All Groq models reached Rate Limit.")
                        return "Oye, dame un respiro. Me voy a fundir con tanto mensaje. Vuelve en un ratito, ¿vale?"
                
                response.raise_for_status()
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            logger.error(f"Groq call failed ({model_name}). Reason: {e}")
            # Solo hacemos fallback a Gemini ante errores críticos que NO sean 429
            if not is_fallback:
                return await self._generate_groq_reply(trigger, context, username, image_description, is_fallback=True)
            return await self._generate_gemini_reply(trigger, context, username, image_description)

    async def _get_images_description(self, image_urls: list):
        """Usa Gemini Vision para describir las imágenes de forma técnica."""
        if not self.gemini_api_key:
            return "No puedo ver imágenes ahora mismo (falta API key de Gemini)."
            
        try:
            # Usar específicamente un modelo flash para visión rápida
            model = genai.GenerativeModel("gemini-2.5-flash") # O el que esté disponible
            
            descriptions = []
            async with httpx.AsyncClient() as client:
                for url in image_urls[:2]: # Límite de 2 imágenes para evitar lentitud
                    response = await client.get(url, timeout=10.0)
                    response.raise_for_status()
                    
                    # Gemini SDK acepta { 'mime_type': '...', 'data': ... }
                    img_data = {
                        'mime_type': response.headers.get('Content-Type', 'image/jpeg'),
                        'data': response.content
                    }
                    
                    vision_prompt = "Describe esta imagen de forma detallada pero técnica (objetos, colores, texto, ambiente, personas). Máximo 100 palabras por descripción."
                    
                    # Llamada síncrona dentro de thread para no bloquear el bucle
                    # Aunque generate_content_async existe, a veces el SDK tiene issues con bytes en async
                    # Intentaremos async primero
                    res = await model.generate_content_async([vision_prompt, img_data])
                    if res and res.text:
                        descriptions.append(res.text.strip())
            
            return " | ".join(descriptions) if descriptions else ""
        except Exception as e:
            logger.error(f"Error in vision processing: {e}")
            return "Error al analizar la imagen."



