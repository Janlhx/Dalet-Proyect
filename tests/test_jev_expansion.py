import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import json
import os
from services.nlp_service import NLPService, ACTION_TO_TOOL_MAP, BEATMAP_VIBE_KEYWORDS


class TestJevExpansion(unittest.IsolatedAsyncioTestCase):
    """
    Tests de validación para la expansión de TypeSafe Jev:
    - Clasificación paralela de 5 preguntas (System One).
    - Enrutamiento directo a comandos (Shortcut LLM focalizado).
    - Inyección contextual de estados emocionales (Moods).
    - Herramienta y flujo de recomendación semántica de beatmaps.
    """

    async def asyncSetUp(self):
        self.mock_user_repo = AsyncMock()
        self.mock_osu_repo = AsyncMock()
        self.mock_osu_service = AsyncMock()
        self.nlp = NLPService(
            gemini_api_key="mock_gemini",
            user_repo=self.mock_user_repo,
            osu_service=self.mock_osu_service,
            osu_repo=self.mock_osu_repo,
        )
        self.nlp.deepseek_api_key = "mock_deepseek"
        self.nlp.typesafe_api_key = "mock_typesafe"

    def test_routing_constants_integrity(self):
        """Verifica la integridad de los diccionarios de enrutamiento."""
        self.assertIn("recent_play", ACTION_TO_TOOL_MAP)
        self.assertIn("top_plays", ACTION_TO_TOOL_MAP)
        self.assertIn("skills", ACTION_TO_TOOL_MAP)
        self.assertIn("profile", ACTION_TO_TOOL_MAP)

        self.assertIn("stamina_streams", BEATMAP_VIBE_KEYWORDS)
        self.assertIn("tech_aim", BEATMAP_VIBE_KEYWORDS)
        self.assertIn("speed_farm", BEATMAP_VIBE_KEYWORDS)
        self.assertIn("reading_chill", BEATMAP_VIBE_KEYWORDS)
        self.assertIn("warmup", BEATMAP_VIBE_KEYWORDS)

    @patch("services.nlp_service.AsyncTypeSafeClient")
    async def test_classify_with_jev_returns_five_keys(self, mock_client_cls):
        """Valida que _classify_with_jev retorne las 5 dimensiones tipadas."""
        mock_instance = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_instance

        mock_ans_opinion = MagicMock(noul=0.85)
        mock_ans_topic = MagicMock(choice="osu")
        mock_ans_action = MagicMock(choice="skills")
        mock_ans_mood = MagicMock(choice="banter")
        mock_ans_scope = MagicMock(choice="self")

        mock_instance.system_one.return_value = MagicMock(
            answers={
                "is_opinion": mock_ans_opinion,
                "topic": mock_ans_topic,
                "direct_osu_action": mock_ans_action,
                "user_mood": mock_ans_mood,
                "player_scope": mock_ans_scope,
            }
        )

        res = await self.nlp._classify_with_jev("dalet mira mis skills a ver si te atreves")
        self.assertEqual(res["is_opinion"], 0.85)
        self.assertEqual(res["topic"], "osu")
        self.assertEqual(res["direct_osu_action"], "skills")
        self.assertEqual(res["user_mood"], "banter")
        self.assertEqual(res["player_scope"], "self")

    @patch.object(NLPService, "_classify_with_jev")
    @patch.object(NLPService, "_shortcut_osu_reply")
    async def test_shortcut_triggered_for_linked_self_action(self, mock_shortcut, mock_jev):
        """Verifica que si Jev detecta direct_osu_action='recent_play' y user_linked, active el shortcut path."""
        mock_jev.return_value = {
            "is_opinion": 0.1,
            "topic": "osu",
            "direct_osu_action": "recent_play",
            "user_mood": "casual",
            "player_scope": "self",
        }
        self.mock_osu_repo.get_linked_username.return_value = "ProPlayer99"
        mock_shortcut.return_value = "Acabas de hacer 1-miss en 6.2★ con 97.4% de acc."

        reply = await self.nlp.generate_reply(
            trigger="pásame mi última play",
            context="",
            username="TestUser",
            user_id=12345,
            language="es"
        )

        mock_shortcut.assert_called_once()
        self.assertEqual(reply, "Acabas de hacer 1-miss en 6.2★ con 97.4% de acc.")

    @patch.object(NLPService, "_classify_with_jev")
    @patch.object(NLPService, "_shortcut_osu_reply")
    @patch.object(NLPService, "_generate_deepseek_reply")
    async def test_shortcut_bypassed_if_unlinked(self, mock_deepseek, mock_shortcut, mock_jev):
        """Si el usuario no está vinculado, el shortcut NO se ejecuta aunque la acción sea directa."""
        mock_jev.return_value = {
            "is_opinion": 0.1,
            "topic": "osu",
            "direct_osu_action": "recent_play",
            "user_mood": "casual",
            "player_scope": "self",
        }
        self.mock_osu_repo.get_linked_username.return_value = None
        mock_deepseek.return_value = "No tienes cuenta enlazada, usa /link primero."

        reply = await self.nlp.generate_reply(
            trigger="pásame mi última play",
            context="",
            username="UnlinkedUser",
            user_id=99999,
            language="es"
        )

        mock_shortcut.assert_not_called()
        self.assertEqual(reply, "No tienes cuenta enlazada, usa /link primero.")

    def test_mood_directives_injection(self):
        """Verifica que cada user_mood inyecte la directiva adecuada al prompt formateado."""
        # Banter en español
        prompt_banter_es = self.nlp._format_user_prompt_with_context(
            trigger="eres malísima",
            context="",
            username="UserA",
            user_mood="banter",
            language="es"
        )
        self.assertIn("DIRECTRIZ DE ÁNIMO: El usuario está en modo banter", prompt_banter_es)

        # Frustrated en inglés
        prompt_frust_en = self.nlp._format_user_prompt_with_context(
            trigger="i choked 3 times in a row i hate this",
            context="",
            username="UserB",
            user_mood="frustrated",
            language="en"
        )
        self.assertIn("MOOD DIRECTIVE: User is frustrated or tilted", prompt_frust_en)

        # Serious en español
        prompt_serious_es = self.nlp._format_user_prompt_with_context(
            trigger="cómo coloco los dedos para no cansarme en tapping",
            context="",
            username="UserC",
            user_mood="serious",
            language="es"
        )
        self.assertIn("DIRECTRIZ DE ÁNIMO: El usuario pide consejo técnico", prompt_serious_es)

    def test_shortcut_tool_data_injection(self):
        """Verifica que shortcut_tool_data se incluya en el cuerpo del prompt."""
        data_json = '{"player": "Litxe", "top": "500pp"}'
        prompt = self.nlp._format_user_prompt_with_context(
            trigger="mi top",
            context="",
            username="Litxe",
            shortcut_tool_data=data_json,
            language="es"
        )
        self.assertIn("[DATOS TÉCNICOS CONSULTADOS AUTÓNOMAMENTE]:", prompt)
        self.assertIn(data_json, prompt)

    async def test_recommend_beatmaps_tool_execution(self):
        """Verifica la ejecución técnica de la herramienta recommend_beatmaps."""
        self.mock_osu_service.search_beatmaps.return_value = [
            {
                "id": 123456,
                "title": "Freedom Dive",
                "artist": "xi",
                "creator": "Nakagawa-Kanon",
                "bpm": 222.22,
                "beatmaps": [
                    {"version": "FOUR DIMENSIONS", "difficulty_rating": 7.3}
                ]
            }
        ]

        result_raw = await self.nlp._execute_osu_tool(
            "recommend_beatmaps",
            {"vibe": "stamina_streams", "star_min": 6.5, "star_max": 8.0, "mode": "osu"}
        )
        data = json.loads(result_raw)
        self.assertEqual(data.get("vibe"), "stamina_streams")
        self.assertEqual(data.get("count"), 1)
        self.assertEqual(len(data.get("recommendations", [])), 1)
        rec = data["recommendations"][0]
        self.assertIn("xi - Freedom Dive", rec["title"])
        self.assertIn("FOUR DIMENSIONS (7.3★)", rec["diffs"])
        self.mock_osu_service.search_beatmaps.assert_called_once_with(
            mode="osu",
            min_stars=6.5,
            max_stars=8.0,
            keyword="stream stamina"
        )


if __name__ == "__main__":
    unittest.main()
