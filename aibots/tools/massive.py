"""Massive.com market data (Polygon-compatible REST API).

Env:
  MASSIVE_API_KEY (required for this client)
  MASSIVE_BASE_URL (optional, default https://api.polygon.io)

Free/basic plans: prev-day aggregates + news are typically available.
Real-time tape often needs a paid plan.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx

_DEFAULT_BASE = "https://api.polygon.io"
_TIMEOUT_S = 15.0


def api_key() -> str | None:
    key = (os.environ.get("MASSIVE_API_KEY") or os.environ.get("POLYGON_API_KEY") or "").strip()
    return key or None


def base_url() -> str:
    return (os.environ.get("MASSIVE_BASE_URL") or _DEFAULT_BASE).rstrip("/")


def is_configured() -> bool:
    return bool(api_key())


async def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    key = api_key()
    if not key:
        raise RuntimeError("MASSIVE_API_KEY not configured")
    q = dict(params or {})
    q["apiKey"] = key
    url = f"{base_url()}{path}"
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        resp = await client.get(url, params=q)
        if resp.status_code == 429:
            raise RuntimeError("Massive rate limit (429)")
        if resp.status_code == 403:
            raise RuntimeError(f"Massive plan forbids this endpoint (403): {path}")
        if resp.status_code >= 400:
            raise RuntimeError(f"Massive HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError("Massive: unexpected response shape")
    return data


async def get_prev_close(ticker: str) -> dict:
    """Previous session OHLC (works on free/basic plans)."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        raise ValueError("ticker must be a non-empty string")
    data = await _get(f"/v2/aggs/ticker/{ticker}/prev", {"adjusted": "true"})
    results = data.get("results") or []
    if not results:
        raise ValueError(f"no Massive prev bar for {ticker}")
    bar = results[0]
    close = bar.get("c")
    return {
        "ticker": ticker,
        "open": bar.get("o"),
        "high": bar.get("h"),
        "low": bar.get("l"),
        "close": close,
        "price": close,
        "volume": bar.get("v"),
        "vwap": bar.get("vw"),
        "timestamp": bar.get("t"),
        "source": "massive",
        "delayed": True,
        "note": "Previous session aggregate (not live tape)",
    }


async def get_quote(ticker: str) -> dict:
    """Best free-plan quote: previous session close as last price."""
    prev = await get_prev_close(ticker)
    return {
        "ticker": prev["ticker"],
        "price": prev["close"],
        "open": prev.get("open"),
        "high": prev.get("high"),
        "low": prev.get("low"),
        "close": prev["close"],
        "volume": prev.get("volume"),
        "source": "massive",
        "delayed": True,
        "note": prev.get("note"),
    }


async def get_news(ticker: str, limit: int = 10) -> dict:
    """Ticker news → journal-friendly items."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        raise ValueError("ticker must be a non-empty string")
    limit = max(1, min(int(limit), 50))
    data = await _get(
        "/v2/reference/news",
        {
            "ticker": ticker,
            "limit": limit,
            "order": "desc",
            "sort": "published_utc",
        },
    )
    items = []
    for raw in data.get("results") or []:
        if not isinstance(raw, dict):
            continue
        headline = str(raw.get("title") or "").strip()
        if not headline:
            continue
        pub = raw.get("published_utc") or ""
        # Normalize to ISO-ish string
        if isinstance(pub, (int, float)):
            pub = datetime.fromtimestamp(pub / 1000.0, tz=timezone.utc).isoformat()
        items.append(
            {
                "headline": headline,
                "datetime": str(pub),
                "source": str(raw.get("publisher", {}).get("name") if isinstance(raw.get("publisher"), dict) else raw.get("author") or "").strip(),
                "url": str(raw.get("article_url") or raw.get("amp_url") or "").strip(),
            }
        )
        if len(items) >= limit:
            break
    out: dict = {
        "ticker": ticker,
        "items": items,
        "source": "massive",
    }
    if not items:
        out["note"] = f"no Massive headlines for {ticker}"
    return out
