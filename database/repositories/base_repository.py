import logging
from database.pool import get_db, DatabasePool

logger = logging.getLogger("dalet.repository")

class BaseRepository:
    def __init__(self):
        pass

    async def execute(self, query, *args):
        pool = await get_db()
        if pool is None:
            logger.debug("DB not available, skipping execute.")
            return None
        async with pool.acquire() as conn:
            try:
                return await conn.execute(query, *args)
            except Exception as e:
                logger.error(f"Error executing query: {e}")
                return None

    async def fetch_one(self, query, *args):
        pool = await get_db()
        if pool is None:
            return None
        async with pool.acquire() as conn:
            try:
                return await conn.fetchrow(query, *args)
            except Exception as e:
                logger.error(f"Error fetching one: {e}")
                return None

    async def fetch_all(self, query, *args):
        pool = await get_db()
        if pool is None:
            return []
        async with pool.acquire() as conn:
            try:
                return await conn.fetch(query, *args)
            except Exception as e:
                logger.error(f"Error fetching all: {e}")
                return []

    async def call_procedure(self, procedure_name, *args):
        placeholders = ', '.join([f'${i+1}' for i in range(len(args))])
        query = f"CALL {procedure_name}({placeholders})"
        return await self.execute(query, *args)
