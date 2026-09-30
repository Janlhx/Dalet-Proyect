from database.repositories.base_repository import BaseRepository


class AdminRepository(BaseRepository):
    """Repositorio para configuración administrativa de servidores, canales e idiomas."""

    _lang_cache: dict[int, str] = {}
    _name_cache: dict[int, str] = {}
    _mod_cache: dict[int, dict | None] = {}

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

        # Asegurar columna Language de forma idempotente
        if not getattr(self, "_migrated_server_lang", False):
            try:
                rows = await self.fetch_all("PRAGMA table_info(Servers)")
                existing_cols = {row[1] for row in rows} if rows else set()
                if "Language" not in existing_cols:
                    await self.execute("ALTER TABLE Servers ADD COLUMN Language TEXT DEFAULT 'en'")
            except Exception:
                pass
            self._migrated_server_lang = True

        query = """
            INSERT INTO Servers (ServerID, ServerName, Language, IsReactive)
            VALUES (?, 'Unknown', ?, 1)
            ON CONFLICT(ServerID) DO UPDATE SET Language = excluded.Language
        """
        return await self.execute(query, server_id, lang)

    async def _ensure_mod_columns(self):
        """Asegura de manera defensiva que las columnas de ModerationConfig existan en Turso."""
        if not hasattr(self, "_migrated_mod_cols"):
            try:
                rows = await self.fetch_all("PRAGMA table_info(ModerationConfig)")
                existing_cols = {row[1] for row in rows} if rows else set()
            except Exception:
                existing_cols = set()

            for col, col_def in [
                ("ScanImages", "BOOLEAN DEFAULT 1"),
                ("AntiFlood", "BOOLEAN DEFAULT 1"),
                ("FilterLinks", "BOOLEAN DEFAULT 1"),
                ("FilterScams", "BOOLEAN DEFAULT 1"),
                ("IgnoredChannels", "TEXT DEFAULT ''"),
            ]:
                if col not in existing_cols:
                    try:
                        await self.execute(f"ALTER TABLE ModerationConfig ADD COLUMN {col} {col_def}")
                    except Exception:
                        pass
            self._migrated_mod_cols = True

    async def get_moderation_config(self, server_id: int) -> dict | None:
        if server_id in self._mod_cache:
            return self._mod_cache[server_id]

        await self._ensure_mod_columns()

        query = """
            SELECT Enabled, LogChannelID, Action, AutoBanOnIllegal, TimeoutMinutes,
                   ScanImages, AntiFlood, FilterLinks, FilterScams, IgnoredChannels
            FROM ModerationConfig WHERE ServerID = ?
        """
        row = await self.fetch_one(query, server_id)
        if not row:
            self._mod_cache[server_id] = None
            return None

        def _get_val(idx, default=None):
            try:
                val = row[idx]
                return default if val is None else val
            except (IndexError, KeyError):
                return default

        raw_ignored = _get_val(9, "") or ""
        ignored_list = [int(cid.strip()) for cid in str(raw_ignored).split(",") if cid.strip().isdigit()]

        cfg = {
            "enabled": bool(_get_val(0, 0)),
            "log_channel_id": _get_val(1, None),
            "action": _get_val(2, "notify"),
            "auto_ban_on_illegal": bool(_get_val(3, 0)),
            "timeout_minutes": int(_get_val(4, 10)),
            "scan_images": bool(_get_val(5, 1)),
            "anti_flood": bool(_get_val(6, 1)),
            "filter_links": bool(_get_val(7, 1)),
            "filter_scams": bool(_get_val(8, 1)),
            "ignored_channels": ignored_list,
        }
        self._mod_cache[server_id] = cfg
        return cfg

    async def set_moderation_config(
        self,
        server_id: int,
        enabled: bool,
        log_channel_id: int | None,
        action: str = "notify",
        auto_ban_on_illegal: bool = False,
        timeout_minutes: int = 10,
        scan_images: bool = True,
        anti_flood: bool = True,
        filter_links: bool = True,
        filter_scams: bool = True,
        ignored_channels: list[int] | None = None,
    ):
        await self._ensure_mod_columns()
        channels_str = ",".join(str(c) for c in (ignored_channels or []))

        query = """
            INSERT INTO ModerationConfig (
                ServerID, Enabled, LogChannelID, Action, AutoBanOnIllegal, TimeoutMinutes,
                ScanImages, AntiFlood, FilterLinks, FilterScams, IgnoredChannels, UpdatedAt
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ServerID) DO UPDATE SET
                Enabled = excluded.Enabled,
                LogChannelID = excluded.LogChannelID,
                Action = excluded.Action,
                AutoBanOnIllegal = excluded.AutoBanOnIllegal,
                TimeoutMinutes = excluded.TimeoutMinutes,
                ScanImages = excluded.ScanImages,
                AntiFlood = excluded.AntiFlood,
                FilterLinks = excluded.FilterLinks,
                FilterScams = excluded.FilterScams,
                IgnoredChannels = excluded.IgnoredChannels,
                UpdatedAt = CURRENT_TIMESTAMP
        """
        res = await self.execute(
            query,
            server_id,
            1 if enabled else 0,
            log_channel_id,
            action,
            1 if auto_ban_on_illegal else 0,
            timeout_minutes,
            1 if scan_images else 0,
            1 if anti_flood else 0,
            1 if filter_links else 0,
            1 if filter_scams else 0,
            channels_str,
        )
        self._mod_cache[server_id] = {
            "enabled": enabled,
            "log_channel_id": log_channel_id,
            "action": action,
            "auto_ban_on_illegal": auto_ban_on_illegal,
            "timeout_minutes": timeout_minutes,
            "scan_images": scan_images,
            "anti_flood": anti_flood,
            "filter_links": filter_links,
            "filter_scams": filter_scams,
            "ignored_channels": ignored_channels or [],
        }
        return res

    async def update_moderation_config(self, server_id: int, **kwargs) -> dict:
        """Actualiza campos específicos de ModerationConfig sin sobreescribir el resto."""
        current = await self.get_moderation_config(server_id)
        if not current:
            current = {
                "enabled": True,
                "log_channel_id": None,
                "action": "notify",
                "auto_ban_on_illegal": False,
                "timeout_minutes": 10,
                "scan_images": True,
                "anti_flood": True,
                "filter_links": True,
                "filter_scams": True,
                "ignored_channels": [],
            }

        merged = {**current, **kwargs}
        await self.set_moderation_config(
            server_id=server_id,
            enabled=merged["enabled"],
            log_channel_id=merged["log_channel_id"],
            action=merged["action"],
            auto_ban_on_illegal=merged["auto_ban_on_illegal"],
            timeout_minutes=merged["timeout_minutes"],
            scan_images=merged["scan_images"],
            anti_flood=merged["anti_flood"],
            filter_links=merged["filter_links"],
            filter_scams=merged["filter_scams"],
            ignored_channels=merged.get("ignored_channels", []),
        )
        return merged

    async def add_ignored_channel(self, server_id: int, channel_id: int) -> list[int]:
        """Añade un canal a la lista de canales exentos de moderación."""
        current = await self.get_moderation_config(server_id)
        channels = list(current.get("ignored_channels", [])) if current else []
        if channel_id not in channels:
            channels.append(channel_id)
            await self.update_moderation_config(server_id, ignored_channels=channels)
        return channels

    async def remove_ignored_channel(self, server_id: int, channel_id: int) -> list[int]:
        """Elimina un canal de la lista de canales exentos de moderación."""
        current = await self.get_moderation_config(server_id)
        channels = list(current.get("ignored_channels", [])) if current else []
        if channel_id in channels:
            channels.remove(channel_id)
            await self.update_moderation_config(server_id, ignored_channels=channels)
        return channels

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
