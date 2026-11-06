from database.repositories.base_repository import BaseRepository

class OsuRepository(BaseRepository):
    async def get_linked_username(self, user_id: int):
        query = "SELECT OsuUsername FROM OsuAccounts WHERE UserID = ? LIMIT 1"
        result = await self.fetch_one(query, user_id)
        return str(result[0]).strip() if result and result[0] else None

    async def link_account(self, user_id, username, osu_id, mode, pp, global_rank, country_rank, accuracy):
        # Asegurar usuario
        await self.execute(
            "INSERT INTO Users (UserID, UserName) VALUES (?, ?) ON CONFLICT(UserID) DO UPDATE SET UserName = excluded.UserName",
            user_id, username
        )
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
        return await self.execute(query, user_id, username, osu_id, mode, pp, global_rank, country_rank, accuracy)

    async def unlink_account(self, user_id: int):
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

