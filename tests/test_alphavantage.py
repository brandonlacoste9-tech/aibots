"""Alpha Vantage client unit tests (HTTP mocked)."""

from __future__ import annotations

import httpx
import pytest

from aibots.tools import alphavantage as av


class _FakeResp:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "err",
                request=httpx.Request("GET", "https://www.alphavantage.co"),
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
        self.calls.append(params)
        return self._resp


@pytest.mark.asyncio
async def test_get_news_normalizes(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "k")
    payload = {
        "feed": [
            {
                "title": "Chip demand rises",
                "time_published": "20240115T143000",
                "source": "Reuters",
                "url": "https://example.com/a",
                "overall_sentiment_label": "Bullish",
                "overall_sentiment_score": 0.3,
            }
        ]
    }
    client = _FakeClient(_FakeResp(payload))
    monkeypatch.setattr(av.httpx, "AsyncClient", lambda **kw: client)

    result = await av.get_news("AAPL", limit=5)
    assert result["source"] == "alphavantage"
    assert result["items"][0]["headline"] == "Chip demand rises"
    assert "2024" in result["items"][0]["datetime"]
    assert client.calls[0]["function"] == "NEWS_SENTIMENT"
    assert client.calls[0]["apikey"] == "k"


@pytest.mark.asyncio
async def test_get_quote(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "k")
    payload = {
        "Global Quote": {
            "01. symbol": "IBM",
            "05. price": "150.25",
            "02. open": "149.00",
            "03. high": "151.00",
            "04. low": "148.50",
            "06. volume": "1000000",
            "07. latest trading day": "2024-01-15",
            "08. previous close": "149.50",
            "09. change": "0.75",
            "10. change percent": "0.50%",
        }
    }
    monkeypatch.setattr(
        av.httpx, "AsyncClient", lambda **kw: _FakeClient(_FakeResp(payload))
    )
    q = await av.get_quote("ibm")
    assert q["ticker"] == "IBM"
    assert q["price"] == 150.25
    assert q["source"] == "alphavantage"


@pytest.mark.asyncio
async def test_rate_limit_note_raises(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "k")
    payload = {"Note": "Thank you for using Alpha Vantage! Our standard API call frequency is..."}
    monkeypatch.setattr(
        av.httpx, "AsyncClient", lambda **kw: _FakeClient(_FakeResp(payload))
    )
    with pytest.raises(RuntimeError, match="rate limit"):
        await av.get_news("AAPL")
