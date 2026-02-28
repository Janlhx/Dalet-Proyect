"""
Punto de Entrada Principal del Bot Dalet.

Este archivo es responsable de:
1. Cargar las variables de entorno (API keys).
2. Configurar el bot de Discord (Intents, Prefijo).
3. Iniciar el servidor web Flask (para el health check de Render).
4. Cargar dinámicamente todas las extensiones (Cogs) desde la carpeta /handlers.
5. Iniciar la conexión del bot con Discord.
"""
import asyncio
from discord.ext import commands
import os
import discord
from dotenv import load_dotenv
from google import genai
from flask import Flask
from threading import Thread
import sys
import logging
from database.pool import DatabasePool

# --- Configuración de Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("dalet.log")
    ]
)
logger = logging.getLogger("dalet.main")

# --- 1. Carga de Configuración ---
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- 2. Configuración del Bot ---
bot = commands.Bot(command_prefix=["D.","d."], intents=discord.Intents.all(), case_insensitive=True)

# --- 3. Servidor Web (Health Check para Render) ---
app = Flask('')

@app.route('/')
def home():
    return "El bot está vivo."

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 4. Carga de Extensiones (Cogs) ---
async def load_extensions():
    logger.info("<<<<< INICIANDO CARGA DE MÓDULOS... >>>>>")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    handlers_path = os.path.join(script_dir, "handlers")

    if not os.path.exists(handlers_path):
        logger.error("!!!!!! ERROR GRAVE: La carpeta 'handlers' no se encontró.")
        return

    for filename in os.listdir(handlers_path):
        if filename.endswith(".py") and not filename.startswith("__") and filename != "db_connector.py":
            module_name = f"handlers.{filename[:-3]}"
            try:
                await bot.load_extension(module_name)
                logger.info(f"--- ✅ Cargado: {module_name}")
            except Exception as e:
                logger.error(f"!!!!!! ❌ ERROR FATAL AL CARGAR {module_name} !!!!!! | DETALLE: {e}")

# --- 5. Punto de Entrada Principal ---
async def main():
    try:
        # Inicializar el pool de base de datos
        await DatabasePool.get_pool()

        # --- Inyección de Dependencias ---
        from database.repositories.user_repository import UserRepository
        from database.repositories.osu_repository import OsuRepository
        from database.repositories.admin_repository import AdminRepository
        from services.nlp_service import NLPService
        from services.memory_service import MemoryService
        from services.osu_service import OsuService

        # Instanciar Repositorios
        bot.user_repo = UserRepository()
        bot.user_repo.start_flush_task(asyncio.get_event_loop())
        bot.osu_repo = OsuRepository()
        bot.admin_repo = AdminRepository()

        # Instanciar Servicios
        bot.nlp_service = NLPService(GEMINI_API_KEY, user_repo=bot.user_repo)
        bot.memory_service = MemoryService(bot.user_repo)
        bot.osu_service = OsuService(
            client_id=int(os.getenv("OSU_CLIENT_ID", 0)),
            client_secret=os.getenv("OSU_CLIENT_SECRET", "")
        )
        
        # --- Middleware de Seguridad (Global Check) ---
        @bot.check
        async def global_block_check(ctx):
            # 1. Comandos de administrador para gestión de canales siempre permitidos
            allowed_commands = ["unlock", "cs", "channelstatus"]
            if ctx.command and ctx.command.name in allowed_commands:
                return True
            
            # 2. Otros comandos están sujetos al candado de la DB
            is_locked = await bot.admin_repo.is_channel_locked(ctx.channel.id)
            if is_locked:
                return False
            
            return True

        async with bot:
            await load_extensions()
            await bot.start(DISCORD_TOKEN)
    except Exception as e:
        logger.critical(f"Error crítico en el bucle principal: {e}")
    finally:
        await DatabasePool.close()

if __name__ == "__main__":
    keep_alive()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot desconectado manualmente.")

