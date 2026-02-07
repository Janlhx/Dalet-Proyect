import httpx
import os
import logging
from database.repositories.base_repository import BaseRepository

logger = logging.getLogger("dalet.services.osu")

class OsuService:
    def __init__(self, client_id: int, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.token_expiry = 0
        self.base_url = "https://osu.ppy.sh/api/v2"

    async def _authenticate(self):
        async with httpx.AsyncClient() as client:
            url = "https://osu.ppy.sh/oauth/token"
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
                "scope": "public"
            }
            response = await client.post(url, json=data)
            response.raise_for_status()
            res_json = response.json()
            self.token = res_json["access_token"]
            # Set expiry with small buffer
            import time
            self.token_expiry = time.time() + res_json["expires_in"] - 60

    async def get_token(self):
        import time
        if not self.token or time.time() > self.token_expiry:
            await self._authenticate()
        return self.token

    async def _get(self, endpoint: str, params=None):
        token = await self.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/{endpoint}", headers=headers, params=params)
            response.raise_for_status()
            return response.json()

    async def get_user(self, username: str, mode: str = "osu"):
        return await self._get(f"users/{username}/{mode}")

    async def get_user_best_scores(self, user_id: int, mode: str = "osu", limit: int = 10):
        params = {"mode": mode, "limit": limit}
        return await self._get(f"users/{user_id}/scores/best", params=params)
