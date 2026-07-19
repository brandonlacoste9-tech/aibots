"""Company news via Finnhub free-tier company-news endpoint.

Without FINNHUB_API_KEY the tool degrades gracefully: empty list, source="none".
Never raises solely for a missing key — research must still complete.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

import httpx

_FINNHUB_URL = "https://finnhub.io/api/v1/company-news"
_TIMEOUT_S = 15.0


def _api_key() -> str | None:
    key = (os.environ.get("FINNHUB_API_KEY") or "").strip()
    return key or None


def _normalize_item(raw: dict) -> dict:
    """Map a Finnhub article dict to the pinned journal schema."""
    # Finnhub uses unix epoch seconds in `datetime`
    ts = raw.get("datetime")
    if isinstance(ts, (int, float)) and ts > 0:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    elif isinstance(ts, str) and ts:
        dt = ts
    else:
        dt = ""

    headline = str(raw.get("headline") or raw.get("summary") or "").strip()
    source = str(raw.get("source") or "").strip()
    url = str(raw.get("url") or "").strip()
    return {
        "headline": headline,
        "datetime": dt,
        "source": source,
        "url": url,
    }


async def get_news(ticker: str, days: int = 7, limit: int = 10) -> dict:
    """Fetch recent company news headlines for *ticker*.

    Returns::

        {
          "ticker": "AAPL",
          "items": [{"headline", "datetime", "source", "url"}, ...],
          "source": "finnhub" | "none",
          "note": optional degradation / empty-result note,
        }

    Degrades (does not raise) when FINNHUB_API_KEY is unset or the API fails.
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        raise ValueError("ticker must be a non-empty string")

    days = max(1, min(int(days), 30))
    limit = max(1, min(int(limit), 50))

    key = _api_key()
    if not key:
        return {
            "ticker": ticker,
            "items": [],
            "source": "none",
            "note": "FINNHUB_API_KEY not configured; news skipped",
        }

    today = date.today()
    params = {
        "symbol": ticker,
        "from": (today - timedelta(days=days)).isoformat(),
        "to": today.isoformat(),
        "token": key,
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.get(_FINNHUB_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # network / HTTP / JSON
        return {
            "ticker": ticker,
            "items": [],
            "source": "finnhub",
            "note": f"finnhub request failed: {exc}",
        }

    if not isinstance(payload, list):
        return {
            "ticker": ticker,
            "items": [],
            "source": "finnhub",
            "note": "unexpected finnhub response shape",
        }

    items = [_normalize_item(raw) for raw in payload if isinstance(raw, dict)]
    # Drop empty headlines; Finnhub already sorts newest-first
    items = [it for it in items if it["headline"]][:limit]

    out: dict = {
        "ticker": ticker,
        "items": items,
        "source": "finnhub",
    }
    if not items:
        out["note"] = f"no headlines for {ticker} in the last {days} day(s)"
    return out
