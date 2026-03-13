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
        self._flushing_logs = [] # Buffer temporal durante la escritura en DB

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
        if not self._log_buffer and not self._flushing_logs:
            return
        
        # Si ya hay un flush en curso, esperamos o simplemente dejamos que el siguiente se encargue
        # aunque el semáforo de la conexión/transacción nos protege.
        
        self._flushing_logs = list(self._log_buffer)
        self._log_buffer.clear()
        
        logger.info(f"Flushing {len(self._flushing_logs)} logs to DB...")
        # Nota: Idealmente usaríamos un 'INSERT ... VALUES (...), (...)' masivo
        # pero para mantener compatibilidad con el SP, los llamamos uno a uno en una sola conexión
        try:
            pool = await get_db()
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for log in self._flushing_logs:
                        try:
                            await conn.execute(
                                "CALL sp_LogMessage($1, $2, $3, $4, $5, $6, $7)",
                                *log
                            )
                        except Exception as e:
                            logger.error(f"Error flushing single log: {e}")
        finally:
            self._flushing_logs.clear()

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

    async def get_channel_messages(self, channel_id: int, limit: int = 20):
        """
        Obtiene los últimos mensajes de un canal, combinando los ya persistidos
        en la BD con los que están aún en el buffer de memoria o en proceso de flush.
        """
        # 1. Combinar buffers de memoria (el buffer actual es más nuevo que el de flushing)
        all_local = []
        for log in reversed(self._log_buffer):
            if log[4] == channel_id:
                all_local.append({'username': log[1], 'content': log[6]})
        
        for log in reversed(self._flushing_logs):
            if log[4] == channel_id:
                all_local.append({'username': log[1], 'content': log[6]})
        
        # Recortar si ya tenemos suficientes
        buffered_results = all_local[:limit]

        # 2. Si faltan mensajes para llegar al límite, buscar en la BD
        remaining_limit = limit - len(buffered_results)
        db_results = []
        if remaining_limit > 0:
            query = """
                SELECT UserName as username, Content as content
                FROM V_ChannelMessages
                WHERE ChannelID = $1
                ORDER BY Timestamp DESC
                LIMIT $2
            """
            rows = await self.fetch_all(query, channel_id, remaining_limit)
            if rows:
                db_results = [dict(r) for r in rows]

        # 3. Combinar: Primero el buffer (más nuevo), luego la BD (más viejo)
        return buffered_results + db_results
    
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

    async def get_user_social_stats(self, user_id: int):
        """Calcula estadísticas agregadas sobre el comportamiento del usuario en el chat."""
        query = """
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT DATE(Timestamp)) as days_active,
                AVG(LENGTH(Content)) as avg_len
            FROM V_ChannelMessages
            WHERE UserID = $1
        """
        result = await self.fetch_one(query, user_id)
        if result:
            return {
                "total_messages": result['total_messages'],
                "days_active": result['days_active'],
                "avg_len": result['avg_len'] or 0.0
            }
        return {"total_messages": 0, "days_active": 0, "avg_len": 0.0}
