"""HTTP API for Indie Trader market Q&A desk.

Run locally::

    uvicorn aibots.api:app --host 0.0.0.0 --port 8080

Environment:
  XAI_API_KEY (required for chat)
  XAI_MODEL, XAI_BASE_URL (optional)
  CORS_ORIGINS — comma-separated (default: localhost + Netlify + indie-trader.com)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from aibots import __version__
from aibots.agent.market_chat import run_market_chat
from aibots.journal import append_entry

try:
    from dotenv import load_dotenv

    for _candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[1] / ".env"):
        if _candidate.is_file():
            load_dotenv(_candidate, override=False)
            break
except ImportError:
    pass

DEFAULT_CORS = (
    "http://localhost:3000,"
    "http://localhost:8080,"
    "http://127.0.0.1:5500,"
    "http://127.0.0.1:8080,"
    "https://spiffy-tiramisu-613b09.netlify.app,"
    "https://indie-trader.com,"
    "https://www.indie-trader.com"
)


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS") or DEFAULT_CORS
    return [o.strip() for o in raw.split(",") if o.strip()]


app = FastAPI(
    title="Indie Trader API",
    description="Stock market Q&A desk. Researches and explains — never submits orders.",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    history: list[ChatMessage] = Field(default_factory=list)
    journal: bool = Field(
        default=True,
        description="Append the turn to the JSONL journal when true.",
    )


class ChatResponse(BaseModel):
    assistant_text: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    model: str | None = None
    history: list[dict[str, str]] = Field(default_factory=list)
    journal_id: str | None = None
    mode: str = "market_chat"


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "indie-trader",
        "version": __version__,
        "llm_configured": bool(os.environ.get("XAI_API_KEY")),
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        raise HTTPException(
            503,
            "XAI_API_KEY is not configured on the API host.",
        )
    try:
        result = await run_market_chat(
            body.message,
            api_key=api_key,
            history=[m.model_dump() for m in body.history],
            model=os.environ.get("XAI_MODEL") or None,
            base_url=os.environ.get("XAI_BASE_URL") or None,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Market chat failed: {exc}") from exc

    journal_id = None
    if body.journal:
        stored = append_entry(
            {
                "mode": "market_chat",
                "user_message": body.message,
                "assistant_text": result["assistant_text"],
                "tool_calls": result.get("tool_calls") or [],
                "model": result.get("model"),
                "human_decision": None,
                "decided_at": None,
            }
        )
        journal_id = stored.get("id")

    return ChatResponse(
        assistant_text=result["assistant_text"],
        tool_calls=result.get("tool_calls") or [],
        model=result.get("model"),
        history=result.get("history") or [],
        journal_id=journal_id,
        mode="market_chat",
    )


@app.get("/api/chat")
async def chat_get_hint() -> dict[str, str]:
    return {
        "hint": "POST JSON { message, history? } to this path from the desk UI.",
    }
