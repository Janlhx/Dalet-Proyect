import logging
import re
from database.turso_client import get_db, TursoClient

logger = logging.getLogger("dalet.repository")

class BaseRepository:
    def __init__(self):
        pass
    
    def _convert_query(self, query: str) -> str:
        """Convierte parámetros de PostgreSQL ($1, $2) a SQLite (?)"""
        return re.sub(r'\$\d+', '?', query)

    async def execute(self, query, *args):
        client = await get_db()
        if client is None:
            logger.debug("DB not available, skipping execute.")
            return None
        
        query = self._convert_query(query)
        try:
            return await client.execute(query, args)
        except Exception as e:
            logger.error(f"Error executing query: {e}\nQuery: {query}\nArgs: {args}")
            return None

    async def fetch_one(self, query, *args):
        client = await get_db()
        if client is None:
            return None
        
        query = self._convert_query(query)
        try:
            result = await client.execute(query, args)
            if result.rows:
                return result.rows[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching one: {e}\nQuery: {query}\nArgs: {args}")
            return None

    async def fetch_all(self, query, *args):
        client = await get_db()
        if client is None:
            return []
        
        query = self._convert_query(query)
        try:
            result = await client.execute(query, args)
            return result.rows
        except Exception as e:
            logger.error(f"Error fetching all: {e}\nQuery: {query}\nArgs: {args}")
            return []

    async def call_procedure(self, procedure_name, *args):
        """Turso (SQLite) no soporta stored procedures, solo logueamos o pasamos."""
        logger.warning(f"call_procedure not supported in Turso/SQLite: {procedure_name}")
        return None
