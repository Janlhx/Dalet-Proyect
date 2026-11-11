from database.repositories.base_repository import BaseRepository

class OsuRepository(BaseRepository):
    _server_links_cache: dict[tuple[int, str], str] = {}
    _schema_ensured: bool = False

    @staticmethod
    def _extract_col(row, key: str, idx: int = 0) -> str | None:
        if row is None:
            return None
        if isinstance(row, dict):
            val = row.get(key)
            return str(val).strip() if val is not None else None
        try:
            if hasattr(row, "keys") and key in row.keys():
                val = row[key]
                return str(val).strip() if val is not None else None
        except Exception:
            pass
        try:
            val = row[idx]
            return str(val).strip() if val is not None else None
        except Exception:
            return None

    async def _ensure_server_links_schema(self):
        if OsuRepository._schema_ensured:
            return
        try:
            await self.execute("""
                CREATE TABLE IF NOT EXISTS Users (
                    UserID INTEGER PRIMARY KEY,
                    UserName TEXT NOT NULL,
                    Language TEXT DEFAULT NULL
                )
            """)
            await self.execute("""
                CREATE TABLE IF NOT EXISTS OsuAccounts (
                    UserID INTEGER PRIMARY KEY,
                    OsuUsername TEXT NOT NULL,
                    OsuUserID INTEGER,
                    PlayMode TEXT DEFAULT 'osu',
                    PP REAL,
                    GlobalRank INTEGER,
                    CountryRank INTEGER,
                    Accuracy REAL
                )
            """)
            res = await self.execute("""
                CREATE TABLE IF NOT EXISTS OsuServerLinks (
                    UserID INTEGER NOT NULL,
                    OsuServer TEXT NOT NULL DEFAULT 'bancho',
                    OsuUsername TEXT NOT NULL,
                    OsuUserID INTEGER,
                    PlayMode TEXT DEFAULT 'osu',
                    PP REAL DEFAULT 0.0,
                    GlobalRank INTEGER,
                    CountryRank INTEGER,
                    Accuracy REAL DEFAULT 0.0,
                    UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (UserID, OsuServer)
                )
            """)
            if res is not None:
                OsuRepository._schema_ensured = True
        except Exception:
            pass

    async def get_linked_accounts(self, user_id: int) -> dict[str, str]:
        """Devuelve un mapa {server: osu_username} con todas las cuentas vinculadas del usuario."""
        await self._ensure_server_links_schema()
        linked: dict[str, str] = {}
        rows = await self.fetch_all(
            "SELECT OsuServer, OsuUsername FROM OsuServerLinks WHERE UserID = ?",
            user_id,
        )
        for row in rows:
            srv = self._extract_col(row, "OsuServer", 0)
            uname = self._extract_col(row, "OsuUsername", 1)
            if srv and uname:
                linked[srv.lower()] = uname

        legacy_row = await self.fetch_one(
            "SELECT OsuUsername FROM OsuAccounts WHERE UserID = ? LIMIT 1",
            user_id,
        )
        legacy_uname = self._extract_col(legacy_row, "OsuUsername", 0)
        if legacy_uname and "bancho" not in linked:
            linked["bancho"] = legacy_uname
        return linked

    async def get_linked_username(self, user_id: int, server: str = "bancho"):
        """Obtiene el nombre de usuario vinculado para el servidor de osu! indicado (aislado por servidor)."""
        srv = (server or "bancho").lower().strip()
        cache_key = (user_id, srv)
        if cache_key in self._server_links_cache:
            return self._server_links_cache[cache_key]

        await self._ensure_server_links_schema()

        if srv != "bancho":
            row = await self.fetch_one(
                "SELECT OsuUsername FROM OsuServerLinks WHERE UserID = ? AND OsuServer = ? LIMIT 1",
                user_id, srv
            )
            uname = self._extract_col(row, "OsuUsername", 0)
            if not uname and srv.startswith("akatsuki"):
                # Vanilla, Relax y Autopilot comparten cuenta en Akatsuki
                row = await self.fetch_one(
                    "SELECT OsuUsername FROM OsuServerLinks WHERE UserID = ? AND OsuServer LIKE 'akatsuki%' ORDER BY UpdatedAt DESC LIMIT 1",
                    user_id
                )
                uname = self._extract_col(row, "OsuUsername", 0)
            if uname:
                self._server_links_cache[cache_key] = uname
                return uname
            return None

        # Bancho: consultar OsuServerLinks y hacer fallback a la tabla legacy OsuAccounts
        bancho_row = await self.fetch_one(
            "SELECT OsuUsername FROM OsuServerLinks WHERE UserID = ? AND OsuServer = 'bancho' LIMIT 1",
            user_id
        )
        uname = self._extract_col(bancho_row, "OsuUsername", 0)
        if not uname:
            legacy_row = await self.fetch_one(
                "SELECT OsuUsername FROM OsuAccounts WHERE UserID = ? LIMIT 1",
                user_id
            )
            uname = self._extract_col(legacy_row, "OsuUsername", 0)
        if uname:
            self._server_links_cache[cache_key] = uname
            return uname
        return None

    async def link_account(
        self,
        user_id,
        username,
        osu_id,
        mode,
        pp,
        global_rank,
        country_rank,
        accuracy,
        server: str = "bancho",
    ):
        srv = (server or "bancho").lower().strip()
        await self._ensure_server_links_schema()
        # Asegurar fila en Users sin sobreescribir el nombre de Discord si ya existe
        await self.execute(
            "INSERT INTO Users (UserID, UserName) VALUES (?, ?) ON CONFLICT(UserID) DO NOTHING",
            user_id, username
        )
        res = await self.execute(
            """
            INSERT INTO OsuServerLinks (UserID, OsuServer, OsuUsername, OsuUserID, PlayMode, PP, GlobalRank, CountryRank, Accuracy, UpdatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(UserID, OsuServer) DO UPDATE SET
                OsuUsername = excluded.OsuUsername,
                OsuUserID = excluded.OsuUserID,
                PlayMode = excluded.PlayMode,
                PP = excluded.PP,
                GlobalRank = excluded.GlobalRank,
                CountryRank = excluded.CountryRank,
                Accuracy = excluded.Accuracy,
                UpdatedAt = CURRENT_TIMESTAMP
            """,
            user_id, srv, username, osu_id, mode, pp, global_rank, country_rank, accuracy
        )
        if res is None:
            raise RuntimeError(f"Failed to persist osu! link for user_id={user_id} server={srv}")

        # Invalidad/actualizar caché de forma coherente
        self._server_links_cache[(user_id, srv)] = username
        if srv == "akatsuki":
            for variant in ("akatsuki_rx", "akatsuki_ap"):
                self._server_links_cache.pop((user_id, variant), None)

        # Sincronizar OsuAccounts (ranking/snapshots) cuando es Bancho
        if srv == "bancho":
            query = """
                INSERT INTO OsuAccounts (UserID, OsuUsername, OsuUserID, PlayMode, PP, GlobalRank, CountryRank, Accuracy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(UserID) DO UPDATE SET
                    OsuUsername = excluded.OsuUsername,
                    OsuUserID = excluded.OsuUserID,
                    PlayMode = excluded.PlayMode,
                    PP = excluded.PP,
                    GlobalRank = excluded.GlobalRank,
                    CountryRank = excluded.CountryRank,
                    Accuracy = excluded.Accuracy
            """
            bancho_res = await self.execute(query, user_id, username, osu_id, mode, pp, global_rank, country_rank, accuracy)
            if bancho_res is None:
                raise RuntimeError(f"Failed to persist Bancho account for user_id={user_id}")
            return bancho_res
        return True

    async def unlink_account(self, user_id: int, server: str | None = None):
        await self._ensure_server_links_schema()
        if server and server.lower().strip() != "all":
            srv = server.lower().strip()
            self._server_links_cache.pop((user_id, srv), None)
            if srv.startswith("akatsuki"):
                for ak_var in ("akatsuki", "akatsuki_rx", "akatsuki_ap"):
                    self._server_links_cache.pop((user_id, ak_var), None)
            await self.execute("DELETE FROM OsuServerLinks WHERE UserID = ? AND OsuServer = ?", user_id, srv)
            if srv == "bancho":
                return await self.execute("DELETE FROM OsuAccounts WHERE UserID = ?", user_id)
            return True

        # Desvincular todos los servidores
        keys_to_del = [k for k in self._server_links_cache if k[0] == user_id]
        for k in keys_to_del:
            self._server_links_cache.pop(k, None)
        await self.execute("DELETE FROM OsuServerLinks WHERE UserID = ?", user_id)
        query = "DELETE FROM OsuAccounts WHERE UserID = ?"
        return await self.execute(query, user_id)

    async def update_cached_stats(self, user_id: int, osu_username: str, pp: float, global_rank: int, country_rank: int, accuracy: float, mode: str = "osu"):
        """Actualiza las estadísticas cacheadas de un usuario en OsuAccounts sin alterar su PlayMode preferido si no coincide."""
        query = """
            UPDATE OsuAccounts
            SET OsuUsername = ?,
                PP = ?,
                GlobalRank = ?,
                CountryRank = ?,
                Accuracy = ?
            WHERE UserID = ? AND (PlayMode = ? OR PlayMode IS NULL)
        """
        return await self.execute(query, osu_username, pp, global_rank, country_rank, accuracy, user_id, mode)

    async def get_ranking(self, mode: str = "osu", limit: int = 500) -> list[dict]:
        """Obtiene las cuentas vinculadas ordenadas por PP descendente para el ranking del servidor."""
        mode_clean = (mode or "osu").lower().strip()
        query = """
            SELECT 
                oa.UserID,
                u.UserName,
                oa.OsuUsername,
                oa.OsuUserID,
                oa.PlayMode,
                oa.PP,
                oa.GlobalRank,
                oa.CountryRank,
                oa.Accuracy,
                RANK() OVER (ORDER BY oa.PP DESC) AS CalculatedRank
            FROM OsuAccounts oa
            LEFT JOIN Users u ON oa.UserID = u.UserID
            WHERE oa.PP > 0 AND (LOWER(oa.PlayMode) = ? OR (oa.PlayMode IS NULL AND ? = 'osu'))
            ORDER BY oa.PP DESC
            LIMIT ?
        """
        raw_rows = await self.fetch_all(query, mode_clean, mode_clean, limit)
        results = []
        for r in raw_rows:
            if isinstance(r, dict):
                results.append(r)
            elif hasattr(r, "asdict") and callable(r.asdict):
                results.append(r.asdict())
            elif hasattr(r, "_asdict") and callable(r._asdict):
                results.append(r._asdict())
            elif hasattr(r, "keys"):
                results.append({k: r[k] for k in r.keys()})
            else:
                try:
                    results.append(dict(r))
                except Exception:
                    results.append({
                        "UserID": r[0] if len(r) > 0 else None,
                        "UserName": r[1] if len(r) > 1 else None,
                        "OsuUsername": r[2] if len(r) > 2 else (r[1] if len(r) > 1 else None),
                        "OsuUserID": r[3] if len(r) > 3 else None,
                        "PlayMode": r[4] if len(r) > 4 else mode_clean,
                        "PP": r[5] if len(r) > 5 else 0,
                        "GlobalRank": r[6] if len(r) > 6 else None,
                        "CountryRank": r[7] if len(r) > 7 else None,
                        "Accuracy": r[8] if len(r) > 8 else 0,
                    })
        return results


    async def get_recommended_maps(self, min_stars: float, max_stars: float, focus: str, limit: int = 5) -> list:
        """Obtiene mapas recomendados según rango de estrellas y habilidad técnica."""
        query = """
            SELECT beatmapid, beatmapsetid, title, artist, version, stars
            FROM osurecommendedmaps
            WHERE stars BETWEEN ? AND ?
              AND (skills LIKE '%' || ? || '%' OR skills = ?)
            ORDER BY RANDOM()
            LIMIT ?
        """
        results = await self.fetch_all(query, min_stars, max_stars, focus, focus, limit)
        if results:
            return [dict(r) for r in results]

        # Fallback 1: Si no hay mapas con esa debilidad específica, buscar con 'consistencia general'
        if focus != "consistencia general":
            results = await self.fetch_all(query, min_stars, max_stars, "consistencia general", "consistencia general", limit)
            if results:
                return [dict(r) for r in results]

        # Fallback 2: Buscar cualquier mapa en ese rango de estrellas
        query_any = """
            SELECT beatmapid, beatmapsetid, title, artist, version, stars
            FROM osurecommendedmaps
            WHERE stars BETWEEN ? AND ?
            ORDER BY RANDOM()
            LIMIT ?
        """
        results = await self.fetch_all(query_any, min_stars, max_stars, limit)
        return [dict(r) for r in results]

