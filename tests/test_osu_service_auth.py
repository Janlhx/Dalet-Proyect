import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from services.osu_service import OsuService


def _make_response(status_code: int, json_data: dict, url: str = "https://osu.ppy.sh/api/v2/users/Litxe/osu") -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(status_code=status_code, json=json_data, request=request)


@pytest.mark.asyncio
async def test_get_refreshes_token_on_401():
    service = OsuService(client_id=123, client_secret="secret")
    service.token = "stale-token"
    service.token_expiry = 9999999999.0

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    # First GET returns 401 with stale-token; then POST /oauth/token returns new-token;
    # then retried GET returns 200.
    mock_client.request = AsyncMock(
        side_effect=[
            _make_response(401, {"authentication": "basic"}),
            _make_response(200, {"id": 42, "username": "Litxe"}),
        ]
    )
    mock_client.post = AsyncMock(
        return_value=_make_response(
            200,
            {"access_token": "fresh-token", "expires_in": 86400},
            url="https://osu.ppy.sh/oauth/token",
        )
    )

    with patch("services.osu_service.httpx.AsyncClient", return_value=mock_client):
        data = await service._get("users/Litxe/osu")

    assert data == {"id": 42, "username": "Litxe"}
    assert service.token == "fresh-token"
    assert mock_client.post.await_count == 1
    assert mock_client.request.await_count == 2
    second_call_headers = mock_client.request.await_args_list[1].kwargs["headers"]
    assert second_call_headers["Authorization"] == "Bearer fresh-token"


@pytest.mark.asyncio
async def test_authenticate_resets_token_on_failure():
    service = OsuService(client_id=123, client_secret="secret")
    service.token = "old-token"
    service.token_expiry = 9999999999.0

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(
        return_value=_make_response(503, {"error": "unavailable"}, url="https://osu.ppy.sh/oauth/token")
    )

    with patch("services.osu_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(httpx.HTTPStatusError):
            await service._authenticate(force=True)

    assert service.token is None
    assert service.token_expiry == 0
