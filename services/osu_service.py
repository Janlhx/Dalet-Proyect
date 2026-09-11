import httpx
import time
import logging
import asyncio

logger = logging.getLogger("dalet.services.osu")


class OsuService:
    """Wrapper para la API pública de osu! v2."""

    def __init__(self, client_id: int, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token: str | None = None
        self.token_expiry: float = 0
        self.base_url = "https://osu.ppy.sh/api/v2"
        self._attr_cache: dict = {}

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def _authenticate(self):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://osu.ppy.sh/oauth/token",
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                    "scope": "public",
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            self.token = data["access_token"]
            self.token_expiry = time.time() + data["expires_in"] - 60

    async def _get_token(self) -> str:
        if not self.token or time.time() > self.token_expiry:
            await self._authenticate()
        return self.token

    async def _get(self, endpoint: str, params: dict = None) -> dict | list:
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/{endpoint}",
                headers=headers,
                params=params,
                timeout=20.0,
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Usuarios
    # ------------------------------------------------------------------

    async def get_user(self, username: str, mode: str = "osu") -> dict:
        """Perfil completo de un usuario."""
        return await self._get(f"users/{username}/{mode}")

    async def get_user_by_id(self, user_id: int, mode: str = "osu") -> dict:
        """Perfil de un usuario por ID numérico."""
        return await self._get(f"users/{user_id}/{mode}", params={"key": "id"})

    # ------------------------------------------------------------------
    # Scores del usuario
    # ------------------------------------------------------------------

    async def get_user_best_scores(self, user_id: int, mode: str = "osu", limit: int = 10) -> list:
        """Top plays del usuario."""
        return await self._get(
            f"users/{user_id}/scores/best",
            params={"mode": mode, "limit": limit}
        )

    async def get_user_recent_scores(
        self, user_id: int, mode: str = "osu", limit: int = 10, include_fails: int = 1
    ) -> list:
        """Jugadas recientes del usuario."""
        return await self._get(
            f"users/{user_id}/scores/recent",
            params={"mode": mode, "limit": limit, "include_fails": include_fails}
        )

    async def get_user_pinned_scores(self, user_id: int, mode: str = "osu") -> list:
        """Scores anclados en el perfil del usuario."""
        return await self._get(
            f"users/{user_id}/scores/pinned",
            params={"mode": mode, "limit": 10}
        )

    async def get_user_firsts(self, user_id: int, mode: str = "osu", limit: int = 10) -> list:
        """#1s globales del usuario."""
        return await self._get(
            f"users/{user_id}/scores/firsts",
            params={"mode": mode, "limit": limit}
        )

    # ------------------------------------------------------------------
    # Beatmaps
    # ------------------------------------------------------------------

    async def get_beatmap(self, beatmap_id: int) -> dict:
        """Información de un beatmap específico."""
        return await self._get(f"beatmaps/{beatmap_id}")

    async def get_beatmap_scores(self, beatmap_id: int, mode: str = "osu") -> dict:
        """Top scores globales de un beatmap."""
        return await self._get(
            f"beatmaps/{beatmap_id}/scores",
            params={"mode": mode}
        )

    async def search_beatmaps(
        self, mode: str = "osu", min_stars: float = 0, max_stars: float = 10,
        keyword: str = "", status: str = "ranked"
    ) -> list:
        """Busca beatmaps con filtros."""
        q = f"status={status}"
        if keyword:
            q += f" {keyword}"
        params = {
            "q": q,
            "m": {"osu": 0, "taiko": 1, "fruits": 2, "mania": 3}.get(mode, 0),
            "sort": "plays_desc",
        }
        res = await self._get("beatmapsets/search", params=params)
        sets = res.get("beatmapsets", [])
        # Filtrar por rango de estrellas en Python
        return [
            s for s in sets
            if any(
                min_stars <= b.get("difficulty_rating", 0) <= max_stars
                for b in s.get("beatmaps", [])
            )
        ]

    async def get_beatmap_attributes(self, beatmap_id: int, ruleset_id: int = 0, mods: list = None) -> dict:
        """Obtiene atributos de dificultad de la API v2 (Lazer/Bancho): aim_difficulty, speed_difficulty, etc."""
        cache_key = f"{beatmap_id}_{ruleset_id}_{tuple(sorted(mods or []))}"
        if cache_key in self._attr_cache:
            return self._attr_cache[cache_key]

        endpoint = f"beatmaps/{beatmap_id}/attributes"
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"ruleset_id": ruleset_id}
        if mods:
            payload["mods"] = mods

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/{endpoint}",
                    headers=headers,
                    json=payload,
                    timeout=10.0
                )
                if resp.status_code == 200:
                    attrs = resp.json().get("attributes", {})
                    self._attr_cache[cache_key] = attrs
                    return attrs
        except Exception as e:
            logger.debug(f"No se pudieron obtener atributos de dificultad para {beatmap_id}: {e}")

        return {}

    async def enrich_scores_with_attributes(self, scores: list, mode: str = "osu") -> list:
        """Enriquece una lista de jugadas con atributos oficiales de dificultad de Bancho (Star Rating oficial con mods)."""
        if not scores:
            return scores

        mode_int = {"osu": 0, "taiko": 1, "fruits": 2, "mania": 3}.get((mode or "osu").lower(), 0)
        tasks = []
        indices_to_fetch = []

        for idx, p in enumerate(scores):
            bm = p.get("beatmap", {})
            b_id = bm.get("id")
            mods = p.get("mods", [])
            if b_id and mods:
                tasks.append(self.get_beatmap_attributes(b_id, ruleset_id=mode_int, mods=mods))
                indices_to_fetch.append(idx)
            else:
                base_sr = float(bm.get("difficulty_rating", 0.0) or 0.0)
                if base_sr > 0:
                    p["official_sr"] = base_sr

        if tasks:
            results = await asyncio.gather(*tasks)
            for idx, attrs in zip(indices_to_fetch, results):
                if attrs and attrs.get("star_rating"):
                    scores[idx]["official_sr"] = attrs["star_rating"]
                    scores[idx]["beatmap_attributes"] = attrs

        return scores

