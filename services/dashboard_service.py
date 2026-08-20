import time
import os
import logging
from database.turso_client import TursoClient
from database.sqlite_manager import SQLiteManager

logger = logging.getLogger("dalet.services.dashboard")

class DashboardService:
    """
    Servicio de Dashboard y Telemetría en tiempo real para Dalet.
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

        # 2. AI & Token Telemetry (desde NLPService)
        ai_stats = {}
        if bot and hasattr(bot, "nlp_service") and bot.nlp_service:
            ai_stats = bot.nlp_service.get_telemetry()
        else:
            ai_stats = {
                "routing_mode": os.getenv("AI_ROUTING_MODE", "auto"),
                "gemini": {"model": "gemini-2.5-flash", "healthy": True, "requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "avg_latency_ms": 0, "errors": 0},
                "groq": {"model": "llama-3.3-70b-versatile", "healthy": True, "requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "avg_latency_ms": 0, "errors": 0},
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
            "turso_status": "ONLINE (libSQL HTTP Pipeline)" if turso_online else "OFFLINE (Fallback Activo)",
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
        """Genera el HTML moderno del Dashboard con Chart.js y estilos responsivos."""
        return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dalet • System Telemetry Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg: #0e0e11;
            --surface: #17171c;
            --surface-hover: #1f1f26;
            --border: #272730;
            --pink: #ff69b4;
            --pink-glow: rgba(255, 105, 180, 0.15);
            --emerald: #22c55e;
            --emerald-glow: rgba(34, 197, 94, 0.15);
            --amber: #f59e0b;
            --sky: #0ea5e9;
            --purple: #a855f7;
            --text: #f4f4f5;
            --text-muted: #a1a1aa;
            --text-dark: #71717a;
            --radius: 14px;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Plus Jakarta Sans', sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            padding: 24px;
            overflow-x: hidden;
        }

        .container { max-width: 1380px; margin: 0 auto; }

        /* Top Header */
        header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: var(--surface);
            border: 1px solid var(--border);
            padding: 18px 26px;
            border-radius: var(--radius);
            margin-bottom: 24px;
            backdrop-filter: blur(10px);
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 14px;
        }
        .brand-icon {
            width: 44px;
            height: 44px;
            background: linear-gradient(135deg, var(--pink), var(--purple));
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 22px;
            color: #fff;
            box-shadow: 0 0 20px var(--pink-glow);
        }
        .brand-text h1 { font-size: 20px; font-weight: 800; letter-spacing: -0.5px; }
        .brand-text p { font-size: 13px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .pulse-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            background: var(--emerald-glow);
            border: 1px solid rgba(34, 197, 94, 0.3);
            color: var(--emerald);
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .pulse-dot {
            width: 8px;
            height: 8px;
            background: var(--emerald);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
        }

        .btn {
            background: var(--surface-hover);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 8px 16px;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            font-family: inherit;
        }
        .btn:hover { background: var(--border); color: #fff; }
        .btn.active { background: var(--pink); color: #fff; border-color: var(--pink); box-shadow: 0 0 15px var(--pink-glow); }

        /* Grid Layout */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 18px;
            margin-bottom: 24px;
        }

        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 22px;
            position: relative;
            overflow: hidden;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }
        .card:hover { border-color: rgba(255, 105, 180, 0.3); }

        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
        }
        .card-title {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .card-tag {
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
            background: var(--surface-hover);
            border: 1px solid var(--border);
            color: var(--text-muted);
        }

        .metric-value {
            font-size: 32px;
            font-weight: 800;
            letter-spacing: -1px;
            color: #fff;
            margin-bottom: 8px;
            font-family: 'JetBrains Mono', monospace;
        }
        .metric-sub {
            font-size: 13px;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 6px;
        }

        /* Accent Top Bars */
        .card::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: var(--accent-bar, var(--border));
        }
        .card-pink { --accent-bar: var(--pink); }
        .card-sky { --accent-bar: var(--sky); }
        .card-emerald { --accent-bar: var(--emerald); }
        .card-amber { --accent-bar: var(--amber); }

        /* Two Column Section */
        .dashboard-row {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
        }
        @media (max-width: 980px) {
            .dashboard-row { grid-template-columns: 1fr; }
        }

        .chart-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 24px;
        }
        .chart-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .chart-title { font-size: 16px; font-weight: 700; }
        .chart-container { position: relative; height: 260px; width: 100%; }

        /* Provider Cards Breakdown */
        .provider-box {
            background: var(--surface-hover);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 14px;
        }
        .provider-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .provider-name {
            font-size: 15px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .provider-status {
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
        }
        .status-ok { background: var(--emerald-glow); color: var(--emerald); border: 1px solid rgba(34, 197, 94, 0.3); }
        .status-warn { background: rgba(245, 158, 11, 0.15); color: var(--amber); border: 1px solid rgba(245, 158, 11, 0.3); }

        .token-row {
            display: flex;
            justify-content: space-between;
            font-size: 13px;
            color: var(--text-muted);
            margin-top: 6px;
            font-family: 'JetBrains Mono', monospace;
        }
        .token-row span:last-child { color: var(--text); font-weight: 600; }

        /* Tables & Feeds */
        .table-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 24px;
            margin-bottom: 24px;
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 13px;
        }
        th {
            padding: 12px 16px;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--border);
        }
        td {
            padding: 14px 16px;
            border-bottom: 1px solid var(--border);
            color: var(--text);
        }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: var(--surface-hover); }

        .tag-model {
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            padding: 3px 8px;
            background: var(--surface-hover);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--pink);
        }

        .latency-badge {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            color: var(--emerald);
        }

        footer {
            text-align: center;
            font-size: 12px;
            color: var(--text-dark);
            margin-top: 30px;
            font-family: 'JetBrains Mono', monospace;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand">
                <div class="brand-icon">D</div>
                <div class="brand-text">
                    <h1>Dalet • Telemetry Dashboard</h1>
                    <p>SMART LOAD BALANCER & SYSTEM MONITOR</p>
                </div>
            </div>
            <div class="header-actions">
                <div class="pulse-badge">
                    <div class="pulse-dot"></div>
                    <span id="gateway-status">ONLINE</span>
                </div>
                <button class="btn active" id="btn-autorefresh" onclick="toggleAutoRefresh()">Auto-refresh (5s)</button>
                <button class="btn" onclick="fetchTelemetry()">Actualizar</button>
            </div>
        </header>

        <!-- Top Metrics Grid -->
        <div class="stats-grid">
            <div class="card card-pink">
                <div class="card-header">
                    <span class="card-title">Consumo de Tokens</span>
                    <span class="card-tag" id="routing-mode-tag">AUTO</span>
                </div>
                <div class="metric-value" id="total-tokens">0</div>
                <div class="metric-sub">
                    <span>Prompt: <b id="prompt-tokens">0</b></span> • <span>Resp: <b id="completion-tokens">0</b></span>
                </div>
            </div>

            <div class="card card-emerald">
                <div class="card-header">
                    <span class="card-title">Interacciones de IA</span>
                    <span class="card-tag">TOTAL</span>
                </div>
                <div class="metric-value" id="total-ai-requests">0</div>
                <div class="metric-sub">
                    <span>Gemini: <b id="gemini-reqs">0</b></span> • <span>Groq: <b id="groq-reqs">0</b></span>
                </div>
            </div>

            <div class="card card-sky">
                <div class="card-header">
                    <span class="card-title">Latencia Promedio</span>
                    <span class="card-tag">IA ENGINE</span>
                </div>
                <div class="metric-value" id="avg-latency">0<small style="font-size: 16px;">ms</small></div>
                <div class="metric-sub">
                    <span>Groq: <b id="groq-lat">0ms</b></span> • <span>Gemini: <b id="gemini-lat">0ms</b></span>
                </div>
            </div>

            <div class="card card-amber">
                <div class="card-header">
                    <span class="card-title">Discord & Uptime</span>
                    <span class="card-tag" id="discord-ping">0ms</span>
                </div>
                <div class="metric-value" id="uptime-str" style="font-size: 24px; padding-top: 6px;">0s</div>
                <div class="metric-sub">
                    <span><b id="guilds-count">0</b> Servidores</span> • <span><b id="users-count">0</b> Miembros</span>
                </div>
            </div>
        </div>

        <!-- Middle Section: Chart & Provider Breakdown -->
        <div class="dashboard-row">
            <div class="chart-card">
                <div class="chart-header">
                    <span class="chart-title">Distribución de Tráfico y Tokens</span>
                    <span class="card-tag">Gemini vs Groq</span>
                </div>
                <div class="chart-container">
                    <canvas id="tokensChart"></canvas>
                </div>
            </div>

            <div class="chart-card">
                <div class="chart-header">
                    <span class="chart-title">Estado de Proveedores</span>
                    <span class="card-tag">CIRCUIT BREAKER</span>
                </div>

                <!-- Groq Provider Box -->
                <div class="provider-box">
                    <div class="provider-header">
                        <span class="provider-name">⚡ Groq (LPUs)</span>
                        <span class="provider-status status-ok" id="groq-status-badge">HEALTHY</span>
                    </div>
                    <div class="token-row"><span>Modelo</span><span id="groq-model-name">-</span></div>
                    <div class="token-row"><span>Tokens Totales</span><span id="groq-total-tokens">0</span></div>
                    <div class="token-row"><span>Latencia Media</span><span id="groq-avg-lat">0ms</span></div>
                </div>

                <!-- Gemini Provider Box -->
                <div class="provider-box">
                    <div class="provider-header">
                        <span class="provider-name">🔵 Google Gemini</span>
                        <span class="provider-status status-ok" id="gemini-status-badge">HEALTHY</span>
                    </div>
                    <div class="token-row"><span>Modelo</span><span id="gemini-model-name">-</span></div>
                    <div class="token-row"><span>Tokens Totales</span><span id="gemini-total-tokens">0</span></div>
                    <div class="token-row"><span>Latencia Media</span><span id="gemini-avg-lat">0ms</span></div>
                </div>

                <!-- OpenRouter Provider Box -->
                <div class="provider-box" style="margin-bottom: 0;">
                    <div class="provider-header">
                        <span class="provider-name">🌐 OpenRouter (Free Tier)</span>
                        <span class="provider-status status-ok" id="openrouter-status-badge">HEALTHY</span>
                    </div>
                    <div class="token-row"><span>Modelo</span><span id="openrouter-model-name">-</span></div>
                    <div class="token-row"><span>Tokens Totales</span><span id="openrouter-total-tokens">0</span></div>
                    <div class="token-row"><span>Latencia Media</span><span id="openrouter-avg-lat">0ms</span></div>
                </div>
            </div>
        </div>

        <!-- Bottom Table: Live Feed -->
        <div class="table-card">
            <div class="chart-header">
                <span class="chart-title">Últimas Interacciones de IA en Tiempo Real</span>
                <span class="card-tag">LIVE FEED</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Hora</th>
                        <th>Proveedor</th>
                        <th>Modelo</th>
                        <th>Usuario</th>
                        <th>Mensaje</th>
                        <th>Tokens (In/Out)</th>
                        <th>Latencia</th>
                    </tr>
                </thead>
                <tbody id="interactions-body">
                    <tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Esperando interacciones de IA...</td></tr>
                </tbody>
            </table>
        </div>

        <footer>
            Dalet • Antigravity Agentic Bot Framework • Sistema de Persistencia Híbrida libSQL + SQLite
        </footer>
    </div>

    <script>
        let autoRefresh = true;
        let refreshInterval = null;
        let chartInstance = null;

        function initChart() {
            const ctx = document.getElementById('tokensChart').getContext('2d');
            chartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['Groq (LPUs)', 'Gemini Flash', 'OpenRouter Free'],
                    datasets: [
                        {
                            label: 'Prompt Tokens',
                            data: [0, 0, 0],
                            backgroundColor: 'rgba(255, 105, 180, 0.7)',
                            borderRadius: 6
                        },
                        {
                            label: 'Completion Tokens',
                            data: [0, 0, 0],
                            backgroundColor: 'rgba(14, 165, 233, 0.7)',
                            borderRadius: 6
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { grid: { color: '#272730' }, ticks: { color: '#a1a1aa' } },
                        y: { grid: { color: '#272730' }, ticks: { color: '#a1a1aa' } }
                    },
                    plugins: {
                        legend: { labels: { color: '#f4f4f5' } }
                    }
                }
            });
        }

        async function fetchTelemetry() {
            try {
                const res = await fetch('/api/telemetry');
                if (!res.ok) return;
                const data = await res.json();
                updateUI(data);
            } catch (e) {
                console.error("Error fetching telemetry:", e);
            }
        }

        function updateUI(data) {
            const ai = data.ai || {};
            const gemini = ai.gemini || {};
            const groq = ai.groq || {};
            const openrouter = ai.openrouter || {};
            const discord = data.discord || {};

            // Discord Card
            document.getElementById('discord-ping').innerText = `${discord.latency_ms}ms`;
            document.getElementById('uptime-str').innerText = discord.uptime_formatted || '0s';
            document.getElementById('guilds-count').innerText = discord.guilds || 0;
            document.getElementById('users-count').innerText = discord.users || 0;
            document.getElementById('gateway-status').innerText = discord.online ? 'ONLINE' : 'DISCONNECTED';

            // AI Card
            const totalTokens = (gemini.total_tokens || 0) + (groq.total_tokens || 0) + (openrouter.total_tokens || 0);
            const totalPrompt = (gemini.prompt_tokens || 0) + (groq.prompt_tokens || 0) + (openrouter.prompt_tokens || 0);
            const totalCompl = (gemini.completion_tokens || 0) + (groq.completion_tokens || 0) + (openrouter.completion_tokens || 0);
            const totalReqs = (gemini.requests || 0) + (groq.requests || 0) + (openrouter.requests || 0);

            document.getElementById('total-tokens').innerText = totalTokens.toLocaleString();
            document.getElementById('prompt-tokens').innerText = totalPrompt.toLocaleString();
            document.getElementById('completion-tokens').innerText = totalCompl.toLocaleString();
            document.getElementById('routing-mode-tag').innerText = (ai.routing_mode || 'AUTO').toUpperCase();

            document.getElementById('total-ai-requests').innerText = totalReqs.toLocaleString();
            document.getElementById('gemini-reqs').innerText = (gemini.requests || 0).toLocaleString();
            document.getElementById('groq-reqs').innerText = (groq.requests || 0).toLocaleString();

            // Latencies
            document.getElementById('gemini-lat').innerText = `${gemini.avg_latency_ms || 0}ms`;
            document.getElementById('groq-lat').innerText = `${groq.avg_latency_ms || 0}ms`;
            const overallAvg = totalReqs > 0 ? Math.round(((gemini.avg_latency_ms || 0) * (gemini.requests || 0) + (groq.avg_latency_ms || 0) * (groq.requests || 0) + (openrouter.avg_latency_ms || 0) * (openrouter.requests || 0)) / totalReqs) : 0;
            document.getElementById('avg-latency').innerHTML = `${overallAvg}<small style="font-size: 16px;">ms</small>`;

            // Provider Boxes
            document.getElementById('groq-model-name').innerText = groq.model || 'openai/gpt-oss-120b';
            document.getElementById('groq-total-tokens').innerText = (groq.total_tokens || 0).toLocaleString();
            document.getElementById('groq-avg-lat').innerText = `${groq.avg_latency_ms || 0}ms`;
            const groqBadge = document.getElementById('groq-status-badge');
            if (groq.healthy) {
                groqBadge.className = "provider-status status-ok";
                groqBadge.innerText = "HEALTHY";
            } else {
                groqBadge.className = "provider-status status-warn";
                groqBadge.innerText = `COOLDOWN (${groq.cooldown_remaining}s)`;
            }

            document.getElementById('gemini-model-name').innerText = gemini.model || 'gemini-2.5-flash';
            document.getElementById('gemini-total-tokens').innerText = (gemini.total_tokens || 0).toLocaleString();
            document.getElementById('gemini-avg-lat').innerText = `${gemini.avg_latency_ms || 0}ms`;
            const geminiBadge = document.getElementById('gemini-status-badge');
            if (gemini.healthy) {
                geminiBadge.className = "provider-status status-ok";
                geminiBadge.innerText = "HEALTHY";
            } else {
                geminiBadge.className = "provider-status status-warn";
                geminiBadge.innerText = `COOLDOWN (${gemini.cooldown_remaining}s)`;
            }

            document.getElementById('openrouter-model-name').innerText = openrouter.model || 'openrouter/free';
            document.getElementById('openrouter-total-tokens').innerText = (openrouter.total_tokens || 0).toLocaleString();
            document.getElementById('openrouter-avg-lat').innerText = `${openrouter.avg_latency_ms || 0}ms`;
            const openrouterBadge = document.getElementById('openrouter-status-badge');
            if (openrouter.healthy) {
                openrouterBadge.className = "provider-status status-ok";
                openrouterBadge.innerText = "HEALTHY";
            } else {
                openrouterBadge.className = "provider-status status-warn";
                openrouterBadge.innerText = `COOLDOWN (${openrouter.cooldown_remaining}s)`;
            }

            // Update Chart
            if (chartInstance) {
                chartInstance.data.datasets[0].data = [groq.prompt_tokens || 0, gemini.prompt_tokens || 0, openrouter.prompt_tokens || 0];
                chartInstance.data.datasets[1].data = [groq.completion_tokens || 0, gemini.completion_tokens || 0, openrouter.completion_tokens || 0];
                chartInstance.update();
            }

            // Update Table
            const tbody = document.getElementById('interactions-body');
            const items = ai.recent_interactions || [];
            if (items.length > 0) {
                tbody.innerHTML = items.slice().reverse().map(it => `
                    <tr>
                        <td style="font-family: 'JetBrains Mono', monospace; color: var(--text-muted);">${it.timestamp}</td>
                        <td><b>${it.provider}</b></td>
                        <td><span class="tag-model">${it.model}</span></td>
                        <td>${it.user}</td>
                        <td style="color: var(--text-muted); max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${it.trigger}</td>
                        <td style="font-family: 'JetBrains Mono', monospace;">${it.prompt_tokens} / ${it.completion_tokens}</td>
                        <td><span class="latency-badge">${it.latency_ms}ms</span></td>
                    </tr>
                `).join('');
            }
        }

        function toggleAutoRefresh() {
            autoRefresh = !autoRefresh;
            const btn = document.getElementById('btn-autorefresh');
            if (autoRefresh) {
                btn.className = "btn active";
                btn.innerText = "Auto-refresh (5s)";
                startInterval();
            } else {
                btn.className = "btn";
                btn.innerText = "Auto-refresh (OFF)";
                clearInterval(refreshInterval);
            }
        }

        function startInterval() {
            if (refreshInterval) clearInterval(refreshInterval);
            refreshInterval = setInterval(fetchTelemetry, 5000);
        }

        window.onload = () => {
            initChart();
            fetchTelemetry();
            startInterval();
        };
    </script>
</body>
</html>
"""
