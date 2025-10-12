# osu_api.py
import requests
import time
import asyncio
import random
class OsuAPI:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.token_expiry = 0

    def authenticate(self):
        # ... (código sin cambios)
        url = "https://osu.ppy.sh/oauth/token"
        data = {"client_id": self.client_id, "client_secret": self.client_secret, "grant_type": "client_credentials", "scope": "public"}
        response = requests.post(url, json=data)
        res_json = response.json()
        self.token = res_json["access_token"]
        self.token_expiry = time.time() + res_json["expires_in"]

    def get_token(self):
        # ... (código sin cambios)
        if not self.token or time.time() > self.token_expiry:
            self.authenticate()
        return self.token

    def get_user(self, username, mode="osu"):
        # ... (código sin cambios)
        token = self.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"https://osu.ppy.sh/api/v2/users/{username}/{mode}", headers=headers)
        return response.json()

    def get_user_best_scores(self, user_id, mode="osu", limit=10):
        # ... (código sin cambios)
        token = self.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        params = {'mode': mode, 'limit': limit}
        response = requests.get(f"https://osu.ppy.sh/api/v2/users/{user_id}/scores/best", headers=headers, params=params)
        return response.json()

    def get_user_recent_scores(self, user_id, mode="osu", limit=20):
        # ... (código sin cambios)
        token = self.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        params = {'mode': mode, 'limit': limit, 'include_fails': 1}
        response = requests.get(f"https://osu.ppy.sh/api/v2/users/{user_id}/scores/recent", headers=headers, params=params)
        return response.json()

    # --- FUNCIÓN DE BÚSQUEDA CORREGIDA ---
    def search_beatmaps(self, mode: str, min_stars: float, max_stars: float, keyword: str):
        """Busca mapas usando una palabra clave y los filtra por estrellas."""
        token = self.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Priorizamos la relevancia y la fecha para encontrar mapas más interesantes
        sort_options = ['relevance', 'ranked_date_desc']
        random_sort = random.choice(sort_options)
        
        # Usamos la palabra clave en la query
        params = {'q': keyword, 'm': mode, 's': 'ranked', 'sort': random_sort}
        response = requests.get("https://osu.ppy.sh/api/v2/beatmapsets/search", headers=headers, params=params)
        
        all_beatmapsets = response.json().get('beatmapsets', [])
        
        filtered_results = []
        for beatmapset in all_beatmapsets:
            if beatmapset.get('beatmaps'):
                for beatmap in beatmapset['beatmaps']:
                    difficulty_rating = beatmap.get('difficulty_rating', 0)
                    if min_stars <= difficulty_rating <= max_stars:
                        filtered_results.append(beatmapset)
                        break 
        return filtered_results

    async def async_search_beatmaps(self, mode: str, min_stars: float, max_stars: float, keyword: str):
        """Wrapper asíncrono que ahora también acepta la palabra clave."""
        return await asyncio.to_thread(self.search_beatmaps, mode, min_stars, max_stars, keyword)
    
    
async def setup(bot):
    pass