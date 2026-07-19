"""Company news with multi-provider fallback.

Order:
1. Finnhub company-news (if FINNHUB_API_KEY set)
2. Massive / Polygon reference news (if MASSIVE_API_KEY set)
3. Alpha Vantage NEWS_SENTIMENT (if ALPHA_VANTAGE_API_KEY set)
4. Degrade to empty list with note (never hard-fail research)
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import httpx

from aibots.tools import alphavantage as av
from aibots.tools import bigdata as bigdata_md
from aibots.tools import massive as massive_md

_FINNHUB_URL = "https://finnhub.io/api/v1/company-news"
_TIMEOUT_S = 15.0


def _finnhub_key() -> str | None:
    key = (os.environ.get("FINNHUB_API_KEY") or "").strip()
    return key or None


def _any_news_key() -> bool:
    return bool(
        _finnhub_key()
        or massive_md.is_configured()
        or av.is_configured()
        or bigdata_md.is_configured()
    )


def _normalize_finnhub_item(raw: dict) -> dict:
    ts = raw.get("datetime")
    if isinstance(ts, (int, float)) and ts > 0:
        from datetime import datetime, timezone

        dt = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    elif isinstance(ts, str) and ts:
        dt = ts
    else:
        dt = ""

    return {
        "headline": str(raw.get("headline") or raw.get("summary") or "").strip(),
        "datetime": dt,
        "source": str(raw.get("source") or "").strip(),
        "url": str(raw.get("url") or "").strip(),
    }


async def _finnhub_news(ticker: str, days: int, limit: int) -> dict | None:
    key = _finnhub_key()
    if not key:
        return None

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
    except Exception as exc:  # network / HTTP
        return {
            "ticker": ticker,
            "items": [],
            "source": "finnhub",
            "note": f"finnhub request failed: {exc}",
            "_failed": True,
        }

    if not isinstance(payload, list):
        return {
            "ticker": ticker,
            "items": [],
            "source": "finnhub",
            "note": "unexpected finnhub response shape",
            "_failed": True,
        }

    items = [_normalize_finnhub_item(raw) for raw in payload if isinstance(raw, dict)]
    items = [it for it in items if it["headline"]][:limit]
    out: dict = {"ticker": ticker, "items": items, "source": "finnhub"}
    if not items:
        out["note"] = f"no finnhub headlines for {ticker} in the last {days} day(s)"
    return out


def _with_fallback_note(result: dict, notes: list[str]) -> dict:
    if notes:
        extra = "fallback after: " + "; ".join(notes)
        result = dict(result)
        result["note"] = (result.get("note") + "; " if result.get("note") else "") + extra
    return result


async def get_news(ticker: str, days: int = 7, limit: int = 10) -> dict:
    """Fetch recent company news headlines for *ticker*."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        raise ValueError("ticker must be a non-empty string")

    days = max(1, min(int(days), 30))
    limit = max(1, min(int(limit), 50))
    notes: list[str] = []

    finnhub = await _finnhub_news(ticker, days, limit)
    if finnhub is not None and not finnhub.pop("_failed", False) and finnhub.get("items"):
        return finnhub
    if finnhub is not None:
        notes.append(str(finnhub.get("note") or "finnhub empty"))

    if massive_md.is_configured():
        try:
            m_news = await massive_md.get_news(ticker, limit=limit)
            if m_news.get("items"):
                return _with_fallback_note(m_news, notes)
            if m_news.get("note"):
                notes.append(str(m_news["note"]))
        except Exception as exc:  # noqa: BLE001
            notes.append(f"massive failed: {exc}")

    if av.is_configured():
        try:
            av_news = await av.get_news(ticker, limit=limit)
            if av_news.get("items"):
                return _with_fallback_note(av_news, notes)
            if av_news.get("note"):
                notes.append(str(av_news["note"]))
        except Exception as exc:  # noqa: BLE001
            notes.append(f"alphavantage failed: {exc}")

    if bigdata_md.is_configured():
        try:
            bd_news = await bigdata_md.get_news(ticker, limit=limit)
            if bd_news.get("items"):
                return _with_fallback_note(bd_news, notes)
            if bd_news.get("note"):
                notes.append(str(bd_news["note"]))
        except Exception as exc:  # noqa: BLE001
            notes.append(f"bigdata failed: {exc}")

    if not _any_news_key():
        return {
            "ticker": ticker,
            "items": [],
            "source": "none",
            "note": (
                "No news API key configured "
                "(set FINNHUB_API_KEY, MASSIVE_API_KEY, ALPHA_VANTAGE_API_KEY, or BIGDATA_API_KEY)"
            ),
        }

    return {
        "ticker": ticker,
        "items": [],
        "source": "none",
        "note": "; ".join(notes) if notes else "no headlines available",
    }
