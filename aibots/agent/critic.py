"""Single bear-case critic pass over the same tool outputs + bull proposal."""

from __future__ import annotations

import json
from typing import Any

CRITIC_SYSTEM = """You are a skeptical risk analyst reviewing a paper-trading proposal.

Rules:
- Argue the strongest possible bear case against the proposed trade (or against complacent hold).
- Be concrete. Cite specific numbers from the tool outputs only.
- Do not invent prices, indicators, headlines, or dates.
- If the tools show thin or missing data, say so — that is itself a bear argument.
- Keep it tight: 1 short paragraph + 3–6 concrete bullet points max.
- This is educational paper trading; never claim certainty of loss or gain.
"""


def build_critic_user_message(
    tool_calls: list[dict[str, Any]],
    bull_proposal: dict[str, Any] | None,
    assistant_text: str = "",
) -> str:
    """Assemble the critic user payload from journal-shaped tool_calls + proposal."""
    # Strip bulky full bar series for the critic context; keep compact research.
    compact_tools = []
    for call in tool_calls:
        entry = {
            "name": call.get("name"),
            "ok": call.get("ok"),
            "args": _compact_args(call.get("name"), call.get("args") or {}),
        }
        if call.get("ok"):
            entry["result"] = _compact_result(call.get("name"), call.get("result"))
        else:
            entry["error"] = call.get("error")
        compact_tools.append(entry)

    payload = {
        "tool_outputs": compact_tools,
        "bull_proposal": bull_proposal,
        "assistant_summary": assistant_text,
    }
    return (
        "Given the exact same tool outputs below and the proposed trade, "
        "argue the strongest possible bear case. Be concrete. Cite specific "
        "numbers from the tools. Do not invent data.\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, default=str)}\n```"
    )


def _compact_args(name: str | None, args: dict[str, Any]) -> dict[str, Any]:
    if name == "compute_indicators" and "bars" in args:
        bars = args.get("bars") or []
        return {
            **{k: v for k, v in args.items() if k != "bars"},
            "bars_count": len(bars) if isinstance(bars, list) else 0,
            "bars_tail": bars[-5:] if isinstance(bars, list) else [],
        }
    return args


def _compact_result(name: str | None, result: Any) -> Any:
    if not isinstance(result, dict):
        return result
    if name == "get_price_history":
        bars = result.get("bars") or []
        return {
            "ticker": result.get("ticker"),
            "source": result.get("source"),
            "cached": result.get("cached"),
            "bars_count": len(bars) if isinstance(bars, list) else 0,
            "bars_tail": bars[-5:] if isinstance(bars, list) else [],
            "last_close": bars[-1].get("close") if isinstance(bars, list) and bars else None,
        }
    return result


async def run_bear_critique(
    *,
    tool_calls: list[dict[str, Any]],
    bull_proposal: dict[str, Any] | None,
    assistant_text: str = "",
    api_key: str,
    model: str | None = None,
    base_url: str | None = None,
) -> str:
    """One extra Grok call that returns the bear-case text (never empty on success)."""
    from openai import AsyncOpenAI

    resolved_base = (base_url or "https://api.x.ai/v1").rstrip("/")
    resolved_model = model or "grok-4-1-fast-non-reasoning"
    client = AsyncOpenAI(api_key=api_key, base_url=resolved_base)

    user_msg = build_critic_user_message(tool_calls, bull_proposal, assistant_text)
    resp = await client.chat.completions.create(
        model=resolved_model,
        messages=[
            {"role": "system", "content": CRITIC_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
    )
    text = (resp.choices[0].message.content or "").strip()
    return text or "(critic returned empty response)"
