# Desk / preflight integration contract

`aibots` is the research brain only. The control plane (tradingbot) owns policy, TTL, confirm UI, and order submit.

## Freeform market Q&A (any question)

```bash
python -m aibots serve --port 8080
# Web UI: site/desk.html or /desk on Netlify → set API base URL
```

```python
from aibots.agent.market_chat import run_market_chat

out = await run_market_chat(
    "Why do rate cuts move growth stocks?",
    api_key=os.environ["XAI_API_KEY"],
    history=[...],  # optional multi-turn
)
# out["assistant_text"], out["tool_calls"], out["history"]
```

HTTP: `POST /api/chat` with `{ "message": "...", "history": [] }`.

## Call from control plane (paper proposal)

```python
import os
from aibots.preflight import research_for_desk

preflight = await research_for_desk(
    "Research AAPL and propose a paper trade or hold.",
    api_key=os.environ["XAI_API_KEY"],
    with_critic=True,
    ttl_seconds=180,
)
# preflight is modal-ready; journal entry already appended
```

Or stepwise:

```python
from aibots.agent.loop import run_research_turn
from aibots.journal import append_entry
from aibots.preflight import to_preflight_payload

entry = await run_research_turn(
    "Research AAPL and propose a paper trade or hold.",
    api_key=os.environ["XAI_API_KEY"],
    with_critic=True,
)
stored = append_entry(entry)
preflight = to_preflight_payload(stored, ttl_seconds=180)
```

## Preflight payload shape

```ts
{
  journal_id: string;
  symbol: string;
  side: "buy" | "sell" | "hold";
  qty?: number;
  order_type?: "limit" | "market";
  limit_price?: number;
  ttl_seconds: number;

  bull: {
    text: string;
    order?: Record<string, unknown> | null;
  };
  bear: {
    text: string;
  };
  tools: {
    price?: unknown;
    indicators?: unknown;
    news?: unknown;
  };

  // pass-through for policy engine / modal
  assistant_text?: string;
  human_decision: null;
  decided_at: null;
}
```

UI: **Bull** and **Bear** side-by-side. Human clicks Confirm / Reject / Edit.

## After human action

```python
from aibots.journal import set_human_decision

set_human_decision(preflight["journal_id"], "confirm")  # or reject | edit | expired
# optional notes=
```

Control plane still runs its own policy re-check + paper submit path.  
`set_human_decision` only closes the **research journal** loop — it never submits orders.
