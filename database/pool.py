import logging
from database.turso_client import TursoClient, get_db

logger = logging.getLogger("dalet.database")

class DatabasePool:
    """Bridge de compatibilidad hacia TursoClient."""
    @classmethod
    async def get_pool(cls):
        return await get_db()

    @classmethod
    def is_available(cls):
        return TursoClient.is_available()

    @classmethod
    async def close(cls):
        TursoClient.close()

