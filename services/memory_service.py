import google.generativeai as genai
import logging
from database.repositories.user_repository import UserRepository

logger = logging.getLogger("dalet.services.memory")

class MemoryService:
    def __init__(self, user_repo, relevance_model="models/gemini-embedding-001"):


        self.relevance_model = relevance_model
        self.repo = user_repo

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
        context_lines = []

        # 1. Historial de chat (10 mensajes para mejor contexto)
        try:
            chat_history = await self.repo.get_channel_messages(channel_id, 10)
            for record in reversed(chat_history):
                context_lines.append(f"{record['username']}: {record['content']}")
        except Exception as e:
            logger.error(f"Error getting channel context: {e}")

        # 2. Recuerdos de usuario (Embeddings) - Solo los 3 más relevantes
        if check_user_memory:
            try:
                memories_raw = await self.repo.get_all_user_memories(user_id)
                if memories_raw:
                    texts = [current_message] + [m['content'] for m in memories_raw]
                    embeddings = genai.embed_content(
                        model=self.relevance_model,
                        content=texts,
                        task_type="retrieval_query"
                    )
                    
                    vec_query = embeddings['embedding'][0]
                    relevant_memories = []
                    for i, memory in enumerate(memories_raw):
                        vec_memory = embeddings['embedding'][i + 1]
                        if self._calculate_similarity(vec_query, vec_memory) >= 0.60: # Más generoso (antes 0.75)
                            relevant_memories.append(f"Dato: {memory['content']}")
                    
                    # Inyectar solo 2 recuerdos para evitar saturar de "spam" el cerebro
                    context_lines = relevant_memories[:2] + context_lines
            except Exception as e:
                logger.error(f"Error processing user memories: {e}")

        return "\n".join(context_lines)

    async def add_memory(self, user_id, user_name, content, topic="general"):
        return await self.repo.add_user_memory(user_id, user_name, content, topic)
