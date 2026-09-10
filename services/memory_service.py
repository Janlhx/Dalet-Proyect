import logging
import os
from collections import deque

logger = logging.getLogger("dalet.services.memory")

class MemoryService:
    """
    Servicio de memoria que combina historial local (RAM) con historial de BD.
    Sin llamadas a APIs de embeddings — para no gastar cuota de Gemini.
    """
    def __init__(self, user_repo):
        self.repo = user_repo
        self.max_db_history = 6  # Ventana optimizada de 6 mensajes (ahorro masivo de tokens)

    async def get_relevant_context(self, channel_id: int, user_id: int, current_message: str, check_user_memory: bool = True):
        """
        Construye el contexto de conversación optimizado combinando:
        1. Historial reciente del canal (BD + local RAM, ventana adaptativa)
        2. Memorias relevantes del usuario (máx 2 datos clave)
        """
        history_section = []
        
        # Ajustar límite de mensajes según longitud del mensaje actual
        msg_len = len(current_message.split())
        history_limit = 4 if msg_len <= 3 else self.max_db_history

        # 1. Historial Unificado (BD + Buffer, que ahora incluye a Dalet)
        try:
            db_history = await self.repo.get_channel_messages(channel_id, history_limit)
            if db_history:
                for record in reversed(db_history):
                    usr = record.get('username') or record.get('UserName') or 'Desconocido'
                    cnt = record.get('content') or record.get('Content') or ''
                    if cnt.strip():
                        history_section.append(f"{usr}: {cnt}")
        except Exception as e:
            logger.error(f"Error obteniendo historial: {e}")

        # 2. Memorias de usuario — búsqueda simple por palabras clave (SIN embeddings/API)
        memory_section = []
        if check_user_memory:
            try:
                memories_raw = await self.repo.get_all_user_memories(user_id)
                if memories_raw:
                    msg_words = set(current_message.lower().split())
                    for m in memories_raw[:6]:
                        content = m.get('content', '')
                        memory_words = set(content.lower().split())
                        if memory_words & msg_words:
                            memory_section.append(f"Dato usuario: {content}")
                            if len(memory_section) >= 2:
                                break
                    
                    # Fallback a 1 memoria reciente si no hubo match
                    if not memory_section and memories_raw:
                        memory_section.append(f"Dato usuario: {memories_raw[-1].get('content', '')}")
            except Exception as e:
                logger.error(f"Error obteniendo memorias: {e}")

        # Construir contexto final compacto
        final_context = ""
        if memory_section:
            final_context += "INFO USUARIO:\n" + "\n".join(memory_section[:2]) + "\n\n"
        
        if history_section:
            final_context += "CHAT RECIENTE:\n" + "\n".join(history_section)
        
        return final_context if final_context.strip() else "Sin historial previo."

    async def add_memory(self, user_id, user_name, content, topic="general"):
        """Guarda una memoria sobre el usuario en la BD."""
        return await self.repo.add_user_memory(user_id, user_name, content, topic)
