from database.repositories.base_repository import BaseRepository

class AdminRepository(BaseRepository):
    async def is_channel_locked(self, channel_id: int):
        """Verifica si los comandos están bloqueados en un canal."""
        query = "SELECT fn_IsChannelLocked($1)"
        result = await self.fetch_one(query, channel_id)
        return result[0] if result else True

    async def set_channel_lock(self, channel_id: int, channel_name: str, server_id: int, server_name: str, is_locked: bool):
        """Activa o desactiva el bloqueo de comandos en un canal."""
        return await self.call_procedure(
            "sp_SetChannelLock",
            channel_id, channel_name, server_id, server_name, is_locked
        )
