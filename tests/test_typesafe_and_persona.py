import unittest
from unittest.mock import AsyncMock, MagicMock
from services.nlp_service import NLPService


class TestTypeSafeAndPersona(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.nlp = NLPService()
        self.nlp.osu_service = MagicMock()
        self.nlp.osu_repo = AsyncMock()

    def test_personality_anti_fence_sitting_rules(self):
        """Verifica que el prompt en español e inglés prohíba expresamente el relativismo o tibieza diplomática."""
        prompt_es = self.nlp._get_system_prompt("Dalet", "es")
        self.assertIn("PROHIBIDO EL RELATIVISMO Y LA TIBIEZA CORPORATIVA", prompt_es)
        self.assertIn("Dalet SIEMPRE SE MOJA", prompt_es)
        self.assertIn("ambos son buenos", prompt_es)

        prompt_en = self.nlp._get_system_prompt("Dalet", "en")
        self.assertIn("no fence-sitting", prompt_en.lower())
        self.assertIn("dalet always takes a stand", prompt_en.lower())

    def test_personality_game_decoupling_rules(self):
        """Verifica que el prompt prohíba meter osu! con calzador al preguntar por otros juegos."""
        prompt_es = self.nlp._get_system_prompt("Dalet", "es")
        self.assertIn("PROHIBIDO METER OSU! CON CALZADOR EN OTROS JUEGOS", prompt_es)
        self.assertIn("Valorant", prompt_es)

        prompt_en = self.nlp._get_system_prompt("Dalet", "en")
        self.assertIn("STRICT NO FORCED OSU! IN OTHER GAMES", prompt_en)

    def test_format_user_prompt_other_game(self):
        """Verifica que al consultar sobre otro juego se inyecte la directriz de no mencionar osu!."""
        msg = self.nlp._format_user_prompt_with_context(
            trigger="cómo mejoro mi crosshair en valorant?",
            context="chat",
            username="Gamer",
            topic="other_game"
        )
        self.assertIn("[DIRECTRIZ ESTRICTA: La consulta es sobre otro juego. Prohibido mencionar o recomendar osu!", msg)

    def test_format_user_prompt_comparison(self):
        """Verifica que al consultar comparativas se inyecte la directriz de tomar postura."""
        msg = self.nlp._format_user_prompt_with_context(
            trigger="qué es mejor rust o go?",
            context="chat",
            username="Dev",
            topic="comparison"
        )
        self.assertIn("[DIRECTRIZ ESTRICTA: El usuario pide comparar o elegir entre opciones. Prohibido ser neutral", msg)

    def test_format_user_prompt_linked_user_opinion(self):
        """Verifica que para usuario vinculado pidiendo opinión se indique usar herramientas y NO pedir comandos."""
        msg = self.nlp._format_user_prompt_with_context(
            trigger="qué opinas de mi juego?",
            context="chat",
            username="Juan",
            linked_osu_username="Juanlhx",
            is_opinion_req=True
        )
        self.assertIn("Cuenta osu! vinculada: Juanlhx", msg)
        self.assertIn("usa tus herramientas para consultar sus datos en silencio y dale tu veredicto. ¡NO le pidas que ejecute comandos como /skills o /top!", msg)

    def test_format_user_prompt_unlinked_user_opinion(self):
        """Verifica que para usuario no vinculado pidiendo opinión se recomiende /link <usuario>."""
        msg = self.nlp._format_user_prompt_with_context(
            trigger="qué opinas de mi juego?",
            context="chat",
            username="Pedro",
            linked_osu_username=None,
            is_opinion_req=True
        )
        self.assertIn("Cuenta osu! vinculada: Ninguna vinculada", msg)
        self.assertIn("recomiéndale con tu estilo vincular su cuenta con /link <usuario>", msg)

    async def test_execute_osu_tool_fallback_to_linked_user(self):
        """Verifica que _execute_osu_tool resuelva automáticamente la cuenta enlazada si el usuario dice 'mi' o no pasa nick."""
        self.nlp.osu_repo.get_linked_username.return_value = "LinkedOsuNick"
        self.nlp.osu_service.get_user = AsyncMock(return_value={"id": 9999, "username": "LinkedOsuNick", "statistics": {}})
        self.nlp.osu_service.get_user_recent_scores = AsyncMock(return_value=[])

        res = await self.nlp._execute_osu_tool("get_recent_osu_play", {"username": "mi"}, user_id=123456789)
        self.assertIn("LinkedOsuNick", res)
        self.nlp.osu_service.get_user.assert_called_with("LinkedOsuNick")


if __name__ == "__main__":
    unittest.main()
