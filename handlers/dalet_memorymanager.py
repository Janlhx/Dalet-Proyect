import google.generativeai as genai
from datetime import datetime, timezone
from discord.ext import commands
import discord
import db_connector
import traceback

class MemoryManager(commands.Cog):
    """
    Maneja la memoria contextual y los recuerdos de usuario usando la base de datos.
    """

    def __init__(self, bot, relevance_model="models/embedding-001", allowed_channels=None):
        self.bot = bot
        self.relevance_model = relevance_model
        self.allowed_channels = allowed_channels or []

    async def add_user_memory(self, user_id: int, user_name: str, content: str, topic: str = "general"):
        """Guarda un recuerdo específico para un usuario en la base de datos."""
        print(f"--- [Memory DEBUG] Guardando recuerdo para user {user_id}: '{content}' (topic: {topic})")
        try:
            db_connector.execute_procedure(
                "sp_AddUserMemory",
                (user_id, user_name, content, topic)
            )
            print(f"--- [Memory DEBUG] Recuerdo guardado exitosamente.")
        except Exception as e:
            print(f"!!!!!! [Memory DEBUG] ERROR al guardar recuerdo para user {user_id}: {e}")
            traceback.print_exc()

    def _calculate_similarity(self, vec_a, vec_b):
        """Calcula la similitud coseno entre dos vectores de embedding."""
        try:
            dot_product = sum(x * y for x, y in zip(vec_a, vec_b))
            norm_a = sum(x * x for x in vec_a) ** 0.5
            norm_b = sum(y * y for y in vec_b) ** 0.5
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot_product / (norm_a * norm_b)
        except Exception as e:
            print(f"!!!!!! [Memory DEBUG] ERROR en _calculate_similarity: {e}")
            return 0.0

    # ==========================================================
    # ▼▼▼ FUNCIÓN get_relevant_context MODIFICADA (¡AQUÍ ESTÁ LA MAGIA!) ▼▼▼
    # ==========================================================
    def get_relevant_context(self, guild_id: int, channel_id: int, user_id: int, current_message: str, check_user_memory: bool = True):
        """
        Obtiene contexto del canal (BD) y recuerdos relevantes del usuario (BD + 1 sola llamada de API).
        """
        print(f"\n--- [Memory DEBUG] Obteniendo contexto para user {user_id} en canal {channel_id}...")
        context_lines = []

        # 1️⃣ Últimos mensajes del canal (desde la Base de Datos)
        try:
            query = """
                SELECT UserName, Content
                FROM V_ChannelMessages
                WHERE ChannelID = %s
                ORDER BY Timestamp DESC
                LIMIT 20
            """
            registros_canal = db_connector.fetch_all(query, (channel_id,))
            registros_canal.reverse()
            print(f"--- [Memory DEBUG] {len(registros_canal)} mensajes de canal obtenidos de BD.")
            for autor, contenido in registros_canal:
                context_lines.append(f"{autor}: {contenido}")
        except Exception as e:
            print(f"!!!!!! [Memory DEBUG] ERROR al obtener contexto del canal desde BD: {e}")
            traceback.print_exc()

        # 2️⃣ Memoria relevante del usuario (MODIFICADO para 1 sola llamada)
        if check_user_memory:
            print(f"--- [Memory DEBUG] Buscando recuerdos relevantes para user {user_id}...")
            relevant_user_memories = []
            try:
                # Obtenemos TODOS los recuerdos del usuario desde la BD
                query_mem = "SELECT topic, content FROM fn_GetAllUserMemories(%s)"
                user_memories_raw = db_connector.fetch_all(query_mem, (user_id,))
                print(f"--- [Memory DEBUG] {len(user_memories_raw)} recuerdos totales obtenidos de BD.")

                if user_memories_raw:
                    # Preparamos el lote para la API
                    content_list_for_api = [current_message]
                    for topic, content in user_memories_raw:
                        content_list_for_api.append(content)
                    
                    print(f"--- [Memory DEBUG] Enviando lote de {len(content_list_for_api)} textos a la API de embeddings...")
                    # ¡Hacemos UNA SOLA llamada a la API!
                    embeddings = genai.embed_content(
                        model=self.relevance_model,
                        content=content_list_for_api,
                        task_type="RETRIEVAL_QUERY"
                    )
                    
                    vec_query = embeddings['embedding'][0] # El vector del mensaje actual
                    
                    # Comparamos los resultados en Python (esto es ultra rápido)
                    for i, (topic, content) in enumerate(user_memories_raw):
                        vec_memory = embeddings['embedding'][i + 1] # El vector del recuerdo
                        similarity = self._calculate_similarity(vec_query, vec_memory)
                        
                        if similarity >= 0.75:
                            print(f"--- [Memory DEBUG] Recuerdo relevante encontrado (Similitud: {similarity:.2f})")
                            relevant_user_memories.append(f"Recuerdo sobre {topic}: {content}")

                print(f"--- [Memory DEBUG] {len(relevant_user_memories)} recuerdos relevantes encontrados.")
                context_lines = relevant_user_memories + context_lines

            except Exception as e:
                print(f"!!!!!! [Memory DEBUG] ERROR al obtener/procesar recuerdos de usuario: {e}")
                traceback.print_exc()

        final_context = "\n".join(context_lines[-30:])
        print(f"--- [Memory DEBUG] Contexto final generado (longitud): {len(final_context)} chars")
        print("--- [Memory DEBUG] --- Fin get_relevant_context ---\n")
        return final_context

async def setup(bot):
    await bot.add_cog(MemoryManager(bot))