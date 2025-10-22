import json
import os
import google.generativeai as genai
from datetime import datetime
from discord.ext import commands
import discord

# --- AÑADIMOS EL CONECTOR DE BASE DE DATOS ---
import db_connector

MEMORY_FILE = "memoria_contextual.json"


class MemoryManager(commands.Cog):
    """
    Maneja la memoria contextual del bot (mensajes recientes, recuerdos de usuarios, contexto de servidores).
    Guarda mensajes en memoria local y permite recuperar contexto relevante para el NLP.
    """

    def __init__(self, bot, relevance_model="models/embedding-001", allowed_channels=None):
        self.bot = bot
        self.relevance_model = relevance_model
        self.allowed_channels = allowed_channels or []  # IDs de canales permitidos

        # --- MANTENEMOS ESTO ---
        # Aún necesitamos cargar el JSON para la función de "memoria de usuario"
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {"servers": {}, "users": {}}

    # ----------------------------------------------------------------
    # 💾 Guardado y lectura (Aún se necesita para 'add_user_memory')
    # ----------------------------------------------------------------
    def save(self):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    # ----------------------------------------------------------------
    # 🧠 Guardar recuerdos
    # ----------------------------------------------------------------
    
    # --- FUNCIÓN MODIFICADA ---
    # Ya no necesitamos que esta función guarde mensajes del canal,
    # 'dalet_chatlogger.py' ya lo hace en la base de datos.
    # La dejamos vacía para no romper nada, pero su lógica se ha ido.
    def add_message(self, guild_id, channel_id, user_id, content):
        pass # Esta función ahora es manejada automáticamente por ChatLogger y la BD

    # --- FUNCIÓN SIN CAMBIOS ---
    # Esta función maneja los "recuerdos" específicos del usuario,
    # que siguen viviendo en el JSON. La dejamos intacta.
    def add_user_memory(self, user_id, content, topic="general"):
        now = datetime.utcnow().isoformat()
        user_mem = self.data["users"].setdefault(str(user_id), [])
        user_mem.append({"topic": topic, "content": content, "timestamp": now})
        user_mem = user_mem[-20:]
        self.data["users"][str(user_id)] = user_mem
        self.save()

    # ----------------------------------------------------------------
    # 🔍 Relevancia (Sin cambios)
    # ----------------------------------------------------------------
    def _is_relevant(self, context, memory_text):
        # ... (Tu código de embeddings se mantiene intacto)
        try:
            embeddings = genai.embed_content(
                model=self.relevance_model,
                content=[context, memory_text]
            )
            if not embeddings or "embedding" not in embeddings:
                return False
            a, b = embeddings["embedding"][0], embeddings["embedding"][1]
            similarity = sum(x*y for x, y in zip(a, b)) / (
                (sum(x*x for x in a)**0.5) * (sum(y*y for y in b)**0.5)
            )
            return similarity >= 0.75
        except Exception as e:
            print("Error al evaluar relevancia:", e)
            return False

    # ----------------------------------------------------------------
    # 📚 Recuperar contexto relevante (¡AQUÍ ESTÁ EL CAMBIO!)
    # ----------------------------------------------------------------
    def get_relevant_context(self, guild_id, channel_id, user_id, current_message, check_user_memory=True):
        context = []

        # ======================================================================
        # ▼▼▼ PARTE 1: MODIFICADA PARA USAR LA BASE DE DATOS ▼▼▼
        # ======================================================================
        # 1️⃣ Últimos mensajes del canal (desde la Base de Datos)
        try:
            # Obtenemos los últimos 10 mensajes del canal
            query = """
                SELECT u.UserName, m.Content
                FROM Messages m
                JOIN Users u ON m.UserID = u.UserID
                WHERE m.ChannelID = %s
                ORDER BY m.Timestamp DESC
                LIMIT 20
            """
            registros = db_connector.fetch_all(query, (channel_id,))
            
            # Los invertimos para que estén en orden cronológico
            registros.reverse() 
            
            for autor, contenido in registros:
                context.append(f"{autor}: {contenido}")
                
        except Exception as e:
            print(f"Error al obtener contexto del canal desde la BD: {e}")
        # ======================================================================
        # ▲▲▲ FIN DE LA PARTE MODIFICADA ▲▲▲
        # ======================================================================


        # ======================================================================
        # ▼▼▼ PARTE 2: SIN CAMBIOS (Usa el JSON para memoria de usuario) ▼▼▼
        # ======================================================================
        # 2️⃣ Memoria del usuario (SOLO si el interruptor está encendido)
        if check_user_memory:
            user_mem = self.data.get("users", {}).get(str(user_id), [])
            for mem in user_mem:
                if self._is_relevant(current_message, mem["content"]):
                    context.append(f"Recuerdo sobre {mem['topic']}: {mem['content']}")
        # ======================================================================
        # ▲▲▲ FIN DE LA PARTE SIN CAMBIOS ▲▲▲
        # ======================================================================

        return "\n".join(context[-25:])
    

# ----------------------------------------------------------------
# 🔧 Configuración para extensión de Discord (Sin cambios)
# ----------------------------------------------------------------
async def setup(bot):
    # Aquí puedes pasar IDs de canales permitidos
    allowed_channels = [
        # 123456789012345678,  # ejemplo
        # agrega más IDs de canales aquí
    ]
    await bot.add_cog(MemoryManager(bot, allowed_channels=allowed_channels))