"""Alpha Vantage client (free tier).

Env: ALPHA_VANTAGE_API_KEY (alias: ALPHAVANTAGE_API_KEY)

Tight rate limits (~5 calls/min on free tier) — use for news / quote fallback,
not as the hammer for every chat turn. yfinance remains primary for history.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import httpx

_BASE = "https://www.alphavantage.co/query"
_TIMEOUT_S = 20.0


def api_key() -> str | None:
    key = (
        os.environ.get("ALPHA_VANTAGE_API_KEY")
        or os.environ.get("ALPHAVANTAGE_API_KEY")
        or ""
    ).strip()
    return key or None


def is_configured() -> bool:
    return bool(api_key())


async def _query(**params: Any) -> dict[str, Any]:
    key = api_key()
    if not key:
        raise RuntimeError("ALPHA_VANTAGE_API_KEY not configured")
    q = dict(params)
    q["apikey"] = key
    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        resp = await client.get(_BASE, params=q)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError("Alpha Vantage: unexpected response shape")
    if data.get("Note"):
        raise RuntimeError(f"Alpha Vantage rate limit: {str(data['Note'])[:160]}")
    if data.get("Information"):
        info = str(data["Information"])
        if any(
            s in info
            for s in ("Thank you", "API call frequency", "premium", "rate limit")
        ):
            raise RuntimeError(f"Alpha Vantage limit: {info[:160]}")
    if data.get("Error Message"):
        raise RuntimeError(f"Alpha Vantage error: {data['Error Message']}")
    return data


def _parse_av_time(raw: str | None) -> str:
    """Alpha Vantage NEWS uses YYYYMMDDTHHMMSS."""
    if not raw:
        return ""
    s = str(raw).strip()
    try:
        if "T" in s and len(s) >= 15 and s[8] == "T":
            dt = datetime.strptime(s[:15], "%Y%m%dT%H%M%S")
            return dt.isoformat() + "Z"
    except ValueError:
        pass
    return s


async def get_news(ticker: str, limit: int = 10) -> dict:
    """NEWS_SENTIMENT feed for a ticker → same item shape as Finnhub path."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        raise ValueError("ticker must be a non-empty string")
    limit = max(1, min(int(limit), 50))

    data = await _query(
        function="NEWS_SENTIMENT",
        tickers=ticker,
        limit=str(limit),
        sort="LATEST",
    )
    feed = data.get("feed") or []
    items = []
    for raw in feed[:limit]:
        if not isinstance(raw, dict):
            continue
        headline = str(raw.get("title") or "").strip()
        if not headline:
            continue
        items.append(
            {
                "headline": headline,
                "datetime": _parse_av_time(raw.get("time_published")),
                "source": str(raw.get("source") or "").strip(),
                "url": str(raw.get("url") or "").strip(),
                "sentiment": raw.get("overall_sentiment_label"),
                "sentiment_score": raw.get("overall_sentiment_score"),
            }
        )
    out: dict = {
        "ticker": ticker,
        "items": items,
        "source": "alphavantage",
    }
    if not items:
        out["note"] = f"no Alpha Vantage headlines for {ticker}"
    return out


async def get_quote(ticker: str) -> dict:
    """GLOBAL_QUOTE for a single symbol."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        raise ValueError("ticker must be a non-empty string")
    data = await _query(function="GLOBAL_QUOTE", symbol=ticker)
    gq = data.get("Global Quote") or {}
    price_raw = gq.get("05. price")
    if not gq or price_raw in (None, ""):
        raise ValueError(f"no Alpha Vantage quote for {ticker}")
    price = float(price_raw)
    return {
        "ticker": gq.get("01. symbol") or ticker,
        "price": price,
        "open": _float(gq.get("02. open")),
        "high": _float(gq.get("03. high")),
        "low": _float(gq.get("04. low")),
        "close": price,
        "volume": _float(gq.get("06. volume")),
        "latest_trading_day": gq.get("07. latest trading day"),
        "previous_close": _float(gq.get("08. previous close")),
        "change": _float(gq.get("09. change")),
        "change_percent": gq.get("10. change percent"),
        "source": "alphavantage",
    }


def _float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace("%", ""))
    except (TypeError, ValueError):
        return None
