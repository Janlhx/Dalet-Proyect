from database.repositories.base_repository import BaseRepository

class AdminRepository(BaseRepository):
    async def is_channel_locked(self, channel_id: int):
        """Verifica si los comandos están bloqueados en un canal."""
        query = "SELECT fn_IsChannelLocked($1)"
        result = await self.fetch_one(query, channel_id)
        return result[0] if result else False

    async def set_channel_lock(self, channel_id: int, channel_name: str, server_id: int, server_name: str, is_locked: bool):
        """Activa o desactiva el bloqueo de comandos en un canal."""
        return await self.call_procedure(
            "sp_SetChannelLock",
            channel_id, channel_name, server_id, server_name, is_locked
        )

    async def get_server_custom_name(self, server_id: int):
        """Obtiene el nombre personalizado del bot para un servidor."""
        query = "SELECT fn_GetServerCustomName($1)"
        result = await self.fetch_one(query, server_id)
        return result[0] if result else "Dalet"

    async def set_server_custom_name(self, server_id: int, custom_name: str):
        """Establece un nombre personalizado para el bot en un servidor."""
        return await self.call_procedure(
            "sp_SetServerCustomName",
            server_id, custom_name
        )

    async def get_welcome_channel(self, server_id: int):
        """Obtiene el ID del canal de bienvenida de un servidor."""
        query = "SELECT fn_GetWelcomeChannel($1)"
        result = await self.fetch_one(query, server_id)
        return result[0] if result else None

    async def set_welcome_channel(self, server_id: int, channel_id: int | None):
        """Establece o elimina el canal de bienvenida para un servidor."""
        return await self.call_procedure(
            "sp_SetWelcomeChannel",
            server_id, channel_id
        )
