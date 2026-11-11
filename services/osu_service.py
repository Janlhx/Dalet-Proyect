import httpx
import re
import time
import logging
import asyncio
from datetime import datetime, timezone
from urllib.parse import quote
from collections import OrderedDict

try:
    from cachetools import TTLCache
except ImportError:
    class TTLCache(OrderedDict):
        """Fallback LRU+TTL acotado en stdlib cuando cachetools no está instalado en el entorno."""

        def __init__(self, maxsize: int = 128, ttl: float = 3600):
            super().__init__()
            self._maxsize = max(1, int(maxsize))
            self._ttl = float(ttl)
            self._expiry: dict = {}

        def _purge(self):
            now = time.monotonic()
            expired = [k for k, exp in self._expiry.items() if now >= exp]
            for k in expired:
                self._expiry.pop(k, None)
                OrderedDict.pop(self, k, None)

        def __contains__(self, key) -> bool:
            self._purge()
            return super().__contains__(key)

        def __getitem__(self, key):
            self._purge()
            val = super().__getitem__(key)
            self.move_to_end(key)
            return val

        def get(self, key, default=None):
            self._purge()
            if super().__contains__(key):
                val = super().__getitem__(key)
                self.move_to_end(key)
                return val
            return default

        def __setitem__(self, key, value):
            self._purge()
            super().__setitem__(key, value)
            self._expiry[key] = time.monotonic() + self._ttl
            self.move_to_end(key)
            while len(self) > self._maxsize:
                old_key, _ = self.popitem(last=False)
                self._expiry.pop(old_key, None)

try:
    import rosu_pp_py as rp
except ImportError:
    rp = None

logger = logging.getLogger("dalet.services.osu")


class OsuUserNotFoundError(ValueError):
    """Se lanza cuando el jugador solicitado no existe en el servidor de osu! indicado."""

MOD_BITFLAGS = [
    (1, "NF"),
    (2, "EZ"),
    (8, "HD"),
    (16, "HR"),
    (32, "SD"),
    (64, "DT"),
    (128, "RX"),
    (256, "HT"),
    (512, "NC"),
    (1024, "FL"),
    (2048, "AT"),
    (4096, "SO"),
    (8192, "AP"),
    (16384, "PF"),
    (32768, "4K"),
    (65536, "5K"),
    (131072, "6K"),
    (262144, "7K"),
    (524288, "8K"),
    (1048576, "FI"),
    (2097152, "RD"),
    (16777216, "9K"),
    (536870912, "V2"),
    (1073741824, "MR"),
]


def decode_mods_bitmask(mods_val) -> list[str]:
    """Convierte un entero bitwise de mods de osu! (usado por Akatsuki y Gatari) en una lista de acrónimos."""
    if isinstance(mods_val, list):
        return [m if isinstance(m, str) else str(m.get("acronym", "")) for m in mods_val if m]
    try:
        bits = int(mods_val or 0)
    except Exception:
        return []
    if bits <= 0:
        return []

    mods = []
    for flag, name in MOD_BITFLAGS:
        if bits & flag:
            mods.append(name)
    if "NC" in mods and "DT" in mods:
        mods.remove("DT")
    if "PF" in mods and "SD" in mods:
        mods.remove("SD")
    return mods


def parse_song_name(song_name: str) -> tuple[str, str, str]:
    """Separa 'Artist - Title [Version]' de Akatsuki/Gatari en (artist, title, version)."""
    s = (song_name or "Unknown - Unknown [Normal]").strip()
    version = "Normal"
    if s.endswith("]") and "[" in s:
        idx = s.rfind("[")
        version = s[idx + 1:-1].strip() or "Normal"
        s = s[:idx].strip()
    if " - " in s:
        artist, title = s.split(" - ", 1)
        return artist.strip(), title.strip(), version
    return "", s, version


