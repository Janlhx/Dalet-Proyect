import asyncpg
import os
import logging
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

logger = logging.getLogger("dalet.database")

class DatabasePool:
    _pool = None

    @classmethod
    async def get_pool(cls):
        if cls._pool is None:
            try:
                logger.info("Initializing asyncpg connection pool...")
                cls._pool = await asyncpg.create_pool(
                    DATABASE_URL,
                    min_size=5,
                    max_size=20,
                    command_timeout=60
                )
                logger.info("Database pool initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize database pool: {e}")
                raise
        return cls._pool

    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            logger.info("Database pool closed.")

async def get_db():
    return await DatabasePool.get_pool()
