import unittest
import os
from unittest.mock import patch
import dalet_main


class TestStartupValidation(unittest.TestCase):
    """Pruebas para la validación fail-fast de variables de entorno al arranque."""

    def test_validate_environment_success(self):
        """Pasa cleanly cuando DISCORD_TOKEN y GEMINI_API_KEY están presentes."""
        with patch.dict(os.environ, {"DISCORD_TOKEN": "mock_token", "GEMINI_API_KEY": "mock_gemini"}):
            # No debe lanzar SystemExit
            try:
                dalet_main.validate_environment()
            except SystemExit:
                self.fail("validate_environment lanzó SystemExit inesperadamente")

    def test_validate_environment_missing_discord_token(self):
        """Lanza SystemExit(1) de forma fail-fast si falta DISCORD_TOKEN."""
        with patch.dict(os.environ, {"DISCORD_TOKEN": "", "GEMINI_API_KEY": "mock_gemini"}, clear=True):
            with self.assertRaises(SystemExit) as cm:
                dalet_main.validate_environment()
            self.assertEqual(cm.exception.code, 1)

    def test_validate_environment_missing_all_ai_keys(self):
        """Lanza SystemExit(1) si no hay ni GEMINI_API_KEY ni OPENROUTER_API_KEY."""
        with patch.dict(os.environ, {"DISCORD_TOKEN": "mock_token", "GEMINI_API_KEY": "", "OPENROUTER_API_KEY": ""}, clear=True):
            with self.assertRaises(SystemExit) as cm:
                dalet_main.validate_environment()
            self.assertEqual(cm.exception.code, 1)


if __name__ == '__main__':
    unittest.main()
