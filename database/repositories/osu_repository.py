from database.repositories.base_repository import BaseRepository

class OsuRepository(BaseRepository):
    async def get_linked_username(self, user_id: int):
        query = "SELECT osuusername FROM osuaccounts WHERE userid = $1 LIMIT 1"
        result = await self.fetch_one(query, user_id)
        return str(result[0]).strip() if result and result[0] else None

    async def link_account(self, user_id, username, osu_id, mode, pp, global_rank, country_rank, accuracy):
        return await self.call_procedure(
            "sp_LinkOsuAccount",
            user_id, username, osu_id, mode, pp, global_rank, country_rank, accuracy
        )

    async def unlink_account(self, user_id: int):
        return await self.call_procedure("sp_UnlinkOsuAccount", user_id)

    async def save_score(self, score_id, user_id, osu_user_id, beatmap_id, score, accuracy, mods, score_type, timestamp):
        return await self.call_procedure(
            "sp_SaveOrUpdateOsuScore",
            score_id, user_id, osu_user_id, beatmap_id, score, accuracy, mods, score_type, timestamp
        )

    async def get_ranking(self, limit: int = 10):
        # Usamos join manual en lugar de la vista para poder leer UserID (el Discord ID)
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
            LIMIT $1
        """
        return await self.fetch_all(query, limit)

    async def get_score_history(self, user_id: int, limit: int = 10):
        query = "SELECT * FROM fn_GetScoreHistory($1, $2)"
        return await self.fetch_all(query, user_id, limit)

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

