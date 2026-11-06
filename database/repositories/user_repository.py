import logging
import asyncio
import time
from database.repositories.base_repository import BaseRepository
from database.sqlite_manager import SQLiteManager

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
        while True:
            await asyncio.sleep(self._flush_interval)
            await self.flush_logs()

    async def flush_logs(self):
        if not self._log_buffer and not self._flushing_logs:
            return

        self._flushing_logs = list(self._log_buffer)
        self._log_buffer.clear()

        logger.info(f"Flushing {len(self._flushing_logs)} logs to SQLite...")

        query = """
            INSERT INTO Messages (UserID, UserName, ServerID, ServerName, ChannelID, ChannelName, Content)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        # executemany: una sola transacción atómica para todos los logs
        success = await SQLiteManager.executemany(query, self._flushing_logs)
        if success:
            logger.info(f"Flushed {len(self._flushing_logs)} logs correctamente.")
        else:
            logger.error("Error flushing logs. Devolviendo al buffer para reintentar.")
            self._log_buffer.extend(self._flushing_logs)

        self._flushing_logs.clear()

    async def _get_cached(self, key, fetch_func, *args):
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
            query = "SELECT IsReactive FROM Servers WHERE ServerID = ?"
            result = await self.fetch_one(query, sid)
            # Si el servidor no está registrado, asumir reactivo (True) por defecto
            if result is None:
                return True
            return bool(result[0]) if result[0] is not None else True
        
        return await self._get_cached(f"reactive_{server_id}", _fetch, server_id)

    async def is_channel_proactive(self, channel_id: int):
        async def _fetch(cid):
            query = "SELECT IsProactive FROM Channels WHERE ChannelID = ?"
            result = await self.fetch_one(query, cid)
            return bool(result[0]) if result and result[0] is not None else False
            
        return await self._get_cached(f"proactive_{channel_id}", _fetch, channel_id)

    async def set_server_reactive(self, server_id: int, server_name: str, is_reactive: bool):
        query = """
            INSERT INTO Servers (ServerID, ServerName, IsReactive)
            VALUES (?, ?, ?)
            ON CONFLICT(ServerID) DO UPDATE SET
                ServerName = excluded.ServerName,
                IsReactive = excluded.IsReactive
        """
        res = await self.execute(query, server_id, server_name, 1 if is_reactive else 0)
        self._cache.pop(f"reactive_{server_id}", None)
        return res

    async def set_channel_proactive(self, channel_id: int, channel_name: str, server_id: int, is_proactive: bool):
        query = """
            INSERT INTO Channels (ChannelID, ChannelName, ServerID, IsProactive)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ChannelID) DO UPDATE SET
                ChannelName = excluded.ChannelName,
                IsProactive = excluded.IsProactive
        """
        res = await self.execute(query, channel_id, channel_name, server_id, 1 if is_proactive else 0)
        self._cache.pop(f"proactive_{channel_id}", None)
        return res

    async def ensure_memories_schema(self):
        """Asegura que las tablas de la Pirámide Semántica (UserMemories L1 y UserPersonas L2/L3) existan."""
        create_query = """
            CREATE TABLE IF NOT EXISTS UserMemories (
                MemoryID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserID INTEGER NOT NULL,
                Topic TEXT DEFAULT 'general',
                Content TEXT NOT NULL,
                UserMessage TEXT,
                DaletThought TEXT,
                Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        await self.execute(create_query)

        personas_query = """
            CREATE TABLE IF NOT EXISTS UserPersonas (
                UserID INTEGER PRIMARY KEY,
                UserName TEXT,
                PersonaL3 TEXT DEFAULT '',
                ScenarioL2 TEXT DEFAULT '',
                MemoryCount INTEGER DEFAULT 0,
                UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        await self.execute(personas_query)

        insights_query = """
            CREATE TABLE IF NOT EXISTS PersonaInsights (
                InsightID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserID INTEGER,
                UserName TEXT,
                UserMessage TEXT,
                DaletReply TEXT,
                Critique TEXT,
                StyleRule TEXT NOT NULL,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        await self.execute(insights_query)

        # Sembrar las 3 reglas base de auto-calibración (Cold-Start Seed) si la tabla está vacía
        try:
            cnt_row = await self.fetch_one("SELECT COUNT(*) FROM PersonaInsights")
            cnt = 0
            if cnt_row:
                cnt = cnt_row.get("COUNT(*)", 0) if hasattr(cnt_row, "get") else int(cnt_row[0] or 0)
            if cnt == 0:
                seed_rules = [
                    (
                        0,
                        "Sistema (Calibración Base)",
                        "hay que no puedo ver mis mensajes ahora?",
                        "eso suena a que estás escribiendo en otro canal... recarga con ctrl+r",
                        "Dalet interpretó literalmente una réplica retórica ('hay' = '¡ay!') tras una broma y dio soporte técnico de Discord.",
                        "Distinguir preguntas retóricas y erratas de chat ('hay' por 'ay') tras una broma; jamás activar modo soporte técnico literal cuando el usuario está siguiendo el juego.",
                    ),
                    (
                        0,
                        "Sistema (Calibración Base)",
                        "hay q socializar",
                        "socializar con el segundo monitor y no con las personas del server, gran técnica. luego te quejas de que nadie te habla",
                        "Dalet repitió el mismo ángulo de burla ('segundo monitor') por tercer turno consecutivo y lanzó un golpe bajo innecesario.",
                        "Prohibido encasillarse repitiendo el mismo roast en turnos seguidos o tratar al usuario como enemigo; cuando buscan socializar, pasar a charla cómplice con ingenio seco.",
                    ),
                    (
                        0,
                        "Sistema (Calibración Base)",
                        "sabes eres grosera cruel y arrogante xd",
                        "es mi forma de dar ánimo",
                        "El usuario señaló exceso de hostilidad tras varios ataques seguidos.",
                        "Si el usuario señala que Dalet está siendo muy cruel o pesada, bajar media rayita con autoconciencia y humor seco en lugar de redoblar la hostilidad.",
                    ),
                ]
                for uid, uname, umsg, dreply, crit, srule in seed_rules:
                    await self.execute(
                        """
                        INSERT INTO PersonaInsights (UserID, UserName, UserMessage, DaletReply, Critique, StyleRule, CreatedAt)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        uid, uname, umsg, dreply, crit, srule,
                    )
                self._cache.pop("persona_insights", None)
        except Exception:
            pass

        try:
            rows = await self.fetch_all("PRAGMA table_info(UserMemories)")
            existing_cols = {row[1] for row in rows} if rows else set()
        except Exception:
            existing_cols = set()

        for col in ["UserMessage", "DaletThought"]:
            if col not in existing_cols:
                try:
                    await self.execute(f"ALTER TABLE UserMemories ADD COLUMN {col} TEXT")
                except Exception:
                    pass

    async def add_persona_insight(
        self,
        user_id: int,
        user_name: str,
        user_message: str,
        dalet_reply: str,
        critique: str,
        style_rule: str,
    ):
        """Guarda una regla de auto-calibración de personalidad aprendida por Dalet tras una conversación."""
        if not style_rule or not style_rule.strip():
            return None
        res = await self.execute(
            """
            INSERT INTO PersonaInsights (UserID, UserName, UserMessage, DaletReply, Critique, StyleRule, CreatedAt)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            user_id,
            user_name,
            (user_message or "")[:200],
            (dalet_reply or "")[:200],
            (critique or "")[:250],
            style_rule.strip()[:250],
        )
        # Podar insights antiguos más allá de los 30 más recientes para mantener la tabla ligera
        try:
            await self.execute(
                """
                DELETE FROM PersonaInsights
                WHERE InsightID NOT IN (
                    SELECT InsightID FROM PersonaInsights
                    ORDER BY CreatedAt DESC, InsightID DESC
                    LIMIT 30
                )
                """
            )
        except Exception:
            pass
        self._cache.pop("persona_insights", None)
        return res

    async def get_recent_persona_insights(self, limit: int = 4) -> list[dict]:
        """Obtiene las reglas de estilo y auto-calibración más recientes aprendidas por Dalet."""
        async def _fetch(lim):
            query = """
                SELECT InsightID, UserID, UserName, UserMessage, DaletReply, Critique, StyleRule, CreatedAt
                FROM PersonaInsights
                ORDER BY CreatedAt DESC, InsightID DESC
                LIMIT ?
            """
            rows = await self.fetch_all(query, lim)
            if not rows:
                return []
            results = []
            for row in rows:
                if hasattr(row, "get"):
                    results.append({
                        "id": row.get("InsightID") or row.get("id"),
                        "user_id": row.get("UserID") or row.get("user_id"),
                        "user_name": row.get("UserName") or row.get("user_name") or "",
                        "user_message": row.get("UserMessage") or row.get("user_message") or "",
                        "dalet_reply": row.get("DaletReply") or row.get("dalet_reply") or "",
                        "critique": row.get("Critique") or row.get("critique") or "",
                        "style_rule": row.get("StyleRule") or row.get("style_rule") or "",
                        "created_at": str(row.get("CreatedAt") or row.get("created_at") or ""),
                    })
                else:
                    results.append({
                        "id": row[0] if len(row) > 0 else None,
                        "user_id": row[1] if len(row) > 1 else None,
                        "user_name": row[2] if len(row) > 2 and row[2] else "",
                        "user_message": row[3] if len(row) > 3 and row[3] else "",
                        "dalet_reply": row[4] if len(row) > 4 and row[4] else "",
                        "critique": row[5] if len(row) > 5 and row[5] else "",
                        "style_rule": row[6] if len(row) > 6 and row[6] else "",
                        "created_at": str(row[7]) if len(row) > 7 and row[7] else "",
                    })
            return results

        return await self._get_cached("persona_insights", _fetch, limit)

    async def get_user_persona(self, user_id: int) -> dict | None:
        """Obtiene las capas superiores de la pirámide semántica (L3 Persona y L2 Scenario) del usuario."""
        async def _fetch(uid):
            query = """
                SELECT PersonaL3, ScenarioL2, MemoryCount, UpdatedAt
                FROM UserPersonas WHERE UserID = ?
            """
            row = await self.fetch_one(query, uid)
            if not row:
                return None
            if hasattr(row, "get"):
                return {
                    "persona_l3": row.get("PersonaL3") or row.get("persona_l3") or "",
                    "scenario_l2": row.get("ScenarioL2") or row.get("scenario_l2") or "",
                    "memory_count": row.get("MemoryCount") or row.get("memory_count") or 0,
                    "updated_at": str(row.get("UpdatedAt") or ""),
                }
            return {
                "persona_l3": row[0] if len(row) > 0 and row[0] else "",
                "scenario_l2": row[1] if len(row) > 1 and row[1] else "",
                "memory_count": int(row[2]) if len(row) > 2 and row[2] is not None else 0,
                "updated_at": str(row[3]) if len(row) > 3 and row[3] else "",
            }

        return await self._get_cached(f"persona_{user_id}", _fetch, user_id)

    async def upsert_user_persona(
        self,
        user_id: int,
        user_name: str,
        persona_l3: str,
        scenario_l2: str = "",
    ):
        """Actualiza atómicamente (UPSERT O(1)) las capas L3 Persona y L2 Scenario del usuario."""
        query = """
            INSERT INTO UserPersonas (UserID, UserName, PersonaL3, ScenarioL2, MemoryCount, UpdatedAt)
            VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(UserID) DO UPDATE SET
                UserName = excluded.UserName,
                PersonaL3 = excluded.PersonaL3,
                ScenarioL2 = CASE WHEN excluded.ScenarioL2 != '' THEN excluded.ScenarioL2 ELSE UserPersonas.ScenarioL2 END,
                MemoryCount = UserPersonas.MemoryCount + 1,
                UpdatedAt = CURRENT_TIMESTAMP
        """
        res = await self.execute(query, user_id, user_name, persona_l3, scenario_l2 or "")
        self._cache.pop(f"persona_{user_id}", None)
        return res

    async def prune_old_user_memories(self, user_id: int, max_atoms: int = 20):
        """Poda átomos L1 antiguos cuando superan el umbral, ya que su esencia fue destilada en L3."""
        query = """
            DELETE FROM UserMemories
            WHERE UserID = ? AND MemoryID NOT IN (
                SELECT MemoryID FROM UserMemories
                WHERE UserID = ?
                ORDER BY Timestamp DESC, MemoryID DESC
                LIMIT ?
            )
        """
        res = await self.execute(query, user_id, user_id, max_atoms)
        self._cache.pop(f"memories_{user_id}", None)
        return res

    async def add_user_memory(
        self,
        user_id: int,
        user_name: str,
        content: str,
        topic: str = "general",
        user_message: str | None = None,
        dalet_thought: str | None = None,
    ):
        # Asegurar usuario
        await self.execute(
            "INSERT INTO Users (UserID, UserName) VALUES (?, ?) ON CONFLICT(UserID) DO UPDATE SET UserName = excluded.UserName",
            user_id, user_name
        )
        res = await self.execute(
            "INSERT INTO UserMemories (UserID, Topic, Content, UserMessage, DaletThought) VALUES (?, ?, ?, ?, ?)",
            user_id, topic, content, user_message, dalet_thought
        )
        if res is None:
            res = await self.execute(
                "INSERT INTO UserMemories (UserID, Topic, Content) VALUES (?, ?, ?)",
                user_id, topic, content
            )
        self._cache.pop(f"memories_{user_id}", None)
        return res

    async def get_all_user_memories(self, user_id: int):
        async def _fetch(uid):
            query = """
                SELECT Topic as topic, Content as content, UserMessage as user_message, DaletThought as dalet_thought, Timestamp as timestamp
                FROM UserMemories WHERE UserID = ? ORDER BY Timestamp DESC LIMIT 25
            """
            rows = await self.fetch_all(query, uid)
            if not rows:
                fallback_query = "SELECT Topic as topic, Content as content FROM UserMemories WHERE UserID = ? ORDER BY Timestamp DESC LIMIT 25"
                rows = await self.fetch_all(fallback_query, uid)
            return rows
            
        return await self._get_cached(f"memories_{user_id}", _fetch, user_id)


    async def get_channel_messages(self, channel_id: int, limit: int = 20):
        """
        Obtiene los últimos mensajes de un canal desde SQLite y el buffer de memoria.
        """
        # 1. Combinar buffers de memoria
        all_local = []
        for log in reversed(self._log_buffer):
            if log[4] == channel_id:
                all_local.append({'user_id': log[0], 'username': log[1], 'content': log[6]})
        
        for log in reversed(self._flushing_logs):
            if log[4] == channel_id:
                all_local.append({'user_id': log[0], 'username': log[1], 'content': log[6]})
        
        buffered_results = all_local[:limit]

        # 2. Si faltan mensajes, buscar en SQLite
        remaining_limit = limit - len(buffered_results)
        if remaining_limit > 0:
            query = """
                SELECT UserID as user_id, UserName as username, Content as content
                FROM Messages
                WHERE ChannelID = ?
                ORDER BY Timestamp DESC
                LIMIT ?
            """
            rows = await SQLiteManager.fetch_all(query, channel_id, remaining_limit)
            if rows:
                db_results = [dict(r) for r in rows]
                return buffered_results + db_results

        return buffered_results
    
    async def log_message(self, user_id, user_name, server_id, server_name, channel_id, channel_name, content):
        clean_content = (content or "").strip()
        if not clean_content:
            return False

        # Evitar duplicar el mismo mensaje inmediatamente consecutivo en el mismo canal (ej: doble log de respuesta)
        if self._log_buffer:
            last = self._log_buffer[-1]
            if last[0] == user_id and last[4] == channel_id and last[6].strip() == clean_content:
                return True

        self._log_buffer.append((user_id, user_name, server_id, server_name, channel_id, channel_name, clean_content))
        if len(self._log_buffer) >= self._max_buffer_size:
            asyncio.create_task(self.flush_logs())
        return True

    async def search_lore(self, query: str, channel_id: int, limit: int = 25):
        """Busca fragmentos de mensajes pasados en SQLite."""
        sql_query = """
            SELECT UserName, Content, Timestamp
            FROM Messages
            WHERE Content LIKE ?
            AND ChannelID = ?
            ORDER BY Timestamp DESC
            LIMIT ?
        """
        search_term = f"%{query}%"
        rows = await SQLiteManager.fetch_all(sql_query, search_term, channel_id, limit)
        return rows

    async def get_user_social_stats(self, user_id: int):
        """Calcula estadísticas agregadas desde SQLite."""
        query = """
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT DATE(Timestamp)) as days_active,
                AVG(LENGTH(Content)) as avg_len
            FROM Messages
            WHERE UserID = ?
        """
        result = await SQLiteManager.fetch_one(query, user_id)
        if result:
            return {
                "total_messages": result['total_messages'],
                "days_active": result['days_active'],
                "avg_len": result['avg_len'] or 0.0
            }
        return {"total_messages": 0, "days_active": 0, "avg_len": 0.0}
