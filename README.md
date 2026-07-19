# aibots

Research brain for a paper-trading desk: **proposes**, never submits orders.

**Docs site (Netlify):** https://spiffy-tiramisu-613b09.netlify.app  
(Static landing page only — the research loop runs via CLI/API, not in the browser.)

Standalone library you can wire into [tradingbot](https://github.com/brandonlacoste9-tech/tradingbot) (or any control plane) later. Control plane stays external: LLM proposes → policy gate → human confirm → journal.

## What it does

1. **Forced research tools** (always run before any proposal)
   - `get_price_history` — yfinance OHLCV with TTL cache + one retry
   - `compute_indicators` — pure-Python SMA / RSI / MACD / Bollinger (server-side only)
   - `get_news` — Finnhub company-news (degrades cleanly without a key)
2. **Proposal tools** (journaled only)
   - `propose_order` / `decide_hold` — `submitted: false` always
3. **Bear-case critic** — one extra Grok call on the same tool outputs
4. **JSONL journal** — every tool output, bull proposal, and bear critique side by side

## Install

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env   # set XAI_API_KEY; optional FINNHUB_API_KEY
```

## CLI

```bash
# Full research turn (tools → proposal → critic → journal)
python -m aibots research AAPL

# Skip critic
python -m aibots research AAPL --no-critic

# Indicator table only (no LLM)
python -m aibots indicators AAPL --period 6mo

# Read journal
python -m aibots journal --limit 10
```

## Journal entry shape

```json
{
  "id": "...",
  "ts": "...",
  "user_message": "...",
  "assistant_text": "...",
  "tool_calls": [
    {"name": "get_price_history", "args": {}, "ok": true, "result": {}},
    {"name": "compute_indicators", "args": {}, "ok": true, "result": {}},
    {"name": "get_news", "args": {}, "ok": true, "result": {}},
    {"name": "propose_order", "args": {}, "ok": true, "result": {}}
  ],
  "bull_proposal": {"text": "...", "order": {"symbol": "AAPL", "side": "buy", "...": "..."}},
  "bear_critique": "...",
  "human_decision": null,
  "decided_at": null
}
```

`human_decision` is filled downstream by your control plane (preflight modal), not by this library.

## Library usage

```python
import asyncio
from aibots.agent.loop import run_research_turn
from aibots.journal import append_entry

async def main():
    entry = await run_research_turn(
        "Research AAPL. Propose a paper trade or hold.",
        api_key="...",
        with_critic=True,
    )
    append_entry(entry)

asyncio.run(main())
```

## Design choices

| Choice | Why |
|--------|-----|
| Forced tools before propose | Numbers are auditable; LLM cannot skip market data |
| Indicators computed server-side | Never let the model invent RSI/MACD |
| Pure Python indicators | No pandas-ta dependency; deterministic tests |
| Finnhub optional | Small watchlist; degrades without key |
| Single critic pass | High ROI vs multi-agent debate cost/latency |
| No Streamlit/Gradio | Conversational UI lives on the existing AI Desk |

## Tests

```bash
pytest -q
```

All network and LLM boundaries are mocked in unit tests.
