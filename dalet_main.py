import asyncio
from discord.ext import commands
import os
import discord
from dotenv import load_dotenv
from flask import Flask, jsonify, Response, request
from functools import wraps
from threading import Thread
import sys
import logging
import signal
from database.turso_client import TursoClient
from database.sqlite_manager import SQLiteManager
from services.dashboard_service import DashboardService

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
DASHBOARD_SECRET = (os.getenv("DASHBOARD_SECRET") or "").strip()


def validate_environment() -> None:
    """Valida la presencia de credenciales críticas en el inicio (fail-fast)."""
    missing = []
    if not os.getenv("DISCORD_TOKEN"):
        missing.append("DISCORD_TOKEN")
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("OPENROUTER_API_KEY"):
        missing.append("GEMINI_API_KEY o OPENROUTER_API_KEY")

    if missing:
        logger.critical(f"[FAIL-FAST] No se puede iniciar Dalet. Variables críticas ausentes: {', '.join(missing)}")
        sys.exit(1)


def require_dashboard_auth(f):
    """
    Protege endpoints sensibles de telemetría y feedbacks.
    Permite acceso si:
    - DASHBOARD_SECRET no está configurado (modo desarrollo local).
    - Se envía cabecera 'Authorization: Bearer <secret>' o 'X-Dashboard-Secret: <secret>'.
    - Se envía query param '?key=<secret>'.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not DASHBOARD_SECRET:
            return f(*args, **kwargs)

        auth_header = request.headers.get("Authorization", "").strip()
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            if token == DASHBOARD_SECRET:
                return f(*args, **kwargs)

        custom_header = request.headers.get("X-Dashboard-Secret", "").strip()
        if custom_header == DASHBOARD_SECRET:
            return f(*args, **kwargs)

        query_key = request.args.get("key", "").strip()
        if query_key == DASHBOARD_SECRET:
            return f(*args, **kwargs)

        return jsonify({
            "error": "Unauthorized",
            "message": "Acceso restringido. Proporciona una clave válida vía header o parámetro '?key='."
        }), 401
    return decorated_function


# --- Servidor Web (Dashboard & Health Check) ---
app = Flask(__name__)

@app.route('/')
@app.route('/dashboard')
def home():
    """Sirve la interfaz web del Dashboard de telemetría."""
    return Response(DashboardService.get_dashboard_html(), mimetype='text/html')

@app.route('/api/telemetry')
@require_dashboard_auth
def api_telemetry():
    """Devuelve métricas en tiempo real en formato JSON."""
    return jsonify(DashboardService.get_full_telemetry())

@app.route('/api/feedbacks')
@require_dashboard_auth
def api_feedbacks():
    """Devuelve los feedbacks enviados por usuarios en formato JSON (thread-safe WAL)."""
    try:
        import sqlite3
        db_path = os.path.join(os.path.dirname(__file__), "dalet_local.db")
        if not os.path.exists(db_path):
            db_path = os.path.join(os.path.dirname(__file__), "data", "dalet_local.db")
        if not os.path.exists(db_path):
            return jsonify({"feedbacks": [], "total": 0})
        conn = sqlite3.connect(db_path, timeout=3.0)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT FeedbackID, UserID, UserName, UserAvatar, ServerID, ServerName, ChannelID, ChannelName, Content, CreatedAt
            FROM Feedbacks
            ORDER BY CreatedAt DESC
            LIMIT 50
        """)
        rows = cursor.fetchall()
        conn.close()
        feedbacks = []
        for r in rows:
            feedbacks.append({
                "id": r[0],
                "user_id": r[1],
                "user_name": r[2],
                "user_avatar": r[3] or "",
                "server_id": r[4],
                "server_name": r[5] or "Direct Message",
                "channel_id": r[6],
                "channel_name": r[7] or "DM",
                "content": r[8],
                "created_at": str(r[9])
            })
        return jsonify({"feedbacks": feedbacks, "total": len(feedbacks)})
    except Exception as e:
        logger.error(f"Error consultando feedbacks: {e}")
        return jsonify({"feedbacks": [], "total": 0, "error": str(e)})

@app.route('/health')
@app.route('/ping')
def health():
    """Health check simple para Render."""
    return "OK", 200

@app.route('/terms')
@app.route('/tos')
def terms():
    """Términos de servicio para verificación en Discord."""
    terms_path = os.path.join(os.path.dirname(__file__), "docs", "TERMS_OF_SERVICE.md")
    content = "Terms of Service"
    if os.path.exists(terms_path):
        with open(terms_path, "r", encoding="utf-8") as f:
            content = f.read()
    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>Terms of Service — Dalet</title>
