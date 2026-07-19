"""Tests for aibots.tools.news — Finnhub boundary fully mocked."""

from __future__ import annotations

import httpx
import pytest

from aibots.tools import news


class _FakeResp:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=httpx.Request("GET", "https://finnhub.io"),
                response=httpx.Response(self.status_code),
            )

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, resp):
        self._resp = resp
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, params=None):
        self.calls.append({"url": url, "params": params})
        return self._resp


@pytest.mark.asyncio
async def test_missing_api_key_degrades(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    result = await news.get_news("aapl")
    assert result["ticker"] == "AAPL"
    assert result["items"] == []
    assert result["source"] == "none"
    assert "FINNHUB_API_KEY" in result["note"]


@pytest.mark.asyncio
async def test_fetches_and_normalizes(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    payload = [
        {
            "headline": "Apple ships new chip",
            "datetime": 1_700_000_000,
            "source": "Reuters",
            "url": "https://example.com/a",
        },
        {
            "headline": "AAPL upgrade",
            "datetime": 1_700_086_400,
            "source": "Bloomberg",
            "url": "https://example.com/b",
        },
    ]
    client = _FakeClient(_FakeResp(payload))
    monkeypatch.setattr(news.httpx, "AsyncClient", lambda **kw: client)

    result = await news.get_news("AAPL", days=7, limit=10)

    assert result["source"] == "finnhub"
    assert len(result["items"]) == 2
    assert result["items"][0]["headline"] == "Apple ships new chip"
    assert result["items"][0]["source"] == "Reuters"
    assert result["items"][0]["url"].startswith("https://")
    assert "T" in result["items"][0]["datetime"]  # ISO timestamp
    assert client.calls[0]["params"]["symbol"] == "AAPL"
    assert client.calls[0]["params"]["token"] == "test-key"


@pytest.mark.asyncio
async def test_limit_truncates(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "k")
    payload = [
        {"headline": f"h{i}", "datetime": 1_700_000_000 + i, "source": "S", "url": f"u{i}"}
        for i in range(20)
    ]
    monkeypatch.setattr(
        news.httpx, "AsyncClient", lambda **kw: _FakeClient(_FakeResp(payload))
    )
    result = await news.get_news("MSFT", limit=3)
    assert len(result["items"]) == 3


@pytest.mark.asyncio
async def test_http_error_degrades(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "k")
    monkeypatch.setattr(
        news.httpx, "AsyncClient", lambda **kw: _FakeClient(_FakeResp([], status_code=500))
    )
    result = await news.get_news("AAPL")
    assert result["items"] == []
    assert "failed" in result["note"]


@pytest.mark.asyncio
async def test_blank_ticker_raises(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "k")
    with pytest.raises(ValueError):
        await news.get_news("  ")
