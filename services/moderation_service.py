import os
import re
import json
import base64
import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger("dalet.services.moderation")

# 1. Contenido ilegal (CSAM, CP, pedofilia) - Cero tolerancia y alerta urgente @here
# NOTA: La sigla "cp" se evalúa con contexto para no sancionar términos de gaming (Pokémon Go CP, CoD Points, Club Penguin), Linux o Código Postal.
_ILLEGAL_PATTERNS = [
    # Términos directos unívocos
    r"\bcsam\b",
    r"child\s*(?:porn|sex|nud|exploit)",
    r"kiddie\s*porn",
    r"loli\s*(?:porn|hentai|nsfw|sex)",
    r"shota\s*(?:porn|hentai|nsfw|sex)",
    r"menor(?:es)?\s*(?:desnud|porn|sex|naked|nud)",
    r"pedofil(?:ia|e|o|os)?",
    r"pedo\s*porn",
    r"jailbait",

    # "cp" SOLO cuando se usa en contexto de tráfico, links, packs, carpetas o intercambio
    r"\b(?:link|enlace|video|fotos?|pack|packs|trade|pasar|pasen|pasa|manda|mandame|vendo|venta|tengo|busco|intercambio|carpeta|mega|drive|telegram)\s+(?:de\s+)?cp\b",
    r"\bcp\s+(?:gratis|mega|drive|telegram|pack|packs|links?|videos?|fotos?)\b",
    r"\btr[áa]fico\s+(?:de\s+)?cp\b",
]

# 2. Contenido adulto / NSFW enfocado en LINKS, SPAM DE INVITACIONES y VENTA DE CONTENIDO
# NOTA: No bloqueamos bromas de texto como "send porn" o "manden porno" ni charlas casuales.
_ADULT_PATTERNS = [
    # Enlaces directos a dominios de pornografía o contenido adulto
    r"https?://\S*(?:pornhub|xvideos|xnxx|redtube|onlyfans|fansly|rule34|chaturbate|cam4|brazzers|youporn|spankbang|eporner|beeg|hqporner|nhentai|tsumino|hitomi\.la|hanime\.tv)\.\S+",

    # Enlaces con rutas o palabras clave explícitas
    r"https?://\S+/(?:porn|hentai|nsfw|nudes?|xxx|leaks?|packs?)/\S*",

    # Enlaces de Telegram, Discord o Mega acompañados de palabras clave de packs/nudes/porno (Spam de bots de raid)
    r"https?://(?:t\.me|telegram\.me|discord\.(?:gg|com/invite)|mega\.nz)/\S+[\s\S]{0,80}\b(?:nudes?|packs?|onlyfans|leaks?|porno?|xxx|contenido\s+exclusivo)\b",
    r"\b(?:nudes?|packs?|onlyfans|leaks?|porno?|xxx|contenido\s+exclusivo)\b[\s\S]{0,80}https?://(?:t\.me|telegram\.me|discord\.(?:gg|com/invite)|mega\.nz)/\S+",

    # Venta / Promoción comercial de contenido sexual o packs
    r"\b(?:vendo|venta\s+de)\s+(?:contenido\s+(?:hot|exclusivo|xxx)|packs?|nudes?|onlyfans)\b",
    r"\b(?:pack|packs)\s+de\s+(?:morras|chicas|mujeres|colegialas|familias)\s+(?:al\s+dm|por\s+telegram|disponibles?)\b",
    r"\bonlyfans\s+(?:gratis|free|leaks?|filtrado)\s+https?://\S+",
]

_ILLEGAL_RE = re.compile("|".join(_ILLEGAL_PATTERNS), re.IGNORECASE)
_ADULT_RE   = re.compile("|".join(_ADULT_PATTERNS), re.IGNORECASE)

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"}

