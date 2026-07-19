"""Price-history tool backed by yfinance: async wrapper, TTL cache, one retry."""

from __future__ import annotations

import asyncio
import time

import yfinance as yf

_INTRADAY_INTERVALS = frozenset({"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"})
_INTRADAY_TTL_S = 300.0
_DAILY_TTL_S = 3600.0
_BACKOFF_S = 1.0

_cache: dict[tuple[str, str, str], tuple[float, dict]] = {}


def _is_intraday(interval: str) -> bool:
    return interval.lower() in _INTRADAY_INTERVALS


def _ttl_s(interval: str) -> float:
    return _INTRADAY_TTL_S if _is_intraday(interval) else _DAILY_TTL_S


def _fetch_frame(ticker: str, period: str, interval: str):
    """Blocking yfinance call; intended for asyncio.to_thread."""
    return yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)


def _bar_date(idx, intraday: bool) -> str:
    if intraday:
        return idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
    if hasattr(idx, "strftime"):
        return idx.strftime("%Y-%m-%d")
    return str(idx)[:10]


def _normalize(ticker: str, frame, interval: str) -> dict:
    if frame is None or frame.empty:
        raise ValueError(f"no data for {ticker}")
    intraday = _is_intraday(interval)
    bars = []
    for idx, row in frame.sort_index().iterrows():
        try:
            volume = int(row["Volume"])
        except (TypeError, ValueError):
            volume = 0
        bars.append(
            {
                "date": _bar_date(idx, intraday),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": volume,
            }
        )
    return {"ticker": ticker, "bars": bars, "source": "yfinance", "cached": False}


def _copy(result: dict, cached: bool) -> dict:
    return {
        "ticker": result["ticker"],
        "bars": [dict(b) for b in result["bars"]],
        "source": result["source"],
        "cached": cached,
    }


async def get_price_history(ticker: str, period: str = "6mo", interval: str = "1d") -> dict:
    """Return OHLCV bars for *ticker*, oldest first.

    Results are cached per (ticker, period, interval): 300s TTL for intraday
    intervals, 3600s otherwise. Retries once with 1s backoff on fetch errors;
    raises ValueError when the ticker yields no data.
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        raise ValueError("ticker must be a non-empty string")

    key = (ticker, period, interval)
    hit = _cache.get(key)
    if hit is not None and time.time() - hit[0] < _ttl_s(interval):
        return _copy(hit[1], cached=True)

    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            frame = await asyncio.to_thread(_fetch_frame, ticker, period, interval)
            result = _normalize(ticker, frame, interval)
            _cache[key] = (time.time(), _copy(result, cached=False))
            return result
        except ValueError:
            raise  # empty frame: no retry, no caching
        except Exception as exc:  # network / yfinance failure
            last_exc = exc
            if attempt == 0:
                await asyncio.sleep(_BACKOFF_S)
    raise ValueError(f"no data for {ticker}") from last_exc
