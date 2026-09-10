import logging
from database.sqlite_manager import SQLiteManager

logger = logging.getLogger("dalet.repository.analytics")

class AnalyticsRepository:
    """
    Repositorio para escritura de datos analíticos:
    CommandUsage, AIInteractions, BotErrors y OsuHistory.
    Ahora utiliza SQLite local para minimizar costos en Neon.
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
        import datetime
        today = datetime.date.today().isoformat()
        
        query = """
            INSERT INTO OsuHistory (UserID, LogDate, PP, GlobalRank, CountryRank, Accuracy, PlayMode)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(UserID, LogDate) DO UPDATE SET
                PP = excluded.PP,
                GlobalRank = excluded.GlobalRank,
                CountryRank = excluded.CountryRank,
                Accuracy = excluded.Accuracy,
                PlayMode = excluded.PlayMode
        """
        await SQLiteManager.execute(query, user_id, today, pp, global_rank, country_rank, accuracy, play_mode)

    async def get_osu_progress(self, user_id: int, limit: int = 10):
        """Obtiene el historial de PP de un jugador desde SQLite."""
        # Nota: SQLite no tiene la función LAG de la misma forma exacta que Postgres 
        # en versiones muy viejas, pero la mayoría soportan Window Functions ahora.
        # Si no, simplemente traemos los datos y calculamos en Python.
        query = """
            SELECT RecordedAt, PP, GlobalRank
            FROM OsuHistory
            WHERE UserID = ?
            ORDER BY RecordedAt DESC
            LIMIT ?
        """
        rows = await SQLiteManager.fetch_all(query, user_id, limit)
        # Adaptar formato de Row a list/dict si es necesario
        results = []
        for i, row in enumerate(rows):
            pp = row['PP']
            # Calcular pp_change comparando con el siguiente (que es más viejo en el tiempo)
            pp_change = 0.0
            if i + 1 < len(rows):
                pp_change = pp - rows[i+1]['PP']
            
            results.append({
                'recorded_at': row['RecordedAt'],
                'pp': pp,
                'global_rank': row['GlobalRank'],
                'pp_change': pp_change
            })
        return results
