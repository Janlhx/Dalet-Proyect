import logging
from typing import Any
from database.turso_client import get_db

logger = logging.getLogger("dalet.repository.base")


class BaseRepository:
    """
    Repositorio base asíncrono para interactuar con la base de datos Turso (LibSQL).
    Proporciona métodos estandarizados para ejecución y consulta con parámetros posicionales SQLite (?).
    """

    async def execute(self, query: str, *args: Any) -> Any | None:
        """Ejecuta una sentencia SQL (INSERT, UPDATE, DELETE) en Turso."""
        client = await get_db()
        if client is None:
            logger.debug("Base de datos no disponible, ignorando execute.")
            return None

        try:
            return await client.execute(query, args)
        except Exception as e:
            logger.error(f"Error ejecutando consulta en BD: {e} | Query: {query} | Args: {args}")
            return None

    async def fetch_one(self, query: str, *args: Any) -> Any | None:
        """Obtiene la primera fila de una consulta o None si no hay resultados."""
        client = await get_db()
        if client is None:
            return None

        try:
            result = await client.execute(query, args)
            if result.rows:
                return result.rows[0]
            return None
        except Exception as e:
            logger.error(f"Error en fetch_one: {e} | Query: {query} | Args: {args}")
            return None

    async def fetch_all(self, query: str, *args: Any) -> list[Any]:
        """Obtiene todas las filas resultantes de una consulta o lista vacía."""
        client = await get_db()
        if client is None:
            return []

        try:
            result = await client.execute(query, args)
            return result.rows
        except Exception as e:
            logger.error(f"Error en fetch_all: {e} | Query: {query} | Args: {args}")
            return []
