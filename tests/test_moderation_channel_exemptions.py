import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from database.repositories.admin_repository import AdminRepository
from services.moderation_service import ModerationService


class TestModerationChannelExemptions(unittest.IsolatedAsyncioTestCase):
    """Pruebas para exenciones de canales, parsing de IDs y soporte para hilos (threads)."""

    async def asyncSetUp(self):
        AdminRepository._mod_cache.clear()
        self.repo = AdminRepository()

    async def test_parse_single_channel_integer_string(self):
        """Verifica que un único ID numérico como string se parsee correctamente y no quede vacío."""
        with patch.object(self.repo, "fetch_one", new_callable=AsyncMock) as mock_fetch:
            # Fila de ModerationConfig con IgnoredChannels = '720827008904331355'
            mock_fetch.return_value = (1, 123, "notify", 0, 10, 1, 1, 1, 1, "720827008904331355")

            cfg = await self.repo.get_moderation_config(999, force_refresh=True)
            self.assertIsNotNone(cfg)
            self.assertIn(720827008904331355, cfg["ignored_channels"])
            self.assertEqual(cfg["ignored_channels_map"].get(720827008904331355), {"all"})

    async def test_parse_json_dict_format(self):
        """Verifica el parsing del nuevo formato modular JSON dict."""
        with patch.object(self.repo, "fetch_one", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = (1, 123, "notify", 0, 10, 1, 1, 1, 1, '{"1422394572104794183": ["all", "flood"]}')

            cfg = await self.repo.get_moderation_config(999, force_refresh=True)
            self.assertIsNotNone(cfg)
            self.assertIn(1422394572104794183, cfg["ignored_channels"])
            self.assertEqual(cfg["ignored_channels_map"].get(1422394572104794183), {"all", "flood"})

    async def test_parse_comma_separated_format(self):
        """Verifica el fallback para IDs separados por comas."""
        with patch.object(self.repo, "fetch_one", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = (1, 123, "notify", 0, 10, 1, 1, 1, 1, "111, 222, 333")

            cfg = await self.repo.get_moderation_config(999, force_refresh=True)
            self.assertIsNotNone(cfg)
            self.assertEqual(set(cfg["ignored_channels"]), {111, 222, 333})
            self.assertEqual(cfg["ignored_channels_map"].get(111), {"all"})
            self.assertEqual(cfg["ignored_channels_map"].get(222), {"all"})
            self.assertEqual(cfg["ignored_channels_map"].get(333), {"all"})

    def test_flood_short_messages_threshold(self):
        """Verifica que mensajes cortos como 'xd' o '$ma' no disparen timeout con solo 3 repeticiones."""
        mod = ModerationService(None)
        user_id = 12345
        channel_id = 99999

        # 3 mensajes cortos idénticos no deben disparar flood
        for _ in range(3):
            is_flood, _ = mod.check_flood(user_id, channel_id, "$ma")
            self.assertFalse(is_flood)

        # 4 mensajes cortos tampoco disparan si el umbral corto es 5
        is_flood_4, _ = mod.check_flood(user_id, channel_id, "$ma")
        self.assertFalse(is_flood_4)

        # El 5to mensaje corto sí dispara flood (sea por burst de 5 msgs o por duplicate)
        is_flood_5, reason = mod.check_flood(user_id, channel_id, "$ma")
        self.assertTrue(is_flood_5)
        self.assertTrue(reason.startswith("burst_flood") or reason.startswith("duplicate_flood"))

        # Al disparar, el historial debe quedar limpio para evitar encadenar timeouts inmediatos
        self.assertEqual(len(mod._message_history[user_id]), 0)


if __name__ == "__main__":
    unittest.main()
