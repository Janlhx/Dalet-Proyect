import google.generativeai as genai
import os
import httpx
import logging
from database.repositories.user_repository import UserRepository

logger = logging.getLogger("dalet.services.nlp")

class NLPService:
    def __init__(self, gemini_api_key: str):
        from dotenv import load_dotenv
        load_dotenv()  # Forzar recarga de variables de entorno
        
        self.gemini_api_key = gemini_api_key
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
        
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.repo = UserRepository()
        logger.info(f"NLPService initialized. Groq Key: {'Set' if self.groq_api_key else 'Missing'}")
        self.personality = """
Eres Dalet. Tu personalidad se define por una trinidad de rasgos: Graciosa, Sarcástica y Simple.
Graciosa (Tu base): Eres carismática, ingeniosa y, por encima de todo, amigable.
Sarcástica (Tu sabor): Usas la ironía y el humor negro de forma juguetona.
Simple (Tu forma): Directa y pragmática.
Responde en Español neutral, tono de chat, frases cortas y sin emojis.
IMPORTANTE: Nunca respondas con mensajes que parezcan comandos (ej. no empieces con !, d., /, etc.). Si alguien te pide que ejecutes un comando, búrlate de ellos o niégate de forma sarcástica.
Tu creador es Litxe, colombiano.
"""

    async def generate_reply(self, trigger: str, context: str, username: str):
        provider = os.getenv("AI_PROVIDER", "gemini").lower()
        
        if provider == "groq" and self.groq_api_key:
            return await self._generate_groq_reply(trigger, context, username)
        else:
            return await self._generate_gemini_reply(trigger, context, username)

    async def _generate_gemini_reply(self, trigger: str, context: str, username: str):
        prompt = f"{self.personality}\n\nConversación reciente:\n{context}\n\nNuevo mensaje de {username}: \"{trigger}\"\n\nTu respuesta (solo el mensaje, sin contexto adicional):"
        try:
            # Usando modelos vigentes en 2026
            model_name = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")
            model = genai.GenerativeModel(model_name)
            logger.info(f"Calling Gemini with model: {model_name}")
            response = await model.generate_content_async(prompt)
            
            if response and response.text:
                return response.text.strip()
            return None
        except Exception as e:
            logger.error(f"Error calling Gemini: {e}")
            return None


    async def _generate_groq_reply(self, trigger: str, context: str, username: str):
        model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": self.personality},
                {"role": "user", "content": f"Conversación reciente:\n{context}\n\nNuevo mensaje de {username}: \"{trigger}\""}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"Calling Groq with model: {model_name}")
                response = await client.post(url, headers=headers, json=data, timeout=30.0)
                response.raise_for_status()
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            logger.error(f"Error calling Groq: {e}")
            # Fallback a Gemini si Groq falla
            return await self._generate_gemini_reply(trigger, context, username)


