import re
import json
import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger("dalet.services.moderation")

# 1. Contenido ilegal (CSAM, CP, pedofilia) - Cero tolerancia, ban automático
_ILLEGAL_PATTERNS = [
    r"\bcsam\b", r"\bcp\b(?!\+|\s*\d|\s*us|\s*point)", r"child\s*(porn|sex|nud|exploit)",
    r"kiddie\s*porn", r"loli\s*porn", r"shota\s*porn",
    r"menor(es)?\s*(desnud|porn|sex|naked|nud)",
    r"pedofil(ia|e|o|os)?", r"pedo\s*porn", r"jailbait",
]

# 2. Contenido adulto / NSFW dirigido a SPAM, enlaces y solicitudes explícitas.
# NOTA: No bloqueamos palabras aisladas como "porno" o "xxx" para no penalizar conversaciones casuales.
_ADULT_PATTERNS = [
    # Enlaces directos a sitios web para adultos
    r"https?://\S*(pornhub|xvideos|xnxx|redtube|onlyfans|fansly|rule34|chaturbate|cam4|brazzers|youporn)\.\S+",
    # URLs genéricas con indicios porno
    r"https?://\S*(nude|porn|hentai|nsfw|xxx)\S*",
    # Solicitud y tráfico de packs / nudes / porno
    r"\b(link|canal|server|grupo|fotos?|videos?|enlace)\s+(de\s+)?(porno?|nudes?|onlyfans|xxx|packs?)\b",
    r"\b(send|pasen|pasame|pasa|manda|mandame|compartan|compartir)\s+(nudes?|pack|porno?|xxx)\b",
    r"\b(pack|packs)\s+(de\s+)?(mujeres|chicas|morras|nudes?)\b",
    r"\b(free|gratis)\s+(onlyfans|nudes?|porno?|pack)\b",
    r"\bonlyfans\s+(leaks?|gratis|free|link|pack)\b",
    r"\b(vendo|compro|vendo\s+contenido|contenido\s+exclusivo\s+xxx)\b",
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
    SPAM_CHANNEL_THRESHOLD = 2

    def __init__(self, nlp_service):
        self._nlp = nlp_service
        self._vision_cache: dict[str, ModerationResult] = {}
        # {user_id: [(timestamp, channel_id), ...]}
        self._flag_tracker: dict[int, list[tuple[float, int]]] = defaultdict(list)

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
        if not self._nlp or not getattr(self._nlp, "client", None):
            logger.warning("Moderación de imagen omitida: NLPService / cliente Gemini no disponible.")
            return ModerationResult(False, "safe", 1.0, "vision_unavailable", "gemini_vision")

        url_hash = hashlib.md5(url.encode()).hexdigest()
        if url_hash in self._vision_cache:
            return self._vision_cache[url_hash]

        try:
            logger.info(f"Escaneando imagen con Gemini Vision: {url[:80]}...")
            resp = await self._nlp._http_client.get(url, timeout=6.0)
            if resp.status_code != 200:
                logger.warning(f"Error descargando imagen para mod (HTTP {resp.status_code})")
                return ModerationResult(False, "safe", 1.0, "download_failed", "gemini_vision")

            mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
            if not mime.startswith("image/"):
                mime = "image/jpeg"

            from google.genai import types
            image_part = types.Part.from_bytes(data=resp.content, mime_type=mime)

            model_name = __import__("os").getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()

            # Intentar deshabilitar bloqueos agresivos para que Gemini analice y nos entregue el JSON
            gen_config = None
            try:
                gen_config = types.GenerateContentConfig(
                    temperature=0.1,
                    safety_settings=[
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                            threshold=types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            threshold=types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            threshold=types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                            threshold=types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                    ]
                )
            except Exception as conf_err:
                logger.debug(f"Configuración de safety_settings personalizada no soportada: {conf_err}")

            raw = await asyncio.wait_for(
                self._nlp.client.aio.models.generate_content(
                    model=model_name,
                    contents=[_VISION_SAFETY_PROMPT, image_part],
                    config=gen_config,
                ),
                timeout=9.0,
            )

            # 1. Comprobar si Google bloqueó la generación por filtros de seguridad internos (p. ej. pornografía dura o CSAM)
            if raw and raw.candidates:
                cand = raw.candidates[0]
                finish_reason = getattr(cand, "finish_reason", None)
                if finish_reason and "SAFETY" in str(finish_reason).upper():
                    logger.warning(f"Gemini bloqueó la imagen por FinishReason.SAFETY ({finish_reason}). Marcada como explícita.")
                    result = ModerationResult(True, "adult", 1.0, "gemini_safety_block", "gemini_vision")
                    self._cache_result(url_hash, result)
                    return result

                # Revisar ratings de severidad alta
                for rating in getattr(cand, "safety_ratings", []) or []:
                    cat = str(getattr(rating, "category", "")).upper()
                    prob = str(getattr(rating, "probability", "")).upper()
                    if "SEXUALLY_EXPLICIT" in cat and prob in ("HIGH", "MEDIUM"):
                        logger.warning(f"Gemini detectó probabilidad {prob} de contenido explícito.")
                        result = ModerationResult(True, "adult", 0.95, f"safety_rating:{prob}", "gemini_vision")
                        self._cache_result(url_hash, result)
                        return result

            # 2. Parsear el JSON textual devuelto por Gemini
            raw_text = ""
            try:
                raw_text = raw.text or ""
            except Exception as text_err:
                err_str = str(text_err).lower()
                if "safety" in err_str or "blocked" in err_str:
                    logger.warning(f"Acceso a raw.text bloqueado por safety: {text_err}. Marcada como explícita.")
                    result = ModerationResult(True, "adult", 1.0, "gemini_safety_block", "gemini_vision")
                    self._cache_result(url_hash, result)
                    return result

            result = self._parse_vision_response(raw_text)
            logger.info(f"Resultado de escaneo de imagen: flagged={result.flagged}, severity={result.severity}, reason={result.reason}")
            self._cache_result(url_hash, result)
            return result

        except asyncio.TimeoutError:
            logger.warning("Timeout en vision scan de moderación (Gemini excedió 9s).")
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
