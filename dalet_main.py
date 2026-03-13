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
import signal
import socket
from database.pool import DatabasePool

# --- Configuración de Logging ---
file_handler = logging.FileHandler("dalet.log", encoding='utf-8')
stream_handler = logging.StreamHandler(sys.stdout)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[stream_handler, file_handler]
)
logger = logging.getLogger("dalet.main")

# --- 0. Seguro Anti-Duplicados (Puerto de Bloqueo) ---
# Intentamos abrir un socket en el puerto de Flask. Si falla, es que ya hay otro bot corriendo.
def check_single_instance(port=8080):
    try:
        s = socket.socket(socket.getaddrinfo('0.0.0.0', port)[0][0], socket.SOCK_STREAM)
        s.bind(('0.0.0.0', port))
        return s # Retornamos el socket para mantenerlo abierto
    except socket.error:
        logger.error(f"!!!!!! ERROR: Puerto {port} ocupado. ¿Ya hay otra Dalet corriendo?")
        sys.exit(1)

# --- 1. Carga de Configuración ---
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- 2. Servidor Web (Health Check para Render) ---
app = Flask('')

@app.route('/')
def home():
    return "El bot está vivo."

def run_flask():
    # En producción/local usamos el puerto 8080
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()

# --- 3. Carga de Extensiones (Cogs) ---
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
                logger.info(f"--- [OK] Cargado: {module_name}")
            except Exception as e:
                logger.error(f"!!!!!! [ERROR] FATAL AL CARGAR {module_name} !!!!!! | DETALLE: {e}")

# --- 4. Punto de Entrada Principal ---
async def main():
    # El socket lock solo se activa si NO estamos en un entorno de re-ejecución (prevención local)
    # En Render, esto nos asegura que el health check solo lo tenga el proceso activo.
    _lock_socket = check_single_instance()

    retry_count = 0
    while True:
        try:
            # Inicializar el pool de base de datos UNA VEZ
            await DatabasePool.get_pool()

            from database.repositories.user_repository import UserRepository
            from database.repositories.osu_repository import OsuRepository
            from database.repositories.admin_repository import AdminRepository
            from database.repositories.analytics_repository import AnalyticsRepository
            from services.nlp_service import NLPService
            from services.memory_service import MemoryService
            from services.osu_service import OsuService

            bot = commands.Bot(command_prefix=["D.","d."], intents=discord.Intents.all(), case_insensitive=True)
            
            # Inyectar Repositorios y Servicios
            bot.user_repo = UserRepository()
            bot.osu_repo = OsuRepository()
            bot.admin_repo = AdminRepository()
            bot.analytics_repo = AnalyticsRepository()

            bot.nlp_service = NLPService(GEMINI_API_KEY, user_repo=bot.user_repo)
            bot.memory_service = MemoryService(bot.user_repo)
            bot.osu_service = OsuService(
                client_id=int(os.getenv("OSU_CLIENT_ID", 0)),
                client_secret=os.getenv("OSU_CLIENT_SECRET", "")
            )

            # Tareas de fondo
            async def _purge_expired_messages():
                while True:
                    await asyncio.sleep(3600)
                    try:
                        pool = await DatabasePool.get_pool()
                        async with pool.acquire() as conn:
                            await conn.fetchval("SELECT fn_PurgeExpiredMessages()")
                    except asyncio.CancelledError: break
                    except Exception: pass

            purge_task = asyncio.create_task(_purge_expired_messages())
            flush_task = asyncio.create_task(bot.user_repo._periodic_flush())

            @bot.check
            async def global_block_check(ctx):
                allowed = ["unlock", "cs", "channelstatus"]
                if ctx.command and ctx.command.name in allowed: return True
                return not await bot.admin_repo.is_channel_locked(ctx.channel.id)

            # --- Manejo de Cierre Elegante (SIGINT/SIGTERM) ---
            stop_event = asyncio.Event()

            def signal_handler():
                logger.info("Señal de apagado recibida...")
                stop_event.set()

            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    asyncio.get_event_loop().add_signal_handler(sig, signal_handler)
                except NotImplementedError:
                    pass

            async with bot:
                await load_extensions(bot)
                
                bot_task = asyncio.create_task(bot.start(DISCORD_TOKEN))
                stop_task = asyncio.create_task(stop_event.wait())
                
                done, pending = await asyncio.wait(
                    [bot_task, stop_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                if stop_event.is_set():
                    logger.info("Cerrando sesión de Discord...")
                    await bot.close()
                else:
                    stop_task.cancel()
                    if bot_task.exception():
                        raise bot_task.exception()
                
                purge_task.cancel()
                flush_task.cancel()
                await bot.user_repo.flush_logs()
                break # Salir del while si todo terminó bien

        except discord.HTTPException as e:
            if e.status == 429:
                retry_count += 1
                wait = min(60 * retry_count, 300) # Máximo 5 minutos
                logger.error(f"Rate Limit Detectado (429/1015). Reintentando en {wait}s... (Intento {retry_count})")
                await asyncio.sleep(wait)
            else:
                logger.error(f"Error de Discord: {e}")
                break
            except Exception as e:
                logger.error(f"Error inesperado: {e}", exc_info=True)
                await asyncio.sleep(10)
                retry_count += 1
                if retry_count > 5: break
        finally:
            logger.info("Cerrando pool de base de datos...")
            await DatabasePool.close()
            if '_lock_socket' in locals():
                _lock_socket.close()
            logger.info("Apagado completo.")

if __name__ == "__main__":
    # Nota: No llamamos a keep_alive aquí porque Flask ocupará el puerto
    # que check_single_instance ya está validando. Usaremos el Thread de Flask
    # dentro de main o lo dejaremos que corra solo si el puerto está libre.
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

