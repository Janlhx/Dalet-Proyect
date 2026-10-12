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
