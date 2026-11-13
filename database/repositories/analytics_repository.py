import logging
import datetime
from database.sqlite_manager import SQLiteManager
from database.repositories.base_repository import BaseRepository

logger = logging.getLogger("dalet.repository.analytics")


class AnalyticsRepository(BaseRepository):
    """
    Repositorio para escritura de datos analíticos:
    CommandUsage, AIInteractions, BotErrors en SQLite local y OsuHistory persistente en Turso/SQLite.
    """
    _history_schema_ensured: bool = False

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
        """Registra la ejecución de un comando en SQLite."""
        query = """
            INSERT INTO CommandUsage (CommandName, UserID, UserName, ServerID, ChannelID, Success)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        await SQLiteManager.execute(query, command_name, user_id, user_name, server_id, channel_id, 1 if success else 0)
        
        # Opcional: Actualizar el nombre en Postgres de forma asíncrona si el pool existe
        # pero para ahorrar cuota, omitiremos esta llamada frecuente por ahora 
        # o delegaremos a un UserRepository que ya lo gestione.

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
        """Registra una respuesta de la IA en SQLite."""
        query = """
            INSERT INTO AIInteractions (ServerID, ChannelID, TriggerType, Provider, ResponseTimeMs, Success)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        await SQLiteManager.execute(query, server_id, channel_id, trigger_type, provider, response_time_ms, 1 if success else 0)

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
        """Registra un error crítico del bot en SQLite."""
        query = """
            INSERT INTO BotErrors (ErrorType, ErrorMsg, Context, ServerID)
            VALUES (?, ?, ?, ?)
        """
        await SQLiteManager.execute(query, error_type, str(error_msg)[:2000], context, server_id)

    # ------------------------------------------------------------------
    # OsuHistory (Persistente en Turso Cloud + SQLite fallback)
    # ------------------------------------------------------------------

    @staticmethod
    def _col(row, key: str, idx: int):
        if row is None:
            return None
        if isinstance(row, dict):
            return row.get(key)
        try:
            if hasattr(row, "keys") and key in row.keys():
                return row[key]
        except Exception:
            pass
        try:
            return row[idx]
        except Exception:
            return None

    async def _ensure_osu_history_schema(self):
        if AnalyticsRepository._history_schema_ensured:
            return
        try:
            await self.execute("""
                CREATE TABLE IF NOT EXISTS OsuHistory (
                    HistoryID INTEGER PRIMARY KEY AUTOINCREMENT,
                    UserID INTEGER NOT NULL,
                    LogDate DATE NOT NULL,
                    PP REAL,
                    GlobalRank INTEGER,
                    CountryRank INTEGER,
                    Accuracy REAL,
                    PlayMode TEXT DEFAULT 'osu',
                    RecordedAt DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            AnalyticsRepository._history_schema_ensured = True
        except Exception as e:
            logger.debug(f"No se pudo asegurar esquema OsuHistory: {e}")

    async def record_osu_snapshot(
        self,
        user_id: int,
        pp: float,
        global_rank: int,
        country_rank: int,
        accuracy: float,
        play_mode: str
    ):
        """Guarda un snapshot del perfil osu! en Turso/SQLite. Permite múltiples puntos el mismo día si el PP cambió."""
        await self._ensure_osu_history_schema()
        today = datetime.date.today().isoformat()
        mode_clean = (play_mode or "osu").lower().strip()
        pp_val = float(pp or 0.0)

        last_row = await self.fetch_one(
            """
            SELECT HistoryID, LogDate, PP
            FROM OsuHistory
            WHERE UserID = ? AND (LOWER(PlayMode) = ? OR (PlayMode IS NULL AND ? = 'osu'))
            ORDER BY LogDate DESC, RecordedAt DESC, HistoryID DESC
            LIMIT 1
            """,
            user_id, mode_clean, mode_clean
        )

        if last_row:
            last_id = self._col(last_row, "HistoryID", 0)
            last_date = str(self._col(last_row, "LogDate", 1) or "")[:10]
            last_pp = float(self._col(last_row, "PP", 2) or 0.0)
            if last_date == today and abs(pp_val - last_pp) < 0.01 and last_id is not None:
                await self.execute(
                    """
                    UPDATE OsuHistory
                    SET GlobalRank = ?, CountryRank = ?, Accuracy = ?, RecordedAt = CURRENT_TIMESTAMP
                    WHERE HistoryID = ?
                    """,
                    global_rank, country_rank, accuracy, last_id
                )
                return

        res = await self.execute(
            """
            INSERT INTO OsuHistory (UserID, LogDate, PP, GlobalRank, CountryRank, Accuracy, PlayMode, RecordedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            user_id, today, pp_val, global_rank, country_rank, accuracy, mode_clean
        )
        if res is None:
            # Fallback por si una tabla antigua tiene UNIQUE(UserID, LogDate)
            await self.execute(
                """
                UPDATE OsuHistory
                SET PP = ?, GlobalRank = ?, CountryRank = ?, Accuracy = ?, PlayMode = ?, RecordedAt = CURRENT_TIMESTAMP
                WHERE UserID = ? AND LogDate = ?
                """,
                pp_val, global_rank, country_rank, accuracy, mode_clean, user_id, today
            )

    async def get_osu_progress(self, user_id: int, mode: str = "osu", limit: int = 30):
        """Obtiene el historial cronológico de PP de un jugador filtrado por modo de juego."""
        await self._ensure_osu_history_schema()
        mode_clean = (mode or "osu").lower().strip()
        query = """
            SELECT LogDate, RecordedAt, PP, GlobalRank, Accuracy, PlayMode
            FROM OsuHistory
            WHERE UserID = ? AND (LOWER(PlayMode) = ? OR (PlayMode IS NULL AND ? = 'osu'))
            ORDER BY LogDate DESC, RecordedAt DESC, HistoryID DESC
            LIMIT ?
        """
        rows = await self.fetch_all(query, user_id, mode_clean, mode_clean, limit)
        results = []
        for i, row in enumerate(rows):
            pp = float(self._col(row, "PP", 2) or 0.0)
            glob_rank = self._col(row, "GlobalRank", 3)
            log_date = self._col(row, "LogDate", 0)
            rec_at = self._col(row, "RecordedAt", 1)
            acc = float(self._col(row, "Accuracy", 4) or 0.0)

            pp_change = 0.0
            if i + 1 < len(rows):
                prev_pp = float(self._col(rows[i + 1], "PP", 2) or 0.0)
                pp_change = pp - prev_pp

            results.append({
                'log_date': log_date,
                'recorded_at': rec_at or log_date,
                'pp': pp,
                'global_rank': glob_rank,
                'accuracy': acc,
                'pp_change': pp_change
            })
        return results
