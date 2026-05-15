from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.integrations.quote_client import FALLBACK_QUOTE, fetch_random_quote


@pytest.mark.asyncio
async def test_returns_quote_on_success() -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(
        return_value=[{"q": "Stay hungry", "a": "Steve Jobs", "h": ""}]
    )
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__.return_value = mock_client

    with patch("app.integrations.quote_client.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_random_quote()

    assert result == {"quote": "Stay hungry", "author": "Steve Jobs"}


@pytest.mark.asyncio
async def test_falls_back_on_network_error() -> None:
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("boom"))
    mock_client.__aenter__.return_value = mock_client

    with patch("app.integrations.quote_client.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_random_quote()

    assert result == FALLBACK_QUOTE


@pytest.mark.asyncio
async def test_falls_back_on_timeout() -> None:
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("slow"))
    mock_client.__aenter__.return_value = mock_client

    with patch("app.integrations.quote_client.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_random_quote()

    assert result == FALLBACK_QUOTE


@pytest.mark.asyncio
async def test_falls_back_on_malformed_payload() -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=[])  # empty list
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__.return_value = mock_client

    with patch("app.integrations.quote_client.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_random_quote()

    assert result == FALLBACK_QUOTE


@pytest.mark.asyncio
async def test_falls_back_on_missing_fields() -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=[{"q": "only quote"}])  # missing 'a'
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__.return_value = mock_client

    with patch("app.integrations.quote_client.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_random_quote()

    assert result == FALLBACK_QUOTE
