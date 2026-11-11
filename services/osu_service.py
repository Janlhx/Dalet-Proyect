import httpx
import time
import logging
import asyncio
from datetime import datetime, timezone

logger = logging.getLogger("dalet.services.osu")

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
        data = await self._get(f"users/{username}/{mode}")
        if isinstance(data, dict):
            data["_server"] = "bancho"
        return data

    async def get_user_by_id(self, user_id: int, mode: str = "osu", server: str = "bancho") -> dict:
        """Perfil de un usuario por ID numérico."""
        srv = (server or "bancho").lower().strip()
        if srv.startswith("akatsuki") or srv in ("rx", "ap"):
            return await self._get_akatsuki_user(str(user_id), mode=mode, rx=self._server_rx_flag(srv), by_id=True)
        if srv == "gatari":
            return await self._get_gatari_user(str(user_id), mode=mode)
        data = await self._get(f"users/{user_id}/{mode}", params={"key": "id"})
        if isinstance(data, dict):
            data["_server"] = "bancho"
        return data

    async def _get_akatsuki_user(self, username_or_id: str, mode: str = "osu", rx: int = 0, by_id: bool = False) -> dict:
        params = {"id": username_or_id} if (by_id or str(username_or_id).isdigit()) else {"name": username_or_id}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://akatsuki.gg/api/v1/users/full", params=params)
            if resp.status_code != 200 and "id" in params:
                resp = await client.get("https://akatsuki.gg/api/v1/users/full", params={"name": username_or_id})
            resp.raise_for_status()
            raw = resp.json()

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

    async def _get_gatari_user(self, username_or_id: str, mode: str = "osu") -> dict:
        mode_int = self._mode_to_int(mode)
        async with httpx.AsyncClient(timeout=15.0) as client:
            u_resp, s_resp = await asyncio.gather(
                client.get("https://api.gatari.pw/users/get", params={"u": username_or_id}),
                client.get("https://api.gatari.pw/user/stats", params={"u": username_or_id, "mode": mode_int}),
            )
            u_resp.raise_for_status()
            s_resp.raise_for_status()
            u_json = u_resp.json()
            s_json = s_resp.json()

        users_list = u_json.get("users") or []
        if not users_list:
            raise ValueError(f"Gatari user '{username_or_id}' not found")
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

