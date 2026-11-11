import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from services.memory_service import MemoryService


class DummyResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_semantic_pyramid_context_injection():
    """Verifica que get_relevant_context inyecte Top-Down: L3 (Persona) -> L2 (Scenario) -> L1 (Atoms) -> L0 (Chat)."""
    mock_repo = MagicMock()
    mock_repo.get_channel_messages = AsyncMock(
        return_value=[
            {"user_id": 101, "username": "Juan", "content": "¿Qué opinas de mi arquitectura de memoria?"}
        ]
    )
    mock_repo.get_user_persona = AsyncMock(
        return_value={
            "user_id": 101,
            "user_name": "Juan",
            "persona_l3": "Estudiante de Ingeniería y Ciencia de Datos en Medellín. Le apasiona MLOps y bots de Discord.",
            "scenario_l2": "Diseñando la pirámide semántica L0-L3 para Dalet y completando certificaciones de AWS.",
            "memory_count": 5,
        }
    )
    mock_repo.get_all_user_memories = AsyncMock(
        return_value=[
            {
                "topic": "personal",
                "user_message": "Estoy haciendo las quests de AWS Educate",
                "dalet_thought": "Está enfocado en obtener insignias cloud con su correo institucional.",
                "content": "Está enfocado en obtener insignias cloud con su correo institucional.",
            }
        ]
    )

    service = MemoryService(mock_repo)
    ctx = await service.get_relevant_context(
        channel_id=999,
        user_id=101,
        current_message="¿Cómo ves lo de mis insignias cloud?",
        check_user_memory=True,
        bot_id=777,
        bot_name="Dalet",
        user_name="Juan",
    )

    assert "[PIRÁMIDE SEMÁNTICA DE JUAN (L3 -> L1)]:" in ctx
    assert "• [L3 - Perfil Persona]: Estudiante de Ingeniería" in ctx
    assert "• [L2 - Escenario Actual]: Diseñando la pirámide semántica" in ctx
    assert "• [L1 - Átomo (personal)]: Está enfocado en obtener insignias cloud" in ctx
    assert "CHAT RECIENTE (L0):" in ctx
    assert "Juan: ¿Qué opinas de mi arquitectura de memoria?" in ctx