<style>body{{font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #121214; color: #e4e4e7; line-height: 1.6; padding: 40px 20px; max-width: 800px; margin: 0 auto;}} pre{{white-space: pre-wrap; font-family: inherit;}} a{{color: #ff69b4;}}</style>
</head><body><pre>{content}</pre></body></html>"""
    return Response(html, mimetype='text/html')

@app.route('/privacy')
def privacy():
    """Política de privacidad para verificación en Discord."""
    privacy_path = os.path.join(os.path.dirname(__file__), "docs", "PRIVACY_POLICY.md")
    content = "Privacy Policy"
    if os.path.exists(privacy_path):
        with open(privacy_path, "r", encoding="utf-8") as f:
            content = f.read()
    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>Privacy Policy — Dalet</title>
<style>body{{font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #121214; color: #e4e4e7; line-height: 1.6; padding: 40px 20px; max-width: 800px; margin: 0 auto;}} pre{{white-space: pre-wrap; font-family: inherit;}} a{{color: #ff69b4;}}</style>
</head><body><pre>{content}</pre></body></html>"""
    return Response(html, mimetype='text/html')

def run_flask():
    try:
        port = int(os.getenv("PORT", 8080))
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
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
    # Validación fail-fast temprana antes de levantar servicios
    validate_environment()

    # Abrir Flask primero (Render necesita ver el puerto)
    keep_alive()
    logger.info("Health Check iniciado en puerto 8080.")

    retry_count = 0
    while True:
        try:
            # Inicializar Turso client
            TursoClient.get_client()

            from database.repositories.user_repository import UserRepository
            from database.repositories.osu_repository import OsuRepository
            from database.repositories.admin_repository import AdminRepository
            from database.repositories.analytics_repository import AnalyticsRepository
            from services.nlp_service import NLPService
            from services.memory_service import MemoryService
            from services.osu_service import OsuService

            # Gateway Intents optimizados: activamos solo lo necesario y omitimos 'presences'
            # para reducir drásticamente el consumo de RAM y tráfico de WebSocket innecesario
            intents = discord.Intents.default()
            intents.messages = True
            intents.message_content = True
            intents.guilds = True
            intents.members = True

            bot = commands.Bot(
                command_prefix=["D.", "d."],
                intents=intents,
                case_insensitive=True
            )

            # Contadores globales de rate limit
            bot.global_error_cooldown = 0
            bot.global_consecutive_429s = 0

            # Semáforo global: máx 6 respuestas de IA generándose en paralelo
            # Evita bursts descontrolados pero permite interacción simultánea en múltiples servidores
            bot.discord_semaphore = asyncio.Semaphore(6)

            # Inyección de dependencias
            bot.user_repo = UserRepository()
            bot.osu_repo = OsuRepository()
            bot.admin_repo = AdminRepository()
            bot.analytics_repo = AnalyticsRepository()

            bot.osu_service = OsuService(
                client_id=int(os.getenv("OSU_CLIENT_ID", 0)),
                client_secret=os.getenv("OSU_CLIENT_SECRET", "")
            )
            bot.nlp_service = NLPService(
                GEMINI_API_KEY,
                user_repo=bot.user_repo,
                osu_service=bot.osu_service,
                osu_repo=bot.osu_repo
            )
            bot.memory_service = MemoryService(bot.user_repo)

            # Registrar referencia de bot para telemetría en tiempo real del Dashboard
            DashboardService.register_bot(bot)

            # flush_task para los logs batch de UserRepo
            flush_task = asyncio.create_task(bot.user_repo._periodic_flush())

            # Check global: bloqueo de canales
            @bot.check
            async def global_block_check(ctx):
                allowed = ["unlock", "cs", "channelstatus", "status"]
                if ctx.command and ctx.command.name in allowed:
                    return True

                if not TursoClient.is_available():
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

                flush_task.cancel()

                # Flush final del buffer de logs antes de cerrar y liberar recursos
                await bot.user_repo.flush_logs()
                if hasattr(bot, "nlp_service") and bot.nlp_service:
                    await bot.nlp_service.close()
                await SQLiteManager.close()
                await asyncio.sleep(0.25)  # Permite al conector SSL de aiohttp/discord cerrarse limpiamente
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
            TursoClient.close()
            await SQLiteManager.close()
            logger.info("Apagado completo.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
