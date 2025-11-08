"""
Handler (Cog) para la Gestión de Memoria Contextual.

Este Cog es el "cerebro" de la IA. Es responsable de dos tareas:
1. Guardar "recuerdos" específicos del usuario en la BD ('sp_AddUserMemory').
2. Construir el 'prompt' de contexto para la IA ('get_relevant_context')
   combinando el historial de chat reciente (de 'V_ChannelMessages')
   con los recuerdos relevantes del usuario (de 'fn_GetAllUserMemories').

La lógica de relevancia de recuerdos está optimizada para usar una
única llamada de API de embeddings por lote.
"""
import google.generativeai as genai
from datetime import datetime, timezone
from discord.ext import commands
import discord
import db_connector
import traceback

class MemoryManager(commands.Cog):
    """Maneja la memoria contextual y los recuerdos de usuario usando la base de datos."""

    def __init__(self, bot, relevance_model="models/embedding-001", allowed_channels=None):
        self.bot = bot
        self.relevance_model = relevance_model
        self.allowed_channels = allowed_channels or []

    async def add_user_memory(self, user_id: int, user_name: str, content: str, topic: str = "general"):
        """
        Guarda un recuerdo específico para un usuario en la base de datos.

        Llama al procedimiento 'sp_AddUserMemory', que también se encarga
        de registrar al usuario si no existe y de limitar la cantidad
        de recuerdos por usuario.
        """
        try:
            db_connector.execute_procedure(
                "sp_AddUserMemory",
                (user_id, user_name, content, topic)
            )
        except Exception as e:
            print(f"!!!!!! [MemoryManager] ERROR al guardar recuerdo para user {user_id}: {e}")
            traceback.print_exc()

    def _calculate_similarity(self, vec_a, vec_b):
        """
        Calcula la similitud coseno entre dos vectores de embedding.
        Función auxiliar interna.
        """
        try:
            dot_product = sum(x * y for x, y in zip(vec_a, vec_b))
            norm_a = sum(x * x for x in vec_a) ** 0.5
            norm_b = sum(y * y for y in vec_b) ** 0.5
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot_product / (norm_a * norm_b)
        except Exception as e:
            print(f"!!!!!! [MemoryManager] ERROR en _calculate_similarity: {e}")
            return 0.0

    def get_relevant_context(self, guild_id: int, channel_id: int, user_id: int, current_message: str, check_user_memory: bool = True):
        """
        Construye el prompt de contexto completo para la IA.

        Esta función optimizada realiza 3 pasos:
        1. Obtiene el historial de chat reciente de 'V_ChannelMessages' (1 llamada a BD).
        2. Obtiene TODOS los recuerdos del usuario de 'fn_GetAllUserMemories' (1 llamada a BD).
        3. Realiza UNA llamada a la API de embeddings con el mensaje actual + todos
           los recuerdos para calcular la relevancia de forma eficiente.
        """
        context_lines = []

        # 1. Obtener historial de chat reciente (Usando la Vista)
        try:
            query = """
                SELECT UserName, Content
                FROM V_ChannelMessages
                WHERE ChannelID = %s
                ORDER BY Timestamp DESC
                LIMIT 10
            """
            registros_canal = db_connector.fetch_all(query, (channel_id,))
            registros_canal.reverse()
            for autor, contenido in registros_canal:
                context_lines.append(f"{autor}: {contenido}")
        except Exception as e:
            print(f"!!!!!! [MemoryManager] ERROR al obtener contexto del canal desde BD: {e}")
            traceback.print_exc()

        # 2. Obtener recuerdos de usuario relevantes (Lógica Optimizada)
        if check_user_memory:
            relevant_user_memories = []
            try:
                # Obtener TODOS los recuerdos del usuario (1 llamada a BD)
                query_mem = "SELECT topic, content FROM fn_GetAllUserMemories(%s)"
                user_memories_raw = db_connector.fetch_all(query_mem, (user_id,))

                if user_memories_raw:
                    # Preparar el lote para la API de Embeddings
                    content_list_for_api = [current_message]
                    content_list_for_api.extend([content for topic, content in user_memories_raw])
                    
                    # Realizar UNA sola llamada a la API para todos los textos
                    embeddings = genai.embed_content(
                        model=self.relevance_model,
                        content=content_list_for_api,
                        task_type="RETRIEVAL_QUERY"
                    )
                    
                    vec_query = embeddings['embedding'][0] # Vector del mensaje actual
                    
                    # Comparar localmente (muy rápido)
                    for i, (topic, content) in enumerate(user_memories_raw):
                        vec_memory = embeddings['embedding'][i + 1] # Vector del recuerdo
                        similarity = self._calculate_similarity(vec_query, vec_memory)
                        
                        # Umbral de relevancia
                        if similarity >= 0.65:
                            relevant_user_memories.append(f"Recuerdo sobre {topic}: {content}")

                # Añadir recuerdos relevantes al principio del contexto
                context_lines = relevant_user_memories + context_lines

            except Exception as e:
                print(f"!!!!!! [MemoryManager] ERROR al obtener/procesar recuerdos de usuario: {e}")
                traceback.print_exc()

        # Devolver las últimas 30 líneas combinadas
        return "\n".join(context_lines[-30:])


async def setup(bot):
    """Función 'setup' para cargar el Cog."""
    await bot.add_cog(MemoryManager(bot))