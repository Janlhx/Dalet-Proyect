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

    def test_extract_reaction_and_pass_tags(self):
        """Verifica que extract_reaction separe correctamente texto, reacciones Unicode/custom y [PASS]."""
        # Texto + reacción Unicode
        txt, rx = NLPService.extract_reaction("qué mala suerte la de jeiden [REACTION: 😆]")
        self.assertEqual(txt, "qué mala suerte la de jeiden")
        self.assertEqual(rx, "😆")

        # Solo reacción (modo proactivo silencioso)
        txt_only, rx_only = NLPService.extract_reaction("[REACTION: 💀]")
        self.assertEqual(txt_only, "")
        self.assertEqual(rx_only, "💀")

        # Reacción con emoji custom de servidor
        txt_c, rx_c = NLPService.extract_reaction("buen intento [REACTION: <:dalet_smug:987654321>]")
        self.assertEqual(txt_c, "buen intento")
        self.assertEqual(rx_c, "<:dalet_smug:987654321>")

        # Etiqueta [PASS]
        txt_pass, rx_pass = NLPService.extract_reaction("[PASS]")
        self.assertEqual(txt_pass, "")
        self.assertIsNone(rx_pass)

    def test_clean_reply_text_preserve_reaction_flag(self):
        """Verifica que _clean_reply_text preserve [REACTION: ...] y [PASS] solo cuando preserve_reaction=True."""
        raw = "Dalet: qué risa jajaja [REACTION: 😆]"
        cleaned_default = NLPService._clean_reply_text(raw, bot_name="Dalet", preserve_reaction=False)
        self.assertEqual(cleaned_default, "qué risa jajaja")

        cleaned_preserved = NLPService._clean_reply_text(raw, bot_name="Dalet", preserve_reaction=True)
        self.assertEqual(cleaned_preserved, "qué risa jajaja [REACTION: 😆]")

        pass_default = NLPService._clean_reply_text("[PASS]", bot_name="Dalet", preserve_reaction=False)
        self.assertEqual(pass_default, "")

        pass_preserved = NLPService._clean_reply_text("[PASS]", bot_name="Dalet", preserve_reaction=True)
        self.assertEqual(pass_preserved, "[PASS]")

    def test_proactive_meaningful_filter_and_per_channel_isolation(self):
        """Verifica que el filtro proactivo descarte ruido y mantenga contadores independientes por canal."""
        from handlers.dalet_nlpchat import DaletNLPChat, MIN_MESSAGES_BETWEEN_REPLIES, MAX_MESSAGES_WINDOW

        self.assertFalse(DaletNLPChat._is_meaningful_proactive_message("xd"))
        self.assertFalse(DaletNLPChat._is_meaningful_proactive_message("jajajajaja lol"))
        self.assertFalse(DaletNLPChat._is_meaningful_proactive_message("ok gracias"))
        self.assertTrue(
            DaletNLPChat._is_meaningful_proactive_message("imagina que a jeiden se le va la luz en pleno torneo")
        )

        bot_mock = MagicMock()
        cog = DaletNLPChat(bot_mock)

        # Enviar 5 mensajes en el canal 100 (debajo del mínimo de 6)
        for _ in range(MIN_MESSAGES_BETWEEN_REPLIES - 1):
            self.assertFalse(cog._should_respond(100, "este es un mensaje con suficiente contenido"))

        # El canal 200 debe seguir con contador independiente en 1
        self.assertFalse(cog._should_respond(200, "mensaje en otro canal completamente distinto"))
        self.assertEqual(cog.proactive_channels[200]["count"], 1)

        # Si en el canal 100 llega al tope de ventana pero el mensaje es ruido ("xd"), espera al siguiente con sustancia
        cog.proactive_channels[100]["count"] = MAX_MESSAGES_WINDOW
        self.assertFalse(cog._should_respond(100, "xd"))
        self.assertTrue(cog._should_respond(100, "imagina que a jeiden se le va la luz justo ahora"))

    def test_proactive_observer_prompt_framing(self):
        """Verifica que en modo proactivo el prompt enmarque a Dalet como observadora autónoma y no como destinataria."""
        nlp = NLPService.__new__(NLPService)
        proactive_prompt = nlp._format_user_prompt_with_context(
            trigger="A mí solo me gusta su combate",
            context="Rey: qué tal ese juego",
            username="Rey",
            language="es",
            is_proactive=True,
        )
        self.assertIn("MODO PROACTIVO — INTERVENCIÓN POR CUENTA PROPIA", proactive_prompt)
        self.assertIn("NO dirigido a ti", proactive_prompt)
        self.assertNotIn("Responde a lo que te dicen AHORA", proactive_prompt)
        self.assertNotIn("Mensaje actual de Rey:", proactive_prompt)

        reactive_prompt = nlp._format_user_prompt_with_context(
            trigger="dalet qué opinas de ese combate",
            context="Rey: qué tal ese juego",
            username="Rey",
            language="es",
            is_proactive=False,
        )
        self.assertIn("Mensaje actual de Rey:", reactive_prompt)
        self.assertIn("Responde a lo que te dicen AHORA", reactive_prompt)

    def test_deepseek_web_search_and_fetch_tools(self):
        """Verifica que DeepSeek sea el proveedor prioritario para web_search y que _execute_osu_tool ejecute web_search y web_fetch."""
        nlp = NLPService(osu_service=MagicMock())
        nlp.deepseek_api_key = "test_ds_key"
        nlp._deepseek_cooldown_until = 0

        # 1. _select_provider debe priorizar DeepSeek para needs_web_search cuando no hay imágenes
        chosen = nlp._select_provider(has_images=False, needs_web_search=True, trigger="busca noticias de osu")
        self.assertEqual(chosen, "deepseek")

        # 2. Extracción XML debe reconocer web_search y web_fetch
        xml_calls = NLPService._extract_xml_tool_calls('<web_search><query>osu lazer update 2026</query></web_search>')
        self.assertEqual(xml_calls, [("web_search", {"query": "osu lazer update 2026"})])

        # 3. _execute_osu_tool despacha web_search y web_fetch hacia los endpoints /v1/tools/search y /v1/tools/fetch
        mock_search_resp = MagicMock()
        mock_search_resp.status_code = 200
        mock_search_resp.json.return_value = {
            "results": [
                {"title": "osu!lazer 2026 Release", "url": "https://osu.ppy.sh/home/news", "summary": "New PP rework and lazer updates."}
            ]
        }
        mock_fetch_resp = MagicMock()
        mock_fetch_resp.status_code = 200
        mock_fetch_resp.json.return_value = {
            "title": "osu! News",
            "content": "# Big Update\nFull markdown body here."
        }

        async def run_web_tools():
            nlp._http_client.post = AsyncMock(side_effect=[mock_search_resp, mock_fetch_resp])
            res_s = json.loads(await nlp._execute_osu_tool("web_search", {"query": "osu lazer 2026"}))
            res_f = json.loads(await nlp._execute_osu_tool("web_fetch", {"url": "https://osu.ppy.sh/home/news"}))
            return res_s, res_f

        search_data, fetch_data = asyncio.run(run_web_tools())
        self.assertEqual(search_data["query"], "osu lazer 2026")
        self.assertEqual(len(search_data["results"]), 1)
        self.assertEqual(search_data["results"][0]["title"], "osu!lazer 2026 Release")
        self.assertEqual(fetch_data["title"], "osu! News")
        self.assertIn("# Big Update", fetch_data["content"])


if __name__ == "__main__":
    unittest.main()

