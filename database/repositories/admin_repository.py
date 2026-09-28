from database.repositories.base_repository import BaseRepository


class AdminRepository(BaseRepository):
    """Repositorio para configuración administrativa de servidores, canales e idiomas."""

    _lang_cache: dict[int, str] = {}
    _name_cache: dict[int, str] = {}

    async def is_channel_locked(self, channel_id: int) -> bool:
        """Verifica si los comandos están bloqueados en un canal."""
        query = "SELECT CommandsLocked FROM Channels WHERE ChannelID = ?"
        result = await self.fetch_one(query, channel_id)
        return bool(result[0]) if result and result[0] is not None else False

    async def set_channel_lock(
        self,
        channel_id: int,
        channel_name: str,
        server_id: int,
        server_name: str,
        is_locked: bool
    ):
        """Activa o desactiva el bloqueo de comandos en un canal."""
        await self.execute(
            "INSERT INTO Servers (ServerID, ServerName, IsReactive) VALUES (?, ?, 1) ON CONFLICT(ServerID) DO UPDATE SET ServerName = excluded.ServerName",
            server_id, server_name
        )
        query = """
            INSERT INTO Channels (ChannelID, ChannelName, ServerID, CommandsLocked)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ChannelID) DO UPDATE SET
                ChannelName = excluded.ChannelName,
                CommandsLocked = excluded.CommandsLocked
        """
        return await self.execute(query, channel_id, channel_name, server_id, 1 if is_locked else 0)

    async def get_server_custom_name(self, server_id: int) -> str:
        """Obtiene el nombre personalizado del bot para un servidor con caché en memoria."""
        if server_id in self._name_cache:
            return self._name_cache[server_id]

        query = "SELECT CustomName FROM Servers WHERE ServerID = ?"
        result = await self.fetch_one(query, server_id)
        name = result[0] if result and result[0] else "Dalet"
        self._name_cache[server_id] = name
        return name

    async def set_server_custom_name(self, server_id: int, custom_name: str):
        """Establece un nombre personalizado para el bot en un servidor y actualiza la caché."""
        query = """
            INSERT INTO Servers (ServerID, ServerName, CustomName, IsReactive)
            VALUES (?, 'Unknown', ?, 1)
            ON CONFLICT(ServerID) DO UPDATE SET CustomName = excluded.CustomName
        """
        res = await self.execute(query, server_id, custom_name)
        self._name_cache[server_id] = custom_name
        return res

    async def get_welcome_channel(self, server_id: int) -> int | None:
        """Obtiene el ID del canal de bienvenida de un servidor."""
        query = "SELECT WelcomeChannelID FROM Servers WHERE ServerID = ?"
        result = await self.fetch_one(query, server_id)
        return result[0] if result and result[0] else None

    async def set_welcome_channel(self, server_id: int, channel_id: int | None):
        """Establece o elimina el canal de bienvenida para un servidor."""
        query = """
            INSERT INTO Servers (ServerID, ServerName, WelcomeChannelID, IsReactive)
            VALUES (?, 'Unknown', ?, 1)
            ON CONFLICT(ServerID) DO UPDATE SET WelcomeChannelID = excluded.WelcomeChannelID
        """
        return await self.execute(query, server_id, channel_id)

    async def get_server_language(self, server_id: int) -> str:
        """Obtiene el idioma ('en' o 'es') configurado para un servidor."""
        if server_id in self._lang_cache:
            return self._lang_cache[server_id]

        query = "SELECT Language FROM Servers WHERE ServerID = ?"
        result = await self.fetch_one(query, server_id)
        lang = result[0] if result and result[0] in ("en", "es") else "en"
        self._lang_cache[server_id] = lang
        return lang

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
            INSERT INTO Servers (ServerID, ServerName, Language, IsReactive)
            VALUES (?, 'Unknown', ?, 1)
            ON CONFLICT(ServerID) DO UPDATE SET Language = excluded.Language
        """
        return await self.execute(query, server_id, lang)

    async def get_moderation_config(self, server_id: int) -> dict | None:
        query = "SELECT Enabled, LogChannelID, Action, AutoBanOnIllegal, TimeoutMinutes FROM ModerationConfig WHERE ServerID = ?"
        row = await self.fetch_one(query, server_id)
        if not row:
            return None
        return {
            "enabled": bool(row[0]),
            "log_channel_id": row[1],
            "action": row[2] or "notify",
            "auto_ban_on_illegal": bool(row[3]),
            "timeout_minutes": row[4] or 10,
        }

    async def set_moderation_config(
        self,
        server_id: int,
        enabled: bool,
        log_channel_id: int | None,
        action: str = "notify",
        auto_ban_on_illegal: bool = True,
        timeout_minutes: int = 10,
    ):
        query = """
            INSERT INTO ModerationConfig (ServerID, Enabled, LogChannelID, Action, AutoBanOnIllegal, TimeoutMinutes, UpdatedAt)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ServerID) DO UPDATE SET
                Enabled = excluded.Enabled,
                LogChannelID = excluded.LogChannelID,
                Action = excluded.Action,
                AutoBanOnIllegal = excluded.AutoBanOnIllegal,
                TimeoutMinutes = excluded.TimeoutMinutes,
                UpdatedAt = CURRENT_TIMESTAMP
        """
        return await self.execute(query, server_id, 1 if enabled else 0, log_channel_id, action, 1 if auto_ban_on_illegal else 0, timeout_minutes)

    async def log_mod_action(
        self,
        server_id: int,
        channel_id: int,
        user_id: int,
        user_name: str,
        severity: str,
        method: str,
        reason: str,
        action_taken: str,
    ):
        query = """
            INSERT INTO ModActions (ServerID, ChannelID, UserID, UserName, Severity, Method, Reason, ActionTaken)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        return await self.execute(query, server_id, channel_id, user_id, user_name, severity, method, reason, action_taken)

    async def get_recent_mod_actions(self, server_id: int, limit: int = 10) -> list:
        query = """
            SELECT UserName, Severity, Method, Reason, ActionTaken, OccurredAt
            FROM ModActions
            WHERE ServerID = ?
            ORDER BY OccurredAt DESC
            LIMIT ?
        """
        return await self.fetch_all(query, server_id, limit)
