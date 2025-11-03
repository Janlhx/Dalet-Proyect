"""
Módulo de Conexión a la API v2 de osu!.

Esta clase maneja la autenticación (OAuth Client Credentials) y
envuelve los endpoints de la API de osu! que el bot necesita.
"""
import requests
import time
import asyncio
import random

class OsuAPI:
    """Maneja la autenticación y las llamadas a la API de osu!."""
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.token_expiry = 0

    def authenticate(self):
        """Obtiene un nuevo token de acceso de la API de osu!."""
        print("--- [OsuAPI] Autenticando...")
        try:
            url = "https://osu.ppy.sh/oauth/token"
            data = {"client_id": self.client_id, "client_secret": self.client_secret, "grant_type": "client_credentials", "scope": "public"}
            response = requests.post(url, json=data)
            response.raise_for_status() # Lanza error si la petición falla
            res_json = response.json()
            self.token = res_json["access_token"]
            self.token_expiry = time.time() + res_json["expires_in"]
            print("--- [OsuAPI] Autenticación exitosa.")
        except Exception as e:
            print(f"!!!!!! [OsuAPI] ERROR DE AUTENTICACIÓN: {e}")
            self.token = None
            self.token_expiry = 0

    def get_token(self):
        """
        Obtiene un token válido.
        
        Devuelve el token existente si aún es válido, o
        llama a 'authenticate' para obtener uno nuevo si está expirado.
        """
        if not self.token or time.time() > self.token_expiry - 60: # Margen de 60 seg
            self.authenticate()
        return self.token

    def _make_request(self, endpoint, params=None):
        """Función auxiliar interna para realizar peticiones GET."""
        token = self.get_token()
        if not token:
            raise Exception("No se pudo obtener el token de autenticación de osu!.")
        
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"https://osu.ppy.sh/api/v2/{endpoint}", headers=headers, params=params)
        response.raise_for_status() # Lanza error si la API devuelve 4xx o 5xx
        return response.json()

    # --- Endpoints Públicos ---

    def get_user(self, username, mode="osu"):
        """Obtiene los datos del perfil de un usuario."""
        return self._make_request(f"users/{username}/{mode}")

    def get_user_best_scores(self, user_id, mode="osu", limit=10):
        """Obtiene los 'best scores' (top plays) de un usuario."""
        params = {'mode': mode, 'limit': limit}
        return self._make_request(f"users/{user_id}/scores/best", params=params)

    def get_user_recent_scores(self, user_id, mode="osu", limit=20):
        """Obtiene los 'recent scores' (últimas jugadas) de un usuario."""
        params = {'mode': mode, 'limit': limit, 'include_fails': 1}
        return self._make_request(f"users/{user_id}/scores/recent", params=params)

    def search_beatmaps(self, mode: str, min_stars: float, max_stars: float, keyword: str):
        """
        Busca beatmaps usando una palabra clave y los filtra por estrellas.
        
        Nota: Este método es síncrono.
        """
        token = self.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        sort_options = ['relevance', 'ranked_date_desc']
        random_sort = random.choice(sort_options)
        
        params = {'q': keyword, 'm': mode, 's': 'ranked', 'sort': random_sort}
        response = requests.get("https://osu.ppy.sh/api/v2/beatmapsets/search", headers=headers, params=params)
        response.raise_for_status()
        
        all_beatmapsets = response.json().get('beatmapsets', [])
        
        filtered_results = []
        for beatmapset in all_beatmapsets:
            if beatmapset.get('beatmaps'):
                for beatmap in beatmapset['beatmaps']:
                    difficulty_rating = beatmap.get('difficulty_rating', 0)
                    if min_stars <= difficulty_rating <= max_stars:
                        filtered_results.append(beatmapset)
                        break # Ir al siguiente beatmapset
        return filtered_results

    async def async_search_beatmaps(self, mode: str, min_stars: float, max_stars: float, keyword: str):
        """Wrapper asíncrono para 'search_beatmaps'."""
        return await asyncio.to_thread(self.search_beatmaps, mode, min_stars, max_stars, keyword)
    
async def setup(bot):
    """Función 'setup' vacía (este módulo no es un Cog)."""
    pass