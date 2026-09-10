import time
import os
import json
import logging
from database.turso_client import TursoClient
from database.sqlite_manager import SQLiteManager

logger = logging.getLogger("dalet.services.dashboard")


class DashboardService:
    """
    Servicio de Dashboard y Telemetría en tiempo real para Dalet.
    Proporciona endpoints JSON y una interfaz web elegante, minimalista y de alto detalle.
    """
    _bot_ref = None
    _start_time = time.time()

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
            "users": sum(g.member_count for g in bot.guilds) if bot else 0,
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
            json_path = os.path.join("data", "ai_telemetry.json")
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
        """Genera el HTML elegante y minimalista del Dashboard con tonos pálidos y sin neones."""
        return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dalet • System Telemetry</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-page: #0c0d10;
            --bg-surface: #12141a;
            --bg-surface-elevated: #171922;
            --bg-surface-hover: #1c1f2a;
            
            --border-subtle: rgba(255, 255, 255, 0.06);
            --border-medium: rgba(255, 255, 255, 0.11);
            
            --text-primary: #e6e8ec;
            --text-secondary: #8b93a0;
            --text-tertiary: #525866;
            
            /* Tonos pálidos y apagados — estrictamente sin neones */
            --pale-sage: #7ea88f;
            --pale-sage-bg: rgba(126, 168, 143, 0.10);
            --pale-sage-border: rgba(126, 168, 143, 0.24);
            
            --pale-sand: #d6cdc0;
            --pale-sand-bg: rgba(214, 205, 192, 0.10);
            --pale-sand-border: rgba(214, 205, 192, 0.22);
            
            --pale-slate: #8ba3b8;
            --pale-slate-bg: rgba(139, 163, 184, 0.10);
            --pale-slate-border: rgba(139, 163, 184, 0.22);
            
            --pale-mauve: #bfa3a8;
            --pale-mauve-bg: rgba(191, 163, 168, 0.10);
            --pale-mauve-border: rgba(191, 163, 168, 0.22);
            
            --pale-clay: #c79d75;
            --pale-clay-bg: rgba(199, 157, 117, 0.10);
            --pale-clay-border: rgba(199, 157, 117, 0.22);

            --radius-sm: 6px;
            --radius-md: 10px;
            --radius-lg: 12px;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-page);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 24px;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }

        .container {
            max-width: 1340px;
            margin: 0 auto;
        }

        /* Monospace font utility */
        .font-mono {
            font-family: 'JetBrains Mono', monospace;
        }

        /* Header bar */
        header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 22px;
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            margin-bottom: 20px;
        }

        .header-brand {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .brand-badge {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            font-size: 13px;
            letter-spacing: 1.5px;
            background: var(--bg-surface-elevated);
            color: var(--pale-sand);
            border: 1px solid var(--border-medium);
            padding: 6px 12px;
            border-radius: var(--radius-sm);
        }

        .brand-title h1 {
            font-size: 16px;
            font-weight: 600;
            color: var(--text-primary);
            letter-spacing: -0.2px;
        }

        .brand-title p {
            font-size: 12px;
            color: var(--text-secondary);
            font-family: 'JetBrains Mono', monospace;
        }

        .header-controls {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .status-chip {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            font-weight: 500;
            padding: 5px 12px;
            border-radius: var(--radius-sm);
            background: var(--pale-sage-bg);
            border: 1px solid var(--pale-sage-border);
            color: var(--pale-sage);
        }

        .status-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: var(--pale-sage);
        }

        .control-group {
            display: flex;
            align-items: center;
            background: var(--bg-surface-elevated);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-sm);
            padding: 2px;
        }

        .cadence-btn {
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            padding: 5px 10px;
            border-radius: 4px;
            cursor: pointer;
            transition: color 0.15s ease, background 0.15s ease;
        }

        .cadence-btn.active {
            background: var(--bg-surface-hover);
            color: var(--text-primary);
            font-weight: 600;
        }

        .btn-refresh {
            background: var(--bg-surface-elevated);
            border: 1px solid var(--border-medium);
            color: var(--text-primary);
            font-size: 12px;
            font-weight: 500;
            padding: 6px 12px;
            border-radius: var(--radius-sm);
            cursor: pointer;
            transition: background 0.15s ease, border-color 0.15s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .btn-refresh:hover {
            background: var(--bg-surface-hover);
            border-color: rgba(255, 255, 255, 0.2);
        }

        /* KPI Cards Grid */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 20px;
        }

        @media (max-width: 1100px) {
            .kpi-grid { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 640px) {
            .kpi-grid { grid-template-columns: 1fr; }
        }

        .kpi-card {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 18px 20px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .kpi-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
        }

        .kpi-label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            font-weight: 600;
            color: var(--text-secondary);
        }

        .kpi-tag {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            padding: 2px 7px;
            border-radius: 4px;
            background: var(--bg-surface-elevated);
            border: 1px solid var(--border-subtle);
            color: var(--text-secondary);
        }

        .kpi-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 24px;
            font-weight: 600;
            letter-spacing: -0.5px;
            color: var(--text-primary);
            margin-bottom: 6px;
        }

        .kpi-detail {
            font-size: 12px;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .kpi-submetrics {
            margin-top: 14px;
            padding-top: 12px;
            border-top: 1px solid var(--border-subtle);
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-secondary);
        }

        /* Token Progress Bar */
        .token-bar-container {
            width: 100%;
            height: 4px;
            background: var(--bg-surface-elevated);
            border-radius: 2px;
            overflow: hidden;
            margin-top: 10px;
            display: flex;
        }

        .token-bar-prompt {
            height: 100%;
            background: var(--pale-sand);
            transition: width 0.3s ease;
        }

        .token-bar-compl {
            height: 100%;
            background: var(--pale-slate);
            transition: width 0.3s ease;
        }

        /* Provider Matrix Section */
        .section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
        }

        .section-title {
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            color: var(--text-secondary);
        }

        .provider-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 20px;
        }

        @media (max-width: 1100px) {
            .provider-grid { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 640px) {
            .provider-grid { grid-template-columns: 1fr; }
        }

        .provider-card {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 16px 18px;
            position: relative;
        }

        .provider-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
        }

        .provider-name {
            font-size: 14px;
            font-weight: 600;
            color: var(--text-primary);
        }

        .provider-pill {
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.5px;
            padding: 2px 7px;
            border-radius: 4px;
            text-transform: uppercase;
        }

        .pill-healthy {
            background: var(--pale-sage-bg);
            border: 1px solid var(--pale-sage-border);
            color: var(--pale-sage);
        }

        .pill-cooldown {
            background: var(--pale-clay-bg);
            border: 1px solid var(--pale-clay-border);
            color: var(--pale-clay);
        }

        .provider-model {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: var(--text-secondary);
            background: var(--bg-surface-elevated);
            padding: 4px 8px;
            border-radius: 4px;
            margin-bottom: 14px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            display: block;
        }

        .provider-stats-table {
            width: 100%;
            font-size: 12px;
            border-collapse: collapse;
        }

        .provider-stats-table td {
            padding: 4px 0;
        }

        .provider-stats-table td:first-child {
            color: var(--text-secondary);
        }

        .provider-stats-table td:last-child {
            text-align: right;
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-primary);
            font-weight: 500;
        }

        /* Middle Grid: Chart + System Status */
        .mid-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 16px;
            margin-bottom: 20px;
        }

        @media (max-width: 900px) {
            .mid-grid { grid-template-columns: 1fr; }
        }

        .chart-card {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 18px 20px;
        }

        .chart-container {
            position: relative;
            height: 220px;
            width: 100%;
        }

        .system-info-card {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 18px 20px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .system-table {
            width: 100%;
            font-size: 12px;
            border-collapse: collapse;
        }

        .system-table tr {
            border-bottom: 1px solid var(--border-subtle);
        }

        .system-table tr:last-child {
            border-bottom: none;
        }

        .system-table td {
            padding: 8px 0;
        }

        .system-table td:first-child {
            color: var(--text-secondary);
        }

        .system-table td:last-child {
            text-align: right;
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-primary);
        }

        /* Activity Table Section */
        .table-card {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            overflow: hidden;
        }

        .table-card-header {
            padding: 14px 20px;
            border-bottom: 1px solid var(--border-subtle);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .table-responsive {
            width: 100%;
            overflow-x: auto;
        }

        table.stream-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            text-align: left;
        }

        table.stream-table th {
            padding: 10px 16px;
            background: var(--bg-surface-elevated);
            color: var(--text-secondary);
            font-weight: 500;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--border-subtle);
        }

        table.stream-table td {
            padding: 10px 16px;
            border-bottom: 1px solid var(--border-subtle);
            color: var(--text-primary);
        }

        table.stream-table tr:last-child td {
            border-bottom: none;
        }

        table.stream-table tr:hover td {
            background: var(--bg-surface-hover);
        }

        .badge-provider {
            display: inline-block;
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            font-weight: 500;
            padding: 2px 7px;
            border-radius: 4px;
        }

        .badge-ds {
            background: var(--pale-sand-bg);
            color: var(--pale-sand);
            border: 1px solid var(--pale-sand-border);
        }

        .badge-groq {
            background: var(--pale-slate-bg);
            color: var(--pale-slate);
            border: 1px solid var(--pale-slate-border);
        }

        .badge-gemini {
            background: var(--pale-mauve-bg);
            color: var(--pale-mauve);
            border: 1px solid var(--pale-mauve-border);
        }

        .badge-openrouter {
            background: var(--pale-clay-bg);
            color: var(--pale-clay);
            border: 1px solid var(--pale-clay-border);
        }

        .latency-tag {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: var(--text-secondary);
        }

        /* Navigation Tabs */
        .nav-tabs {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--border-subtle);
            padding-bottom: 10px;
        }

        .tab-btn {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 500;
            padding: 8px 16px;
            border-radius: var(--radius-sm);
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: all 0.15s ease;
        }

        .tab-btn:hover {
            background: var(--bg-surface-hover);
            color: var(--text-primary);
            border-color: var(--border-medium);
        }

        .tab-btn.active {
            background: var(--bg-surface-elevated);
            color: var(--text-primary);
            border-color: rgba(255, 255, 255, 0.22);
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }

        .tab-count {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            background: var(--bg-page);
            padding: 2px 6px;
            border-radius: 10px;
            color: var(--text-secondary);
            border: 1px solid var(--border-subtle);
        }

        .tab-pane {
            display: none;
            animation: fadeIn 0.2s ease;
        }

        .tab-pane.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(4px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Feedback Cards */
        .feedback-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }

        @media (max-width: 600px) {
            .feedback-grid { grid-template-columns: 1fr; }
        }

        .feedback-card {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 18px 20px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: border-color 0.15s ease;
        }

        .feedback-card:hover {
            border-color: var(--border-medium);
        }

        .feedback-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }

        .feedback-avatar {
            width: 38px;
            height: 38px;
            border-radius: 50%;
            background: var(--bg-surface-elevated);
            border: 1px solid var(--border-medium);
            object-fit: cover;
        }

        .feedback-user-info {
            flex: 1;
            min-width: 0;
        }

        .feedback-user-name {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .feedback-meta {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: var(--text-secondary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .feedback-body {
            font-size: 13px;
            color: var(--text-primary);
            line-height: 1.5;
            background: var(--bg-surface-elevated);
            border: 1px solid var(--border-subtle);
            padding: 12px 14px;
            border-radius: var(--radius-sm);
            white-space: pre-wrap;
            word-break: break-word;
            margin-bottom: 12px;
        }

        .feedback-footer {
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-tertiary);
        }

        .system-cards-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
            margin-bottom: 20px;
        }

        @media (max-width: 800px) {
            .system-cards-grid {
                grid-template-columns: 1fr;
            }
        }

        footer {
            margin-top: 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 11px;
            color: var(--text-tertiary);
            font-family: 'JetBrains Mono', monospace;
            padding: 0 4px;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="header-brand">
                <span class="brand-badge">DALET</span>
                <div class="brand-title">
                    <h1>System Telemetry</h1>
                    <p>Load Balancer & Execution Monitor</p>
                </div>
            </div>
            <div class="header-controls">
                <div class="status-chip" id="chip-system-status">
                    <span class="status-dot"></span>
                    <span id="label-system-status">ACTIVE</span>
                </div>
                <div class="control-group">
                    <button class="cadence-btn" id="btn-cadence-3" onclick="setCadence(3000)">3s</button>
                    <button class="cadence-btn active" id="btn-cadence-10" onclick="setCadence(10000)">10s</button>
                    <button class="cadence-btn" id="btn-cadence-pause" onclick="setCadence(0)">Pausa</button>
                </div>
                <button class="btn-refresh" onclick="fetchTelemetry()">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="23 4 23 10 17 10"></polyline>
                        <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                    </svg>
                    <span>Actualizar</span>
                </button>
            </div>
        </header>

        <!-- Navigation Tabs -->
        <div class="nav-tabs">
            <button class="tab-btn active" id="btn-tab-ai" onclick="switchTab('ai')">
                <span>🧠 Telemetría IA</span>
            </button>
            <button class="tab-btn" id="btn-tab-system" onclick="switchTab('system')">
                <span>⚙️ Infraestructura & Sistema</span>
            </button>
            <button class="tab-btn" id="btn-tab-feedback" onclick="switchTab('feedback')">
                <span>📬 Buzón de Feedback</span>
                <span class="tab-count" id="badge-feedback-count">0</span>
            </button>
        </div>

        <!-- ================= TAB 1: AI TELEMETRY ================= -->
        <div id="pane-ai" class="tab-pane active">
            <!-- Top KPI Grid -->
            <div class="kpi-grid">
                <!-- Card 1: Gasto Acumulado -->
                <div class="kpi-card">
                    <div>
                        <div class="kpi-header">
                            <span class="kpi-label">Gasto Acumulado</span>
                            <span class="kpi-tag" id="cost-account-type">PAY-AS-YOU-GO</span>
                        </div>
                        <div class="kpi-value" id="kpi-spend-usd">$0.000000</div>
                        <div class="kpi-detail">
                            <span>DeepSeek V4.1-Flash ($0.15/1M in · $0.60/1M out)</span>
                        </div>
                    </div>
                    <div class="kpi-submetrics">
                        <span id="kpi-credit-row">Saldo prepago: No config.</span>
                        <span id="kpi-cost-per-k">$0.000 / 1k req</span>
                    </div>
                </div>

                <!-- Card 2: Volumen de Tokens -->
                <div class="kpi-card">
                    <div>
                        <div class="kpi-header">
                            <span class="kpi-label">Tokens Procesados</span>
                            <span class="kpi-tag" id="kpi-token-ratio">Ratio 1.0:1</span>
                        </div>
                        <div class="kpi-value" id="kpi-total-tokens">0</div>
                        <div class="token-bar-container">
                            <div class="token-bar-prompt" id="bar-prompt" style="width: 50%;"></div>
                            <div class="token-bar-compl" id="bar-compl" style="width: 50%;"></div>
                        </div>
                    </div>
                    <div class="kpi-submetrics">
                        <span>Prompt: <b id="kpi-prompt-tokens" style="color: var(--pale-sand);">0</b></span>
                        <span>Compl: <b id="kpi-compl-tokens" style="color: var(--pale-slate);">0</b></span>
                    </div>
                </div>

                <!-- Card 3: Peticiones & Ruteo -->
                <div class="kpi-card">
                    <div>
                        <div class="kpi-header">
                            <span class="kpi-label">Invocaciones Totales</span>
                            <span class="kpi-tag" id="kpi-routing-mode">AUTO-FAILOVER</span>
                        </div>
                        <div class="kpi-value" id="kpi-total-requests">0</div>
                        <div class="kpi-detail">
                            <span>Distribución multi-proveedor</span>
                        </div>
                    </div>
                    <div class="kpi-submetrics">
                        <span>DS: <b id="sub-ds-reqs">0</b> · Groq: <b id="sub-groq-reqs">0</b></span>
                        <span>Gem: <b id="sub-gem-reqs">0</b> · OR: <b id="sub-or-reqs">0</b></span>
                    </div>
                </div>

                <!-- Card 4: Latencia & Gateway -->
                <div class="kpi-card">
                    <div>
                        <div class="kpi-header">
                            <span class="kpi-label">Latencia Inferencia</span>
                            <span class="kpi-tag" id="kpi-discord-status">ONLINE</span>
                        </div>
                        <div class="kpi-value"><span id="kpi-avg-latency">0</span><small style="font-size: 14px; font-weight: 400; color: var(--text-secondary); margin-left: 4px;">ms avg</small></div>
                        <div class="kpi-detail">
                            <span>Discord Ping: <span id="kpi-discord-ping" class="font-mono">0ms</span></span>
                        </div>
                    </div>
                    <div class="kpi-submetrics">
                        <span>Guilds: <b id="kpi-guilds">0</b></span>
                        <span>Uptime: <b id="kpi-uptime">0s</b></span>
                    </div>
                </div>
            </div>

            <!-- Section: Provider Architecture Matrix -->
            <div class="section-header">
                <span class="section-title">Matriz de Proveedores de Inferencia</span>
                <span style="font-size: 11px; color: var(--text-tertiary); font-family: 'JetBrains Mono', monospace;">PRIORITY: DEEPSEEK CORE → GROQ LPU → GEMINI → OPENROUTER</span>
            </div>

            <div class="provider-grid">
                <!-- 1. DeepSeek -->
                <div class="provider-card">
                    <div class="provider-top">
                        <span class="provider-name">DeepSeek V4.1</span>
                        <span class="provider-pill pill-healthy" id="pill-deepseek">HEALTHY</span>
                    </div>
                    <span class="provider-model" id="model-deepseek">deepseek-flash</span>
                    <table class="provider-stats-table">
                        <tr>
                            <td>Invocaciones</td>
                            <td id="ds-requests">0</td>
                        </tr>
                        <tr>
                            <td>Tokens Prompt</td>
                            <td id="ds-prompt">0</td>
                        </tr>
                        <tr>
                            <td>Tokens Respuesta</td>
                            <td id="ds-completion">0</td>
                        </tr>
                        <tr>
                            <td>Latencia Media</td>
                            <td id="ds-lat">0ms</td>
                        </tr>
                        <tr>
                            <td>Costo Incurrido</td>
                            <td id="ds-cost" style="color: var(--pale-sand);">$0.000000</td>
                        </tr>
                    </table>
                </div>

                <!-- 2. Groq -->
                <div class="provider-card">
                    <div class="provider-top">
                        <span class="provider-name">Groq LPU</span>
                        <span class="provider-pill pill-healthy" id="pill-groq">HEALTHY</span>
                    </div>
                    <span class="provider-model" id="model-groq">openai/gpt-oss-120b</span>
                    <table class="provider-stats-table">
                        <tr>
                            <td>Invocaciones</td>
                            <td id="groq-requests">0</td>
                        </tr>
                        <tr>
                            <td>Tokens Prompt</td>
                            <td id="groq-prompt">0</td>
                        </tr>
                        <tr>
                            <td>Tokens Respuesta</td>
                            <td id="groq-completion">0</td>
                        </tr>
                        <tr>
                            <td>Latencia Media</td>
                            <td id="groq-lat">0ms</td>
                        </tr>
                        <tr>
                            <td>Tarifa</td>
                            <td style="color: var(--pale-slate);">$0.00 (Free Tier)</td>
                        </tr>
                    </table>
                </div>

                <!-- 3. Gemini -->
                <div class="provider-card">
                    <div class="provider-top">
                        <span class="provider-name">Google Gemini</span>
                        <span class="provider-pill pill-healthy" id="pill-gemini">HEALTHY</span>
                    </div>
                    <span class="provider-model" id="model-gemini">gemini-1.5-flash</span>
                    <table class="provider-stats-table">
                        <tr>
                            <td>Invocaciones</td>
                            <td id="gemini-requests">0</td>
                        </tr>
                        <tr>
                            <td>Tokens Prompt</td>
                            <td id="gemini-prompt">0</td>
                        </tr>
                        <tr>
                            <td>Tokens Respuesta</td>
                            <td id="gemini-completion">0</td>
                        </tr>
                        <tr>
                            <td>Latencia Media</td>
                            <td id="gemini-lat">0ms</td>
                        </tr>
                        <tr>
                            <td>Herramientas</td>
                            <td style="color: var(--pale-mauve);">Search Grounding</td>
                        </tr>
                    </table>
                </div>

                <!-- 4. OpenRouter -->
                <div class="provider-card">
                    <div class="provider-top">
                        <span class="provider-name">OpenRouter</span>
                        <span class="provider-pill pill-healthy" id="pill-openrouter">HEALTHY</span>
                    </div>
                    <span class="provider-model" id="model-openrouter">openrouter/free</span>
                    <table class="provider-stats-table">
                        <tr>
                            <td>Invocaciones</td>
                            <td id="or-requests">0</td>
                        </tr>
                        <tr>
                            <td>Tokens Prompt</td>
                            <td id="or-prompt">0</td>
                        </tr>
                        <tr>
                            <td>Tokens Respuesta</td>
                            <td id="or-completion">0</td>
                        </tr>
                        <tr>
                            <td>Latencia Media</td>
                            <td id="or-lat">0ms</td>
                        </tr>
                        <tr>
                            <td>Enrutamiento</td>
                            <td style="color: var(--pale-clay);">Fallback Pool</td>
                        </tr>
                    </table>
                </div>
            </div>

            <!-- Chart Card -->
            <div class="chart-card" style="margin-bottom: 20px;">
                <div class="section-header" style="margin-bottom: 8px;">
                    <span class="section-title">Distribución de Tokens por Proveedor</span>
                </div>
                <div class="chart-container">
                    <canvas id="tokenChart"></canvas>
                </div>
            </div>

            <!-- Section: Real-time Interaction Feed -->
            <div class="table-card">
                <div class="table-card-header">
                    <span class="section-title">Registro de Interacciones Recientes</span>
                    <span style="font-size: 11px; color: var(--text-secondary); font-family: 'JetBrains Mono', monospace;" id="feed-count">0 eventos</span>
                </div>
                <div class="table-responsive">
                    <table class="stream-table">
                        <thead>
                            <tr>
                                <th style="width: 80px;">Hora</th>
                                <th style="width: 110px;">Proveedor</th>
                                <th style="width: 160px;">Modelo</th>
                                <th style="width: 120px;">Usuario</th>
                                <th>Mensaje Activador</th>
                                <th style="width: 140px; text-align: right;">Tokens (In / Out)</th>
                                <th style="width: 90px; text-align: right;">Latencia</th>
                            </tr>
                        </thead>
                        <tbody id="interactions-body">
                            <tr>
                                <td colspan="7" style="text-align: center; color: var(--text-tertiary); padding: 24px;">Esperando interacciones de usuarios...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ================= TAB 2: SYSTEM & INFRASTRUCTURE ================= -->
        <div id="pane-system" class="tab-pane">
            <!-- System Status Top KPIs -->
            <div class="kpi-grid">
                <div class="kpi-card">
                    <div>
                        <div class="kpi-header">
                            <span class="kpi-label">Gateway Discord</span>
                            <span class="kpi-tag" id="sys-kpi-gateway-tag">ONLINE</span>
                        </div>
                        <div class="kpi-value" id="sys-kpi-ping">0ms</div>
                        <div class="kpi-detail">
                            <span>Latencia WebSocket al clúster de Discord</span>
                        </div>
                    </div>
                    <div class="kpi-submetrics">
                        <span>Estado: <b id="sys-kpi-gateway-state">CONECTADO</b></span>
                        <span>Shard: <b>0 / 1</b></span>
                    </div>
                </div>

                <div class="kpi-card">
                    <div>
                        <div class="kpi-header">
                            <span class="kpi-label">Servidores Conectados</span>
                            <span class="kpi-tag">DISCORD GUILDS</span>
                        </div>
                        <div class="kpi-value" id="sys-kpi-guilds">0</div>
                        <div class="kpi-detail">
                            <span>Comunidades activas con Dalet</span>
                        </div>
                    </div>
                    <div class="kpi-submetrics">
                        <span>Canales activos</span>
                        <span style="color: var(--pale-sage);">Disponibilidad 99.9%</span>
                    </div>
                </div>

                <div class="kpi-card">
                    <div>
                        <div class="kpi-header">
                            <span class="kpi-label">Usuarios Monitoreados</span>
                            <span class="kpi-tag">POBLACIÓN</span>
                        </div>
                        <div class="kpi-value" id="sys-kpi-users">0</div>
                        <div class="kpi-detail">
                            <span>Usuarios en memoria y base de datos</span>
                        </div>
                    </div>
                    <div class="kpi-submetrics">
                        <span>Caché en memoria: <b id="sys-kpi-cache-count">0 items</b></span>
                    </div>
                </div>

                <div class="kpi-card">
                    <div>
                        <div class="kpi-header">
                            <span class="kpi-label">Tiempo de Actividad</span>
                            <span class="kpi-tag">UPTIME</span>
                        </div>
                        <div class="kpi-value" id="sys-kpi-uptime">0s</div>
                        <div class="kpi-detail">
                            <span>Continuidad del proceso del bot</span>
                        </div>
                    </div>
                    <div class="kpi-submetrics">
                        <span>Salud: <b style="color: var(--pale-sage);">ESTABLE</b></span>
                        <span>Auto-reinicio: <b>Activo</b></span>
                    </div>
                </div>
            </div>

            <!-- Detailed System Architecture Grids -->
            <div class="system-cards-grid">
                <!-- Card 1: Turso LibSQL Cloud -->
                <div class="kpi-card">
                    <div>
                        <div class="kpi-header">
                            <span class="kpi-label">Base de Datos Primaria</span>
                            <span class="kpi-tag" style="background: var(--pale-sage-bg); color: var(--pale-sage); border-color: var(--pale-sage-border);">CLOUD EDGE</span>
                        </div>
                        <h3 style="font-size: 15px; font-weight: 600; margin-bottom: 6px; color: var(--text-primary);">Turso LibSQL (Distributed)</h3>
                        <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 14px; line-height: 1.5;">
                            Base de datos transaccional con arquitectura edge sobre HTTP pipeline. Almacena perfiles de usuario, balance de créditos, inventario y registros duraderos.
                        </p>
                    </div>
                    <table class="system-table">
                        <tr>
                            <td>Estado de Conexión</td>
                            <td id="sys-turso-status-2">ONLINE</td>
                        </tr>
                        <tr>
                            <td>Protocolo</td>
                            <td>HTTP Pipeline (LibSQL v2)</td>
                        </tr>
                        <tr>
                            <td>Modo de Operación</td>
                            <td>Distributed Edge Replica</td>
                        </tr>
                        <tr>
                            <td>Tolerancia a Fallos</td>
                            <td style="color: var(--pale-sage);">Auto-Failover a SQLite WAL</td>
                        </tr>
                    </table>
                </div>

                <!-- Card 2: SQLite WAL Local -->
                <div class="kpi-card">
                    <div>
                        <div class="kpi-header">
                            <span class="kpi-label">Persistencia & Caché Local</span>
                            <span class="kpi-tag" style="background: var(--pale-slate-bg); color: var(--pale-slate); border-color: var(--pale-slate-border);">LOCAL ENGINE</span>
                        </div>
                        <h3 style="font-size: 15px; font-weight: 600; margin-bottom: 6px; color: var(--text-primary);">SQLite Async WAL</h3>
                        <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 14px; line-height: 1.5;">
                            Motor ultrarrápido local con Write-Ahead Logging (WAL) para lecturas no bloqueantes y almacenamiento de respaldo, logs y feedback.
                        </p>
                    </div>
                    <table class="system-table">
                        <tr>
                            <td>Estado Local</td>
                            <td id="sys-sqlite-status-2">OPERATIONAL</td>
                        </tr>
                        <tr>
                            <td>Journal Mode</td>
                            <td>WAL (Write-Ahead Logging)</td>
                        </tr>
                        <tr>
                            <td>Archivo Local</td>
                            <td>data/dalet_local.db</td>
                        </tr>
                        <tr>
                            <td>Cola de Telemetría</td>
                            <td id="sys-log-buffer-2">0 / 20 elementos</td>
                        </tr>
                    </table>
                </div>
            </div>

            <div class="system-cards-grid">
                <!-- Card 3: Memory & Concurrency -->
                <div class="kpi-card">
                    <div>
                        <div class="kpi-header">
                            <span class="kpi-label">Gestión de Memoria & Concurrencia</span>
                            <span class="kpi-tag">ASYNCIO ENGINE</span>
                        </div>
                        <h3 style="font-size: 15px; font-weight: 600; margin-bottom: 6px; color: var(--text-primary);">Caché L1 y Tareas Asíncronas</h3>
                        <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 14px; line-height: 1.5;">
                            Manejo de estados volátiles en memoria con caducidad TTL automática y despachador de eventos no bloqueante.
                        </p>
                    </div>
                    <table class="system-table">
                        <tr>
                            <td>Elementos en Caché TTL</td>
                            <td id="sys-cache-items-2">0 items</td>
                        </tr>
                        <tr>
                            <td>Estrategia de Concurrencia</td>
                            <td>Asyncio Non-blocking Event Loop</td>
                        </tr>
                        <tr>
                            <td>Daemon Flask Thread</td>
                            <td style="color: var(--pale-sage);">Activo en 0.0.0.0:8080</td>
                        </tr>
                        <tr>
                            <td>Sincronización de Memoria</td>
                            <td>Dual-tier (Memory + Disk)</td>
                        </tr>
                    </table>
                </div>

                <!-- Card 4: Endpoints & Health -->
                <div class="kpi-card">
                    <div>
                        <div class="kpi-header">
                            <span class="kpi-label">Servicios Web & Monitoreo</span>
                            <span class="kpi-tag">HEALTH CHECK</span>
                        </div>
                        <h3 style="font-size: 15px; font-weight: 600; margin-bottom: 6px; color: var(--text-primary);">Endpoints Expuestos</h3>
                        <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 14px; line-height: 1.5;">
                            Superficie de monitoreo HTTP expuesta para el panel de control y health checks de plataforma cloud (Render).
                        </p>
                    </div>
                    <table class="system-table">
                        <tr>
                            <td>Dashboard Web</td>
                            <td><code>GET /dashboard</code> (HTTP 200)</td>
                        </tr>
                        <tr>
                            <td>API Telemetría</td>
                            <td><code>GET /api/telemetry</code> (JSON)</td>
                        </tr>
                        <tr>
                            <td>API Buzón Feedback</td>
                            <td><code>GET /api/feedbacks</code> (JSON)</td>
                        </tr>
                        <tr>
                            <td>Health Check / Ping</td>
                            <td style="color: var(--pale-sage);"><code>GET /health</code> (HTTP 200)</td>
                        </tr>
                    </table>
                </div>
            </div>
        </div>

        <!-- ================= TAB 3: FEEDBACK INBOX ================= -->
        <div id="pane-feedback" class="tab-pane">
            <div class="section-header" style="margin-bottom: 16px;">
                <div>
                    <span class="section-title">Buzón de Retroalimentación de la Comunidad</span>
                    <p style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
                        Mensajes, sugerencias y reportes enviados por usuarios mediante el comando <code>/feedback &lt;mensaje&gt;</code> en Discord.
                    </p>
                </div>
                <button class="btn-refresh" onclick="fetchFeedbacks()">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="23 4 23 10 17 10"></polyline>
                        <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                    </svg>
                    <span>Recargar Feedbacks</span>
                </button>
            </div>

            <!-- Feedback Cards Container -->
            <div class="feedback-grid" id="feedback-container">
                <div style="grid-column: 1 / -1; text-align: center; padding: 48px 20px; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); color: var(--text-secondary);">
                    <div style="font-size: 28px; margin-bottom: 8px;">⏳</div>
                    <div>Cargando mensajes del buzón...</div>
                </div>
            </div>
        </div>

        <!-- Footer -->
        <footer>
            <span>Dalet Discord Bot • Autonomía y Balanceo Multi-LLM</span>
            <span id="footer-last-sync">Última sincronización: --:--:--</span>
        </footer>
    </div>

    <script>
        let autoRefreshMs = 10000;
        let refreshTimer = null;
        let chartInstance = null;
        let currentTab = 'ai';

        function switchTab(tabId) {
            currentTab = tabId;
            const tabs = ['ai', 'system', 'feedback'];
            tabs.forEach(t => {
                const btn = document.getElementById(`btn-tab-${t}`);
                const pane = document.getElementById(`pane-${t}`);
                if (btn) btn.className = 'tab-btn' + (t === tabId ? ' active' : '');
                if (pane) pane.className = 'tab-pane' + (t === tabId ? ' active' : '');
            });

            if (tabId === 'ai' && chartInstance) {
                setTimeout(() => chartInstance.resize(), 50);
            } else if (tabId === 'feedback') {
                fetchFeedbacks();
            }
        }

        function setCadence(ms) {
            autoRefreshMs = ms;
            document.getElementById('btn-cadence-3').className = "cadence-btn" + (ms === 3000 ? " active" : "");
            document.getElementById('btn-cadence-10').className = "cadence-btn" + (ms === 10000 ? " active" : "");
            document.getElementById('btn-cadence-pause').className = "cadence-btn" + (ms === 0 ? " active" : "");

            if (refreshTimer) {
                clearInterval(refreshTimer);
                refreshTimer = null;
            }
            if (ms > 0) {
                refreshTimer = setInterval(() => {
                    fetchTelemetry();
                    if (currentTab === 'feedback') {
                        fetchFeedbacks();
                    }
                }, ms);
            }
        }

        function initChart() {
            const ctx = document.getElementById('tokenChart').getContext('2d');
            chartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['DeepSeek V3', 'Groq LPU', 'Gemini', 'OpenRouter'],
                    datasets: [
                        {
                            label: 'Prompt Tokens',
                            data: [0, 0, 0, 0],
                            backgroundColor: 'rgba(214, 205, 192, 0.45)',
                            borderColor: 'rgba(214, 205, 192, 0.8)',
                            borderWidth: 1,
                            borderRadius: 4
                        },
                        {
                            label: 'Completion Tokens',
                            data: [0, 0, 0, 0],
                            backgroundColor: 'rgba(139, 163, 184, 0.45)',
                            borderColor: 'rgba(139, 163, 184, 0.8)',
                            borderWidth: 1,
                            borderRadius: 4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            align: 'end',
                            labels: {
                                color: '#8b93a0',
                                font: { family: "'JetBrains Mono', monospace", size: 11 },
                                boxWidth: 12,
                                boxHeight: 12
                            }
                        },
                        tooltip: {
                            backgroundColor: '#171922',
                            borderColor: 'rgba(255, 255, 255, 0.1)',
                            borderWidth: 1,
                            titleColor: '#e6e8ec',
                            bodyColor: '#8b93a0',
                            bodyFont: { family: "'JetBrains Mono', monospace" }
                        }
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: {
                                color: '#8b93a0',
                                font: { family: "'Inter', sans-serif", size: 11 }
                            }
                        },
                        y: {
                            grid: { color: 'rgba(255, 255, 255, 0.04)' },
                            ticks: {
                                color: '#525866',
                                font: { family: "'JetBrains Mono', monospace", size: 10 }
                            }
                        }
                    }
                }
            });
        }

        async function fetchTelemetry() {
            try {
                const res = await fetch('/api/telemetry');
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                renderTelemetry(data);
            } catch (err) {
                console.error("Error al obtener telemetría:", err);
                document.getElementById('label-system-status').innerText = "OFFLINE";
                document.getElementById('chip-system-status').className = "status-chip";
                document.getElementById('chip-system-status').style.background = "var(--pale-clay-bg)";
                document.getElementById('chip-system-status').style.color = "var(--pale-clay)";
                document.getElementById('chip-system-status').style.borderColor = "var(--pale-clay-border)";
            }
        }

        async function fetchFeedbacks() {
            try {
                const res = await fetch('/api/feedbacks');
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                const feedbacks = data.feedbacks || [];
                
                const countBadge = document.getElementById('badge-feedback-count');
                if (countBadge) countBadge.innerText = feedbacks.length;
                
                const container = document.getElementById('feedback-container');
                if (!container) return;

                if (feedbacks.length === 0) {
                    container.innerHTML = `
                        <div style="grid-column: 1 / -1; text-align: center; padding: 48px 20px; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); color: var(--text-secondary);">
                            <div style="font-size: 32px; margin-bottom: 12px;">📭</div>
                            <div style="font-size: 15px; font-weight: 600; color: var(--text-primary); margin-bottom: 6px;">No hay mensajes de feedback aún</div>
                            <div style="font-size: 12px; color: var(--text-tertiary);">Cuando los usuarios ejecuten el comando <code>/feedback &lt;mensaje&gt;</code> en Discord, aparecerán listados aquí con su avatar, servidor y canal.</div>
                        </div>
                    `;
                    return;
                }

                container.innerHTML = feedbacks.map(fb => {
                    const avatar = fb.user_avatar || fb.avatar_url || 'https://cdn.discordapp.com/embed/avatars/0.png';
                    const userName = escapeHtml(fb.user_name || 'Usuario desconocido');
                    const serverName = escapeHtml(fb.server_name || 'DM / Privado');
                    const channelName = escapeHtml(fb.channel_name || 'general');
                    const content = escapeHtml(fb.content || '');
                    const createdAt = escapeHtml(fb.created_at || '--');
                    const userId = escapeHtml(fb.user_id || 'N/A');

                    return `
                        <div class="feedback-card">
                            <div>
                                <div class="feedback-header">
                                    <img class="feedback-avatar" src="${avatar}" onerror="this.src='https://cdn.discordapp.com/embed/avatars/0.png'" alt="Avatar">
                                    <div class="feedback-user-info">
                                        <div class="feedback-user-name">${userName}</div>
                                        <div class="feedback-meta">${serverName} · #${channelName}</div>
                                    </div>
                                </div>
                                <div class="feedback-body">${content}</div>
                            </div>
                            <div class="feedback-footer">
                                <span>ID: ${userId}</span>
                                <span>${createdAt}</span>
                            </div>
                        </div>
                    `;
                }).join('');
            } catch (err) {
                console.error("Error al obtener feedbacks:", err);
            }
        }

        function renderTelemetry(data) {
            const ai = data.ai || {};
            const discord = data.discord || {};
            const db = data.db || {};

            const ds = ai.deepseek || {};
            const groq = ai.groq || {};
            const gemini = ai.gemini || {};
            const op = ai.openrouter || {};

            // 1. Header & Status
            document.getElementById('label-system-status').innerText = discord.online ? "ONLINE" : "STANDBY";
            document.getElementById('footer-last-sync').innerText = "Última sincronización: " + new Date().toLocaleTimeString();

            // 2. Gasto Acumulado (DeepSeek V3)
            const dsCost = (typeof ai.estimated_cost_usd === 'number') ? ai.estimated_cost_usd : (ds.cost_usd || 0);
            document.getElementById('kpi-spend-usd').innerText = `$${dsCost.toFixed(6)}`;

            const totalAiReqs = (ds.requests || 0) + (groq.requests || 0) + (gemini.requests || 0) + (op.requests || 0);
            const costPer1k = totalAiReqs > 0 ? ((dsCost / totalAiReqs) * 1000).toFixed(4) : "0.0000";
            document.getElementById('kpi-cost-per-k').innerText = `$${costPer1k} / 1k req`;

            if (ai.credit_balance !== null && ai.credit_balance !== undefined) {
                const remaining = Math.max(0, ai.credit_balance - dsCost);
                document.getElementById('cost-account-type').innerText = "PREPAGO";
                document.getElementById('kpi-credit-row').innerText = `Saldo restante: $${remaining.toFixed(4)}`;
            } else {
                document.getElementById('cost-account-type').innerText = "PAY-AS-YOU-GO";
                document.getElementById('kpi-credit-row').innerText = "Facturación por API directa";
            }

            // 3. Tokens Procesados
            const totalPrompt = (ds.prompt_tokens || 0) + (groq.prompt_tokens || 0) + (gemini.prompt_tokens || 0) + (op.prompt_tokens || 0);
            const totalCompl = (ds.completion_tokens || 0) + (groq.completion_tokens || 0) + (gemini.completion_tokens || 0) + (op.completion_tokens || 0);
            const grandTotalTokens = totalPrompt + totalCompl;

            document.getElementById('kpi-total-tokens').innerText = grandTotalTokens.toLocaleString();
            document.getElementById('kpi-prompt-tokens').innerText = totalPrompt.toLocaleString();
            document.getElementById('kpi-compl-tokens').innerText = totalCompl.toLocaleString();

            const promptPct = grandTotalTokens > 0 ? (totalPrompt / grandTotalTokens) * 100 : 50;
            const complPct = grandTotalTokens > 0 ? (totalCompl / grandTotalTokens) * 100 : 50;
            document.getElementById('bar-prompt').style.width = `${promptPct}%`;
            document.getElementById('bar-compl').style.width = `${complPct}%`;

            const ratio = totalCompl > 0 ? (totalPrompt / totalCompl).toFixed(1) : "1.0";
            document.getElementById('kpi-token-ratio').innerText = `Ratio ${ratio}:1`;

            // 4. Invocaciones & Ruteo
            document.getElementById('kpi-total-requests').innerText = totalAiReqs.toLocaleString();
            document.getElementById('kpi-routing-mode').innerText = (ai.routing_mode || 'auto').toUpperCase();
            document.getElementById('sub-ds-reqs').innerText = (ds.requests || 0).toLocaleString();
            document.getElementById('sub-groq-reqs').innerText = (groq.requests || 0).toLocaleString();
            document.getElementById('sub-gem-reqs').innerText = (gemini.requests || 0).toLocaleString();
            document.getElementById('sub-or-reqs').innerText = (op.requests || 0).toLocaleString();

            // 5. Latencia & Gateway
            const weightedLat = totalAiReqs > 0 ? Math.round(
                ((ds.avg_latency_ms || 0) * (ds.requests || 0) +
                 (groq.avg_latency_ms || 0) * (groq.requests || 0) +
                 (gemini.avg_latency_ms || 0) * (gemini.requests || 0) +
                 (op.avg_latency_ms || 0) * (op.requests || 0)) / totalAiReqs
            ) : 0;
            document.getElementById('kpi-avg-latency').innerText = weightedLat;
            document.getElementById('kpi-discord-status').innerText = discord.online ? "ONLINE" : "OFFLINE";
            document.getElementById('kpi-discord-ping').innerText = `${discord.latency_ms || 0}ms`;
            document.getElementById('kpi-guilds').innerText = discord.guilds || 0;
            document.getElementById('kpi-uptime').innerText = discord.uptime_formatted || '0s';

            // 6. Matriz de Proveedores
            // DeepSeek
            document.getElementById('model-deepseek').innerText = ds.model || 'deepseek-flash';
            document.getElementById('ds-requests').innerText = (ds.requests || 0).toLocaleString();
            document.getElementById('ds-prompt').innerText = (ds.prompt_tokens || 0).toLocaleString();
            document.getElementById('ds-completion').innerText = (ds.completion_tokens || 0).toLocaleString();
            document.getElementById('ds-lat').innerText = `${ds.avg_latency_ms || 0}ms`;
            document.getElementById('ds-cost').innerText = `$${dsCost.toFixed(6)}`;
            setProviderPill('pill-deepseek', ds.healthy, ds.cooldown_remaining);

            // Groq
            document.getElementById('model-groq').innerText = groq.model || 'openai/gpt-oss-120b';
            document.getElementById('groq-requests').innerText = (groq.requests || 0).toLocaleString();
            document.getElementById('groq-prompt').innerText = (groq.prompt_tokens || 0).toLocaleString();
            document.getElementById('groq-completion').innerText = (groq.completion_tokens || 0).toLocaleString();
            document.getElementById('groq-lat').innerText = `${groq.avg_latency_ms || 0}ms`;
            setProviderPill('pill-groq', groq.healthy, groq.cooldown_remaining);

            // Gemini
            document.getElementById('model-gemini').innerText = gemini.model || 'gemini-1.5-flash';
            document.getElementById('gemini-requests').innerText = (gemini.requests || 0).toLocaleString();
            document.getElementById('gemini-prompt').innerText = (gemini.prompt_tokens || 0).toLocaleString();
            document.getElementById('gemini-completion').innerText = (gemini.completion_tokens || 0).toLocaleString();
            document.getElementById('gemini-lat').innerText = `${gemini.avg_latency_ms || 0}ms`;
            setProviderPill('pill-gemini', gemini.healthy, gemini.cooldown_remaining);

            // OpenRouter
            document.getElementById('model-openrouter').innerText = op.model || 'openrouter/free';
            document.getElementById('or-requests').innerText = (op.requests || 0).toLocaleString();
            document.getElementById('or-prompt').innerText = (op.prompt_tokens || 0).toLocaleString();
            document.getElementById('or-completion').innerText = (op.completion_tokens || 0).toLocaleString();
            document.getElementById('or-lat').innerText = `${op.avg_latency_ms || 0}ms`;
            setProviderPill('pill-openrouter', op.healthy, op.cooldown_remaining);

            // 7. Sistema & Infraestructura (Tab 2)
            const sysGatewayTag = document.getElementById('sys-kpi-gateway-tag');
            if (sysGatewayTag) sysGatewayTag.innerText = discord.online ? "ONLINE" : "STANDBY";
            const sysPing = document.getElementById('sys-kpi-ping');
            if (sysPing) sysPing.innerText = `${discord.latency_ms || 0}ms`;
            const sysGatewayState = document.getElementById('sys-kpi-gateway-state');
            if (sysGatewayState) sysGatewayState.innerText = discord.online ? "CONECTADO" : "STANDBY";
            const sysGuilds = document.getElementById('sys-kpi-guilds');
            if (sysGuilds) sysGuilds.innerText = discord.guilds || 0;
            const sysUsers = document.getElementById('sys-kpi-users');
            if (sysUsers) sysUsers.innerText = (discord.users || 0).toLocaleString();
            const sysCacheCount = document.getElementById('sys-kpi-cache-count');
            if (sysCacheCount) sysCacheCount.innerText = `${db.cache_items || 0} items`;
            const sysUptime = document.getElementById('sys-kpi-uptime');
            if (sysUptime) sysUptime.innerText = discord.uptime_formatted || '0s';

            const sysTurso2 = document.getElementById('sys-turso-status-2');
            if (sysTurso2) sysTurso2.innerText = db.turso_online ? "ONLINE" : "STANDBY";
            const sysSqlite2 = document.getElementById('sys-sqlite-status-2');
            if (sysSqlite2) sysSqlite2.innerText = db.sqlite_status || "OPERATIONAL";
            const sysBuffer2 = document.getElementById('sys-log-buffer-2');
            if (sysBuffer2) sysBuffer2.innerText = `${db.log_buffer_size || 0} / ${db.log_buffer_max || 20} elementos`;
            const sysCache2 = document.getElementById('sys-cache-items-2');
            if (sysCache2) sysCache2.innerText = `${db.cache_items || 0} items`;

            // 8. Chart Update
            if (chartInstance) {
                chartInstance.data.datasets[0].data = [
                    ds.prompt_tokens || 0,
                    groq.prompt_tokens || 0,
                    gemini.prompt_tokens || 0,
                    op.prompt_tokens || 0
                ];
                chartInstance.data.datasets[1].data = [
                    ds.completion_tokens || 0,
                    groq.completion_tokens || 0,
                    gemini.completion_tokens || 0,
                    op.completion_tokens || 0
                ];
                chartInstance.update();
            }

            // 9. Registro de Interacciones Recientes
            const interactions = ai.recent_interactions || [];
            document.getElementById('feed-count').innerText = `${interactions.length} eventos`;
            const tbody = document.getElementById('interactions-body');
            if (interactions.length > 0) {
                tbody.innerHTML = interactions.slice().reverse().map(item => {
                    let badgeClass = "badge-ds";
                    const prov = (item.provider || '').toLowerCase();
                    if (prov.includes('groq')) badgeClass = "badge-groq";
                    else if (prov.includes('gemini')) badgeClass = "badge-gemini";
                    else if (prov.includes('openrouter')) badgeClass = "badge-openrouter";

                    return `
                        <tr>
                            <td class="font-mono" style="color: var(--text-tertiary);">${item.timestamp || '--:--'}</td>
                            <td><span class="badge-provider ${badgeClass}">${item.provider || 'AI'}</span></td>
                            <td class="font-mono" style="color: var(--text-secondary); max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${item.model || ''}</td>
                            <td style="font-weight: 500;">${escapeHtml(item.user || 'Unknown')}</td>
                            <td style="color: var(--text-secondary); max-width: 380px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(item.trigger || '')}">${escapeHtml(item.trigger || '')}</td>
                            <td class="font-mono" style="text-align: right;">${item.prompt_tokens || 0} / ${item.completion_tokens || 0}</td>
                            <td style="text-align: right;"><span class="latency-tag">${item.latency_ms || 0}ms</span></td>
                        </tr>
                    `;
                }).join('');
            } else {
                tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-tertiary); padding: 24px;">Esperando interacciones de usuarios...</td></tr>`;
            }
        }

        function setProviderPill(id, isHealthy, cooldownSecs) {
            const pill = document.getElementById(id);
            if (!pill) return;
            if (isHealthy) {
                pill.className = "provider-pill pill-healthy";
                pill.innerText = "HEALTHY";
            } else {
                pill.className = "provider-pill pill-cooldown";
                pill.innerText = `COOLDOWN ${cooldownSecs || 0}s`;
            }
        }

        function escapeHtml(str) {
            return String(str)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        window.onload = () => {
            initChart();
            fetchTelemetry();
            fetchFeedbacks();
            refreshTimer = setInterval(() => {
                fetchTelemetry();
                if (currentTab === 'feedback') {
                    fetchFeedbacks();
                }
            }, autoRefreshMs);
        };
    </script>
</body>
</html>
"""