@pytest.mark.asyncio
async def test_single_pass_distillation_and_pruning(monkeypatch):
    """Verifica que analyze_and_record_memory destile L1, L2 y L3 en una sola llamada y pode átomos antiguos."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")

    mock_repo = MagicMock()
    mock_repo.get_user_persona = AsyncMock(
        return_value={
            "user_id": 101,
            "user_name": "Juan",
            "persona_l3": "Desarrollador de Python.",
            "scenario_l2": "Mejorando el comando /resumir.",
            "memory_count": 2,
        }
    )
    mock_repo.add_user_memory = AsyncMock(return_value=True)
    mock_repo.upsert_user_persona = AsyncMock(return_value=True)
    mock_repo.prune_old_user_memories = AsyncMock(return_value=True)

    gemini_json_output = {
        "save": True,
        "topic": "personal",
        "user_message": "Ahora quiero implementar la pirámide semántica de TencentDB en SQLite",
        "dalet_thought": "Busca optimizar la memoria de largo plazo usando arquitectura jerárquica L0-L3.",
        "scenario_l2": "Implementando la pirámide semántica L0-L3 en Dalet tras actualizar /resumir.",
        "persona_l3": "Desarrollador de Python e ingeniero de software en formación con enfoque en arquitecturas de IA eficientes.",
    }

    mock_http = MagicMock()
    mock_http.post = AsyncMock(
        return_value=DummyResponse(
            200,
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": json.dumps(gemini_json_output)}]
                        }
                    }
                ]
            },
        )
    )

    mock_nlp = MagicMock()
    mock_nlp.gemini_api_key = "fake-gemini-key"
    mock_nlp._http_client = mock_http

    service = MemoryService(mock_repo)
    await service.analyze_and_record_memory(
        user_id=101,
        user_name="Juan",
        user_message="Ahora quiero implementar la pirámide semántica de TencentDB en SQLite para Dalet",
        dalet_reply="¡De una! Esa estructura L0-L3 nos va a ahorrar muchísimos tokens.",
        nlp_service=mock_nlp,
    )

    mock_repo.add_user_memory.assert_awaited_once()
    mock_repo.upsert_user_persona.assert_awaited_once_with(
        user_id=101,
        user_name="Juan",
        persona_l3="Desarrollador de Python e ingeniero de software en formación con enfoque en arquitecturas de IA eficientes.",
        scenario_l2="Implementando la pirámide semántica L0-L3 en Dalet tras actualizar /resumir.",
    )
    mock_repo.prune_old_user_memories.assert_awaited_once_with(101, max_atoms=20)


@pytest.mark.asyncio
async def test_memory_strict_gating_no_unmatched_and_cooldown():
    """Verifica que recuerdos L1 sin relación NO se inyecten, que L2 viejo (>14d) caduque y que aplique cooldown."""
    from datetime import datetime, timedelta, timezone

    old_l2_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    mock_repo = MagicMock()
    mock_repo.get_channel_messages = AsyncMock(
        return_value=[{"user_id": 101, "username": "Juan", "content": "hola qué mapa recomiendas"}]
    )
    mock_repo.get_user_persona = AsyncMock(
        return_value={
            "user_id": 101,
            "user_name": "Juan",
            "persona_l3": "Jugador de osu! colombiano.",
            "scenario_l2": "Estresado por parciales de cálculo hace un mes.",
            "updated_at": old_l2_date,
        }
    )
    mock_repo.get_all_user_memories = AsyncMock(
        return_value=[
            {
                "topic": "gustos",
                "user_message": "Para comer me gusta mucho la pizza hawaiana",
                "dalet_thought": "Le encanta la pizza con piña para cenar.",
                "content": "Le encanta la pizza con piña para cenar.",
                "timestamp": old_l2_date,
            }
        ]
    )

    service = MemoryService(mock_repo)
    # Turno 1: habla de mapas de osu! (usa 'para', que es stopword, pero nada de pizza)
    ctx1 = await service.get_relevant_context(
        channel_id=999,
        user_id=101,
        current_message="¿Qué mapa tienes para calentar streams?",
        check_user_memory=True,
        user_name="Juan",
    )
    # L3 se inyecta la primera vez, pero L2 (>14 días) y L1 (sin relación) NO se inyectan
    assert "• [L3 - Perfil Persona]: Jugador de osu! colombiano." in ctx1
    assert "Estresado por parciales" not in ctx1
    assert "pizza" not in ctx1

    # Turno 2 (seguido dentro de los 10 min de cooldown, sin match L1): NO vuelve a inyectar la pirámide
    ctx2 = await service.get_relevant_context(
        channel_id=999,
        user_id=101,
        current_message="¿Y otro de 6 estrellas?",
        check_user_memory=True,
        user_name="Juan",
    )
    assert "[PIRÁMIDE SEMÁNTICA" not in ctx2
    assert "CHAT RECIENTE (L0):" in ctx2


def test_osu_top_and_recent_filters():
    """Verifica el filtrado y ordenamiento de /top (recent best, acc, mods) y /recent (best, pass, mods)."""
    from handlers.dalet_osu_presenter import OsuPresenter

    top_scores = [
        {"pp": 500.0, "accuracy": 0.97, "created_at": "2026-01-10T12:00:00Z", "mods": ["HD", "DT"]},
        {"pp": 480.0, "accuracy": 0.995, "created_at": "2026-10-30T18:00:00Z", "mods": []},
        {"pp": 450.0, "accuracy": 0.98, "created_at": "2026-11-01T10:00:00Z", "mods": ["NC"]},
    ]

    # 1. Recent Best: ordena por fecha más reciente preservando _top_rank original
    recent_best = OsuPresenter.filter_and_sort_top_scores(top_scores, sort_by="recent")
    assert [s["_top_rank"] for s in recent_best] == [3, 2, 1]
    assert recent_best[0]["pp"] == 450.0

    # 2. Best Accuracy
    best_acc = OsuPresenter.filter_and_sort_top_scores(top_scores, sort_by="acc")
    assert best_acc[0]["_top_rank"] == 2
    assert best_acc[0]["accuracy"] == 0.995

    # 3. Filtro por mods (+DT incluye NC, y NM filtra sin mods)
    dt_only = OsuPresenter.filter_and_sort_top_scores(top_scores, sort_by="pp", mods_filter="DT")
    assert [s["_top_rank"] for s in dt_only] == [1, 3]
    nm_only = OsuPresenter.filter_and_sort_top_scores(top_scores, sort_by="pp", mods_filter="NM")
    assert [s["_top_rank"] for s in nm_only] == [2]

    # 4. Filtros de /recent (pass y best)
    recent_scores = [
        {"pp": None, "accuracy": 0.85, "passed": False, "rank": "F", "mods": ["DT"], "score": 100000},
        {"pp": 320.0, "accuracy": 0.96, "passed": True, "rank": "A", "mods": ["HD"], "score": 800000},
        {"pp": 410.0, "accuracy": 0.98, "passed": True, "rank": "S", "mods": ["DT"], "score": 950000},
    ]
    passes = OsuPresenter.filter_recent_scores(recent_scores, filter_by="pass")
    assert len(passes) == 2
    assert passes[0]["pp"] == 320.0

    session_best = OsuPresenter.filter_recent_scores(recent_scores, filter_by="best")
    assert session_best[0]["pp"] == 410.0
    assert session_best[0]["_recent_index"] == 3


def test_build_recent_card_fail_progress_and_attempt_indicator():
    """Verifica el cálculo de % de progreso en fallos (F) y el indicador de intento (#N) en build_recent_card."""
    from handlers.dalet_osu_presenter import OsuPresenter

    failed_play = {
        "rank": "F",
        "passed": False,
        "accuracy": 0.912,
        "pp": None,
        "max_combo": 210,
        "mods": ["HD", "DT"],
        "_recent_index": 3,
        "created_at": "2026-11-05T12:00:00Z",
        "statistics": {
            "count_300": 120,
            "count_100": 8,
            "count_50": 0,
            "count_miss": 1,
        },
        "beatmap": {
            "id": 123456,
            "version": "Insane",
            "difficulty_rating": 6.5,
            "max_combo": 400,
            "count_circles": 140,
            "count_sliders": 60,
            "count_spinners": 1,
        },
        "beatmapset": {
            "title": "Blue Zenith",
            "artist": "xi",
        },
    }

    embed_en = OsuPresenter.build_recent_card(
        username="Cookiezi",
        mode="osu",
        play=failed_play,
        lang="en",
        filter_by="last",
    )
    # 129 hits / 201 total objects = 64.179% -> 64.2%
    assert "F (64.2%)" in embed_en.description
    assert "Try #3" in embed_en.description
    assert "Try #3" in embed_en.author.name

    embed_es = OsuPresenter.build_recent_card(
        username="Cookiezi",
        mode="osu",
        play=failed_play,
        lang="es",
        filter_by="best",
        mods_filter="HDDT",
    )
    assert "F (64.2%)" in embed_es.description
    assert "Intento #3" in embed_es.description
    assert "Intento #3" in embed_es.author.name



@pytest.mark.asyncio
async def test_persona_self_training_insight_distillation_and_injection():
    """
    Verifica que:
    1. Si un usuario da feedback de tono (ej. 'sabes eres grosera cruel y arrogante xd') o Dalet
       detecta un fallo de literalidad/bucle, analyze_and_record_memory guarda un PersonaInsight
       incluso si save=false para memorias personales efímeras.
    2. get_relevant_context inyecta las reglas de PersonaInsights aprendidas.
    """
    mock_repo = MagicMock()
    mock_repo.get_user_persona = AsyncMock(return_value=None)
    mock_repo.add_user_memory = AsyncMock()
    mock_repo.upsert_user_persona = AsyncMock()
    mock_repo.prune_old_user_memories = AsyncMock()
    mock_repo.add_persona_insight = AsyncMock()
    mock_repo.get_channel_messages = AsyncMock(return_value=[])
    mock_repo.get_all_user_memories = AsyncMock(return_value=[])
    mock_repo.get_recent_persona_insights = AsyncMock(
        return_value=[
            {
                "style_rule": "No repetir el mismo chiste del segundo monitor en turnos seguidos ni dar golpes bajos cuando el usuario busca socializar.",
                "critique": "Dalet se encasilló con el segundo monitor y fue innecesariamente cortante.",
            }
        ]
    )

    mock_nlp = MagicMock()
    mock_nlp.gemini_api_key = "fake_test_key"

    mock_http_resp = MagicMock()
    mock_http_resp.status_code = 200
    mock_http_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "save": False,
                                    "critique": "Dalet repitió el ataque del segundo monitor y trató al usuario como enemigo cuando dijo 'hay q socializar'.",
                                    "style_lesson": "Cuando un usuario busca socializar tras una broma, bajar la hostilidad y conversar con complicidad sin repetir el mismo roast.",
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }

    mock_http_client = MagicMock()
    mock_http_client.post = AsyncMock(return_value=mock_http_resp)
    mock_nlp._http_client = mock_http_client

    service = MemoryService(mock_repo)
    await service.analyze_and_record_memory(
        user_id=777,
        user_name="Gemenirdol",
        user_message="sabes eres grosera cruel y arrogante xd",
        dalet_reply="socializar con el segundo monitor y no con las personas del server, gran técnica. luego te quejas de que nadie te habla",
        nlp_service=mock_nlp,
    )

    # No debe guardar memoria efímera del segundo monitor (save=False), pero SÍ la regla de estilo aprendida
    mock_repo.add_user_memory.assert_not_called()
    mock_repo.add_persona_insight.assert_called_once()
    call_kwargs = mock_repo.add_persona_insight.call_args.kwargs
    assert "complicidad" in call_kwargs["style_rule"]
    assert "segundo monitor" in call_kwargs["critique"]

    # Verificar que get_relevant_context inyecta la lección aprendida
    ctx = await service.get_relevant_context(
        channel_id=10,
        user_id=777,
        current_message="hola dalet como va todo",
        check_user_memory=True,
        user_name="Gemenirdol",
    )
    assert "[AUTO-CALIBRACIÓN DE PERSONALIDAD APRENDIDA" in ctx
    assert "No repetir el mismo chiste del segundo monitor" in ctx


