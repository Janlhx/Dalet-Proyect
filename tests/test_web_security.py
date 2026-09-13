import unittest
import os
import dalet_main


class TestWebSecurityAndEndpoints(unittest.TestCase):
    """Pruebas unitarias para los endpoints del servidor web y autenticación del Dashboard."""

    def setUp(self):
        self.app = dalet_main.app.test_client()
        self.app.testing = True

    def test_health_check_public(self):
        """Verifica que /health responda 200 OK públicamente para Render."""
        res = self.app.get('/health')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data.decode('utf-8'), "OK")

    def test_terms_and_privacy_public(self):
        """Verifica que /terms y /privacy respondan 200 OK públicamente para Discord."""
        res_terms = self.app.get('/terms')
        self.assertEqual(res_terms.status_code, 200)
        res_privacy = self.app.get('/privacy')
        self.assertEqual(res_privacy.status_code, 200)

    def test_endpoints_open_when_no_secret_configured(self):
        """Si DASHBOARD_SECRET está vacío, la API debe permitir acceso en desarrollo."""
        original_secret = dalet_main.DASHBOARD_SECRET
        try:
            dalet_main.DASHBOARD_SECRET = ""
            res_telemetry = self.app.get('/api/telemetry')
            self.assertEqual(res_telemetry.status_code, 200)

            res_feedbacks = self.app.get('/api/feedbacks')
            self.assertEqual(res_feedbacks.status_code, 200)
        finally:
            dalet_main.DASHBOARD_SECRET = original_secret

    def test_endpoints_blocked_when_secret_set_and_unauthorized(self):
        """Si DASHBOARD_SECRET está configurado, peticiones sin token deben recibir 401."""
        original_secret = dalet_main.DASHBOARD_SECRET
        try:
            dalet_main.DASHBOARD_SECRET = "test_super_secret_key_123"

            # 1. Petición sin token
            res = self.app.get('/api/feedbacks')
            self.assertEqual(res.status_code, 401)
            self.assertIn("error", res.get_json())

            # 2. Petición con token incorrecto
            res_wrong = self.app.get('/api/feedbacks', headers={"X-Dashboard-Secret": "clave_incorrecta"})
            self.assertEqual(res_wrong.status_code, 401)

            # 3. Petición con header X-Dashboard-Secret válido
            res_header = self.app.get('/api/feedbacks', headers={"X-Dashboard-Secret": "test_super_secret_key_123"})
            self.assertEqual(res_header.status_code, 200)

            # 4. Petición con Authorization Bearer válido
            res_bearer = self.app.get('/api/telemetry', headers={"Authorization": "Bearer test_super_secret_key_123"})
            self.assertEqual(res_bearer.status_code, 200)

            # 5. Petición con query param ?key=
            res_query = self.app.get('/api/telemetry?key=test_super_secret_key_123')
            self.assertEqual(res_query.status_code, 200)
        finally:
            dalet_main.DASHBOARD_SECRET = original_secret


if __name__ == '__main__':
    unittest.main()
