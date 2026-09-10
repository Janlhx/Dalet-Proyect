from database.repositories.base_repository import BaseRepository

class AdminRepository(BaseRepository):
    async def is_channel_locked(self, channel_id: int):
        """Verifica si los comandos están bloqueados en un canal."""
        query = "SELECT CommandsLocked FROM Channels WHERE ChannelID = ?"
        result = await self.fetch_one(query, channel_id)
        return bool(result[0]) if result and result[0] is not None else False

    async def set_channel_lock(self, channel_id: int, channel_name: str, server_id: int, server_name: str, is_locked: bool):
        """Activa o desactiva el bloqueo de comandos en un canal."""
        # Asegurar servidor
        await self.execute(
            "INSERT INTO Servers (ServerID, ServerName) VALUES (?, ?) ON CONFLICT(ServerID) DO UPDATE SET ServerName = excluded.ServerName",
            server_id, server_name
        )
        # Actualizar canal
        query = """
            INSERT INTO Channels (ChannelID, ChannelName, ServerID, CommandsLocked)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ChannelID) DO UPDATE SET
                ChannelName = excluded.ChannelName,
                CommandsLocked = excluded.CommandsLocked
        """
        return await self.execute(query, channel_id, channel_name, server_id, 1 if is_locked else 0)

    async def get_server_custom_name(self, server_id: int):
        """Obtiene el nombre personalizado del bot para un servidor."""
        query = "SELECT CustomName FROM Servers WHERE ServerID = ?"
        result = await self.fetch_one(query, server_id)
        return result[0] if result and result[0] else "Dalet"

    async def set_server_custom_name(self, server_id: int, custom_name: str):
        """Establece un nombre personalizado para el bot en un servidor."""
        query = """
            INSERT INTO Servers (ServerID, ServerName, CustomName)
            VALUES (?, 'Unknown', ?)
            ON CONFLICT(ServerID) DO UPDATE SET CustomName = excluded.CustomName
        """
        return await self.execute(query, server_id, custom_name)

    async def get_welcome_channel(self, server_id: int):
        """Obtiene el ID del canal de bienvenida de un servidor."""
        query = "SELECT WelcomeChannelID FROM Servers WHERE ServerID = ?"
        result = await self.fetch_one(query, server_id)
        return result[0] if result and result[0] else None

    async def set_welcome_channel(self, server_id: int, channel_id: int | None):
        """Establece o elimina el canal de bienvenida para un servidor."""
        query = """
            INSERT INTO Servers (ServerID, ServerName, WelcomeChannelID)
            VALUES (?, 'Unknown', ?)
            ON CONFLICT(ServerID) DO UPDATE SET WelcomeChannelID = excluded.WelcomeChannelID
        """
        return await self.execute(query, server_id, channel_id)

    # --- Configuración de Idioma (Default: 'en') ---

    _lang_cache: dict = {}

    async def get_server_language(self, server_id: int) -> str:
        """
        Obtiene el idioma configurado para el servidor ('en' o 'es').
        Predeterminado para cualquier servidor nuevo: 'en' (Inglés).
        """
        if server_id in self._lang_cache:
            return self._lang_cache[server_id]

        try:
            query = "SELECT Language FROM Servers WHERE ServerID = ?"
            result = await self.fetch_one(query, server_id)
            if result and result[0]:
                lang = str(result[0]).lower().strip()
                if lang in ("es", "en"):
                    self._lang_cache[server_id] = lang
                    return lang
        except Exception as e:
            # Si la columna aún no existe o falla la BD, fallback seguro a 'en'
            pass

        self._lang_cache[server_id] = "en"
        return "en"

    async def set_server_language(self, server_id: int, language: str):
        """Establece el idioma ('en' o 'es') para un servidor."""
        lang = "es" if language.lower().strip() in ("es", "spanish", "español") else "en"
        self._lang_cache[server_id] = lang

        # Intentar crear la columna por si no existe aún en la tabla Servers
        try:
            await self.execute("ALTER TABLE Servers ADD COLUMN Language TEXT DEFAULT 'en'")
        except Exception:
            pass

        query = """
            INSERT INTO Servers (ServerID, ServerName, Language)
            VALUES (?, 'Unknown', ?)
            ON CONFLICT(ServerID) DO UPDATE SET Language = excluded.Language
        """
        return await self.execute(query, server_id, lang)