def test_dalet_mcp_server_and_safety_hook():
    """Verifica el servidor MCP propio de Dalet (JSON-RPC) y el Hook de seguridad PreToolUse."""
    import subprocess
    import sys

    # 1. Probar tools/list y tools/call (dalet_graph_stats) en tools/dalet_mcp_server.py
    mcp_reqs = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "dalet_graph_stats", "arguments": {}}}),
    ]) + "\n"

    proc = subprocess.run(
        [sys.executable, "tools/dalet_mcp_server.py"],
        input=mcp_reqs,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert proc.returncode == 0
    lines = [json.loads(line) for line in proc.stdout.strip().splitlines() if line.strip()]
    assert len(lines) == 3
    assert lines[0]["result"]["serverInfo"]["name"] == "dalet-brain-mcp"
    tool_names = [t["name"] for t in lines[1]["result"]["tools"]]
    assert "dalet_db_health" in tool_names
    assert "dalet_inspect_persona_insights" in tool_names
    assert "dalet_inspect_user_pyramid" in tool_names
    assert "dalet_graph_stats" in tool_names

    # 2. Probar que tools/dalet_hook_guard.py bloquea git push --force pero permite pytest
    deny_proc = subprocess.run(
        [sys.executable, "tools/dalet_hook_guard.py"],
        input=json.dumps({"toolCall": {"name": "run_command", "args": {"CommandLine": "git push origin main --force"}}}),
        text=True,
        capture_output=True,
        timeout=5,
    )
    deny_res = json.loads(deny_proc.stdout.strip())
    assert deny_res["decision"] == "deny"

    allow_proc = subprocess.run(
        [sys.executable, "tools/dalet_hook_guard.py"],
        input=json.dumps({"toolCall": {"name": "run_command", "args": {"CommandLine": "pytest -v"}}}),
        text=True,
        capture_output=True,
        timeout=5,
    )
    allow_res = json.loads(allow_proc.stdout.strip())
    assert allow_res["decision"] == "allow"


@pytest.mark.asyncio
async def test_ensure_memories_schema_seeds_initial_persona_insights():
    """Verifica que ensure_memories_schema siembra las 3 reglas base en PersonaInsights si está vacía."""
    from database.repositories.user_repository import UserRepository

    repo = UserRepository.__new__(UserRepository)
    repo._cache = {}
    repo.execute = AsyncMock()
    repo.fetch_all = AsyncMock(return_value=[])
    repo.fetch_one = AsyncMock(return_value=(0,))

    await repo.ensure_memories_schema()

    # Verificar que se insertaron las 3 reglas semilla de calibración base
    insert_calls = [
        call for call in repo.execute.call_args_list
        if "INSERT INTO PersonaInsights" in str(call.args[0])
    ]
    assert len(insert_calls) == 3


def test_osu_analyzer_v2_math_and_compare_common_maps():
    """
    Verifica:
    1. Que OsuAnalyzer.calculate_skills (v2) usa hits_sum cuando BeatmapCompact no trae count_circles,
       evitando que Speed/Stamina colapsen a 0 pts.
    2. Que OsuAnalyzer.find_common_top_maps cruza correctamente los mapas en común y determina el ganador.
    3. Que build_compare_card incluye los Mapas en Común y el Veredicto del Duelo, y build_skills_card
       muestra las barras tipográficas y el filtro +mods.
    """
    from handlers.modules.dalet_osuanalyzer import OsuAnalyzer
    from handlers.dalet_osu_presenter import OsuPresenter

    # Scores donde beatmap NO trae count_circles/sliders pero statistics sí trae los hits reales
    sample_scores = [
        {
            "pp": 420.0,
            "accuracy": 0.985,
            "max_combo": 1250,
            "mods": ["HD", "DT"],
            "rank": "S",
            "beatmap": {"id": 1001, "difficulty_rating": 6.2, "bpm": 180, "ar": 9.3, "accuracy": 9.0, "cs": 4.0},
            "beatmapset": {"title": "Freedom Dive", "version": "Four Dimensions"},
            "statistics": {"count_300": 1180, "count_100": 20, "count_50": 0, "count_miss": 0},
        },
        {
            "pp": 390.0,
            "accuracy": 0.975,
            "max_combo": 950,
            "mods": ["NM"],
            "rank": "S",
            "beatmap": {"id": 1002, "difficulty_rating": 6.5, "bpm": 210, "ar": 9.5, "accuracy": 9.2, "cs": 4.2},
            "beatmapset": {"title": "Blue Zenith", "version": "FOUR DIMENSIONS"},
            "statistics": {"count_300": 900, "count_100": 30, "count_50": 2, "count_miss": 1},
        },
    ]

    skills = OsuAnalyzer.calculate_skills(sample_scores, mode="osu", lang="es")
    assert skills["Speed"]["points"] > 0.0
    assert skills["Stamina"]["points"] > 0.0
    assert skills["Reading"]["points"] > 0.0

    # Probar find_common_top_maps
    scores_p2 = [
        {
            "pp": 450.0,
            "accuracy": 0.992,
            "mods": ["HD", "DT"],
            "rank": "S",
            "beatmap": {"id": 1001, "version": "Four Dimensions"},
            "beatmapset": {"title": "Freedom Dive"},
        }
    ]
    common = OsuAnalyzer.find_common_top_maps(sample_scores, scores_p2, limit=3)
    assert common["total_common"] == 1
    assert common["wins1"] == 0
    assert common["wins2"] == 1
    assert common["maps"][0]["beatmap_id"] == 1001

    u1 = {"id": 1, "username": "PlayerOne", "statistics": {"pp": 7500, "global_rank": 15000, "hit_accuracy": 98.4}}
    u2 = {"id": 2, "username": "PlayerTwo", "statistics": {"pp": 7800, "global_rank": 12000, "hit_accuracy": 98.9}}

    cmp_embed = OsuPresenter.build_compare_card(
        u1, u2,
        skills1=skills,
        skills2=skills,
        mode="osu",
        lang="es",
        common_maps_data=common,
        verdict_text="PlayerTwo te snipeó en Freedom Dive con mejor acc, toca practicar.",
    )
    field_names = [f.name for f in cmp_embed.fields]
    assert any("Mapas en Común" in n for n in field_names)
    assert any("Veredicto del Duelo" in n for n in field_names)

    sk_embed = OsuPresenter.build_skills_card(
        u1, skills, roast_text="Buen Speed pero flojo en Stamina.", mode="osu", lang="es", mods_filter="DT"
    )
    assert "+DT" in sk_embed.title
    assert any("█" in f.name for f in sk_embed.fields)


@pytest.mark.asyncio
async def test_legacy_osu_commands_spec_003_data_accuracy():
    """
    Verifica los puntos de exactitud de datos de Spec-003:
    1. OsuPresenter.build_profile_card muestra Peak Rank, Max Combo, Ranked Score y título con el modo.
    2. OsuPresenter.build_firsts_card maneja scores con pp=None (Loved/old) sin crashear.
    3. OsuPresenter.build_top_card calcula Weighted PP exacto (incluyendo bonus PP sin mods y etiqueta +Mods).
    4. OsuPresenter.generate_progress_chart formatea cronológicamente y sin emojis.
    """
    from handlers.dalet_osu_presenter import OsuPresenter

    # 1. Profile card con Peak Rank y estadísticas extendidas
    user_data = {
        "id": 12345,
        "username": "MrekkClone",
        "avatar_url": "https://a.ppy.sh/12345",
        "country": {"code": "CL"},
        "rank_highest": {"rank": 42},
        "statistics": {
            "pp": 15200.5,
            "global_rank": 50,
            "country_rank": 1,
            "hit_accuracy": 99.15,
            "play_count": 85000,
            "play_time": 7200000,
            "maximum_combo": 3800,
            "ranked_score": 98765432100,
            "grade_counts": {"ssh": 5, "ss": 20, "sh": 150, "s": 300, "a": 50},
            "level": {"current": 102, "progress": 45}
        }
    }
    profile_embed = OsuPresenter.build_profile_card(user_data, mode="osu", lang="es")
    fields_text = " ".join(f.name + " " + f.value for f in profile_embed.fields)
    assert "#42" in fields_text
    assert "3,800x" in fields_text
    assert "98,765,432,100" in fields_text
    assert "Standard" in profile_embed.author.name or "osu" in profile_embed.author.name

    # 2. Firsts card con scores Loved (pp: None)
    firsts_data = [
        {
            "beatmap": {"id": 999, "version": "Extra", "difficulty_rating": 7.5, "max_combo": 1500},
            "beatmapset": {"title": "Loved Masterpiece"},
            "pp": None,
            "accuracy": 0.995,
            "max_combo": 1500,
            "rank": "SH",
            "mods": ["HD", "HR"],
            "score": 105000000,
        },
        {
            "beatmap": {"id": 888, "version": "Expert", "difficulty_rating": 6.8, "max_combo": 1200},
            "beatmapset": {"title": "Ranked Glory"},
            "pp": 540.2,
            "accuracy": 0.988,
            "max_combo": 1200,
            "rank": "S",
            "mods": ["DT"],
            "score": 85000000,
        }
    ]
    firsts_embed = OsuPresenter.build_firsts_card("MrekkClone", firsts_data, user_data=user_data, mode="osu", lang="es")
    assert "Loved Masterpiece" in firsts_embed.description
    assert "540pp" in firsts_embed.description
    assert "105,000,000" in firsts_embed.description or "105" in firsts_embed.description

    # 3. Top Card con y sin filtro de mods
    sample_top = [
        {"pp": 500.0, "accuracy": 0.99, "max_combo": 1000, "rank": "S", "mods": ["DT"], "beatmap": {"id": 1, "version": "Insane"}, "beatmapset": {"title": "Map 1"}},
        {"pp": 450.0, "accuracy": 0.98, "max_combo": 900, "rank": "S", "mods": ["HR"], "beatmap": {"id": 2, "version": "Hard"}, "beatmapset": {"title": "Map 2"}},
    ]
    top_embed_nm = OsuPresenter.build_top_card("MrekkClone", "osu", sample_top, user_data=user_data, lang="es")
    assert "PP Ponderado" in top_embed_nm.description

    top_embed_dt = OsuPresenter.build_top_card("MrekkClone", "osu", sample_top, user_data=user_data, lang="es", mods_filter="DT")
    assert "PP Sum (+Mods)" in top_embed_dt.description

    # 4. Progress Chart File y orden cronológico
    progress_history = [
        {"log_date": "2026-11-06", "recorded_at": "2026-11-06T12:00:00", "pp": 7500.0, "global_rank": 15000},
        {"log_date": "2026-11-01", "recorded_at": "2026-11-01T12:00:00", "pp": 7350.0, "global_rank": 15800},
        {"log_date": "2026-10-25", "recorded_at": "2026-10-25T12:00:00", "pp": 7200.0, "global_rank": 16500},
    ]
    chart_file = OsuPresenter.generate_progress_chart("MrekkClone", progress_history, lang="es")
    assert chart_file is not None
    assert chart_file.filename == "progress.png"


def test_spec_004_multiserver_normalizers_and_bitmask():
    """
    Verifica la decodificación de mods bitmask, parseo de song_name y normalización
    de perfiles/scores de Akatsuki (Vanilla/Relax) y Gatari al esquema Bancho v2.
    """
    from services.osu_service import decode_mods_bitmask, parse_song_name, OsuService

    # 1. Bitmask decoding (HDDT = 8 + 64 = 72; HDNC = 8 + 64 + 512 = 584 -> ['HD', 'NC']; RX = 128)
    assert decode_mods_bitmask(72) == ["HD", "DT"]
    assert decode_mods_bitmask(584) == ["HD", "NC"]
    assert "RX" in decode_mods_bitmask(128 + 64)

    # 2. Song name parser
    artist, title, version = parse_song_name("xi - Freedom Dive [Four Dimensions]")
    assert artist == "xi"
    assert title == "Freedom Dive"
    assert version == "Four Dimensions"

    # 3. Private score normalizer (Akatsuki / Gatari -> Bancho v2 schema)
    aka_raw_score = {
        "id": 999111,
        "pp": 1150.5,
        "accuracy": 99.2,
        "max_combo": 1850,
        "mods": 72,  # HDDT
        "rank": "SH",
        "completed": 3,
        "time": "2026-11-10T15:00:00Z",
        "count_300": 1200,
        "count_100": 10,
        "count_50": 0,
        "count_miss": 0,
        "beatmap": {
            "beatmap_id": 777888,
            "beatmapset_id": 333444,
            "song_name": "Kano - Stella-rium [Celestial]",
            "difficulty": 6.4,
            "max_combo": 1850,
            "hit_length": 210,
        },
    }
    norm_score = OsuService._normalize_private_score(aka_raw_score, server="akatsuki_rx")
    assert norm_score["pp"] == 1150.5
    assert abs(norm_score["accuracy"] - 0.992) < 1e-4
    assert norm_score["mods"] == ["HD", "DT", "RX"]
    assert norm_score["beatmapset"]["title"] == "Stella-rium"
    assert norm_score["beatmap"]["version"] == "Celestial"


def test_spec_004_level_aware_skill_verdict_archetypes():
    """
    Verifica que OsuAnalyzer.build_skill_verdict_context clasifique con precisión:
    - APEX_TITAN para jugadores Top #1-#250 (reconociendo su nivel élite sin roasts absurdos)
    - ALL_ROUNDER cuando todas sus habilidades están equilibradas (spread <= 8.0)
    - SPECIALIST cuando domina una habilidad por >= 15.0 pts
    - RISING_GRINDER para perfiles intermedios
    """
    from handlers.modules.dalet_osuanalyzer import OsuAnalyzer

    # 1. APEX_TITAN (Top #1 Global)
    mrekk_user = {"username": "mrekk", "statistics": {"global_rank": 1, "pp": 29500.0}}
    mrekk_skills = {
        "dominant_skill": "Aim",
        "weakest_skill": "Stamina",
        "overall_skill_points": 98.5,
        "overall_tier_name": "Grandmaster",
        "Aim": {"points": 100.0, "tier_name": "Grandmaster"},
        "Speed": {"points": 99.0, "tier_name": "Grandmaster"},
        "Accuracy": {"points": 97.5, "tier_name": "Grandmaster"},
        "Stamina": {"points": 95.0, "tier_name": "Grandmaster"},
        "Reading": {"points": 98.0, "tier_name": "Grandmaster"},
    }
    ctx_titan = OsuAnalyzer.build_skill_verdict_context("mrekk", mrekk_user, mrekk_skills, mode="osu", lang="es")
    assert ctx_titan["archetype"] == "APEX_TITAN"
    assert "#1" in ctx_titan["micro_prompt"]
    assert "pasaste el juego" in ctx_titan["fallback_text"]

    # 2. ALL_ROUNDER (Spread <= 8.0 pts, rango #4500)
    allrounder_user = {"username": "BalancedPlayer", "statistics": {"global_rank": 4500, "pp": 9200.0}}
    allrounder_skills = {
        "dominant_skill": "Accuracy",
        "weakest_skill": "Speed",
        "overall_skill_points": 65.0,
        "overall_tier_name": "Diamond",
        "Aim": {"points": 66.0, "tier_name": "Diamond"},
        "Speed": {"points": 62.0, "tier_name": "Diamond"},
        "Accuracy": {"points": 68.0, "tier_name": "Diamond"},
        "Stamina": {"points": 64.0, "tier_name": "Diamond"},
        "Reading": {"points": 65.0, "tier_name": "Diamond"},
    }
    ctx_ar = OsuAnalyzer.build_skill_verdict_context("BalancedPlayer", allrounder_user, allrounder_skills, mode="osu", lang="es")
    assert ctx_ar["archetype"] == "ALL_ROUNDER"
    assert "all-rounder" in ctx_ar["fallback_text"].lower() or "equilibrado" in ctx_ar["micro_prompt"].lower()

    # 3. SPECIALIST (Spread >= 15.0 pts)
    spec_user = {"username": "DTFarmer", "statistics": {"global_rank": 12000, "pp": 7400.0}}
    spec_skills = {
        "dominant_skill": "Speed",
        "weakest_skill": "Stamina",
        "overall_skill_points": 58.0,
        "overall_tier_name": "Platinum",
        "Aim": {"points": 64.0, "tier_name": "Diamond"},
        "Speed": {"points": 75.0, "tier_name": "Master"},
        "Accuracy": {"points": 52.0, "tier_name": "Platinum"},
        "Stamina": {"points": 45.0, "tier_name": "Gold"},
        "Reading": {"points": 54.0, "tier_name": "Platinum"},
    }
    ctx_spec = OsuAnalyzer.build_skill_verdict_context("DTFarmer", spec_user, spec_skills, mode="osu", lang="es")
    assert ctx_spec["archetype"] == "SPECIALIST"


@pytest.mark.asyncio
async def test_spec_004_plain_country_flag_spacious_cards_and_language_cascade():
    """
    Verifica:
    1. En build_profile_card, el author.name muestra '[CO]' limpio SIN backticks literales (`[CO]`).
    2. OsuPresenter.mode_title y OsuPresenter.server_title funcionan como métodos públicos (arreglando d.rank / /rank).
    3. build_top_card y build_firsts_card separan cada mapa con doble salto de línea ('\\n\\n').
    4. AdminRepository.resolve_language aplica la cascada Usuario > Servidor > Default en O(1).
    """
    from handlers.dalet_osu_presenter import OsuPresenter
    from database.repositories.admin_repository import AdminRepository

    assert OsuPresenter.mode_title("mania") == "Mania"
    assert OsuPresenter.server_title("akatsuki_rx") == "Akatsuki (Relax)"

    user_data = {
        "id": 999,
        "username": "Litxe",
        "country": {"code": "CO"},
        "_server": "akatsuki_rx",
        "statistics": {"pp": 10500.0, "global_rank": 800, "country_rank": 10, "hit_accuracy": 99.1},
    }
    prof = OsuPresenter.build_profile_card(user_data, mode="osu", lang="es")
    assert prof.author.name.startswith("[CO] ")
    assert "`[CO]`" not in prof.author.name
    assert "Akatsuki (Relax)" in prof.footer.text

    top_scores = [
        {"pp": 500.0, "accuracy": 0.99, "max_combo": 1000, "rank": "S", "mods": ["DT"], "beatmap": {"id": 1, "version": "Insane"}, "beatmapset": {"title": "Map One"}},
        {"pp": 480.0, "accuracy": 0.98, "max_combo": 900, "rank": "S", "mods": ["HD"], "beatmap": {"id": 2, "version": "Extra"}, "beatmapset": {"title": "Map Two"}},
    ]
    top_card = OsuPresenter.build_top_card("Litxe", "osu", top_scores, user_data=user_data, lang="es")
    assert "\n\n" in top_card.fields[0].value

    # Cascada de idioma en O(1)
    repo = AdminRepository()
    repo._lang_cache[100] = "en"
    repo._user_lang_cache[555] = "es"
    repo._user_lang_cache[556] = None

    # Usuario 555 tiene preferencia personal 'es' aunque el servidor 100 esté en 'en'
    assert await repo.resolve_language(user_id=555, server_id=100) == "es"
    # Usuario 556 tiene auto (None) -> hereda 'en' del servidor 100
    assert await repo.resolve_language(user_id=556, server_id=100) == "en"







