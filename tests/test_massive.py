"""Massive client unit tests (HTTP mocked)."""

from __future__ import annotations

import httpx
import pytest

from aibots.tools import massive as massive_md


class _FakeResp:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "err",
                request=httpx.Request("GET", "https://api.polygon.io"),
                response=httpx.Response(self.status_code),
            )

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, resp):
        self._resp = resp
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None

    async def get(self, url, params=None):
        self.calls.append({"url": url, "params": params})
        return self._resp


@pytest.mark.asyncio
async def test_get_prev_close(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "k")
    payload = {
        "results": [
            {"o": 10, "h": 12, "l": 9, "c": 11.5, "v": 1000, "t": 1_700_000_000_000}
        ]
    }
    client = _FakeClient(_FakeResp(payload))
    monkeypatch.setattr(massive_md.httpx, "AsyncClient", lambda **kw: client)
    q = await massive_md.get_prev_close("aapl")
    assert q["ticker"] == "AAPL"
    assert q["close"] == 11.5
    assert q["source"] == "massive"
    assert "apiKey" in client.calls[0]["params"]


@pytest.mark.asyncio
async def test_get_news(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "k")
    payload = {
        "results": [
            {
                "title": "Apple event",
                "published_utc": "2024-06-01T12:00:00Z",
                "article_url": "https://example.com",
                "publisher": {"name": "Reuters"},
            }
        ]
    }
    monkeypatch.setattr(
        massive_md.httpx, "AsyncClient", lambda **kw: _FakeClient(_FakeResp(payload))
    )
    n = await massive_md.get_news("AAPL", limit=5)
    assert n["source"] == "massive"
    assert n["items"][0]["headline"] == "Apple event"


@pytest.mark.asyncio
async def test_403_raises(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "k")
    monkeypatch.setattr(
        massive_md.httpx,
        "AsyncClient",
        lambda **kw: _FakeClient(_FakeResp({}, status_code=403)),
    )
    with pytest.raises(RuntimeError, match="403"):
        await massive_md.get_prev_close("AAPL")
