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
        self._local_history = {}  # {channel_id: deque([msg1, msg2, ...])}
        self.max_local_history = 15   # Mensajes en RAM por canal
        self.max_db_history = 10      # Mensajes de BD (menos tokens sin perder contexto)

    async def get_relevant_context(self, channel_id: int, user_id: int, current_message: str, check_user_memory: bool = True):
        """
        Construye el contexto de conversación combinando:
        1. Historial reciente del canal (BD + local RAM)
        2. Memorias relevantes del usuario (búsqueda simple por texto, sin embeddings)
        """
        history_section = []
        
        # 1. Historial de BD (más antiguo)
        try:
            db_history = await self.repo.get_channel_messages(channel_id, self.max_db_history)
            if db_history:
                for record in reversed(db_history):
                    history_section.append(f"{record['username']}: {record['content']}")
        except Exception as e:
            logger.error(f"Error obteniendo historial de BD: {e}")

        # 2. Historial local en RAM (más reciente, sin duplicados)
        if channel_id in self._local_history:
            for msg in list(self._local_history[channel_id]):
                if msg not in history_section:
                    history_section.append(msg)
        
        # Recortar al máximo configurado
        history_section = history_section[-self.max_local_history:]

        # 3. Memorias de usuario — búsqueda simple por palabras clave (SIN embeddings/API)
        memory_section = []
        if check_user_memory:
            try:
                memories_raw = await self.repo.get_all_user_memories(user_id)
                if memories_raw:
                    # Filtro simple: incluir memorias que tengan palabras del mensaje actual
                    msg_words = set(current_message.lower().split())
                    for m in memories_raw[:10]:  # Máximo 10 memorias a revisar
                        content = m.get('content', '')
                        # Si hay alguna palabra en común, incluir la memoria
                        memory_words = set(content.lower().split())
                        # Incluir si hay coincidencia o si las memorias son pocas
                        if memory_words & msg_words or len(memories_raw) <= 3:
                            memory_section.append(f"Recuerdo sobre este usuario: {content}")
                    
                    # Si no hay coincidencias, incluir las últimas 2 memorias de todas formas
                    if not memory_section and memories_raw:
                        for m in memories_raw[-2:]:
                            memory_section.append(f"Dato del usuario: {m.get('content', '')}")
            except Exception as e:
                logger.error(f"Error obteniendo memorias: {e}")

        # Construir contexto final
        final_context = ""
        if memory_section:
            final_context += "DATOS SOBRE QUIEN TE HABLA:\n" + "\n".join(memory_section[:3]) + "\n\n"
        
        if history_section:
            final_context += "CHAT RECIENTE:\n" + "\n".join(history_section)
        
        return final_context if final_context.strip() else "Sin historial previo."

    async def add_memory(self, user_id, user_name, content, topic="general"):
        """Guarda una memoria sobre el usuario en la BD."""
        return await self.repo.add_user_memory(user_id, user_name, content, topic)

    def add_to_local_history(self, channel_id, username, content):
        """Guarda un mensaje en el buffer local (RAM) para contexto inmediato."""
        if channel_id not in self._local_history:
            self._local_history[channel_id] = deque(maxlen=self.max_local_history)
        self._local_history[channel_id].append(f"{username}: {content}")
