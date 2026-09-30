import pytest
import hashlib
from unittest.mock import MagicMock, AsyncMock
from services.moderation_service import ModerationService, ModerationResult


class DummyAttachment:
    def __init__(self, filename, content_type="image/jpeg", url="https://cdn.discordapp.com/attachments/1/1/sample.jpg"):
        self.filename = filename
        self.content_type = content_type
        self.url = url


class DummyEmbed:
    def __init__(self, image_url=None, thumb_url=None, provider_name=None):
        self.image = MagicMock(url=image_url) if image_url else None
        self.thumbnail = MagicMock(url=thumb_url) if thumb_url else None
        self.provider = MagicMock(name=provider_name) if provider_name else None


class DummyMessage:
    def __init__(self, attachments=None, embeds=None, content=""):
        self.attachments = attachments or []
        self.embeds = embeds or []
        self.content = content


def test_extract_image_urls_ignores_safe_player_thumbnails():
    yt_embed = DummyEmbed(thumb_url="https://i.ytimg.com/vi/abc/hqdefault.jpg", provider_name="YouTube")
    msg = DummyMessage(embeds=[yt_embed], content="https://youtu.be/abc")
    urls = ModerationService.extract_image_urls(msg)
    assert len(urls) == 0


def test_extract_image_urls_allows_attachments_and_twitter():
    att = DummyAttachment("photo.png", "image/png", "https://cdn.discordapp.com/attachments/1/photo.png")
    msg = DummyMessage(attachments=[att])
    urls = ModerationService.extract_image_urls(msg)
    assert len(urls) == 1
    assert urls[0] == "https://cdn.discordapp.com/attachments/1/photo.png"

    # Enlace de imagen de Twitter/X
    tw_embed = DummyEmbed(image_url="https://pbs.twimg.com/media/sample.jpg", provider_name="Twitter")
    msg2 = DummyMessage(embeds=[tw_embed])
    urls2 = ModerationService.extract_image_urls(msg2)
    assert len(urls2) == 1
    assert "pbs.twimg.com" in urls2[0]


@pytest.mark.asyncio
async def test_moderation_blacklist_cache_hit_bypasses_gemini():
    nlp_mock = MagicMock()
    nlp_mock.gemini_api_key = "test_key"
    admin_mock = MagicMock()
    admin_mock.get_image_hash = AsyncMock(return_value=None)
    admin_mock.save_image_hash = AsyncMock()

    mod_service = ModerationService(nlp_mock, admin_repo=admin_mock)

    # Simular una imagen ya conocida en la lista negra
    sample_bytes = b"fake_illicit_image_bytes_12345"
    sample_sha256 = hashlib.sha256(sample_bytes).hexdigest()
    mod_service._blacklist_cache[sample_sha256] = ModerationResult(
        flagged=True, severity="adult", confidence=1.0, reason="previously_banned", method="image_hash_blacklist"
    )

    # Configurar mock http client
    http_resp_mock = MagicMock()
    http_resp_mock.status_code = 200
    http_resp_mock.content = sample_bytes
    http_resp_mock.headers = {"Content-Type": "image/jpeg"}

    nlp_mock._http_client = MagicMock()
    nlp_mock._http_client.get = AsyncMock(return_value=http_resp_mock)
    nlp_mock._http_client.post = AsyncMock()  # Gemini nunca debería ser llamado!

    result = await mod_service._scan_image("https://cdn.discordapp.com/attachments/test.jpg")

    assert result.flagged is True
    assert result.method == "image_hash_blacklist"
    assert result.reason == "previously_banned"
    # Verificar que Gemini NUNCA fue llamado
    nlp_mock._http_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_moderation_safe_cache_hit_bypasses_gemini():
    nlp_mock = MagicMock()
    nlp_mock.gemini_api_key = "test_key"
    admin_mock = MagicMock()
    admin_mock.get_image_hash = AsyncMock(return_value=None)

    mod_service = ModerationService(nlp_mock, admin_repo=admin_mock)

    sample_bytes = b"innocent_cat_meme_bytes_67890"
    sample_sha256 = hashlib.sha256(sample_bytes).hexdigest()
    mod_service._safe_cache[sample_sha256] = ModerationResult(
        flagged=False, severity="safe", confidence=1.0, reason="", method="gemini_vision"
    )

    http_resp_mock = MagicMock()
    http_resp_mock.status_code = 200
    http_resp_mock.content = sample_bytes
    http_resp_mock.headers = {"Content-Type": "image/jpeg"}

    nlp_mock._http_client = MagicMock()
    nlp_mock._http_client.get = AsyncMock(return_value=http_resp_mock)
    nlp_mock._http_client.post = AsyncMock()

    result = await mod_service._scan_image("https://cdn.discordapp.com/attachments/cat.jpg")

    assert result.flagged is False
    # Verificar que Gemini NUNCA fue llamado para una imagen limpia ya conocida
    nlp_mock._http_client.post.assert_not_called()
