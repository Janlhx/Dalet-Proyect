import unittest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock
from services.nlp_service import NLPService
from database.repositories.user_repository import UserRepository


class TestDSMLAndChatFlow(unittest.TestCase):
    """Pruebas unitarias para extracción de DSML, sanitización de DSML y flow de chat."""

    def test_extract_dsml_tool_calls_fullwidth_pipes(self):
        """Verifica que el formato DSML de DeepSeek con barras fullwidth (｜) sea extraído correctamente."""
        text = """<｜｜DSML｜｜ calls>
<｜｜DSML｜｜ invoke name="get_osu_user_profile">
<｜｜DSML｜｜ parameter name="username" string="true">mj41</｜｜DSML｜｜ parameter>
</｜｜DSML｜｜ invoke>
<｜｜DSML｜｜ invoke name="get_osu_user_profile">
<｜｜DSML｜｜ parameter name="username" string="true">Sara-</｜｜DSML｜｜ parameter>
</｜｜DSML｜｜ invoke>
</｜｜DSML｜｜ calls>"""
        extracted = NLPService._extract_xml_tool_calls(text)
        self.assertEqual(len(extracted), 2)
        self.assertEqual(extracted[0], ("get_osu_user_profile", {"username": "mj41"}))
        self.assertEqual(extracted[1], ("get_osu_user_profile", {"username": "Sara-"}))

    def test_extract_dsml_tool_calls_ascii_pipes(self):
        """Verifica que el formato DSML con barras ASCII estándar (|) funcione igual."""
        text = """<||DSML|| calls>
<||DSML|| invoke name="get_osu_most_played">
<||DSML|| parameter name="username" string="true">peppy</||DSML|| parameter>
<||DSML|| parameter name="limit">5</||DSML|| parameter>
</||DSML|| invoke>
</||DSML|| calls>"""
        extracted = NLPService._extract_xml_tool_calls(text)
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0], ("get_osu_most_played", {"username": "peppy", "limit": 5}))

    def test_strip_dsml_calls_from_clean_reply(self):
        """Verifica que cualquier bloque de llamadas DSML sea eliminado limpiamente de la respuesta visible."""
        raw = """<｜｜DSML｜｜ calls>
<｜｜DSML｜｜ invoke name="get_osu_user_profile">
<｜｜DSML｜｜ parameter name="username" string="true">mj41</｜｜DSML｜｜ parameter>
</｜｜DSML｜｜ invoke>
</｜｜DSML｜｜ calls>mj41 tiene 4500pp y mejor rank que Sara."""
        cleaned = NLPService._clean_reply_text(raw, bot_name="Dalet")
        self.assertEqual(cleaned, "mj41 tiene 4500pp y mejor rank que Sara.")

    def test_strip_unclosed_dsml_calls(self):
        """Verifica que un bloque DSML cortado o sin cerrar no se filtre en el chat."""
        raw = """<｜｜DSML｜｜ calls>
<｜｜DSML｜｜ invoke name="get_osu_user_profile">
<｜｜DSML｜｜ parameter name="username" """
        cleaned = NLPService._clean_reply_text(raw, bot_name="Dalet")
        self.assertEqual(cleaned, "")

    def test_strip_orphan_dsml_tags(self):
        """Verifica que etiquetas DSML sueltas sean removidas."""
        raw = "esto es un mensaje </｜｜DSML｜｜ calls> normal"
        cleaned = NLPService._clean_reply_text(raw, bot_name="Dalet")
        self.assertEqual(cleaned, "esto es un mensaje normal")

    def test_user_repository_log_message_deduplication(self):
        """Verifica que log_message no inserte duplicados consecutivos para el mismo usuario y canal."""
        repo = UserRepository()
        repo._log_buffer = []

        async def run_dedup():
            # Primer mensaje
            await repo.log_message(101, "Dalet", 1, "Server", 99, "general", "hola que tal")
            # Segundo mensaje idéntico (simulando doble llamada por listener + cog)
            await repo.log_message(101, "Dalet", 1, "Server", 99, "general", "hola que tal")
            # Tercer mensaje diferente
            await repo.log_message(101, "Dalet", 1, "Server", 99, "general", "otro mensaje")

        asyncio.run(run_dedup())
        self.assertEqual(len(repo._log_buffer), 2)
        self.assertEqual(repo._log_buffer[0][6], "hola que tal")
        self.assertEqual(repo._log_buffer[1][6], "otro mensaje")

    def test_get_osu_most_played_execution(self):
        """Verifica que _execute_osu_tool maneje correctamente get_osu_most_played."""
        nlp = NLPService(osu_service=MagicMock())
        nlp.osu_service.get_user = AsyncMock(return_value={"id": 1234, "username": "TestUser"})
        nlp.osu_service.get_user_most_played = AsyncMock(return_value=[
            {
                "count": 150,
                "beatmap": {"version": "Insane", "difficulty_rating": 5.4},
                "beatmapset": {"title": "Harumachi Clover"}
            }
        ])

        async def run_tool():
            res_str = await nlp._execute_osu_tool("get_osu_most_played", {"username": "TestUser", "limit": 5})
            return json.loads(res_str)

        data = asyncio.run(run_tool())
        self.assertEqual(data["player"], "TestUser")
        self.assertEqual(len(data["most_played"]), 1)
        self.assertEqual(data["most_played"][0]["beatmap"], "Harumachi Clover [Insane]")
        self.assertEqual(data["most_played"][0]["plays"], 150)
        self.assertEqual(data["most_played"][0]["stars"], "5.4★")


if __name__ == "__main__":
    unittest.main()
