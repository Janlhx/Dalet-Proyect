import os
import logging
import asyncio
from dotenv import load_dotenv
import libsql_client

load_dotenv()
TURSO_URL = os.getenv("TURSO_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

logger = logging.getLogger("dalet.database")

class TursoClient:
    _client = None
    _db_available = False
    _retry_after = 0.0

    @classmethod
    def get_client(cls):
        """
        Devuelve el cliente de Turso. Si la BD no está disponible, devuelve None.
        NUNCA lanza excepciones — el bot sigue funcionando sin BD.
        """
        import time
        
        # Si el cliente ya existe y está disponible, devolverlo
        if cls._client is not None and cls._db_available:
            return cls._client

        # Si estamos en periodo de espera por error previo, no intentar
        if time.time() < cls._retry_after:
            return None

        try:
            # Si el cliente existe pero no está disponible (ej. conexión perdida), cerrarlo primero
            if cls._client is not None:
                cls.close()

            logger.info("Initializing Turso client...")
            cls._client = libsql_client.create_client(
                url=TURSO_URL,
                auth_token=TURSO_AUTH_TOKEN
            )
            cls._db_available = True
            logger.info("Turso client initialized successfully.")
        except Exception as e:
            cls._client = None
            cls._db_available = False
            cls._retry_after = time.time() + 120
            logger.error(f"Failed to initialize Turso client: {e}. Bot in OFFLINE mode for 2 min.")

        return cls._client

    @classmethod
    def is_available(cls):
        """Devuelve True si la BD está conectada y disponible."""
        return cls._db_available and cls._client is not None

    @classmethod
    def close(cls):
        if cls._client:
            cls._client.close()
            cls._client = None
            cls._db_available = False
            logger.info("Turso client closed.")

async def get_db():
    """Devuelve el cliente. Puede devolver None si la BD no está disponible."""
    # Envolver en corutina para mantener compatibilidad con las partes asíncronas
    return TursoClient.get_client()
