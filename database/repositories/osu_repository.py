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
        # Incluye UserID (Discord ID) para filtrar por servidor en d.rank
        query = "SELECT UserID, UserName, PP, Accuracy, CalculatedRank FROM V_OsuRankingGlobal LIMIT $1"
        return await self.fetch_all(query, limit)

    async def get_score_history(self, user_id: int, limit: int = 10):
        query = "SELECT * FROM fn_GetScoreHistory($1, $2)"
        return await self.fetch_all(query, user_id, limit)
