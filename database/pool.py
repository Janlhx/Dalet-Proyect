import asyncpg
import os
import logging
import asyncio
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

logger = logging.getLogger("dalet.database")

# Error conocido de cuota de Neon — cuando se ve esto, esperar más tiempo
QUOTA_ERROR_KEYWORDS = ["compute time quota", "exceeded", "upgrade your plan"]

class DatabasePool:
    _pool = None
    _db_available = False   # Flag: ¿tenemos conexión a la BD?
    _retry_after = 0.0      # Timestamp: esperar hasta aquí antes de reintentar

    @classmethod
    async def get_pool(cls):
        """
        Devuelve el pool de conexiones. Si la BD no está disponible, devuelve None.
        NUNCA lanza excepciones — el bot sigue funcionando sin BD.
        """
        if cls._pool is not None:
            return cls._pool

        # Si estamos en periodo de espera por cuota, no intentar
        import time
        if time.time() < cls._retry_after:
            return None

        try:
            logger.info("Initializing asyncpg connection pool...")
            cls._pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=1,
                max_size=3,          # Reducido para gastar menos CU de Neon
                max_inactive_connection_lifetime=300,  # Liberar conexiones inactivas
                command_timeout=30
            )
            cls._db_available = True
            logger.info("Database pool initialized successfully.")
        except Exception as e:
            error_str = str(e).lower()
            cls._pool = None
            cls._db_available = False

            # Si es error de cuota de Neon, esperar más tiempo antes de reintentar
            if any(kw in error_str for kw in QUOTA_ERROR_KEYWORDS):
                wait_minutes = 30
                cls._retry_after = time.time() + (wait_minutes * 60)
                logger.warning(
                    f"Neon quota exceeded. Bot will run without DB for {wait_minutes} min. "
                    f"Features requiring DB will be unavailable."
                )
            else:
                # Error de conexión genérico — reintentar más pronto
                cls._retry_after = time.time() + 120  # 2 minutos
                logger.error(f"Failed to initialize database pool: {e}. Retry in 2 min.")

        return cls._pool

    @classmethod
    def is_available(cls):
        """Devuelve True si la BD está disponible."""
        return cls._pool is not None and cls._db_available

    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            cls._db_available = False
            logger.info("Database pool closed.")

async def get_db():
    """Devuelve el pool. Puede devolver None si la BD no está disponible."""
    return await DatabasePool.get_pool()
