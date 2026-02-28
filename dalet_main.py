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

# --- 2. Configuración (El bot se crea dentro de main para mayor resiliencia) ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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
async def load_extensions(bot):
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
        while True:
            # Crear una instancia NUEVA del bot en cada intento
            bot = commands.Bot(command_prefix=["D.","d."], intents=discord.Intents.all(), case_insensitive=True)
            
            # Instanciar Repositorios para este bot
            bot.user_repo = UserRepository()
            bot.user_repo.start_flush_task(asyncio.get_event_loop())
            bot.osu_repo = OsuRepository()
            bot.admin_repo = AdminRepository()

            # Instanciar Servicios para este bot
            bot.nlp_service = NLPService(GEMINI_API_KEY, user_repo=bot.user_repo)
            bot.memory_service = MemoryService(bot.user_repo)
            bot.osu_service = OsuService(
                client_id=int(os.getenv("OSU_CLIENT_ID", 0)),
                client_secret=os.getenv("OSU_CLIENT_SECRET", "")
            )
            
            # Re-aplicar el Middleware de Seguridad
            @bot.check
            async def global_block_check(ctx):
                allowed_commands = ["unlock", "cs", "channelstatus"]
                if ctx.command and ctx.command.name in allowed_commands:
                    return True
                is_locked = await bot.admin_repo.is_channel_locked(ctx.channel.id)
                return not is_locked

            try:
                async with bot:
                    await load_extensions(bot)
                    await bot.start(DISCORD_TOKEN)
            except discord.HTTPException as e:
                if e.status == 429:
                    wait_time = 60 # Esperar 1 minuto base ante 429 en el inicio
                    logger.error(f"Rate limited (429) en el inicio. Reintentando en {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise e
            except Exception as e:
                wait_error = 10
                logger.error(f"Error no esperado en el inicio: {e}. Reintentando en {wait_error}s...")
                await asyncio.sleep(wait_error)
    finally:
        await DatabasePool.close()

if __name__ == "__main__":
    keep_alive()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot desconectado manualmente.")

