import unittest
from unittest.mock import AsyncMock, patch
from database.repositories.admin_repository import AdminRepository


class TestAdminRepository(unittest.IsolatedAsyncioTestCase):
    """Pruebas unitarias para el repositorio de administración y su sistema de caché."""

    async def asyncSetUp(self):
        AdminRepository._name_cache.clear()
        AdminRepository._lang_cache.clear()
        self.repo = AdminRepository()

    async def test_get_server_custom_name_cached(self):
        """Verifica que tras la primera consulta a BD, las siguientes se sirvan desde caché."""
        with patch.object(self.repo, 'fetch_one', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = ("DaletBot",)

            # 1. Primera llamada -> consulta BD
            name1 = await self.repo.get_server_custom_name(12345)
            self.assertEqual(name1, "DaletBot")
            self.assertEqual(mock_fetch.call_count, 1)

            # 2. Segunda llamada -> debe venir de caché en RAM (0 llamadas a BD)
            name2 = await self.repo.get_server_custom_name(12345)
            self.assertEqual(name2, "DaletBot")
            self.assertEqual(mock_fetch.call_count, 1)

    async def test_set_server_custom_name_invalidates_cache(self):
        """Verifica que al cambiar el nombre del servidor se actualice la caché."""
        with patch.object(self.repo, 'execute', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = True
            await self.repo.set_server_custom_name(12345, "NuevoNombre")

            # La caché debe reflejar el nuevo nombre sin consultar BD
            self.assertEqual(AdminRepository._name_cache.get(12345), "NuevoNombre")


if __name__ == '__main__':
    unittest.main()
