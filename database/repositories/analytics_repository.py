import logging
import datetime
from database.sqlite_manager import SQLiteManager

logger = logging.getLogger("dalet.repository.analytics")

class AnalyticsRepository:
    """
    Repositorio para escritura de datos analíticos:
    CommandUsage, AIInteractions, BotErrors y OsuHistory en SQLite local.
    """

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
        """Guarda un snapshot del perfil osu! del jugador en SQLite."""
        today = datetime.date.today().isoformat()
        mode_clean = (play_mode or "osu").lower().strip()
        
        query = """
            INSERT INTO OsuHistory (UserID, LogDate, PP, GlobalRank, CountryRank, Accuracy, PlayMode, RecordedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(UserID, LogDate) DO UPDATE SET
                PP = excluded.PP,
                GlobalRank = excluded.GlobalRank,
                CountryRank = excluded.CountryRank,
                Accuracy = excluded.Accuracy,
                PlayMode = excluded.PlayMode,
                RecordedAt = CURRENT_TIMESTAMP
        """
        await SQLiteManager.execute(query, user_id, today, pp, global_rank, country_rank, accuracy, mode_clean)

    async def get_osu_progress(self, user_id: int, mode: str = "osu", limit: int = 30):
        """Obtiene el historial cronológico de PP de un jugador filtrado por modo de juego."""
        mode_clean = (mode or "osu").lower().strip()
        query = """
            SELECT LogDate, RecordedAt, PP, GlobalRank, Accuracy, PlayMode
            FROM OsuHistory
            WHERE UserID = ? AND (LOWER(PlayMode) = ? OR (PlayMode IS NULL AND ? = 'osu'))
            ORDER BY LogDate DESC, RecordedAt DESC
            LIMIT ?
        """
        rows = await SQLiteManager.fetch_all(query, user_id, mode_clean, mode_clean, limit)
        results = []
        for i, row in enumerate(rows):
            pp = row['PP'] if 'PP' in row.keys() else row[2]
            glob_rank = row['GlobalRank'] if 'GlobalRank' in row.keys() else row[3]
            log_date = row['LogDate'] if 'LogDate' in row.keys() else row[0]
            rec_at = row['RecordedAt'] if 'RecordedAt' in row.keys() else row[1]
            acc = row['Accuracy'] if 'Accuracy' in row.keys() else (row[4] if len(row) > 4 else 0.0)
            
            # Calcular pp_change comparando con el siguiente (que es el día anterior en el tiempo)
            pp_change = 0.0
            if i + 1 < len(rows):
                prev_pp = rows[i+1]['PP'] if 'PP' in rows[i+1].keys() else rows[i+1][2]
                pp_change = (pp or 0.0) - (prev_pp or 0.0)
            
            results.append({
                'log_date': log_date,
                'recorded_at': rec_at or log_date,
                'pp': pp or 0.0,
                'global_rank': glob_rank,
                'accuracy': acc or 0.0,
                'pp_change': pp_change
            })
        return results
