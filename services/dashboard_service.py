import time
import os
import json
import logging
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
        discord_stats = {
            "online": bool(bot and bot.is_ready()),
            "latency_ms": round(bot.latency * 1000) if (bot and bot.latency) else 0,
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
                    "model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip(),
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
        if cls._html_cache is None:
            template_path = os.path.join(BASE_DIR, "ui", "templates", "dashboard.html")
            try:
                with open(template_path, "r", encoding="utf-8") as f:
                    cls._html_cache = f.read()
            except Exception as e:
                logger.error(f"Error cargando plantilla de Dashboard en {template_path}: {e}")
                return "<h1>Error 500: No se pudo cargar el Dashboard</h1>"
        return cls._html_cache
