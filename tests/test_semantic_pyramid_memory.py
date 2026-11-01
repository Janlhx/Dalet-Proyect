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

