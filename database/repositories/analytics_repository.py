import logging
from database.pool import get_db

logger = logging.getLogger("dalet.repository.analytics")

class AnalyticsRepository:
    """
    Repositorio para escritura de datos analíticos:
    CommandUsage, AIInteractions y BotErrors.
    Diseñado para ser lo más ligero posible: usa fire-and-forget
    con manejo de errores silencioso para no impactar el bot.
    """

    async def _execute(self, query: str, *args):
        """Ejecuta una query de escritura de forma segura y silenciosa."""
        try:
            pool = await get_db()
            async with pool.acquire() as conn:
                await conn.execute(query, *args)
        except Exception as e:
            # Los errores de analítica NUNCA deben derribar el bot
            logger.warning(f"Analytics write failed (non-critical): {e}")

    # ------------------------------------------------------------------
    # CommandUsage
    # ------------------------------------------------------------------

    async def log_command(
        self,
        command_name: str,
        user_id: int,
        user_name: str,
        server_id: int,
        channel_id: int,
        success: bool = True
    ):
        """Registra la ejecución de un comando."""
        await self._execute(
            "CALL sp_LogCommandUsage($1, $2, $3, $4, $5, $6)",
            command_name, user_id, user_name, server_id, channel_id, success
        )

    # ------------------------------------------------------------------
    # AIInteractions
    # ------------------------------------------------------------------

    async def log_ai_interaction(
        self,
        server_id: int,
        channel_id: int,
        trigger_type: str,   # 'mention', 'proactive', 'name_trigger'
        provider: str,       # 'gemini', 'groq', 'groq_fallback'
        response_time_ms: int,
        success: bool = True
    ):
        """Registra una respuesta de la IA."""
        await self._execute(
            "CALL sp_LogAIInteraction($1, $2, $3, $4, $5, $6)",
            server_id, channel_id, trigger_type, provider, response_time_ms, success
        )

    # ------------------------------------------------------------------
    # BotErrors
    # ------------------------------------------------------------------

    async def log_error(
        self,
        error_type: str,
        error_msg: str,
        context: str,
        server_id: int = None
    ):
        """Registra un error crítico del bot en la BD."""
        await self._execute(
            "CALL sp_LogBotError($1, $2, $3, $4)",
            error_type, str(error_msg)[:2000], context, server_id
        )

    # ------------------------------------------------------------------
    # OsuHistory
    # ------------------------------------------------------------------

    async def record_osu_snapshot(
        self,
        user_id: int,
        pp: float,
        global_rank: int,
        country_rank: int,
        accuracy: float,
        play_mode: str
    ):
        """Guarda un snapshot del perfil osu! del jugador."""
        await self._execute(
            "CALL sp_RecordOsuSnapshot($1, $2, $3, $4, $5, $6)",
            user_id, pp, global_rank, country_rank, accuracy, play_mode
        )

    async def get_osu_progress(self, user_id: int, limit: int = 10):
        """Obtiene el historial de PP de un jugador."""
        try:
            pool = await get_db()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM fn_GetOsuProgress($1, $2)",
                    user_id, limit
                )
                return rows
        except Exception as e:
            logger.error(f"Error getting osu progress: {e}")
            return []
