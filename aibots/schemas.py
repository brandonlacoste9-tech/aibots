"""Tool schemas for the research agent, in OpenAI/xAI and Anthropic formats.

Research-first tool set: market data, indicators, news, plus recording-only
proposal stubs (propose_order / decide_hold). No broker tools exist by design.
"""

from __future__ import annotations

TOOL_NAMES: list[str] = [
    "get_price_history",
    "compute_indicators",
    "get_news",
    "get_company_profile",
    "propose_order",
    "decide_hold",
]

_INDICATOR_ENUM = ["sma_20", "sma_50", "rsi_14", "macd", "bbands"]

_BAR_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "date": {"type": "string", "description": "YYYY-MM-DD"},
        "open": {"type": "number"},
        "high": {"type": "number"},
        "low": {"type": "number"},
        "close": {"type": "number"},
        "volume": {"type": "integer"},
    },
    "required": ["date", "open", "high", "low", "close", "volume"],
    "additionalProperties": False,
}

_PARAMETERS: dict[str, dict] = {
    "get_price_history": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "minLength": 1, "description": "Ticker symbol, e.g. AAPL."},
            "period": {
                "type": "string",
                "enum": ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"],
                "default": "6mo",
            },
            "interval": {
                "type": "string",
                "enum": ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"],
                "default": "1d",
            },
        },
        "required": ["ticker"],
        "additionalProperties": False,
    },
    "compute_indicators": {
        "type": "object",
        "properties": {
            "bars": {
                "type": "array",
                "items": _BAR_SCHEMA,
                "minItems": 1,
                "description": "OHLCV bars, oldest to newest.",
            },
            "indicators": {
                "type": "array",
                "items": {"type": "string", "enum": _INDICATOR_ENUM},
                "description": "Subset of indicators to compute; defaults to all.",
            },
        },
        "required": ["bars"],
        "additionalProperties": False,
    },
    "get_news": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "minLength": 1},
            "days": {"type": "integer", "minimum": 1, "maximum": 30, "default": 7},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
        },
        "required": ["ticker"],
        "additionalProperties": False,
    },
    "get_company_profile": {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "minLength": 1,
                "description": "Ticker symbol, e.g. AAPL. Resolved via Bigdata knowledge graph.",
            },
        },
        "required": ["ticker"],
        "additionalProperties": False,
    },
    "propose_order": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "minLength": 1},
            "side": {"type": "string", "enum": ["buy", "sell"]},
            "qty": {"type": "number", "exclusiveMinimum": 0},
            "order_type": {"type": "string", "enum": ["limit", "market"], "default": "limit"},
            "limit_price": {"type": "number", "exclusiveMinimum": 0},
            "reason": {"type": "string", "minLength": 8, "description": "Thesis behind the proposal."},
        },
        "required": ["symbol", "side", "qty", "reason"],
        "additionalProperties": False,
    },
    "decide_hold": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "minLength": 1},
            "reason": {"type": "string", "minLength": 8, "description": "Why no trade is warranted."},
        },
        "required": ["reason"],
        "additionalProperties": False,
    },
}

_DESCRIPTIONS: dict[str, str] = {
    "get_price_history": "Fetch OHLCV price history for a ticker (yfinance). Returns bars oldest to newest.",
    "compute_indicators": "Compute technical indicators (SMA, RSI, MACD, Bollinger Bands) from OHLCV bars. Pure Python, synchronous.",
    "get_news": "Fetch recent company news headlines (Finnhub / Massive / Alpha Vantage / Bigdata). Returns an empty list with a note if no API key is configured.",
    "get_company_profile": "Resolve a ticker to company metadata via RavenPack Bigdata knowledge graph (name, sector, industry, country, description).",
    "propose_order": "Record a trade proposal for human review. NEVER submits an order to any broker; the returned payload is journaled only.",
    "decide_hold": "Record a decision to hold (no trade). Journaled for later human review.",
}


def as_openai_tools() -> list[dict]:
    """Tool schemas in OpenAI/xAI chat-completions format."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": _DESCRIPTIONS[name],
                "parameters": _PARAMETERS[name],
            },
        }
        for name in TOOL_NAMES
    ]


def as_anthropic_tools() -> list[dict]:
    """Tool schemas in Anthropic tool-use format."""
    return [
        {
            "name": name,
            "description": _DESCRIPTIONS[name],
            "input_schema": _PARAMETERS[name],
        }
        for name in TOOL_NAMES
    ]
