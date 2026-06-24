import aiosqlite
import os
import logging
import asyncio

logger = logging.getLogger("dalet.database.sqlite")

DB_PATH = "dalet_local.db"


class SQLiteManager:
    _connection: aiosqlite.Connection | None = None
    _initialized: bool = False
    _lock: asyncio.Lock = asyncio.Lock()  # Lock global para serializar escrituras

    @classmethod
    async def get_connection(cls) -> aiosqlite.Connection | None:
        async with cls._lock:
            if cls._connection is None:
                try:
                    cls._connection = await aiosqlite.connect(DB_PATH)
                    cls._connection.row_factory = aiosqlite.Row
                    # WAL mode: mejor concurrencia para lecturas simultáneas
                    await cls._connection.execute("PRAGMA journal_mode=WAL")
                    await cls._connection.execute("PRAGMA synchronous=NORMAL")
                    await cls._connection.execute("PRAGMA cache_size=-8000")  # 8MB cache
                    if not cls._initialized:
                        await cls._initialize_schema()
                        cls._initialized = True
                    logger.info(f"Conexión SQLite establecida en {DB_PATH} (WAL mode)")
                except Exception as e:
                    logger.error(f"Error al conectar con SQLite: {e}")
                    cls._connection = None
                    return None
        return cls._connection

    @classmethod
    async def _initialize_schema(cls):
        """Crea las tablas si no existen. Se llama internamente con el lock activo."""
        queries = [
            # Mensajes — historial de chat para contexto de IA
            """
            CREATE TABLE IF NOT EXISTS Messages (
                MessageID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserID INTEGER NOT NULL,
                UserName TEXT NOT NULL,
                ServerID INTEGER NOT NULL,
                ServerName TEXT NOT NULL,
                ChannelID INTEGER NOT NULL,
                ChannelName TEXT NOT NULL,
                Content TEXT,
                Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Uso de comandos
            """
            CREATE TABLE IF NOT EXISTS CommandUsage (
                UsageID INTEGER PRIMARY KEY AUTOINCREMENT,
                CommandName TEXT NOT NULL,
                UserID INTEGER NOT NULL,
                UserName TEXT,
                ServerID INTEGER NOT NULL,
                ChannelID INTEGER NOT NULL,
                Success BOOLEAN DEFAULT 1,
                ExecutedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Interacciones de IA
            """
            CREATE TABLE IF NOT EXISTS AIInteractions (
                InteractionID INTEGER PRIMARY KEY AUTOINCREMENT,
                ServerID INTEGER NOT NULL,
                ChannelID INTEGER NOT NULL,
                TriggerType TEXT NOT NULL,
                Provider TEXT,
                ResponseTimeMs INTEGER,
                Success BOOLEAN DEFAULT 1,
                InteractedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Errores del bot
            """
            CREATE TABLE IF NOT EXISTS BotErrors (
                ErrorID INTEGER PRIMARY KEY AUTOINCREMENT,
                ErrorType TEXT,
                ErrorMsg TEXT,
                Context TEXT,
                ServerID INTEGER,
                OccurredAt DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Recordatorios diarios/semanales
            """
            CREATE TABLE IF NOT EXISTS Reminders (
                ReminderID INTEGER PRIMARY KEY AUTOINCREMENT,
                ServerID INTEGER NOT NULL,
                ChannelID INTEGER NOT NULL,
                UserID INTEGER NOT NULL,
                ReminderTime TEXT NOT NULL,
                ReminderDays TEXT NOT NULL,
                Message TEXT DEFAULT '¡Es hora del mapa del día!',
                Timezone TEXT DEFAULT 'America/Bogota',
                Active BOOLEAN DEFAULT 1,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Historial osu! (snapshots diarios)
            """
            CREATE TABLE IF NOT EXISTS OsuHistory (
                HistoryID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserID INTEGER NOT NULL,
                LogDate DATE NOT NULL,
                PP REAL,
                GlobalRank INTEGER,
                CountryRank INTEGER,
                Accuracy REAL,
                PlayMode TEXT,
                RecordedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(UserID, LogDate)
            )
            """,
            # Índices de rendimiento
            "CREATE INDEX IF NOT EXISTS idx_msg_channel ON Messages(ChannelID)",
            "CREATE INDEX IF NOT EXISTS idx_msg_timestamp ON Messages(Timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_cmd_time ON CommandUsage(ExecutedAt DESC)",
            "CREATE INDEX IF NOT EXISTS idx_ai_time ON AIInteractions(InteractedAt DESC)",
            "CREATE INDEX IF NOT EXISTS idx_err_time ON BotErrors(OccurredAt DESC)",
        ]

        try:
            for query in queries:
                await cls._connection.execute(query)
            await cls._connection.commit()
            logger.info("Esquema de SQLite inicializado correctamente.")
        except Exception as e:
            logger.error(f"Error al inicializar el esquema de SQLite: {e}")

    @classmethod
    async def execute(cls, query: str, *args) -> aiosqlite.Cursor | None:
        conn = await cls.get_connection()
        if not conn:
            return None
        async with cls._lock:
            try:
                cursor = await conn.execute(query, args)
                await conn.commit()
                return cursor
            except Exception as e:
                logger.error(f"SQLite Execute Error: {e} | Query: {query[:100]}")
                return None

    @classmethod
    async def executemany(cls, query: str, params_list: list) -> bool:
        """Inserción masiva eficiente — usa una sola transacción."""
        if not params_list:
            return True
        conn = await cls.get_connection()
        if not conn:
            return False
        async with cls._lock:
            try:
                await conn.executemany(query, params_list)
                await conn.commit()
                return True
            except Exception as e:
                logger.error(f"SQLite ExecuteMany Error: {e} | Query: {query[:100]}")
                return False

    @classmethod
    async def fetch_all(cls, query: str, *args) -> list:
        conn = await cls.get_connection()
        if not conn:
            return []
        try:
            async with conn.execute(query, args) as cursor:
                return await cursor.fetchall()
        except Exception as e:
            logger.error(f"SQLite FetchAll Error: {e}")
            return []

    @classmethod
    async def fetch_one(cls, query: str, *args):
        conn = await cls.get_connection()
        if not conn:
            return None
        try:
            async with conn.execute(query, args) as cursor:
                return await cursor.fetchone()
        except Exception as e:
            logger.error(f"SQLite FetchOne Error: {e}")
            return None

    @classmethod
    async def close(cls):
        async with cls._lock:
            if cls._connection:
                await cls._connection.close()
                cls._connection = None
                cls._initialized = False
                logger.info("Conexión SQLite cerrada.")
