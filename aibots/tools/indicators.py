"""Pure-Python technical indicators over OHLCV bar dicts.

No pandas/numpy: this layer stays dependency-free. Short series yield None
for the affected values instead of raising; only an empty `bars` list is an
error. All floats in the output are rounded to 4 decimal places.
"""

from __future__ import annotations

DEFAULT_INDICATORS = ["sma_20", "sma_50", "rsi_14", "macd", "bbands"]

_TAIL = 5


def _round(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _ema_series(values: list[float], period: int) -> list[float]:
    """EMA seeded with the SMA of the first `period` values.

    Element 0 aligns with ``values[period - 1]``; returns [] when there are
    fewer than `period` values.
    """
    if len(values) < period:
        return []
    k = 2.0 / (period + 1)
    ema = sum(values[:period]) / period
    series = [ema]
    for v in values[period:]:
        ema = v * k + ema * (1.0 - k)
        series.append(ema)
    return series


def _rsi(closes: list[float], period: int = 14) -> float | None:
    """Wilder-smoothed RSI. Needs at least ``period + 1`` closes."""
    if len(closes) < period + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for prev, cur in zip(closes, closes[1:]):
        change = cur - prev
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _macd(closes: list[float]) -> tuple[float | None, float | None, float | None]:
    """MACD (12/26 EMA, 9 signal). Signal/histogram need >= 34 closes."""
    ema12 = _ema_series(closes, 12)
    ema26 = _ema_series(closes, 26)
    if not ema26:
        return None, None, None
    offset = 26 - 12  # ema12 index aligning with ema26[0]
    macd_series = [ema12[offset + i] - ema26[i] for i in range(len(ema26))]
    signal_series = _ema_series(macd_series, 9)
    macd_value = macd_series[-1]
    if not signal_series:
        return macd_value, None, None
    signal_value = signal_series[-1]
    return macd_value, signal_value, macd_value - signal_value


def _bbands(
    closes: list[float], period: int = 20, num_std: float = 2.0
) -> tuple[float | None, float | None, float | None]:
    """Bollinger Bands (upper, middle, lower) using population stddev."""
    if len(closes) < period:
        return None, None, None
    window = closes[-period:]
    middle = sum(window) / period
    variance = sum((c - middle) ** 2 for c in window) / period
    sd = variance**0.5
    return middle + num_std * sd, middle, middle - num_std * sd


def _sma_tail(closes: list[float], period: int, n: int = _TAIL) -> list[float | None]:
    """SMA value at each of the last n bar positions, None-padded on the left."""
    out: list[float | None] = []
    for i in range(max(0, len(closes) - n), len(closes)):
        if i + 1 >= period:
            out.append(_round(sum(closes[i - period + 1 : i + 1]) / period))
        else:
            out.append(None)
    return [None] * (n - len(out)) + out


def compute_indicators(bars: list[dict], indicators: list[str] | None = None) -> dict:
    """Compute indicator snapshots over OHLCV bars ordered oldest to newest.

    Unknown indicator names are ignored silently. The "latest" block always
    carries the full pinned key set; unrequested or under-fed indicators are
    None. Raises ValueError only when `bars` is empty.
    """
    if not bars:
        raise ValueError("bars must be a non-empty list of OHLCV dicts")
    requested = set(DEFAULT_INDICATORS if indicators is None else indicators)
    closes = [float(bar["close"]) for bar in bars]

    sma_20 = _sma(closes, 20) if "sma_20" in requested else None
    sma_50 = _sma(closes, 50) if "sma_50" in requested else None
    rsi_14 = _rsi(closes, 14) if "rsi_14" in requested else None
    macd, signal, histogram = _macd(closes) if "macd" in requested else (None, None, None)
    upper, middle, lower = _bbands(closes) if "bbands" in requested else (None, None, None)

    return {
        "latest": {
            "sma_20": _round(sma_20),
            "sma_50": _round(sma_50),
            "rsi_14": _round(rsi_14),
            "macd": {
                "macd": _round(macd),
                "signal": _round(signal),
                "histogram": _round(histogram),
            },
            "bbands": {
                "upper": _round(upper),
                "middle": _round(middle),
                "lower": _round(lower),
            },
        },
        "context": {
            "last_close": _round(closes[-1]),
            "bars_used": len(closes),
            "sma_20_series_tail": _sma_tail(closes, 20),
            "close_series_tail": [None] * max(0, _TAIL - len(closes))
            + [_round(c) for c in closes[-_TAIL:]],
        },
    }
