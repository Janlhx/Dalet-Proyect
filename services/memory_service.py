from google import genai
from google.genai import types
import logging
import os

logger = logging.getLogger("dalet.services.memory")

class MemoryService:
    def __init__(self, user_repo, relevance_model="models/gemini-embedding-001"): 
        self.relevance_model = relevance_model
        self.repo = user_repo
        
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
        memory_section = []
        history_section = []

        # 1. Historial de chat
        try:
            chat_history = await self.repo.get_channel_messages(channel_id, 10)
            for record in reversed(chat_history):
                history_section.append(f"{record['username']}: {record['content']}")
        except Exception as e:
            logger.error(f"Error getting channel context: {e}")

        # 2. Recuerdos de usuario (Embeddings)
        if check_user_memory and self.client:
            try:
                memories_raw = await self.repo.get_all_user_memories(user_id)
                if memories_raw:
                    texts = [current_message] + [m['content'] for m in memories_raw]
                    
                    # Usar el nuevo SDK para embeddings
                    res = self.client.models.embed_content(
                        model=self.relevance_model,
                        contents=texts,
                        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
                    )
                    
                    embeddings = res.embeddings
                    vec_query = embeddings[0].values
                    
                    for i, memory in enumerate(memories_raw):
                        vec_memory = embeddings[i + 1].values
                        if self._calculate_similarity(vec_query, vec_memory) >= 0.70:
                            memory_section.append(f"- {memory['content']}")
            except Exception as e:
                logger.error(f"Error processing user memories: {e}")

        final_context = ""
        if memory_section:
            final_context += "DATOS RELEVANTES (MEMORIA):\n" + "\n".join(memory_section[:3]) + "\n\n"
        
        final_context += "HISTORIAL RECIENTE DEL CHAT:\n" + "\n".join(history_section)
        
        return final_context

    async def add_memory(self, user_id, user_name, content, topic="general"):
        return await self.repo.add_user_memory(user_id, user_name, content, topic)
