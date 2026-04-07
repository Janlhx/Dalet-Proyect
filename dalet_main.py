import asyncio
from discord.ext import commands
import os
import discord
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import sys
import logging
import signal
from database.pool import DatabasePool
from database.sqlite_manager import SQLiteManager

# --- Configuración de Logging ---
file_handler = logging.FileHandler("dalet.log", encoding='utf-8')
stream_handler = logging.StreamHandler(sys.stdout)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[stream_handler, file_handler]
)
logger = logging.getLogger("dalet.main")

# --- Carga de Configuración ---
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Servidor Web (Health Check para Render) ---
app = Flask('')


@app.route('/')
def home():
    return "dalet está viva."


def run_flask():
    try:
        app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Error iniciando Flask: {e}")
        os._exit(1)


def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()


# --- Carga de Extensiones (Cogs) ---
async def load_extensions(bot):
    logger.info("<<< INICIANDO CARGA DE MÓDULOS >>>")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    handlers_path = os.path.join(script_dir, "handlers")

    if not os.path.exists(handlers_path):
        logger.error("ERROR GRAVE: La carpeta 'handlers' no existe.")
        return

    for filename in os.listdir(handlers_path):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = f"handlers.{filename[:-3]}"
            try:
                await bot.load_extension(module_name)
                logger.info(f"[OK] Cargado: {module_name}")
            except Exception as e:
                logger.error(f"[ERROR] Fallo cargando {module_name}: {e}")


# --- Punto de Entrada Principal ---
async def main():
    # Abrir Flask primero (Render necesita ver el puerto)
    keep_alive()
    logger.info("Health Check iniciado en puerto 8080.")

    retry_count = 0
    while True:
        try:
            # Intentar conectar a Neon (sin bloquear si no está disponible)
            await DatabasePool.get_pool()

            from database.repositories.user_repository import UserRepository
            from database.repositories.osu_repository import OsuRepository
            from database.repositories.admin_repository import AdminRepository
            from database.repositories.analytics_repository import AnalyticsRepository
            from services.nlp_service import NLPService
            from services.memory_service import MemoryService
            from services.osu_service import OsuService

            bot = commands.Bot(
                command_prefix=["D.", "d."],
                intents=discord.Intents.all(),
                case_insensitive=True
            )

            # Contadores globales de rate limit
            bot.global_error_cooldown = 0
            bot.global_consecutive_429s = 0

            # Inyección de dependencias
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

            # Tarea de purga de mensajes expirados (Postgres, cada hora)
            async def _purge_expired_messages():
                while True:
                    await asyncio.sleep(3600)
                    try:
                        pool = await DatabasePool.get_pool()
                        if pool:
                            async with pool.acquire() as conn:
                                await conn.execute("SELECT fn_PurgeExpiredMessages()")
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.debug(f"Purge task skipped: {e}")

            purge_task = asyncio.create_task(_purge_expired_messages())
            flush_task = asyncio.create_task(bot.user_repo._periodic_flush())

            # Check global: bloqueo de canales
            @bot.check
            async def global_block_check(ctx):
                allowed = ["unlock", "cs", "channelstatus", "status"]
                if ctx.command and ctx.command.name in allowed:
                    return True

                if not DatabasePool.is_available():
                    return True  # Sin BD, permitir todo

                try:
                    return not await bot.admin_repo.is_channel_locked(ctx.channel.id)
                except Exception:
                    return True

            # --- Manejo de Cierre Elegante ---
            stop_event = asyncio.Event()

            def signal_handler():
                logger.info("Señal de apagado recibida.")
                stop_event.set()

            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    asyncio.get_event_loop().add_signal_handler(sig, signal_handler)
                except NotImplementedError:
                    pass  # Windows no soporta add_signal_handler plenamente

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

                # Flush final del buffer de logs antes de cerrar
                await bot.user_repo.flush_logs()
                await SQLiteManager.close()
                break  # Fin normal

        except discord.HTTPException as e:
            try:
                if 'bot' in locals() and not bot.is_closed():
                    await bot.close()
            except Exception:
                pass

            if e.status == 429:
                retry_count += 1
                wait = min(60 * retry_count, 300)
                logger.error(f"Rate Limit 429. Reintentando en {wait}s (intento {retry_count})...")
                await asyncio.sleep(wait)
            else:
                logger.error(f"Error de Discord HTTP: {e}")
                break

        except Exception as e:
            logger.error(f"Error inesperado: {e}", exc_info=True)
            await asyncio.sleep(10)
            retry_count += 1
            if retry_count > 5:
                logger.critical("Demasiados errores consecutivos. Deteniendo.")
                break

        finally:
            logger.info("Cerrando pools de base de datos...")
            await DatabasePool.close()
            await SQLiteManager.close()
            logger.info("Apagado completo.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
