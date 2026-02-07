import logging
from database.pool import get_db

logger = logging.getLogger("dalet.repository")

class BaseRepository:
    def __init__(self):
        pass

    async def execute(self, query, *args):
        pool = await get_db()
        async with pool.acquire() as conn:
            try:
                return await conn.execute(query, *args)
            except Exception as e:
                logger.error(f"Error executing query: {query} | Error: {e}")
                raise

    async def fetch_one(self, query, *args):
        pool = await get_db()
        async with pool.acquire() as conn:
            try:
                return await conn.fetchrow(query, *args)
            except Exception as e:
                logger.error(f"Error fetching one: {query} | Error: {e}")
                raise

    async def fetch_all(self, query, *args):
        pool = await get_db()
        async with pool.acquire() as conn:
            try:
                return await conn.fetch(query, *args)
            except Exception as e:
                logger.error(f"Error fetching all: {query} | Error: {e}")
                raise

    async def call_procedure(self, procedure_name, *args):
        # asyncpg doesn't have a direct 'call' for procedures like psycopg2, 
        # so we use raw SQL 'CALL procedure_name($1, $2, ...)'
        placeholders = ', '.join([f'${i+1}' for i in range(len(args))])
        query = f"CALL {procedure_name}({placeholders})"
        return await self.execute(query, *args)