class OsuService:
    """Wrapper multi-servidor para la API pública de osu! v2 (Bancho), Akatsuki y Gatari."""

    def __init__(self, client_id: int, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token: str | None = None
        self.token_expiry: float = 0
        self.base_url = "https://osu.ppy.sh/api/v2"
        self._attr_cache: dict = {}
        self._bm_cache: dict[int, dict] = {}
        self._osu_file_cache: TTLCache = TTLCache(maxsize=128, ttl=3600)
        self._channel_last_beatmap: TTLCache = TTLCache(maxsize=500, ttl=86400)

    def remember_channel_map(self, channel_id: int | None, beatmap_id: int | None, mode: str = "osu"):
        """Guarda en memoria el último beatmap mostrado en el canal para `d.m` / `/map` sin argumentos."""
        if channel_id and beatmap_id:
            try:
                self._channel_last_beatmap[int(channel_id)] = (int(beatmap_id), (mode or "osu").lower())
            except Exception:
                pass

    def get_channel_map(self, channel_id: int | None) -> tuple[int, str] | None:
        if not channel_id:
            return None
        return self._channel_last_beatmap.get(int(channel_id))

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
    # Usuarios (Bancho / Akatsuki / Gatari)
    # ------------------------------------------------------------------

    @staticmethod
    def _mode_to_int(mode: str) -> int:
        return {"osu": 0, "taiko": 1, "fruits": 2, "mania": 3}.get((mode or "osu").lower(), 0)

    @staticmethod
    def _mode_to_akatsuki_key(mode: str) -> str:
        return {"osu": "std", "taiko": "taiko", "fruits": "ctb", "mania": "mania"}.get((mode or "osu").lower(), "std")

    @staticmethod
    def _server_rx_flag(server: str) -> int:
        s = (server or "bancho").lower().strip()
        if s in ("akatsuki_rx", "rx", "relax"):
            return 1
        if s in ("akatsuki_ap", "ap", "autopilot"):
            return 2
        return 0

    async def get_user(self, username: str, mode: str = "osu", server: str = "bancho") -> dict:
        """Perfil completo de un usuario normalizado al esquema Bancho v2."""
        srv = (server or "bancho").lower().strip()
        if srv.startswith("akatsuki") or srv in ("rx", "ap"):
            return await self._get_akatsuki_user(username, mode=mode, rx=self._server_rx_flag(srv))
        if srv == "gatari":
            return await self._get_gatari_user(username, mode=mode)
        encoded_user = quote(str(username).strip(), safe="")
        try:
            data = await self._get(f"users/{encoded_user}/{mode}")
        except httpx.HTTPStatusError as e:
            if e.response is not None and e.response.status_code == 404:
                raise OsuUserNotFoundError(f"Bancho user '{username}' not found") from e
            raise
        if isinstance(data, dict):
            data["_server"] = "bancho"
        return data

    async def get_user_by_id(self, user_id: int, mode: str = "osu", server: str = "bancho") -> dict:
        """Perfil de un usuario por ID numérico."""
        srv = (server or "bancho").lower().strip()
        if srv.startswith("akatsuki") or srv in ("rx", "ap"):
            return await self._get_akatsuki_user(str(user_id), mode=mode, rx=self._server_rx_flag(srv), by_id=True)
        if srv == "gatari":
            return await self._get_gatari_user(str(user_id), mode=mode, by_id=True)
        try:
            data = await self._get(f"users/{user_id}/{mode}", params={"key": "id"})
        except httpx.HTTPStatusError as e:
            if e.response is not None and e.response.status_code == 404:
                raise OsuUserNotFoundError(f"Bancho user id '{user_id}' not found") from e
            raise
        if isinstance(data, dict):
            data["_server"] = "bancho"
        return data

    async def _get_akatsuki_user(self, username_or_id: str, mode: str = "osu", rx: int = 0, by_id: bool = False) -> dict:
        target = str(username_or_id).strip()
        params = {"id": target} if (by_id or target.isdigit()) else {"name": target}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://akatsuki.gg/api/v1/users/full", params=params)
            if resp.status_code != 200 and "id" in params:
                resp = await client.get("https://akatsuki.gg/api/v1/users/full", params={"name": target})
            if resp.status_code == 404:
                raise OsuUserNotFoundError(f"Akatsuki user '{target}' not found")
            resp.raise_for_status()
            raw = resp.json()
        if not isinstance(raw, dict) or not raw.get("id"):
            raise OsuUserNotFoundError(f"Akatsuki user '{target}' not found")

        uid = raw.get("id", 0)
        uname = raw.get("username", str(username_or_id))
        country_code = (raw.get("country") or "").upper()
        stats_arr = raw.get("stats") or []
        rx_idx = min(max(0, rx), len(stats_arr) - 1) if stats_arr else 0
        mode_key = self._mode_to_akatsuki_key(mode)
        st = (stats_arr[rx_idx] if stats_arr else {}).get(mode_key, {}) or {}

        lvl_float = float(st.get("level") or 0.0)
        lvl_curr = int(lvl_float)
        lvl_prog = int(round((lvl_float - lvl_curr) * 100))
        grades = st.get("grades") or {}

        srv_tag = "akatsuki_rx" if rx == 1 else ("akatsuki_ap" if rx == 2 else "akatsuki")
        return {
            "id": uid,
            "username": uname,
            "playmode": mode,
            "_server": srv_tag,
            "profile_url": f"https://akatsuki.gg/u/{uid}",
            "avatar_url": f"https://a.akatsuki.gg/{uid}",
            "country_code": country_code,
            "country": {"code": country_code, "name": country_code},
            "rank_highest": {"rank": st.get("global_leaderboard_rank")},
            "statistics": {
                "pp": float(st.get("pp") or 0.0),
                "global_rank": st.get("global_leaderboard_rank"),
                "country_rank": st.get("country_leaderboard_rank"),
                "hit_accuracy": float(st.get("accuracy") or 0.0),
                "play_count": int(st.get("playcount") or 0),
                "play_time": int(st.get("playtime") or 0),
                "maximum_combo": int(st.get("max_combo") or 0),
                "ranked_score": int(st.get("ranked_score") or 0),
                "total_score": int(st.get("total_score") or 0),
                "level": {"current": lvl_curr, "progress": lvl_prog},
                "grade_counts": {
                    "ssh": int(grades.get("xh_count") or 0),
                    "ss": int(grades.get("x_count") or 0),
                    "sh": int(grades.get("sh_count") or 0),
                    "s": int(grades.get("s_count") or 0),
                    "a": int(grades.get("a_count") or 0),
                },
            },
        }

    async def _get_gatari_user(self, username_or_id: str, mode: str = "osu", by_id: bool = False) -> dict:
        target = str(username_or_id).strip()
        mode_int = self._mode_to_int(mode)
        user_params = {"id": target} if by_id else {"u": target}
        stats_params = {"id": target, "mode": mode_int} if by_id else {"u": target, "mode": mode_int}
        async with httpx.AsyncClient(timeout=15.0) as client:
            u_resp, s_resp = await asyncio.gather(
                client.get("https://api.gatari.pw/users/get", params=user_params),
                client.get("https://api.gatari.pw/user/stats", params=stats_params),
            )
            if u_resp.status_code == 404:
                raise OsuUserNotFoundError(f"Gatari user '{target}' not found")
            u_resp.raise_for_status()
            u_json = u_resp.json()
            s_json = s_resp.json() if s_resp.status_code == 200 else {}

        users_list = u_json.get("users") or []
        if not users_list:
            raise OsuUserNotFoundError(f"Gatari user '{target}' not found")
        u_raw = users_list[0]
        st = s_json.get("stats") or {}

        uid = u_raw.get("id", 0)
        uname = u_raw.get("username", str(username_or_id))
        country_code = (u_raw.get("country") or "").upper()

        return {
            "id": uid,
            "username": uname,
            "playmode": mode,
            "_server": "gatari",
            "profile_url": f"https://osu.gatari.pw/u/{uid}",
            "avatar_url": f"https://a.gatari.pw/{uid}",
            "country_code": country_code,
            "country": {"code": country_code, "name": country_code},
            "rank_highest": {"rank": st.get("rank")},
            "statistics": {
                "pp": float(st.get("pp") or 0.0),
                "global_rank": st.get("rank"),
                "country_rank": st.get("country_rank"),
                "hit_accuracy": float(st.get("avg_accuracy") or 0.0),
                "play_count": int(st.get("playcount") or 0),
                "play_time": int(st.get("playtime") or 0),
                "maximum_combo": int(st.get("max_combo") or 0),
                "ranked_score": int(st.get("ranked_score") or 0),
                "total_score": int(st.get("total_score") or 0),
                "level": {
                    "current": int(st.get("level") or 0),
                    "progress": int(st.get("level_progress") or 0),
                },
                "grade_counts": {
                    "ssh": int(st.get("xh_count") or 0),
                    "ss": int(st.get("x_count") or 0),
                    "sh": int(st.get("sh_count") or 0),
                    "s": int(st.get("s_count") or 0),
                    "a": int(st.get("a_count") or 0),
                },
            },
        }

    # ------------------------------------------------------------------
    # Scores del usuario (Bancho / Akatsuki / Gatari)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_private_score(raw: dict, server: str) -> dict:
        bm = raw.get("beatmap") or {}
        song_name = bm.get("song_name", "")
        artist_parsed, title_parsed, ver_parsed = parse_song_name(song_name)
        artist = bm.get("artist") or artist_parsed
        title = bm.get("title") or title_parsed
        version = bm.get("version") or ver_parsed
        b_id = bm.get("beatmap_id") or bm.get("id") or 0
        bset_id = bm.get("beatmapset_id") or 0

        diff_2 = bm.get("difficulty2") or {}
        sr = float(bm.get("difficulty") or diff_2.get("std") or 0.0)
        max_c_bm = bm.get("max_combo") or bm.get("fc") or 0

        raw_time = raw.get("time")
        if isinstance(raw_time, (int, float)) and raw_time > 0:
            created_at = datetime.fromtimestamp(raw_time, tz=timezone.utc).isoformat()
        else:
            created_at = str(raw_time or "")

        acc_raw = float(raw.get("accuracy") or 0.0)
        acc_norm = acc_raw / 100.0 if acc_raw > 1.0 else acc_raw
        completed_val = int(raw.get("completed", 3) or 0)
        rank_str = str(raw.get("rank") or raw.get("ranking") or "F").upper()
        passed = completed_val >= 2 and rank_str != "F"

        mods_list = decode_mods_bitmask(raw.get("mods", 0))
        if server == "akatsuki_rx" and "RX" not in mods_list:
            mods_list.append("RX")
        elif server == "akatsuki_ap" and "AP" not in mods_list:
            mods_list.append("AP")

        return {
            "id": raw.get("id"),
            "_server": server,
            "score": int(raw.get("score") or 0),
            "total_score": int(raw.get("score") or 0),
            "max_combo": int(raw.get("max_combo") or 0),
            "accuracy": acc_norm,
            "pp": float(raw.get("pp") or 0.0) if raw.get("pp") is not None else None,
            "rank": rank_str,
            "passed": passed,
            "mods": mods_list,
            "created_at": created_at,
            "statistics": {
                "count_300": int(raw.get("count_300") or 0),
                "count_100": int(raw.get("count_100") or 0),
                "count_50": int(raw.get("count_50") or 0),
                "count_miss": int(raw.get("count_miss") or 0),
            },
            "beatmap": {
                "id": b_id,
                "beatmapset_id": bset_id,
                "version": version,
                "difficulty_rating": sr,
                "ar": float(bm.get("ar") or 9.0),
                "accuracy": float(bm.get("od") or 8.0),
                "cs": float(bm.get("cs") or 4.0),
                "drain": float(bm.get("hp") or 5.0),
                "bpm": float(bm.get("bpm") or 180.0),
                "hit_length": int(bm.get("hit_length") or 180),
                "total_length": int(bm.get("hit_length") or 180),
                "max_combo": int(max_c_bm) if max_c_bm else None,
            },
            "beatmapset": {
                "id": bset_id,
                "title": title,
                "artist": artist,
                "covers": {
                    "list": f"https://assets.ppy.sh/beatmaps/{bset_id}/covers/list.jpg" if bset_id else None,
                    "cover": f"https://assets.ppy.sh/beatmaps/{bset_id}/covers/cover.jpg" if bset_id else None,
                },
            },
        }

    async def get_user_best_scores(self, user_id: int, mode: str = "osu", limit: int = 10, server: str = "bancho") -> list:
        """Top plays del usuario (soporta Bancho, Akatsuki y Gatari)."""
        srv = (server or "bancho").lower().strip()
        mode_int = self._mode_to_int(mode)
        if srv.startswith("akatsuki") or srv in ("rx", "ap"):
            rx_flag = self._server_rx_flag(srv)
            srv_tag = "akatsuki_rx" if rx_flag == 1 else ("akatsuki_ap" if rx_flag == 2 else "akatsuki")
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://akatsuki.gg/api/v1/users/scores/best",
                    params={"id": user_id, "mode": mode_int, "rx": rx_flag, "l": min(limit, 100)},
                )
                resp.raise_for_status()
                scores = resp.json().get("scores") or []
                return [self._normalize_private_score(s, srv_tag) for s in scores]

        if srv == "gatari":
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.gatari.pw/user/scores/best",
                    params={"id": user_id, "mode": mode_int, "l": min(limit, 100), "p": 1},
                )
                resp.raise_for_status()
                scores = resp.json().get("scores") or []
                return [self._normalize_private_score(s, "gatari") for s in scores]

        return await self._get(
            f"users/{user_id}/scores/best",
            params={"mode": mode, "limit": limit}
        )

    async def get_user_recent_scores(
        self, user_id: int, mode: str = "osu", limit: int = 10, include_fails: int = 1, server: str = "bancho"
    ) -> list:
        """Jugadas recientes del usuario (soporta Bancho, Akatsuki y Gatari)."""
        srv = (server or "bancho").lower().strip()
        mode_int = self._mode_to_int(mode)
        if srv.startswith("akatsuki") or srv in ("rx", "ap"):
            rx_flag = self._server_rx_flag(srv)
            srv_tag = "akatsuki_rx" if rx_flag == 1 else ("akatsuki_ap" if rx_flag == 2 else "akatsuki")
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://akatsuki.gg/api/v1/users/scores/recent",
                    params={"id": user_id, "mode": mode_int, "rx": rx_flag, "l": min(limit, 50)},
                )
                resp.raise_for_status()
                scores = resp.json().get("scores") or []
                norm = [self._normalize_private_score(s, srv_tag) for s in scores]
                if not include_fails:
                    norm = [s for s in norm if s.get("passed", True)]
                return norm

        if srv == "gatari":
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.gatari.pw/user/scores/recent",
                    params={"id": user_id, "mode": mode_int, "l": min(limit, 50), "p": 1, "f": include_fails},
                )
                resp.raise_for_status()
                scores = resp.json().get("scores") or []
                return [self._normalize_private_score(s, "gatari") for s in scores]

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

    async def get_user_firsts(self, user_id: int, mode: str = "osu", limit: int = 10, server: str = "bancho") -> list:
        """#1s globales del usuario."""
        srv = (server or "bancho").lower().strip()
        mode_int = self._mode_to_int(mode)
        if srv.startswith("akatsuki") or srv in ("rx", "ap"):
            rx_flag = self._server_rx_flag(srv)
            srv_tag = "akatsuki_rx" if rx_flag == 1 else ("akatsuki_ap" if rx_flag == 2 else "akatsuki")
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        "https://akatsuki.gg/api/v1/users/scores/first",
                        params={"id": user_id, "mode": mode_int, "rx": rx_flag, "l": min(limit, 20)},
                    )
                    if resp.status_code == 200:
                        scores = resp.json().get("scores") or []
                        return [self._normalize_private_score(s, srv_tag) for s in scores]
            except Exception:
                return []
            return []
        if srv == "gatari":
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        "https://api.gatari.pw/user/scores/first",
                        params={"id": user_id, "mode": mode_int, "l": min(limit, 20), "p": 1},
                    )
                    if resp.status_code == 200:
                        scores = resp.json().get("scores") or []
                        return [self._normalize_private_score(s, "gatari") for s in scores]
            except Exception:
                return []
            return []
        return await self._get(
            f"users/{user_id}/scores/firsts",
            params={"mode": mode, "limit": limit}
        )

    async def get_user_most_played(self, user_id: int, limit: int = 5) -> list:
        """Mapas más jugados / con más reintentos por el usuario."""
        return await self._get(
            f"users/{user_id}/beatmapsets/most_played",
            params={"limit": limit}
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
            raw_mods = p.get("mods", [])
            # Filtrar RX/AP para el endpoint de Bancho attributes que solo acepta mods estándar de dificultad
            clean_mods = [
                m for m in raw_mods
                if (isinstance(m, str) and m.upper() not in ("RX", "AP", "V2"))
                or (isinstance(m, dict) and str(m.get("acronym", "")).upper() not in ("RX", "AP", "V2"))
            ]
            base_sr = float(bm.get("difficulty_rating", 0.0) or 0.0)
            if b_id and (clean_mods or base_sr <= 0):
                tasks.append(self.get_beatmap_attributes(b_id, ruleset_id=mode_int, mods=clean_mods))
                indices_to_fetch.append(idx)
            elif base_sr > 0:
                p["official_sr"] = base_sr

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for idx, attrs in zip(indices_to_fetch, results):
                if isinstance(attrs, dict) and attrs.get("star_rating"):
                    scores[idx]["official_sr"] = attrs["star_rating"]
                    scores[idx]["beatmap_attributes"] = attrs
                    bm_ref = scores[idx].get("beatmap")
                    if isinstance(bm_ref, dict) and not bm_ref.get("difficulty_rating"):
                        bm_ref["difficulty_rating"] = attrs["star_rating"]

        return scores

    # ------------------------------------------------------------------
    # Descarga .osu, Simulación rosu-pp (Fails / If-FC / d.m) y Beatmap Resolve
    # ------------------------------------------------------------------

    @staticmethod
    def _to_rosu_mode(mode: str):
        if rp is None:
            return None
        m = (mode or "osu").lower().strip()
        if m in ("taiko",):
            return rp.GameMode.Taiko
        if m in ("fruits", "ctb", "catch"):
            return rp.GameMode.Catch
        if m in ("mania",):
            return rp.GameMode.Mania
        return rp.GameMode.Osu

    @staticmethod
    def _clean_rosu_mods(mods) -> list[str]:
        if not mods:
            return []
        raw_list = []
        if isinstance(mods, str):
            clean = mods.upper().replace("+", "").replace(",", "").replace(" ", "").strip()
            raw_list = [clean[i:i + 2] for i in range(0, len(clean), 2) if len(clean[i:i + 2]) == 2]
        else:
            for m in mods:
                if isinstance(m, str) and m.strip():
                    raw_list.append(m.strip().upper())
                elif isinstance(m, dict) and m.get("acronym"):
                    raw_list.append(str(m["acronym"]).strip().upper())
        # V2/SV2 no altera el cálculo en rosu y algunos acrónimos pueden combinarse
        return [m for m in raw_list if m and m not in ("NM", "V2", "SV2")]

    @classmethod
    def parse_map_args(cls, raw_args: str | None) -> tuple[str, list[str], str | None]:
        """Extrae query/URL/ID, lista de mods (+HDDT) y override de modo (-mania) para d.m."""
        mode_map = {
            "osu": "osu", "std": "osu", "o": "osu",
            "taiko": "taiko", "t": "taiko",
            "fruits": "fruits", "ctb": "fruits", "catch": "fruits", "c": "fruits",
            "mania": "mania", "m": "mania",
        }
        mods_list: list[str] = []
        mode_override: str | None = None
        query_tokens: list[str] = []

        if raw_args:
            for part in raw_args.split():
                low = part.lower().strip()
                stripped = low.lstrip("-")
                if low.startswith("-") and stripped in mode_map:
                    mode_override = mode_map[stripped]
                elif low.startswith("+") and len(low) >= 3:
                    mods_list.extend(cls._clean_rosu_mods(low))
                else:
                    query_tokens.append(part)

        # Mantener unicidad preservando orden
        dedup_mods = list(dict.fromkeys(mods_list))
        return " ".join(query_tokens).strip(), dedup_mods, mode_override

    async def get_osu_file_bytes(self, beatmap_id: int) -> bytes | None:
        """Descarga el archivo .osu público desde osu.ppy.sh/osu/<id> con caché LRU (sin cuota OAuth)."""
        if not beatmap_id:
            return None
        bid = int(beatmap_id)
        if bid in self._osu_file_cache:
            return self._osu_file_cache[bid]
        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                resp = await client.get(f"https://osu.ppy.sh/osu/{bid}")
                if resp.status_code == 200 and resp.content:
                    self._osu_file_cache[bid] = resp.content
                    return resp.content
        except Exception as e:
            logger.debug(f"No se pudo descargar .osu para beatmap {bid}: {e}")
        return None

    @classmethod
    def compute_rosu_score_pp(cls, osu_bytes: bytes, score: dict, mode: str = "osu") -> dict:
        """
        Calcula PP real alcanzado (incluidos fails y mapas unranked), PP 'if FC',
        SR y atributos ajustados a mods usando rosu-pp-py.
        """
        if rp is None or not osu_bytes:
            return {}
        try:
            bm = rp.Beatmap(bytes=osu_bytes)
            target_mode = cls._to_rosu_mode(mode)
            if target_mode is not None and bm.mode != target_mode:
                bm.convert(target_mode)

            mods = cls._clean_rosu_mods(score.get("mods", []))
            stats = cls._normalize_score_stats(score.get("statistics") or {})
            c300 = int(stats.get("count_300") or 0)
            c100 = int(stats.get("count_100") or 0)
            c50 = int(stats.get("count_50") or 0)
            miss = int(stats.get("count_miss") or 0)
            geki = int(stats.get("count_geki") or 0)
            katu = int(stats.get("count_katu") or 0)
            max_combo = int(score.get("max_combo") or 0)

            rank_str = str(score.get("rank") or "").upper()
            is_failed = (score.get("passed") is False) or (rank_str == "F")

            m_low = (mode or "osu").lower().strip()
            if m_low == "mania":
                total_hits = c300 + c100 + c50 + miss + geki + katu
            elif m_low == "taiko":
                total_hits = c300 + c100 + miss
            else:
                total_hits = c300 + c100 + c50 + miss

            acc_raw = float(score.get("accuracy") or 0.0)
            acc_pct = acc_raw * 100.0 if acc_raw <= 1.0 else acc_raw
            acc_pct = max(0.0, min(100.0, acc_pct))

            # Atributos reales del mapa con los mods aplicados
            attr_builder = rp.BeatmapAttributesBuilder(map=bm, mods=mods)
            b_attrs = attr_builder.build()
            diff_res = rp.Difficulty(mods=mods).calculate(bm)
            bm_max_combo = int(getattr(diff_res, "max_combo", 0) or 0)
            full_stars = float(getattr(diff_res, "stars", 0.0) or 0.0)

            # PP actual: si la API ya devolvió PP positivo en pass, lo respetamos como oficial
            api_pp = score.get("pp")
            api_pp_val = float(api_pp) if api_pp is not None else None
            pp_is_simulated = False

            if api_pp_val is not None and api_pp_val > 0.0 and not is_failed:
                actual_pp = api_pp_val
            elif total_hits <= 0:
                actual_pp = 0.0
                pp_is_simulated = True
            else:
                perf_kwargs = dict(
                    mods=mods,
                    n300=c300,
                    n100=c100,
                    n50=c50,
                    misses=miss,
                    combo=max_combo,
                )
                if m_low == "mania":
                    perf_kwargs["n_geki"] = geki
                    perf_kwargs["n_katu"] = katu
                if is_failed and bm.n_objects > 0:
                    perf_kwargs["passed_objects"] = min(total_hits, bm.n_objects)
                res_actual = rp.Performance(**perf_kwargs).calculate(bm)
                actual_pp = float(getattr(res_actual, "pp", 0.0) or 0.0)
                pp_is_simulated = True

            # Simulación "if FC" si falló, tuvo misses o rompió combo notablemente
            needs_fc = (
                is_failed
                or miss > 0
                or (bm_max_combo > 0 and max_combo < int(bm_max_combo * 0.98))
            )
            fc_pp = None
            if needs_fc and total_hits > 0:
                res_fc = rp.Performance(
                    mods=mods,
                    accuracy=acc_pct if acc_pct > 0 else 95.0,
                    misses=0,
                    combo=bm_max_combo if bm_max_combo > 0 else None,
                ).calculate(bm)
                fc_val = float(getattr(res_fc, "pp", 0.0) or 0.0)
                if fc_val > 0:
                    fc_pp = max(fc_val, actual_pp)

            return {
                "actual_pp": actual_pp,
                "pp_is_simulated": pp_is_simulated,
                "fc_pp": fc_pp,
                "star_rating": full_stars,
                "max_combo": bm_max_combo,
                "ar": float(getattr(b_attrs, "ar", bm.ar)),
                "od": float(getattr(b_attrs, "od", bm.od)),
                "cs": float(getattr(b_attrs, "cs", bm.cs)),
                "hp": float(getattr(b_attrs, "hp", bm.hp)),
                "clock_rate": float(getattr(b_attrs, "clock_rate", 1.0) or 1.0),
                "n_circles": int(bm.n_circles),
                "n_sliders": int(bm.n_sliders),
                "n_spinners": int(bm.n_spinners),
                "n_objects": int(bm.n_objects),
            }
        except Exception as e:
            logger.debug(f"Error calculando rosu-pp para score: {e}")
            return {}

    async def enrich_scores_with_pp(self, scores: list, mode: str = "osu", max_maps: int = 5) -> list:
        """Descarga los .osu necesarios en paralelo y enriquece cada jugada con PP real (fails/unranked) + PP if FC."""
        if not scores or rp is None:
            return scores

        targets = scores[:max_maps]
        bm_ids = []
        for s in targets:
            bm = s.get("beatmap") or {}
            bid = bm.get("id")
            if bid:
                bm_ids.append(int(bid))

        if not bm_ids:
            return scores

        unique_ids = list(dict.fromkeys(bm_ids))
        files_list = await asyncio.gather(
            *(self.get_osu_file_bytes(bid) for bid in unique_ids),
            return_exceptions=True,
        )
        file_map = {
            bid: (data if isinstance(data, bytes) else None)
            for bid, data in zip(unique_ids, files_list)
        }

        for s in targets:
            bm = s.get("beatmap")
            if not isinstance(bm, dict):
                continue
            bid = bm.get("id")
            osu_bytes = file_map.get(int(bid)) if bid else None
            if not osu_bytes:
                continue
            sim = self.compute_rosu_score_pp(osu_bytes, s, mode=mode)
            if not sim:
                continue
            s["_pp_actual"] = sim["actual_pp"]
            s["_pp_is_simulated"] = sim["pp_is_simulated"]
            if sim.get("fc_pp") is not None:
                s["_pp_fc"] = sim["fc_pp"]
            if sim.get("star_rating"):
                s["official_sr"] = sim["star_rating"]
                bm["difficulty_rating"] = sim["star_rating"]
            if sim.get("max_combo") and not bm.get("max_combo"):
                bm["max_combo"] = sim["max_combo"]
            if sim.get("n_circles") and not bm.get("count_circles"):
                bm["count_circles"] = sim["n_circles"]
                bm["count_sliders"] = sim["n_sliders"]
                bm["count_spinners"] = sim["n_spinners"]
            s["beatmap_attributes"] = {
                **(s.get("beatmap_attributes") or {}),
                "star_rating": sim["star_rating"],
                "approach_rate": sim["ar"],
                "overall_difficulty": sim["od"],
                "cs": sim["cs"],
                "hp": sim["hp"],
                "clock_rate": sim["clock_rate"],
            }
        return scores

    async def simulate_map_pp_table(self, beatmap_id: int, mode: str = "osu", mods: list[str] | None = None) -> dict:
        """Calcula atributos con mods y tabla PP 95%/98%/99%/100% para d.m / /map."""
        if rp is None or not beatmap_id:
            return {}
        osu_bytes = await self.get_osu_file_bytes(int(beatmap_id))
        if not osu_bytes:
            return {}
        try:
            bm = rp.Beatmap(bytes=osu_bytes)
            target_mode = self._to_rosu_mode(mode)
            if target_mode is not None and bm.mode != target_mode:
                bm.convert(target_mode)
            clean_mods = self._clean_rosu_mods(mods)
            b_attrs = rp.BeatmapAttributesBuilder(map=bm, mods=clean_mods).build()
            diff_res = rp.Difficulty(mods=clean_mods).calculate(bm)
            max_combo = int(getattr(diff_res, "max_combo", 0) or 0)
            stars = float(getattr(diff_res, "stars", 0.0) or 0.0)
            pp_by_acc = {}
            for acc in (95, 98, 99, 100):
                res = rp.Performance(
                    mods=clean_mods,
                    accuracy=float(acc),
                    misses=0,
                    combo=max_combo if max_combo > 0 else None,
                ).calculate(bm)
                pp_by_acc[acc] = float(getattr(res, "pp", 0.0) or 0.0)
            return {
                "stars": stars,
                "max_combo": max_combo,
                "ar": float(getattr(b_attrs, "ar", bm.ar)),
                "od": float(getattr(b_attrs, "od", bm.od)),
                "cs": float(getattr(b_attrs, "cs", bm.cs)),
                "hp": float(getattr(b_attrs, "hp", bm.hp)),
                "clock_rate": float(getattr(b_attrs, "clock_rate", 1.0) or 1.0),
                "bpm": float(bm.bpm or 0.0),
                "n_circles": int(bm.n_circles),
                "n_sliders": int(bm.n_sliders),
                "n_spinners": int(bm.n_spinners),
                "n_objects": int(bm.n_objects),
                "pp": pp_by_acc,
            }
        except Exception as e:
            logger.debug(f"Error calculando tabla PP para beatmap {beatmap_id}: {e}")
            return {}

    @staticmethod
    def _normalize_score_stats(stats: dict | None) -> dict:
        """Normaliza estadísticas Lazer (great/ok/meh/miss) y Stable (count_300/...) a esquema unificado."""
        s = dict(stats or {})
        if "count_300" not in s and "great" in s:
            s["count_300"] = int(s.get("great") or 0)
        if "count_100" not in s and "ok" in s:
            s["count_100"] = int(s.get("ok") or 0)
        if "count_50" not in s and "meh" in s:
            s["count_50"] = int(s.get("meh") or 0)
        if "count_miss" not in s and "miss" in s:
            s["count_miss"] = int(s.get("miss") or 0)
        if "count_geki" not in s and "perfect" in s:
            s["count_geki"] = int(s.get("perfect") or 0)
        if "count_katu" not in s and "good" in s:
            s["count_katu"] = int(s.get("good") or 0)
        return s

    @staticmethod
    def parse_beatmap_reference(text: str) -> tuple[int | None, int | None, str | None]:
        """Extrae (beatmap_id, beatmapset_id, mode) desde URLs (Bancho/Akatsuki/Gatari) o IDs numéricos."""
        if not text:
            return None, None, None
        s = str(text).strip()
        # https://osu.ppy.sh/beatmapsets/12345#osu/67890 (o akatsuki/gatari)
        m_full = re.search(r"beatmapsets/(\d+)(?:#(osu|taiko|fruits|mania)/(\d+))?", s, re.IGNORECASE)
        if m_full:
            set_id = int(m_full.group(1))
            mode = m_full.group(2).lower() if m_full.group(2) else None
            bm_id = int(m_full.group(3)) if m_full.group(3) else None
            return bm_id, set_id, mode
        # https://osu.ppy.sh/b/67890, /beatmaps/67890, akatsuki.gg/b/67890, osu.gatari.pw/b/67890
        m_bm = re.search(
            r"(?:osu\.ppy\.sh|osu\.direct|akatsuki\.gg|osu\.gatari\.pw|ripple\.moe)/(?:b|beatmaps)/(\d+)",
            s,
            re.IGNORECASE,
        )
        if m_bm:
            return int(m_bm.group(1)), None, None
        # Fallback ruta genérica /b/<id> o /beatmaps/<id>
        m_bm_gen = re.search(r"/(?:b|beatmaps)/(\d+)", s, re.IGNORECASE)
        if m_bm_gen:
            return int(m_bm_gen.group(1)), None, None
        # https://assets.ppy.sh/beatmaps/12345/covers/...
        m_cov = re.search(r"assets\.ppy\.sh/beatmaps/(\d+)", s, re.IGNORECASE)
        if m_cov:
            return None, int(m_cov.group(1)), None
        # https://osu.ppy.sh/s/12345
        m_set = re.search(r"/s/(\d+)", s, re.IGNORECASE)
        if m_set:
            return None, int(m_set.group(1)), None
        if s.isdigit():
            return int(s), None, None
        return None, None, None

    @classmethod
    def extract_beatmap_from_message(cls, msg) -> tuple[int | None, int | None, str | None]:
        """
        Extrae (beatmap_id, beatmapset_id, mode) desde cualquier mensaje o embed de Discord
        (Bathbot, owo, TinyBot, Dalet o enlaces directos de usuarios).
        """
        if msg is None:
            return None, None, None

        candidates: list[str] = []
        embeds = getattr(msg, "embeds", None) or []
        for emb in embeds:
            if getattr(emb, "url", None):
                candidates.append(str(emb.url))
            author = getattr(emb, "author", None)
            if author and getattr(author, "url", None):
                candidates.append(str(author.url))
            if getattr(emb, "title", None):
                candidates.append(str(emb.title))
            if getattr(emb, "description", None):
                candidates.append(str(emb.description))
            for fld in getattr(emb, "fields", None) or []:
                if getattr(fld, "name", None):
                    candidates.append(str(fld.name))
                if getattr(fld, "value", None):
                    candidates.append(str(fld.value))
            footer = getattr(emb, "footer", None)
            if footer and getattr(footer, "text", None):
                candidates.append(str(footer.text))
            thumb = getattr(emb, "thumbnail", None)
            if thumb and getattr(thumb, "url", None):
                candidates.append(str(thumb.url))
            img = getattr(emb, "image", None)
            if img and getattr(img, "url", None):
                candidates.append(str(img.url))

        content = getattr(msg, "content", None)
        if content:
            candidates.append(str(content))

        fallback_set: tuple[int | None, int | None, str | None] | None = None
        for text in candidates:
            # No tratar un ID numérico suelto en prosa normal como beatmap ID si vino de texto libre
            if text.strip().isdigit():
                continue
            bid, bsid, mode = cls.parse_beatmap_reference(text)
            if bid:
                return bid, bsid, mode
            if bsid and fallback_set is None:
                fallback_set = (None, bsid, mode)

        return fallback_set or (None, None, None)

    async def detect_beatmap_from_discord(
        self,
        channel,
        ref_message=None,
        skip_message_id: int | None = None,
        history_limit: int = 25,
    ) -> tuple[int | None, int | None, str | None]:
        """
        Cascada bajo demanda para detectar un beatmap en Discord sin escucha pasiva:
        1) Mensaje respondido (Reply directo, ej. al recent play de Bathbot/owo/Dalet).
        2) Escaneo de los últimos mensajes/embeds del canal.
        3) Último mapa recordado en memoria del canal (get_channel_map).
        """
        if ref_message is not None:
            bid, bsid, m_hint = self.extract_beatmap_from_message(ref_message)
            if bid or bsid:
                return bid, bsid, m_hint

        if channel is not None and hasattr(channel, "history"):
            try:
                async for hist_msg in channel.history(limit=history_limit):
                    if skip_message_id and getattr(hist_msg, "id", None) == skip_message_id:
                        continue
                    bid, bsid, m_hint = self.extract_beatmap_from_message(hist_msg)
                    if bid or bsid:
                        return bid, bsid, m_hint
            except Exception as e:
                logger.debug(f"No se pudo leer historial reciente del canal: {e}")

        ch_id = getattr(channel, "id", None)
        if ch_id:
            cached = self.get_channel_map(ch_id)
            if cached:
                return cached[0], None, cached[1]

        return None, None, None

    async def get_user_beatmap_scores(
        self,
        beatmap_id: int,
        user_id: int,
        mode: str = "osu",
        server: str = "bancho",
        beatmap_data: dict | None = None,
    ) -> list:
        """
        Obtiene todas las jugadas guardadas de un jugador en un beatmap específico
        (Bancho v2 /all para todos los mods; Akatsuki/Gatari vía cruce best+recent).
        """
        if not beatmap_id or not user_id:
            return []
        bid = int(beatmap_id)
        uid = int(user_id)
        srv = (server or "bancho").lower().strip()
        raw_scores: list[dict] = []

        if srv == "bancho":
            try:
                res = await self._get(
                    f"beatmaps/{bid}/scores/users/{uid}/all",
                    params={"mode": mode},
                )
                raw_scores = res.get("scores") or [] if isinstance(res, dict) else []
            except httpx.HTTPStatusError as e:
                if e.response is not None and e.response.status_code in (404, 422):
                    raw_scores = []
                else:
                    raise
        else:
            best_res, recent_res = await asyncio.gather(
                self.get_user_best_scores(uid, mode=mode, limit=100, server=srv),
                self.get_user_recent_scores(uid, mode=mode, limit=50, include_fails=1, server=srv),
                return_exceptions=True,
            )
            seen_keys = set()
            for batch in (best_res, recent_res):
                if not isinstance(batch, list):
                    continue
                for s in batch:
                    s_bm_id = int((s.get("beatmap") or {}).get("id") or 0)
                    if s_bm_id != bid:
                        continue
                    mods_key = tuple(str(m) for m in (s.get("mods") or []))
                    dedup_key = (
                        int(s.get("classic_total_score") or s.get("total_score") or s.get("score") or 0),
                        mods_key,
                        str(s.get("created_at") or ""),
                    )
                    if dedup_key not in seen_keys:
                        seen_keys.add(dedup_key)
                        raw_scores.append(s)

        bm_meta = beatmap_data or {}
        bms_meta = bm_meta.get("beatmapset") or {}
        normalized: list[dict] = []
        for item in raw_scores:
            s = dict(item)
            s["statistics"] = self._normalize_score_stats(s.get("statistics"))
            if "total_score" not in s and "legacy_total_score" in s:
                s["total_score"] = s["legacy_total_score"]
            if not s.get("beatmap") and bm_meta:
                s["beatmap"] = bm_meta
            if not s.get("beatmapset") and bms_meta:
                s["beatmapset"] = bms_meta
            s.setdefault("_server", srv)
            normalized.append(s)

        normalized.sort(
            key=lambda x: (
                1 if (x.get("passed", True) and str(x.get("rank", "")).upper() != "F") else 0,
                float(x.get("pp") or 0.0),
                int(x.get("classic_total_score") or x.get("total_score") or x.get("score") or 0),
            ),
            reverse=True,
        )
        return normalized

    async def resolve_beatmap(self, query: str | None = None, preferred_id: int | None = None, mode_hint: str = "osu") -> dict | None:
        """Resuelve un beatmap completo desde ID, URL de osu!, último mapa del canal o búsqueda en Bancho."""
        bm_id, set_id, url_mode = self.parse_beatmap_reference(query or "")
        effective_mode = url_mode or mode_hint or "osu"

        if not bm_id and not set_id and not (query and query.strip()) and preferred_id:
            bm_id = int(preferred_id)

        if bm_id:
            if bm_id in self._bm_cache:
                cached = self._bm_cache[bm_id]
                return {"beatmap": cached, "mode": url_mode or cached.get("mode") or effective_mode}
            try:
                bm = await self.get_beatmap(bm_id)
                if isinstance(bm, dict) and bm.get("id"):
                    self._bm_cache[int(bm["id"])] = bm
                    return {"beatmap": bm, "mode": url_mode or bm.get("mode") or effective_mode}
            except httpx.HTTPStatusError as e:
                if e.response is not None and e.response.status_code == 404:
                    return None
                raise

        if set_id:
            try:
                bmset = await self._get(f"beatmapsets/{set_id}")
                bms = bmset.get("beatmaps") or []
                if bms:
                    chosen = max(bms, key=lambda b: float(b.get("difficulty_rating") or 0.0))
                    chosen["beatmapset"] = bmset
                    return {"beatmap": chosen, "mode": url_mode or chosen.get("mode") or effective_mode}
            except Exception:
                return None

        if query and query.strip():
            params = {
                "q": query.strip(),
                "m": self._mode_to_int(effective_mode),
                "sort": "relevance_desc",
            }
            res = await self._get("beatmapsets/search", params=params)
            sets = res.get("beatmapsets") or []
            if not sets:
                return None
            bmset = sets[0]
            bms = bmset.get("beatmaps") or []
            if not bms:
                return None
            q_low = query.lower()
            chosen = next((b for b in bms if str(b.get("version", "")).lower() in q_low), None)
            if chosen is None:
                chosen = max(bms, key=lambda b: float(b.get("difficulty_rating") or 0.0))
            chosen["beatmapset"] = bmset
            return {"beatmap": chosen, "mode": chosen.get("mode") or effective_mode}

        return None

