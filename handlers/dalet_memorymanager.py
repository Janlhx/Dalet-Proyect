# Quitamos json y os, ya no los necesitamos para esto
import google.generativeai as genai
from datetime import datetime, timezone # Asegurar timezone
from discord.ext import commands
import discord

# Importamos el conector
import db_connector
import traceback # Para errores

# --- 🗑️ SECCIÓN ELIMINADA 🗑️ ---
# Ya no necesitamos MEMORY_FILE para la lógica principal
# MEMORY_FILE = "memoria_contextual.json"
# --- FIN DE LA SECCIÓN ELIMINADA ---


class MemoryManager(commands.Cog):
    """
    Maneja la memoria contextual y los recuerdos de usuario usando la base de datos.
    """

    def __init__(self, bot, relevance_model="models/embedding-001", allowed_channels=None):
        self.bot = bot
        self.relevance_model = relevance_model
        self.allowed_channels = allowed_channels or []

        # --- 🗑️ ELIMINADO ---
        # Ya no cargamos el JSON al iniciar
        # self.data = ...
        # --- FIN ---

    # --- 🗑️ ELIMINADO ---
    # La función save ya no es necesaria
    # def save(self): ...
    # --- FIN ---

    # --- 🗑️😊Holanda ELIMINADO ---
    # La función add_message ya no hace nada aquí
    # def add_message(...): pass
    # --- FIN ---


    # Ahora es async para poder obtener el nombre de usuario
    async def add_user_memory(self, user_id: int, user_name: str, content: str, topic: str = "general"):
        """Guarda un recuerdo específico para un usuario en la base de datos."""
        print(f"--- [Memory DEBUG] Guardando recuerdo para user {user_id}: '{content}' (topic: {topic})")
        try:
            db_connector.execute_procedure(
                "sp_AddUserMemory",
                (user_id, user_name, content, topic) # Pasamos los parámetros al procedimiento
                # El límite de 20 ya lo maneja el procedimiento SQL
            )
            print(f"--- [Memory DEBUG] Recuerdo guardado exitosamente.")
        except Exception as e:
            print(f"!!!!!! [Memory DEBUG] ERROR al guardar recuerdo para user {user_id}: {e}")
            traceback.print_exc()
            # Considerar notificar al usuario o reintentar


    # ----------------------------------------------------------------
    # 🔍 Relevancia (Sin cambios)
    # ----------------------------------------------------------------
    def _is_relevant(self, context_message: str, memory_text: str) -> bool:
        """Calcula la similitud de embeddings entre dos textos."""
        # print(f"--- [Memory DEBUG] Calculando relevancia: '{context_message[:50]}...' vs '{memory_text[:50]}...'")
        try:
            # Asegúrate que tu API Key de Gemini esté configurada
            embeddings = genai.embed_content(
                model=self.relevance_model,
                content=[context_message, memory_text],
                task_type="RETRIEVAL_QUERY" # Especificar tipo para mejor rendimiento
            )

            # Verificar estructura de respuesta de embeddings (puede variar)
            if not embeddings or 'embedding' not in embeddings or len(embeddings['embedding']) < 2:
                 print("!!!!!! [Memory DEBUG] ERROR: Respuesta de embeddings inesperada.")
                 return False

            vec_a = embeddings['embedding'][0]
            vec_b = embeddings['embedding'][1]

            # Calcular similitud coseno
            dot_product = sum(x*y for x, y in zip(vec_a, vec_b))
            norm_a = sum(x*x for x in vec_a)**0.5
            norm_b = sum(y*y for y in vec_b)**0.5

            if norm_a == 0 or norm_b == 0: return False # Evitar división por cero

            similarity = dot_product / (norm_a * norm_b)
            # print(f"--- [Memory DEBUG] Similitud calculada: {similarity:.4f}")
            # Ajustar umbral si es necesario
            is_rel = similarity >= 0.75
            # if is_rel: print("--- [Memory DEBUG] ¡Recuerdo RELEVANTE encontrado!")
            return is_rel
        except Exception as e:
            print(f"!!!!!! [Memory DEBUG] ERROR al calcular embeddings/relevancia: {e}")
            traceback.print_exc()
            return False

    def get_relevant_context(self, guild_id: int, channel_id: int, user_id: int, current_message: str, check_user_memory: bool = True):
        """
        Obtiene contexto del canal (BD) y recuerdos relevantes del usuario (BD + Python).
        """
        print(f"\n--- [Memory DEBUG] Obteniendo contexto para user {user_id} en canal {channel_id}...")
        context_lines = [] # Usaremos una lista para construir el contexto

        # 1️⃣ Últimos mensajes del canal (desde la Base de Datos)
        try:
            # REQUISITO 4: Usamos la VISTA en lugar de un JOIN
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

        # ======================================================================
        # ▼▼▼ PARTE 2: MODIFICADA PARA LEER RECUERDOS DESDE LA BD ▼▼▼
        # ======================================================================
        # 2️⃣ Memoria relevante del usuario (si está activado)
        if check_user_memory:
            print(f"--- [Memory DEBUG] Buscando recuerdos relevantes para user {user_id}...")
            relevant_user_memories = []
            try:
                # Obtenemos TODOS los recuerdos del usuario desde la BD
                query_mem = "SELECT topic, content FROM fn_GetAllUserMemories(%s)"
                user_memories_raw = db_connector.fetch_all(query_mem, (user_id,))
                print(f"--- [Memory DEBUG] {len(user_memories_raw)} recuerdos totales obtenidos de BD.")

                # Filtramos por relevancia en Python usando la función _is_relevant
                for topic, content in user_memories_raw:
                    if self._is_relevant(current_message, content):
                        relevant_user_memories.append(f"Recuerdo sobre {topic}: {content}")

                print(f"--- [Memory DEBUG] {len(relevant_user_memories)} recuerdos relevantes encontrados.")
                # Añadimos los recuerdos relevantes al principio del contexto
                context_lines = relevant_user_memories + context_lines

            except Exception as e:
                print(f"!!!!!! [Memory DEBUG] ERROR al obtener/procesar recuerdos de usuario: {e}")
                traceback.print_exc()
        # ======================================================================

        # Unimos las líneas y limitamos la longitud final (quizás a 25-30 líneas?)
        final_context = "\n".join(context_lines[-30:]) # Limitar a las últimas 30 líneas combinadas
        print(f"--- [Memory DEBUG] Contexto final generado (longitud): {len(final_context)} chars")
        print("--- [Memory DEBUG] --- Fin get_relevant_context ---\n")
        return final_context


# ----------------------------------------------------------------
# 🔧 Configuración para extensión de Discord (Sin cambios)
# ----------------------------------------------------------------
async def setup(bot):
    # Ya no pasamos allowed_channels aquí, la lógica de filtrado podría ir en on_message si es necesaria
    await bot.add_cog(MemoryManager(bot))