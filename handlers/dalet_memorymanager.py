import json
import os
import google.generativeai as genai
from datetime import datetime
from discord.ext import commands
import discord

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

        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {"servers": {}, "users": {}}

    # ----------------------------------------------------------------
    # 💾 Guardado y lectura
    # ----------------------------------------------------------------
    def save(self):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    # ----------------------------------------------------------------
    # 🧠 Guardar recuerdos
    # ----------------------------------------------------------------
    def add_message(self, guild_id, channel_id, user_id, content):
        now = datetime.utcnow().isoformat()
        server = self.data["servers"].setdefault(str(guild_id), {"channels": {}, "topics": []})
        channel = server["channels"].setdefault(str(channel_id), {"messages": []})
        channel["messages"].append({"user": user_id, "content": content, "timestamp": now})
        channel["messages"] = channel["messages"][-50:]  # últimos 50
        self.save()

    def add_user_memory(self, user_id, content, topic="general"):
        now = datetime.utcnow().isoformat()
        user_mem = self.data["users"].setdefault(str(user_id), [])
        user_mem.append({"topic": topic, "content": content, "timestamp": now})
        user_mem = user_mem[-20:]
        self.data["users"][str(user_id)] = user_mem
        self.save()

    # ----------------------------------------------------------------
    # 🔍 Relevancia
    # ----------------------------------------------------------------
    def _is_relevant(self, context, memory_text):
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
    # 📚 Recuperar contexto relevante
    # ----------------------------------------------------------------
    def get_relevant_context(self, guild_id, channel_id, user_id, current_message, check_user_memory=True):
        context = []

        # 1️⃣ Últimos mensajes del canal (siempre se incluyen)
        channel_data = (
            self.data.get("servers", {})
            .get(str(guild_id), {})
            .get("channels", {})
            .get(str(channel_id), {})
            .get("messages", [])
        )
        for msg in channel_data[-10:]:
            # Obtenemos el nombre del autor para un contexto más claro
            author = self.bot.get_user(msg['user'])
            author_name = author.name if author else "Usuario Desconocido"
            context.append(f"{author_name}: {msg['content']}")

        # 2️⃣ Memoria del usuario (SOLO si el interruptor está encendido)
        if check_user_memory:
            user_mem = self.data.get("users", {}).get(str(user_id), [])
            for mem in user_mem:
                if self._is_relevant(current_message, mem["content"]):
                    context.append(f"Recuerdo sobre {mem['topic']}: {mem['content']}")

        return "\n".join(context[-15:])
   

# ----------------------------------------------------------------
# 🔧 Configuración para extensión de Discord
# ----------------------------------------------------------------
async def setup(bot):
    # Aquí puedes pasar IDs de canales permitidos
    allowed_channels = [
        123456789012345678,  # ejemplo
        # agrega más IDs de canales aquí
    ]
    await bot.add_cog(MemoryManager(bot,allowed_channels=allowed_channels))
