import aiosqlite
import os
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger("dalet.database.sqlite")

DB_PATH = "dalet_local.db"

class SQLiteManager:
    _connection = None
    _initialized = False

    @classmethod
    async def get_connection(cls):
        if cls._connection is None:
            try:
                cls._connection = await aiosqlite.connect(DB_PATH)
                cls._connection.row_factory = aiosqlite.Row
                if not cls._initialized:
                    await cls._initialize_schema()
                    cls._initialized = True
                logger.info(f"Conexión a SQLite establecida en {DB_PATH}")
            except Exception as e:
                logger.error(f"Error al conectar con SQLite: {e}")
                return None
        return cls._connection

    @classmethod
    async def _initialize_schema(cls):
        """Crea las tablas de logs y analíticas si no existen."""
        queries = [
            # Tabla de Mensajes (Historial para contexto y stats)
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
            # Tabla de Uso de Comandos
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
            # Tabla de Interacciones de IA
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
            # Tabla de Errores del Bot
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
            # Tabla de Historial Osu! (Snapshots diarios)
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
            # Índices para rendimiento
            "CREATE INDEX IF NOT EXISTS idx_msg_channel ON Messages(ChannelID)",
            "CREATE INDEX IF NOT EXISTS idx_msg_timestamp ON Messages(Timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_cmd_time ON CommandUsage(ExecutedAt DESC)",
            "CREATE INDEX IF NOT EXISTS idx_ai_time ON AIInteractions(InteractedAt DESC)",
            "CREATE INDEX IF NOT EXISTS idx_err_time ON BotErrors(OccurredAt DESC)"
        ]
        
        try:
            for query in queries:
                await cls._connection.execute(query)
            await cls._connection.commit()
            logger.info("Esquema de SQLite inicializado correctamente.")
        except Exception as e:
            logger.error(f"Error al inicializar el esquema de SQLite: {e}")

    @classmethod
    async def execute(cls, query, *args):
        conn = await cls.get_connection()
        if not conn: return None
        try:
            cursor = await conn.execute(query, args)
            await conn.commit()
            return cursor
        except Exception as e:
            logger.error(f"SQLite Execute Error: {e} | Query: {query}")
            return None

    @classmethod
    async def fetch_all(cls, query, *args):
        conn = await cls.get_connection()
        if not conn: return []
        try:
            async with conn.execute(query, args) as cursor:
                return await cursor.fetchall()
        except Exception as e:
            logger.error(f"SQLite FetchAll Error: {e}")
            return []

    @classmethod
    async def fetch_one(cls, query, *args):
        conn = await cls.get_connection()
        if not conn: return None
        try:
            async with conn.execute(query, args) as cursor:
                return await cursor.fetchone()
        except Exception as e:
            logger.error(f"SQLite FetchOne Error: {e}")
            return None

    @classmethod
    async def close(cls):
        if cls._connection:
            await cls._connection.close()
            cls._connection = None
            cls._initialized = False
            logger.info("Conexión a SQLite cerrada.")