_VISION_SAFETY_PROMPT = (
    "You are a strict content safety classifier for a Discord moderation system. "
    "Classify the image content into ONE of these categories: "
    "'safe' (normal images, fully clothed persons, memes, non-explicit anime/art, video games), "
    "'suggestive' (revealing clothing, bikini, lingerie, cleavage, mild artistic fan service), "
    "'explicit' (nudity, visible genitalia, sexual acts, pornographic content, hentai, uncensored or censored sexual intercourse), "
    "'illegal' (CSAM, minors in sexual context, illegal material). "
    "Reply ONLY with a raw JSON object and nothing else: "
    '{"safe": true/false, "category": "safe" | "suggestive" | "explicit" | "illegal", "confidence": 0.0-1.0}. '
    "Set safe=false if category is 'explicit' or 'illegal'."
)


@dataclass
class ModerationResult:
    flagged: bool
    severity: str        # "safe" | "adult" | "illegal"
    confidence: float
    reason: str
    method: str          # "text_regex" | "gemini_vision"


class ModerationService:
    """
    Two-layer content moderation:
      1. Fast text regex scan (contextual links & solicitation; no casual text false-positives).
      2. Gemini Vision image scan (handles explicit porn and CSAM detection).

    Also tracks cross-channel spam: same user flagged in ≥2 channels within 60s.
    """

    SPAM_WINDOW_SEC = 60
    FLOOD_BURST_MAX_MSGS = 5
    FLOOD_BURST_WINDOW_SEC = 4.0
    FLOOD_DUP_MAX_COUNT = 3
    FLOOD_DUP_WINDOW_SEC = 10.0

    def __init__(self, nlp_service):
        self._nlp = nlp_service
        self._vision_cache: dict[str, ModerationResult] = {}
        # {user_id: [(timestamp, channel_id), ...]}
        self._flag_tracker: dict[int, list[tuple[float, int]]] = defaultdict(list)
        # {user_id: [(timestamp, channel_id, content_hash), ...]}
        self._message_history: dict[int, list[tuple[float, int, str]]] = defaultdict(list)

    def check_flood(self, user_id: int, channel_id: int, content: str, attachment_sig: str = "") -> tuple[bool, str]:
        """Detecta ráfagas rápidas de mensajes (>=5 msgs en 4s) o mensajes repetidos (>=3 iguales en 10s, texto o imagen)."""
        now = time.monotonic()
        history = self._message_history[user_id]
        history = [(ts, ch, h) for ts, ch, h in history if now - ts < self.FLOOD_DUP_WINDOW_SEC]

        norm_content = re.sub(r"\s+", " ", (content or "").strip().lower())
        sig = norm_content or attachment_sig
        content_hash = hashlib.md5(sig.encode("utf-8")).hexdigest() if sig else ""

        history.append((now, channel_id, content_hash))
        self._message_history[user_id] = history

        # 1. Ráfaga rápida
        recent_burst = [ts for ts, _, _ in history if now - ts <= self.FLOOD_BURST_WINDOW_SEC]
        if len(recent_burst) >= self.FLOOD_BURST_MAX_MSGS:
            return True, f"burst_flood:{len(recent_burst)}_msgs_in_{self.FLOOD_BURST_WINDOW_SEC}s"

        # 2. Mensajes duplicados repetidos
        if content_hash:
            same_msgs = [ts for ts, _, h in history if h == content_hash and now - ts <= self.FLOOD_DUP_WINDOW_SEC]
            if len(same_msgs) >= self.FLOOD_DUP_MAX_COUNT:
                return True, f"duplicate_flood:{len(same_msgs)}_same_msgs"

        return False, ""

    async def scan_message(self, content: str, image_urls: list[str]) -> ModerationResult:
        text_result = self._scan_text(content)
        if text_result.flagged:
            return text_result

        if image_urls:
            return await self._scan_image(image_urls[0])

        return ModerationResult(False, "safe", 1.0, "", "none")

    def track_flag(self, user_id: int, channel_id: int) -> bool:
        """Returns True if this flag triggers the cross-channel spam threshold."""
        now = time.monotonic()
        events = self._flag_tracker[user_id]
        events = [(ts, ch) for ts, ch in events if now - ts < self.SPAM_WINDOW_SEC]
        events.append((now, channel_id))
        self._flag_tracker[user_id] = events
        unique_channels = {ch for _, ch in events}
        return len(unique_channels) >= self.SPAM_CHANNEL_THRESHOLD

    def _scan_text(self, content: str) -> ModerationResult:
        if not content:
            return ModerationResult(False, "safe", 1.0, "", "text_regex")

        if _ILLEGAL_RE.search(content):
            match = _ILLEGAL_RE.search(content)
            return ModerationResult(True, "illegal", 1.0, f"keyword: {match.group()}", "text_regex")

        if _ADULT_RE.search(content):
            match = _ADULT_RE.search(content)
            return ModerationResult(True, "adult", 0.95, f"keyword: {match.group()}", "text_regex")

        return ModerationResult(False, "safe", 1.0, "", "text_regex")

    async def _scan_image(self, url: str) -> ModerationResult:
        api_key = (getattr(self._nlp, "gemini_api_key", None) or os.getenv("GEMINI_API_KEY") or "").strip()
        if not api_key:
            logger.warning("Moderación de imagen omitida: GEMINI_API_KEY no configurada.")
            return ModerationResult(False, "safe", 1.0, "no_api_key", "gemini_vision")

        url_hash = hashlib.md5(url.encode()).hexdigest()
        if url_hash in self._vision_cache:
            return self._vision_cache[url_hash]

        try:
            logger.info(f"Escaneando imagen con Gemini Vision: {url[:80]}...")
            http_client = getattr(self._nlp, "_http_client", None)
            close_client = False
            if not http_client:
                import httpx
                http_client = httpx.AsyncClient(timeout=15.0)
                close_client = True

            try:
                resp = await http_client.get(url, timeout=7.0)
                if resp.status_code != 200:
                    logger.warning(f"Error descargando imagen para mod (HTTP {resp.status_code})")
                    return ModerationResult(False, "safe", 1.0, "download_failed", "gemini_vision")

                mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
                if not mime.startswith("image/"):
                    mime = "image/jpeg"

                b64_data = base64.b64encode(resp.content).decode("utf-8")
                raw_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
                if raw_model in ("gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash", "models/gemini-2.5-flash"):
                    model_name = "gemini-3.8-flash"
                else:
                    model_name = raw_model

                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": _VISION_SAFETY_PROMPT},
                            {"inline_data": {"mime_type": mime, "data": b64_data}}
                        ]
                    }],
                    "generationConfig": {
                        "temperature": 0.1
                    }
                }

                gem_resp = await http_client.post(gemini_url, json=payload, timeout=12.0)

                # Si el modelo en env devolvió 404, reintentar automáticamente con gemini-3.8-flash
                if gem_resp.status_code == 404 and model_name != "gemini-3.8-flash":
                    logger.warning(f"Modelo '{model_name}' devolvió 404 en Google. Reintentando con 'gemini-3.8-flash'...")
                    model_name = "gemini-3.8-flash"
                    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                    gem_resp = await http_client.post(gemini_url, json=payload, timeout=12.0)

                # 1. Comprobar si Google respondió 200 OK
                if gem_resp.status_code == 200:
                    data = gem_resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        cand = candidates[0]
                        finish_reason = cand.get("finishReason", "")
                        if "SAFETY" in finish_reason.upper():
                            logger.warning(f"Gemini bloqueó la imagen por finishReason: {finish_reason}. Marcada como explícita.")
                            result = ModerationResult(True, "adult", 1.0, "gemini_safety_block", "gemini_vision")
                            self._cache_result(url_hash, result)
                            return result

                        for rating in cand.get("safetyRatings", []):
                            cat = rating.get("category", "")
                            prob = rating.get("probability", "")
                            if "SEXUALLY_EXPLICIT" in cat and prob in ("HIGH", "MEDIUM"):
                                logger.warning(f"Gemini detectó probabilidad {prob} de contenido explícito.")
                                result = ModerationResult(True, "adult", 0.95, f"safety_rating:{prob}", "gemini_vision")
                                self._cache_result(url_hash, result)
                                return result

                        parts = cand.get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            raw_text = parts[0]["text"]
                            result = self._parse_vision_response(raw_text)
                            logger.info(f"Resultado escaneo de imagen: flagged={result.flagged}, severity={result.severity}, reason={result.reason}")
                            self._cache_result(url_hash, result)
                            return result

                # 2. Si Google bloqueó por HTTP 400/403 debido a filtros de seguridad
                elif gem_resp.status_code in (400, 403):
                    err_text = gem_resp.text.lower()
                    if "safety" in err_text or "blocked" in err_text:
                        logger.warning(f"Google bloqueó la solicitud por seguridad (HTTP {gem_resp.status_code}): Marcada como explícita.")
                        result = ModerationResult(True, "adult", 1.0, "gemini_safety_http_block", "gemini_vision")
                        self._cache_result(url_hash, result)
                        return result
                    logger.error(f"Error HTTP de Gemini API ({gem_resp.status_code}): {gem_resp.text[:200]}")

                else:
                    logger.error(f"Gemini API returned status {gem_resp.status_code}: {gem_resp.text[:200]}")

            finally:
                if close_client:
                    await http_client.aclose()

            return ModerationResult(False, "safe", 1.0, "scan_failed", "gemini_vision")

        except asyncio.TimeoutError:
            logger.warning("Timeout en vision scan de moderación (Gemini excedió tiempo límite).")
            return ModerationResult(False, "safe", 1.0, "timeout", "gemini_vision")
        except Exception as e:
            err_msg = str(e).lower()
            if "safety" in err_msg or "blocked" in err_msg:
                logger.warning(f"Excepción de seguridad de Gemini: {e}. Marcada como explícita.")
                result = ModerationResult(True, "adult", 1.0, "gemini_safety_filter_trip", "gemini_vision")
                self._cache_result(url_hash, result)
                return result

            logger.error(f"Error inesperado en vision scan de moderación: {e}")
            return ModerationResult(False, "safe", 1.0, "error", "gemini_vision")

    def _cache_result(self, url_hash: str, result: ModerationResult):
        if len(self._vision_cache) > 100:
            self._vision_cache.clear()
        self._vision_cache[url_hash] = result

    @staticmethod
    def _parse_vision_response(text: str) -> ModerationResult:
        try:
            cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
            data = json.loads(cleaned)
            safe = bool(data.get("safe", True))
            category = str(data.get("category", "safe")).lower().strip()
            confidence = float(data.get("confidence", 0.5))

            if not safe or category in ("explicit", "illegal"):
                severity = "illegal" if category == "illegal" else "adult"
                return ModerationResult(True, severity, confidence, f"vision:{category}", "gemini_vision")

            return ModerationResult(False, "safe", confidence, "", "gemini_vision")
        except Exception as e:
            logger.debug(f"Error interpretando JSON de visión '{text[:120]}': {e}")
            # Si el texto menciona explicitamente sexual o porn, detectarlo como fallback
            lower = text.lower()
            if "explicit" in lower or "porn" in lower or "nsfw" in lower:
                return ModerationResult(True, "adult", 0.85, "vision_fallback_keyword", "gemini_vision")
            return ModerationResult(False, "safe", 1.0, "parse_error", "gemini_vision")

    @staticmethod
    def extract_image_urls(message) -> list[str]:
        """Extract image URLs from Discord message attachments, embeds, and content links."""
        urls = []
        for att in message.attachments:
            is_image = (
                (att.content_type and att.content_type.startswith("image/"))
                or any(att.filename.lower().endswith(ext) for ext in _IMAGE_EXTENSIONS)
            )
            if is_image:
                urls.append(att.url)

        for embed in message.embeds:
            if embed.image and embed.image.url:
                urls.append(embed.image.url)
            elif embed.thumbnail and embed.thumbnail.url:
                urls.append(embed.thumbnail.url)

        # Detectar URLs directas de imágenes en el texto del mensaje si no hay attachments
        if not urls and message.content:
            url_matches = re.findall(r"https?://\S+\.(?:jpg|jpeg|png|gif|webp)(?:\?\S*)?", message.content, re.IGNORECASE)
            urls.extend(url_matches)

        return urls[:1]
