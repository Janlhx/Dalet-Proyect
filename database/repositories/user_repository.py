import logging
from database.repositories.base_repository import BaseRepository
from database.pool import get_db

logger = logging.getLogger("dalet.repository.user")

class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self._cache = {} # Cache simple: {key: value}
        self._cache_ttl = 300 # 5 minutos
        self._log_buffer = []
        self._flush_interval = 60 # Segundos
        self._max_buffer_size = 20
        self._flush_task = None

    def start_flush_task(self, loop):
        """Inicia la tarea de vaciado del buffer si no está activa."""
        if self._flush_task is None:
            self._flush_task = loop.create_task(self._periodic_flush())

    async def _periodic_flush(self):
        import asyncio
        while True:
            await asyncio.sleep(self._flush_interval)
            await self.flush_logs()

    async def flush_logs(self):
        if not self._log_buffer:
            return
        
        logs_to_process = list(self._log_buffer)
        self._log_buffer.clear()
        
        logger.info(f"Flushing {len(logs_to_process)} logs to DB...")
        # Nota: Idealmente usaríamos un 'INSERT ... VALUES (...), (...)' masivo
        # pero para mantener compatibilidad con el SP, los llamamos uno a uno en una sola conexión
        pool = await get_db()
        async with pool.acquire() as conn:
            async with conn.transaction():
                for log in logs_to_process:
                    try:
                        await conn.execute(
                            "CALL sp_LogMessage($1, $2, $3, $4, $5, $6, $7)",
                            *log
                        )
                    except Exception as e:
                        logger.error(f"Error flushing single log: {e}")

    async def _get_cached(self, key, fetch_func, *args):
        import time
        now = time.time()
        if key in self._cache:
            val, expiry = self._cache[key]
            if now < expiry:
                return val
        
        try:
            val = await fetch_func(*args)
            self._cache[key] = (val, now + self._cache_ttl)
            return val
        except Exception:
            # En caso de error de DB, intentar devolver el valor anterior si existe
            if key in self._cache:
                return self._cache[key][0]
            raise

    async def is_server_reactive(self, server_id: int):
        async def _fetch(sid):
            query = "SELECT fn_IsServerReactive($1)"
            result = await self.fetch_one(query, sid)
            return result[0] if result else True
        
        return await self._get_cached(f"reactive_{server_id}", _fetch, server_id)

    async def is_channel_proactive(self, channel_id: int):
        async def _fetch(cid):
            query = "SELECT fn_IsChannelProactive($1)"
            result = await self.fetch_one(query, cid)
            return result[0] if result else False
            
        return await self._get_cached(f"proactive_{channel_id}", _fetch, channel_id)

    async def add_user_memory(self, user_id, user_name, content, topic="general"):
        return await self.call_procedure(
            "sp_AddUserMemory",
            user_id, user_name, content, topic
        )

    async def get_all_user_memories(self, user_id: int):
        async def _fetch(uid):
            query = "SELECT topic, content FROM fn_GetAllUserMemories($1)"
            return await self.fetch_all(query, uid)
            
        return await self._get_cached(f"memories_{user_id}", _fetch, user_id)

    async def get_channel_messages(self, channel_id: int, limit: int = 10):
        query = """
            SELECT UserName, Content
            FROM V_ChannelMessages
            WHERE ChannelID = $1
            ORDER BY Timestamp DESC
            LIMIT $2
        """
        return await self.fetch_all(query, channel_id, limit)
    
    async def log_message(self, user_id, user_name, server_id, server_name, channel_id, channel_name, content):
        self._log_buffer.append((user_id, user_name, server_id, server_name, channel_id, channel_name, content))
        if len(self._log_buffer) >= self._max_buffer_size:
            import asyncio
            asyncio.create_task(self.flush_logs())
        return True

    async def search_lore(self, query: str, channel_id: int, limit: int = 25):
        """Busca fragmentos de mensajes pasados que coincidan con un término."""
        sql_query = """
            SELECT UserName, Content, Timestamp
            FROM V_ChannelMessages
            WHERE Content ILIKE $1
            AND ChannelID = $2
            ORDER BY Timestamp DESC
            LIMIT $3
        """
        search_term = f"%{query}%"
        return await self.fetch_all(sql_query, search_term, channel_id, limit)
