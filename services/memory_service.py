from google import genai
from google.genai import types
import logging
import os

logger = logging.getLogger("dalet.services.memory")

class MemoryService:
    def __init__(self, user_repo, relevance_model="models/gemini-embedding-001"): 
        self.relevance_model = relevance_model
        self.repo = user_repo
        self._local_history = {} # {channel_id: deque([msg1, msg2, ...])}
        from collections import deque
        self.history_class = deque
        self.history_class = deque
        self.max_local_history = 30 # Aumentamos el historial local
        self.max_db_history = 25    # Aumentamos el historial de DB
        self.similarity_threshold = 0.65 # Un poco más permisivo para no perder contexto
        
        # El cliente se inyectará desde nlp_service o se creará aquí si es necesario
        # Para ser consistente, usaremos la API KEY del .env
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = None
            logger.error("No Gemini API Key found for MemoryService")

    def _calculate_similarity(self, vec_a, vec_b):
        try:
            dot_product = sum(x * y for x, y in zip(vec_a, vec_b))
            norm_a = sum(x * x for x in vec_a) ** 0.5
            norm_b = sum(y * y for y in vec_b) ** 0.5
            if norm_a == 0 or norm_b == 0: return 0.0
            return dot_product / (norm_a * norm_b)
        except Exception as e:
            logger.error(f"Error in similarity calculation: {e}")
            return 0.0

    async def get_relevant_context(self, channel_id: int, user_id: int, current_message: str, check_user_memory: bool = True):
        # 1. Obtener Historial Extendido (Combinando DB y Memoria)
        history_section = []
        recent_users = set()
        recent_users.add(user_id) # Siempre incluimos al autor del mensaje actual
        
        try:
            db_history = await self.repo.get_channel_messages(channel_id, self.max_db_history)
            if db_history:
                for record in reversed(db_history):
                    history_section.append(f"{record['username']}: {record['content']}")
                    # Extraer usuarios recientes para saber de quién necesitamos memoria
                    # Nota: Aquí idealmente necesitaríamos el ID, pero usaremos el username para inferir si es necesario
                    # o simplemente confiar en que el repo nos de más adelante una forma de mapear.
                    # Por ahora, nos centramos en el user_id activo.
            
            if channel_id in self._local_history:
                for msg in list(self._local_history[channel_id]):
                    if msg not in history_section:
                        history_section.append(msg)
            
            history_section = history_section[-self.max_local_history:]
        except Exception as e:
            logger.error(f"Error getting history: {e}")

        # 2. Recuerdos de Usuario (Búsqueda por Relevancia / Embeddings)
        memory_section = []
        if check_user_memory and self.client:
            try:
                # Intentar obtener memorias para el usuario actual
                memories_raw = await self.repo.get_all_user_memories(user_id)
                if memories_raw:
                    # Preparar textos para embeddings
                    texts = [current_message] + [m['content'] for m in memories_raw]
                    
                    import asyncio
                    loop = asyncio.get_event_loop()
                    res = await loop.run_in_executor(
                        None,
                        lambda: self.client.models.embed_content(
                            model=self.relevance_model,
                            contents=texts,
                            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
                        )
                    )
                    
                    embeddings = res.embeddings
                    vec_query = embeddings[0].values
                    
                    for i, memory in enumerate(memories_raw):
                        vec_memory = embeddings[i + 1].values
                        if self._calculate_similarity(vec_query, vec_memory) >= self.similarity_threshold:
                            memory_section.append(f"Sobre este usuario: {memory['content']}")
                
                # En un grupo, también es útil tener "Hechos generales" o de otros participantes si hay pocos
                # Pero para no saturar, nos limitamos al autor por ahora o temas clave.
            except Exception as e:
                logger.error(f"Error processing memories: {e}")

        # Construir el prompt de contexto enriquecido
        final_context = "--- CONTEXTO DE CONVERSACIÓN EN GRUPO ---\n"
        if memory_section:
            final_context += "HECHOS RECORDADOS (MEMORIA):\n" + "\n".join(memory_section[:5]) + "\n\n"
        
        final_context += "HISTORIAL RECIENTE (Cronológico):\n" + "\n".join(history_section)
        
        return final_context

    async def add_memory(self, user_id, user_name, content, topic="general"):
        return await self.repo.add_user_memory(user_id, user_name, content, topic)

    def add_to_local_history(self, channel_id, username, content):
        """Guarda un mensaje en el buffer local (en memoria) para emergencias."""
        if channel_id not in self._local_history:
            self._local_history[channel_id] = self.history_class(maxlen=self.max_local_history)
        
        self._local_history[channel_id].append(f"{username}: {content}")
