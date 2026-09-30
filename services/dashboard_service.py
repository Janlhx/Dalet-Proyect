import time
import os
import json
import logging
import math
import asyncio
import sqlite3
from database.turso_client import TursoClient
from database.sqlite_manager import SQLiteManager

logger = logging.getLogger("dalet.services.dashboard")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DashboardService:
    """
    Servicio de Dashboard y Telemetría en tiempo real para Dalet.
    Proporciona endpoints JSON y sirve la interfaz web desacoplada en ui/templates/dashboard.html.
    """
    _bot_ref = None
    _start_time = time.time()
    _html_cache: str | None = None

    @classmethod
    def register_bot(cls, bot):
        """Registra la instancia activa de Discord Bot."""
        cls._bot_ref = bot

    @classmethod
    def get_full_telemetry(cls) -> dict:
        """Recopila todas las métricas del sistema para la API JSON."""
        bot = cls._bot_ref
        now = time.time()
        uptime_seconds = int(now - cls._start_time)

        # 1. Discord Bot Telemetry
        raw_lat = getattr(bot, "latency", None) if bot else None
        latency_ms = round(raw_lat * 1000) if (raw_lat is not None and math.isfinite(raw_lat)) else 0

        discord_stats = {
            "online": bool(bot and bot.is_ready()),
            "latency_ms": latency_ms,
            "guilds": len(bot.guilds) if bot else 0,
            "users": sum((g.member_count or 0) for g in bot.guilds) if bot else 0,
            "uptime_formatted": cls._format_uptime(uptime_seconds),
            "uptime_seconds": uptime_seconds,
            "shard_id": getattr(bot, "shard_id", 0) or 0
        }

        # 2. AI & Token Telemetry (desde NLPService o fallback persistente)
        ai_stats = {}
        if bot and hasattr(bot, "nlp_service") and bot.nlp_service:
            ai_stats = bot.nlp_service.get_telemetry()
        else:
            # Fallback a archivo de telemetría persistida si existe
            persisted = {}
            json_path = os.path.join(BASE_DIR, "data", "ai_telemetry.json")
            if os.path.exists(json_path):
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        persisted = json.load(f)
                except Exception:
                    pass

            ds_data = persisted.get("deepseek", {})
            ds_p = ds_data.get("prompt_tokens", 0)
            ds_c = ds_data.get("completion_tokens", 0)
            ds_cost = round((ds_p * 0.00000015) + (ds_c * 0.00000060), 6)

            gem_data = persisted.get("gemini", {})
            groq_data = persisted.get("groq", {})
            op_data = persisted.get("openrouter", {})

            raw_credit = os.getenv("DEEPSEEK_CREDIT_BALANCE", "").strip()
            credit_balance = float(raw_credit) if raw_credit else None

            total_prompt = ds_p + gem_data.get("prompt_tokens", 0) + groq_data.get("prompt_tokens", 0) + op_data.get("prompt_tokens", 0)
            total_compl = ds_c + gem_data.get("completion_tokens", 0) + groq_data.get("completion_tokens", 0) + op_data.get("completion_tokens", 0)

            ai_stats = {
                "routing_mode": os.getenv("AI_ROUTING_MODE", "auto"),
                "uptime_seconds": uptime_seconds,
                "estimated_cost_usd": ds_cost,
                "credit_balance": credit_balance,
                "prompt_ratio": round(total_prompt / max(1, total_compl), 1),
                "deepseek": {
                    "model": (os.getenv("DEEPSEEK_MODEL") or "deepseek-flash").strip(),
                    "healthy": True,
                    "cooldown_remaining": 0,
                    "requests": ds_data.get("requests", 0),
                    "prompt_tokens": ds_p,
                    "completion_tokens": ds_c,
                    "total_tokens": ds_p + ds_c,
                    "avg_latency_ms": 0,
                    "cost_usd": ds_cost,
                    "errors": ds_data.get("errors", 0)
                },
                "gemini": {
                    "model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip(),
                    "healthy": True,
                    "cooldown_remaining": 0,
                    "requests": gem_data.get("requests", 0),
                    "prompt_tokens": gem_data.get("prompt_tokens", 0),
                    "completion_tokens": gem_data.get("completion_tokens", 0),
                    "total_tokens": gem_data.get("prompt_tokens", 0) + gem_data.get("completion_tokens", 0),
                    "avg_latency_ms": 0,
                    "errors": gem_data.get("errors", 0)
                },
                "groq": {
                    "model": (os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b").strip(),
                    "fallback_model": (os.getenv("GROQ_MODEL_FALLBACK") or "llama-3.1-8b-instant").strip(),
                    "healthy": True,
                    "cooldown_remaining": 0,
                    "requests": groq_data.get("requests", 0),
                    "prompt_tokens": groq_data.get("prompt_tokens", 0),
                    "completion_tokens": groq_data.get("completion_tokens", 0),
                    "total_tokens": groq_data.get("prompt_tokens", 0) + groq_data.get("completion_tokens", 0),
                    "avg_latency_ms": 0,
                    "errors": groq_data.get("errors", 0)
                },
                "openrouter": {
                    "model": (os.getenv("OPENROUTER_MODEL") or "openrouter/free").strip(),
                    "healthy": True,
                    "cooldown_remaining": 0,
                    "requests": op_data.get("requests", 0),
                    "prompt_tokens": op_data.get("prompt_tokens", 0),
                    "completion_tokens": op_data.get("completion_tokens", 0),
                    "total_tokens": op_data.get("prompt_tokens", 0) + op_data.get("completion_tokens", 0),
                    "avg_latency_ms": 0,
                    "errors": op_data.get("errors", 0)
                },
                "recent_interactions": []
            }

        # 3. Database & Memory Telemetry
        turso_online = TursoClient.is_available()
        cache_size = 0
        buffer_size = 0
        if bot and hasattr(bot, "user_repo") and bot.user_repo:
            cache_size = len(getattr(bot.user_repo, "_cache", {}))
            buffer_size = len(getattr(bot.user_repo, "_log_buffer", []))

        db_stats = {
            "turso_online": turso_online,
            "turso_status": "ONLINE (libSQL HTTP Pipeline)" if turso_online else "STANDBY (Fallback Activo)",
            "sqlite_status": "OPERATIONAL (WAL Mode)",
            "cache_items": cache_size,
            "log_buffer_size": buffer_size,
            "log_buffer_max": 20
        }

        return {
            "timestamp": int(now),
            "discord": discord_stats,
            "ai": ai_stats,
            "db": db_stats
        }

    @staticmethod
    def _format_uptime(seconds: int) -> str:
        """Formatea segundos en una cadena legible d h m s."""
        d = seconds // 86400
        h = (seconds % 86400) // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        parts = []
        if d > 0: parts.append(f"{d}d")
        if h > 0: parts.append(f"{h}h")
        if m > 0: parts.append(f"{m}m")
        parts.append(f"{s}s")
        return " ".join(parts)

    @classmethod
    def get_dashboard_html(cls) -> str:
        """Retorna el contenido HTML del Dashboard desde su plantilla estática ui/templates/dashboard.html."""
        # En modo local/desarrollo siempre recarga el HTML si fue modificado
        template_path = os.path.join(BASE_DIR, "ui", "templates", "dashboard.html")
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error cargando plantilla de Dashboard en {template_path}: {e}")
            if cls._html_cache:
                return cls._html_cache
            return "<h1>Error 500: No se pudo cargar el Dashboard</h1>"

    @classmethod
    def _execute_query(cls, query: str, args: tuple = ()) -> list[dict]:
        """
        Ejecuta una consulta SELECT tanto en Turso (si está disponible vía async loop del bot)
        como en SQLite local (fallback thread-safe). Devuelve una lista de diccionarios.
        """
        bot = cls._bot_ref
        # 1. Intentar Turso si está disponible y el loop de bot está corriendo
        if TursoClient.is_available() and bot and getattr(bot, "loop", None) and bot.loop.is_running():
            try:
                async def _turso_fetch():
                    client = TursoClient.get_client()
                    if client:
                        res = await client.execute(query, args)
                        rows = []
                        if res and hasattr(res, "columns") and hasattr(res, "rows"):
                            cols = list(res.columns)
                            for r in res.rows:
                                if isinstance(r, dict):
                                    rows.append(r)
                                else:
                                    rows.append({cols[i]: r[i] for i in range(len(cols))})
                        elif res and hasattr(res, "rows"):
                            for r in res.rows:
                                rows.append(dict(r) if hasattr(r, "keys") else dict(enumerate(r)))
                        return rows
                    return None

                future = asyncio.run_coroutine_threadsafe(_turso_fetch(), bot.loop)
                res = future.result(timeout=4.0)
                if res is not None:
                    return res
            except Exception as e:
                logger.debug(f"Turso query fallback to SQLite: {e}")

        # 2. SQLite local fallback
        db_path = os.path.join(BASE_DIR, "dalet_local.db")
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path, timeout=3.0)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, args)
                rows = [dict(row) for row in cursor.fetchall()]
                conn.close()
                return rows
            except Exception as e:
                logger.debug(f"SQLite local query error: {e}")

        return []

    @classmethod
    def get_database_overview(cls) -> dict:
        """Obtiene métricas y conteo de filas de todas las tablas de la base de datos."""
        tables = [
            ("Users", "Usuarios registrados e historial de interacción", "users"),
            ("UserMemories", "Recuerdos cognitivos y síntesis de pensamiento", "memories"),
            ("Messages", "Historial de mensajes de chat registrados", "messages"),
            ("ModerationConfig", "Configuraciones de moderación activa por servidor", "moderation_config"),
            ("ModActions", "Auditoría de infracciones y acciones automáticas", "mod_actions"),
            ("Feedbacks", "Buzón de sugerencias y comentarios de la comunidad", "feedbacks"),
            ("Reminders", "Recordatorios programados por los usuarios", "reminders"),
        ]

        table_stats = []
        total_rows = 0
        for table_name, description, slug in tables:
            count = 0
            try:
                res = cls._execute_query(f"SELECT COUNT(*) as cnt FROM {table_name}")
                if res:
                    count = res[0].get("cnt", 0)
                    total_rows += count
            except Exception:
                count = 0
            table_stats.append({
                "table": table_name,
                "description": description,
                "slug": slug,
                "row_count": count
            })

        bot = cls._bot_ref
        cache_size = len(getattr(bot.user_repo, "_cache", {})) if (bot and hasattr(bot, "user_repo")) else 0
        buffer_size = len(getattr(bot.user_repo, "_log_buffer", [])) if (bot and hasattr(bot, "user_repo")) else 0

        turso_online = TursoClient.is_available()
        return {
            "tables": table_stats,
            "total_rows": total_rows,
            "engine": "Turso Cloud (libSQL HTTPS)" if turso_online else "SQLite Local (WAL Fallback)",
            "turso_available": turso_online,
            "cache_items": cache_size,
            "log_buffer_size": buffer_size,
            "timestamp": int(time.time())
        }

    @classmethod
    def get_memories(cls, search: str = "", limit: int = 50, offset: int = 0) -> dict:
        """Obtiene recuerdos cognitivos de UserMemories con filtro de búsqueda."""
        limit = min(max(1, limit), 100)
        offset = max(0, offset)

        where_clause = ""
        params: list = []
        if search:
            where_clause = "WHERE Topic LIKE ? OR Content LIKE ? OR UserMessage LIKE ? OR DaletThought LIKE ? OR CAST(UserID as TEXT) LIKE ?"
            like_term = f"%{search}%"
            params = [like_term, like_term, like_term, like_term, like_term]

        count_query = f"SELECT COUNT(*) as total FROM UserMemories {where_clause}"
        total_res = cls._execute_query(count_query, tuple(params))
        total = total_res[0].get("total", 0) if total_res else 0

        data_query = f"""
            SELECT MemoryID, UserID, Topic, Content, UserMessage, DaletThought, Timestamp
            FROM UserMemories
            {where_clause}
            ORDER BY Timestamp DESC
            LIMIT ? OFFSET ?
        """
        rows = cls._execute_query(data_query, tuple(params + [limit, offset]))

        memories = []
        for r in rows:
            memories.append({
                "id": r.get("MemoryID"),
                "user_id": str(r.get("UserID", "")),
                "topic": r.get("Topic") or "general",
                "content": r.get("Content") or "",
                "user_message": r.get("UserMessage") or "",
                "dalet_thought": r.get("DaletThought") or "",
                "timestamp": str(r.get("Timestamp") or "")
            })

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "memories": memories
        }

    @classmethod
    def get_mod_actions(cls, limit: int = 50) -> dict:
        """Obtiene las últimas acciones de moderación registradas."""
        limit = min(max(1, limit), 100)
        query = """
            SELECT ActionID, ServerID, ChannelID, UserID, UserName, Severity, Method, Reason, ActionTaken, OccurredAt
            FROM ModActions
            ORDER BY OccurredAt DESC
            LIMIT ?
        """
        rows = cls._execute_query(query, (limit,))
        actions = []
        for r in rows:
            actions.append({
                "id": r.get("ActionID"),
                "server_id": str(r.get("ServerID", "")),
                "channel_id": str(r.get("ChannelID", "")),
                "user_id": str(r.get("UserID", "")),
                "user_name": r.get("UserName") or "Desconocido",
                "severity": r.get("Severity") or "LOW",
                "method": r.get("Method") or "rule",
                "reason": r.get("Reason") or "",
                "action_taken": r.get("ActionTaken") or "notify",
                "occurred_at": str(r.get("OccurredAt") or "")
            })
        return {
            "total": len(actions),
            "actions": actions
        }

    @classmethod
    def get_feedbacks(cls, limit: int = 50) -> dict:
        """Obtiene feedbacks recibidos de la comunidad."""
        limit = min(max(1, limit), 100)
        query = """
            SELECT FeedbackID, UserID, UserName, UserAvatar, ServerID, ServerName, ChannelID, ChannelName, Content, CreatedAt
            FROM Feedbacks
            ORDER BY CreatedAt DESC
            LIMIT ?
        """
        rows = cls._execute_query(query, (limit,))
        feedbacks = []
        for r in rows:
            feedbacks.append({
                "id": r.get("FeedbackID"),
                "user_id": str(r.get("UserID", "")),
                "user_name": r.get("UserName") or "Anónimo",
                "user_avatar": r.get("UserAvatar") or "",
                "server_id": str(r.get("ServerID", "")),
                "server_name": r.get("ServerName") or "Direct Message",
                "channel_id": str(r.get("ChannelID", "")),
                "channel_name": r.get("ChannelName") or "DM",
                "content": r.get("Content") or "",
                "created_at": str(r.get("CreatedAt") or "")
            })
        return {
            "feedbacks": feedbacks,
            "total": len(feedbacks)
        }

