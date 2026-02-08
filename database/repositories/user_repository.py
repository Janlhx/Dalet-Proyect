from database.repositories.base_repository import BaseRepository

class UserRepository(BaseRepository):
    async def is_server_reactive(self, server_id: int):
        query = "SELECT fn_IsServerReactive($1)"
        result = await self.fetch_one(query, server_id)
        return result[0] if result else True

    async def is_channel_proactive(self, channel_id: int):
        query = "SELECT fn_IsChannelProactive($1)"
        result = await self.fetch_one(query, channel_id)
        return result[0] if result else False

    async def add_user_memory(self, user_id, user_name, content, topic="general"):
        return await self.call_procedure(
            "sp_AddUserMemory",
            user_id, user_name, content, topic
        )

    async def get_all_user_memories(self, user_id: int):
        query = "SELECT topic, content FROM fn_GetAllUserMemories($1)"
        return await self.fetch_all(query, user_id)

    async def get_channel_messages(self, channel_id: int, limit: int = 10):
        query = """
            SELECT UserName, Content
            FROM V_ChannelMessages
            WHERE ChannelID = $1
            ORDER BY Timestamp DESC
            LIMIT $2
        """
        return await self.fetch_all(query, channel_id, limit)
    
    async def log_message(self, user_id, user_name, server_id, server_name, channel_id, channel_name, content):
        return await self.call_procedure(
            "sp_LogMessage",
            user_id, user_name, server_id, server_name, channel_id, channel_name, content
        )

    async def search_lore(self, query: str, channel_id: int, limit: int = 25):
        """Busca fragmentos de mensajes pasados que coincidan con un término."""
        sql_query = """
            SELECT UserName, Content, Timestamp
            FROM V_ChannelMessages
            WHERE Content ILIKE $1
            AND ChannelID = $2
            ORDER BY Timestamp DESC
            LIMIT $3
        """
        search_term = f"%{query}%"
        return await self.fetch_all(sql_query, search_term, channel_id, limit)
