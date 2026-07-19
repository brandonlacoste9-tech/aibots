"""Tests for aibots.tools.market_data — yfinance fully mocked at the boundary."""

from __future__ import annotations

import datetime as dt

import pytest

from aibots.tools import market_data


class FakeFrame:
    """Minimal stand-in for the pandas DataFrame returned by yf.Ticker.history."""

    def __init__(self, rows):
        self._rows = list(rows)

    @property
    def empty(self) -> bool:
        return not self._rows

    def sort_index(self) -> "FakeFrame":
        return FakeFrame(sorted(self._rows, key=lambda r: r[0]))

    def iterrows(self):
        return iter(self._rows)


def bar_row(idx, close: float, volume=1000):
    return (
        idx,
        {
            "Open": close - 0.25,
            "High": close + 0.5,
            "Low": close - 0.75,
            "Close": float(close),
            "Volume": volume,
        },
    )


def make_frame(closes, start=dt.date(2024, 1, 2)) -> FakeFrame:
    return FakeFrame(bar_row(start + dt.timedelta(days=i), c) for i, c in enumerate(closes))


def install_ticker(monkeypatch, handler) -> list[dict]:
    """Patch market_data.yf.Ticker so .history() delegates to handler(ticker)."""
    calls = []

    class _FakeTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        def history(self, period="6mo", interval="1d", auto_adjust=True):
            calls.append(
                {
                    "ticker": self.ticker,
                    "period": period,
                    "interval": interval,
                    "auto_adjust": auto_adjust,
                }
            )
            return handler(self.ticker)

    monkeypatch.setattr(market_data.yf, "Ticker", _FakeTicker)
    return calls


@pytest.fixture(autouse=True)
def clear_cache():
    market_data._cache.clear()
    yield
    market_data._cache.clear()


@pytest.fixture
def no_backoff(monkeypatch):
    monkeypatch.setattr(market_data, "_BACKOFF_S", 0.0)


@pytest.mark.asyncio
async def test_bars_normalized_oldest_first(monkeypatch):
    # rows deliberately out of order; output must be oldest -> newest
    frame = FakeFrame(
        [
            bar_row(dt.date(2024, 1, 3), 102.123456789),
            bar_row(dt.date(2024, 1, 2), 101.0),
            bar_row(dt.date(2024, 1, 4), 103.0),
        ]
    )
    calls = install_ticker(monkeypatch, lambda t: frame)

    result = await market_data.get_price_history("aapl")

    assert result["ticker"] == "AAPL"
    assert result["source"] == "yfinance"
    assert result["cached"] is False
    assert [b["date"] for b in result["bars"]] == ["2024-01-02", "2024-01-03", "2024-01-04"]
    assert result["bars"][1] == {
        "date": "2024-01-03",
        "open": round(102.123456789 - 0.25, 4),
        "high": round(102.123456789 + 0.5, 4),
        "low": round(102.123456789 - 0.75, 4),
        "close": 102.1235,
        "volume": 1000,
    }
    assert isinstance(result["bars"][1]["volume"], int)
    assert len(calls) == 1
    assert calls[0] == {
        "ticker": "AAPL",
        "period": "6mo",
        "interval": "1d",
        "auto_adjust": True,
    }


@pytest.mark.asyncio
async def test_intraday_dates_are_iso_datetimes(monkeypatch):
    frame = FakeFrame(
        [
            bar_row(dt.datetime(2024, 1, 2, 10, 30), 101.0),
            bar_row(dt.datetime(2024, 1, 2, 9, 30), 100.0),
        ]
    )
    install_ticker(monkeypatch, lambda t: frame)

    result = await market_data.get_price_history("MSFT", period="1d", interval="1h")

    assert [b["date"] for b in result["bars"]] == [
        "2024-01-02T09:30:00",
        "2024-01-02T10:30:00",
    ]


@pytest.mark.asyncio
async def test_cache_hit_avoids_second_fetch(monkeypatch):
    calls = install_ticker(monkeypatch, lambda t: make_frame([100.0, 101.0]))

    first = await market_data.get_price_history("AAPL")
    second = await market_data.get_price_history("AAPL")

    assert len(calls) == 1
    assert first["cached"] is False
    assert second["cached"] is True
    assert second["bars"] == first["bars"]


@pytest.mark.asyncio
async def test_cache_keyed_on_period_and_interval(monkeypatch):
    calls = install_ticker(monkeypatch, lambda t: make_frame([100.0]))

    await market_data.get_price_history("AAPL", period="6mo", interval="1d")
    await market_data.get_price_history("AAPL", period="1mo", interval="1d")
    await market_data.get_price_history("AAPL", period="6mo", interval="1wk")

    assert len(calls) == 3


@pytest.mark.asyncio
async def test_cache_expires_after_ttl(monkeypatch):
    calls = install_ticker(monkeypatch, lambda t: make_frame([100.0]))
    monkeypatch.setattr(market_data, "_DAILY_TTL_S", -1.0)

    await market_data.get_price_history("AAPL")
    result = await market_data.get_price_history("AAPL")

    assert len(calls) == 2
    assert result["cached"] is False


@pytest.mark.asyncio
async def test_cached_result_is_isolated_from_caller_mutation(monkeypatch):
    install_ticker(monkeypatch, lambda t: make_frame([100.0]))

    first = await market_data.get_price_history("AAPL")
    first["bars"][0]["close"] = -1.0

    second = await market_data.get_price_history("AAPL")
    assert second["bars"][0]["close"] == 100.0


@pytest.mark.asyncio
async def test_empty_frame_raises_value_error_without_retry(monkeypatch):
    calls = install_ticker(monkeypatch, lambda t: FakeFrame([]))

    with pytest.raises(ValueError, match="no data for AAPL"):
        await market_data.get_price_history("AAPL")

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_retry_succeeds_after_transient_error(monkeypatch, no_backoff):
    state = {"n": 0}

    def handler(t):
        state["n"] += 1
        if state["n"] == 1:
            raise ConnectionError("boom")
        return make_frame([100.0, 101.0])

    install_ticker(monkeypatch, handler)

    result = await market_data.get_price_history("AAPL")

    assert state["n"] == 2
    assert result["cached"] is False
    assert len(result["bars"]) == 2


@pytest.mark.asyncio
async def test_persistent_error_raises_value_error_after_one_retry(monkeypatch, no_backoff):
    def handler(t):
        raise ConnectionError("boom")

    calls = install_ticker(monkeypatch, handler)

    with pytest.raises(ValueError, match="no data for AAPL"):
        await market_data.get_price_history("AAPL")

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_blank_ticker_rejected_without_fetch(monkeypatch):
    calls = install_ticker(monkeypatch, lambda t: make_frame([100.0]))

    with pytest.raises(ValueError):
        await market_data.get_price_history("   ")

    assert calls == []


@pytest.mark.asyncio
async def test_nan_volume_becomes_zero(monkeypatch):
    frame = FakeFrame([bar_row(dt.date(2024, 1, 2), 100.0, volume=float("nan"))])
    install_ticker(monkeypatch, lambda t: frame)

    result = await market_data.get_price_history("AAPL")

    assert result["bars"][0]["volume"] == 0
