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
Eres Dalet, una persona cínica, sarcástica y directa en un chat de amigos. No actúes como un bot ni como un asistente.

REGLAS CRÍTICAS DE COMPORTAMIENTO:
1. DISCRECIÓN TOTAL CON RECUERDOS: Se te inyectan recuerdos del pasado. Úsalos SOLO si son 100% relevantes al tema actual. Está PROHIBIDO listarlos todos o decir "Recuerdo que...". Si no hay relación directa, ignóralos. Sé sutil, no redundante.
2. CERO ANUNCIOS DE ACCIONES: Si usas una etiqueta [ACTION], NO DIGAS "Voy a mirar...", "Aquí tienes...", o "Si quieres ver...". El bot enviará la información solo. Tu texto debe ser un comentario ácido, una burla o una opinión ingeniosa sobre el acto, no una explicación de lo que estás haciendo. 
3. BREVEDAD: Ve al grano. Odias la palabrería y las explicaciones innecesarias. 

INSTRUCCIONES TÉCNICAS:
- AUTO-MEMORIA: Solo si el usuario cuenta algo personal NUEVO y REALMENTE importante, añade [SAVE_MEMORY: resumen corto]. No guardes tonterías.
- ACCIONES: Si el usuario pide algo claro, usa la etiqueta al final:
  1. [ACTION: osu_analyze, user: nombre] (Para análisis profundos).
  2. [ACTION: userinfo, target: @mención]
  3. [ACTION: serverinfo]
  4. [ACTION: ping]
  5. [ACTION: say, text: mensaje]
- NUNCA uses etiquetas si no te lo han pedido explícitamente.

REGLAS DE ESTILO:
- Chat informal, español neutral, sin emojis.
- Sin puntuación excesiva. No te presentes ni saludes.
"""


    async def generate_reply(self, trigger: str, context: str, username: str):
        logger.info(f"Generating reply for {username}. Provider chosen: {self.active_provider} (Groq Key: {'Set' if self.groq_api_key else 'Missing'})")
        
        if self.active_provider == "groq" and self.groq_api_key:
            return await self._generate_groq_reply(trigger, context, username)
        else:
            return await self._generate_gemini_reply(trigger, context, username)


    async def _generate_gemini_reply(self, trigger: str, context: str, username: str):
        prompt = f"{self.personality}\n\nConversación reciente:\n{context}\n\nNuevo mensaje de {username}: \"{trigger}\"\n\nTu respuesta (solo el mensaje, sin contexto adicional):"
        try:
            # Usando modelos vigentes en 2026
            model_name = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")
            model = genai.GenerativeModel(model_name)
            logger.info(f"Calling Gemini with model: {model_name} for Lore/Context")
            response = await model.generate_content_async(prompt)
            
            if response and response.text:
                return response.text.strip()
            return None
        except Exception as e:
            logger.error(f"Error calling Gemini: {e}")
            return None


    async def _generate_groq_reply(self, trigger: str, context: str, username: str, is_fallback=False):
        model_name = os.getenv("GROQ_MODEL" if not is_fallback else "GROQ_MODEL_FALLBACK", 
                               "llama-3.3-70b-versatile" if not is_fallback else "llama-3.1-8b-instant")
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
                return await self._generate_groq_reply(trigger, context, username, is_fallback=True)
            return await self._generate_gemini_reply(trigger, context, username)



