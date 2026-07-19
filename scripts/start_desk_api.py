"""Start the Indie Trader desk API with .env loaded.

Usage (from repo root)::

    .venv\\Scripts\\python.exe scripts/start_desk_api.py
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

import uvicorn  # noqa: E402


if __name__ == "__main__":
    uvicorn.run("aibots.api:app", host="127.0.0.1", port=8080, reload=False)
