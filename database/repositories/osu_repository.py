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

    async def get_ranking(self, limit: int = 10):
        query = """
            SELECT 
                u.UserID,
                u.UserName,
                oa.PP,
                oa.Accuracy,
                RANK() OVER (ORDER BY oa.PP DESC) AS CalculatedRank
            FROM OsuAccounts oa
            JOIN Users u ON oa.UserID = u.UserID
            WHERE oa.PP > 0
            LIMIT ?
        """
        return await self.fetch_all(query, limit)


    async def get_recommended_maps(self, min_stars: float, max_stars: float, focus: str, limit: int = 5) -> list:
        # Intentamos obtener mapas que coincidan con la debilidad y el rango de estrellas
        query = """
            SELECT beatmapid, beatmapsetid, title, artist, version, stars
            FROM osurecommendedmaps
            WHERE stars BETWEEN $1 AND $2
              AND $3 = ANY(skills)
            ORDER BY RANDOM()
            LIMIT $4
        """
        results = await self.fetch_all(query, min_stars, max_stars, focus, limit)
        if results:
            return [dict(r) for r in results]
            
        # Fallback 1: Si no hay mapas con esa debilidad específica, buscar con "consistencia general"
        if focus != "consistencia general":
            results = await self.fetch_all(query, min_stars, max_stars, "consistencia general", limit)
            if results:
                return [dict(r) for r in results]
                
        # Fallback 2: Buscar cualquier mapa en ese rango de estrellas
        query_any = """
            SELECT beatmapid, beatmapsetid, title, artist, version, stars
            FROM osurecommendedmaps
            WHERE stars BETWEEN $1 AND $2
            ORDER BY RANDOM()
            LIMIT $3
        """
        results = await self.fetch_all(query_any, min_stars, max_stars, limit)
        return [dict(r) for r in results]

