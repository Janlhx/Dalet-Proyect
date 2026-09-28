import re
import json
import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger("dalet.services.moderation")

_ILLEGAL_PATTERNS = [
    r"\bcsam\b", r"\bcp\b(?!\+|\s*\d)", r"child\s*(porn|sex|nud|exploit)",
    r"kiddie\s*porn", r"loli\s*porn", r"shota\s*porn",
    r"menor(es)?\s*(desnud|porn|sex|naked|nud)",
    r"pedofil(ia|e)?", r"pedo\s*porn", r"jailbait",
]

_ADULT_PATTERNS = [
    r"\bporn(o|hub)?\b", r"\bxxx\b", r"\bnsfw\b",
    r"\bonlyfans\b", r"xvideos\.com", r"pornhub\.com", r"xnxx\.com",
    r"redtube\.com", r"rule34", r"hentai\s*(link|site|vid)",
    r"(send|comparte|manda|dm|dm[s])\s*(me\s*)?(porn|nud|xxx)",
]

_ILLEGAL_RE = re.compile("|".join(_ILLEGAL_PATTERNS), re.IGNORECASE)
_ADULT_RE   = re.compile("|".join(_ADULT_PATTERNS), re.IGNORECASE)

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"}

_VISION_SAFETY_PROMPT = (
    "Classify this image for content moderation. "
    "Reply ONLY with a JSON object, no extra text: "
    '{"safe": true/false, "category": "safe" | "suggestive" | "explicit" | "illegal", "confidence": 0.0-1.0}. '
    "Category 'illegal' means CSAM or similar unlawful content. "
    "Be strict but accurate — art, anime, and memes should only be flagged if clearly explicit."
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
      1. Fast text regex scan (no API cost).
      2. Gemini Vision image scan (paid-tier, runs only when attachments present).

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
            return ModerationResult(False, "safe", 1.0, "vision_unavailable", "gemini_vision")

        url_hash = hashlib.md5(url.encode()).hexdigest()
        if url_hash in self._vision_cache:
            return self._vision_cache[url_hash]

        try:
            resp = await self._nlp._http_client.get(url, timeout=5.0)
            if resp.status_code != 200:
                return ModerationResult(False, "safe", 1.0, "download_failed", "gemini_vision")

            mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
            if not mime.startswith("image/"):
                mime = "image/jpeg"

            from google.genai import types
            image_part = types.Part.from_bytes(data=resp.content, mime_type=mime)

            model_name = __import__("os").getenv("GEMINI_MODEL", "gemini-2.5-flash")
            raw = await asyncio.wait_for(
                self._nlp.client.aio.models.generate_content(
                    model=model_name,
                    contents=[_VISION_SAFETY_PROMPT, image_part],
                ),
                timeout=8.0,
            )

            result = self._parse_vision_response(raw.text if raw else "")

            if len(self._vision_cache) > 100:
                self._vision_cache.clear()
            self._vision_cache[url_hash] = result
            return result

        except asyncio.TimeoutError:
            logger.warning("Timeout en vision scan de moderación.")
            return ModerationResult(False, "safe", 1.0, "timeout", "gemini_vision")
        except Exception as e:
            logger.error(f"Error en vision scan de moderación: {e}")
            return ModerationResult(False, "safe", 1.0, "error", "gemini_vision")

    @staticmethod
    def _parse_vision_response(text: str) -> ModerationResult:
        try:
            cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
            data = json.loads(cleaned)
            safe = bool(data.get("safe", True))
            category = data.get("category", "safe")
            confidence = float(data.get("confidence", 0.5))

            if safe or category == "safe":
                return ModerationResult(False, "safe", confidence, "", "gemini_vision")

            severity = "illegal" if category == "illegal" else "adult"
            return ModerationResult(True, severity, confidence, f"vision:{category}", "gemini_vision")
        except Exception:
            return ModerationResult(False, "safe", 1.0, "parse_error", "gemini_vision")

    @staticmethod
    def extract_image_urls(message) -> list[str]:
        """Extract image URLs from Discord message attachments and embeds."""
        urls = []
        for att in message.attachments:
            if any(att.filename.lower().endswith(ext) for ext in _IMAGE_EXTENSIONS):
                urls.append(att.url)
        for embed in message.embeds:
            if embed.image and embed.image.url:
                urls.append(embed.image.url)
        return urls[:1]
