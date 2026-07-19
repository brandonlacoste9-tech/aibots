"""RavenPack Bigdata.com client (bd_v2_ API keys).

Env: BIGDATA_API_KEY

Uses the official ``bigdata-client`` SDK when installed.
Knowledge-graph company resolution works on typical free/trial keys.
Full content search (news chunks) may return 403 depending on plan.
"""

from __future__ import annotations

import os
from typing import Any

def api_key() -> str | None:
    key = (os.environ.get("BIGDATA_API_KEY") or "").strip()
    return key or None


def is_configured() -> bool:
    return bool(api_key())


def _client():
    key = api_key()
    if not key:
        raise RuntimeError("BIGDATA_API_KEY not configured")
    try:
        from bigdata_client import Bigdata
    except ImportError as exc:
        raise RuntimeError(
            "bigdata-client is not installed. pip install bigdata-client"
        ) from exc
    return Bigdata(api_key=key)


def _company_to_dict(company: Any) -> dict[str, Any]:
    return {
        "entity_id": getattr(company, "id", None),
        "name": getattr(company, "name", None),
        "ticker": getattr(company, "ticker", None),
        "description": getattr(company, "description", None),
        "sector": getattr(company, "sector", None),
        "industry": getattr(company, "industry", None),
        "industry_group": getattr(company, "industry_group", None),
        "country": getattr(company, "country", None),
        "company_type": getattr(company, "company_type", None),
        "webpage": getattr(company, "webpage", None),
        "source": "bigdata",
    }


async def resolve_company(ticker: str) -> dict[str, Any]:
    """Resolve a ticker to a Bigdata company entity (knowledge graph)."""
    import asyncio

    ticker = (ticker or "").strip().upper()
    if not ticker:
        raise ValueError("ticker must be a non-empty string")

    def _sync() -> dict[str, Any]:
        bd = _client()
        # Prefer exact ticker match from autosuggest
        for hit in bd.knowledge_graph.autosuggest(ticker, limit=10):
            if str(getattr(hit, "ticker", "") or "").upper() == ticker:
                return _company_to_dict(hit)
        # Fallback: find_companies by ticker text
        try:
            found = bd.knowledge_graph.find_companies(ticker, limit=5) or []
        except Exception:
            found = []
        for hit in found:
            if str(getattr(hit, "ticker", "") or "").upper() == ticker:
                return _company_to_dict(hit)
        if found:
            return _company_to_dict(found[0])
        raise ValueError(f"no Bigdata company for ticker {ticker}")

    return await asyncio.to_thread(_sync)


async def get_company_profile(ticker: str) -> dict[str, Any]:
    """Public tool shape: company fundamentals metadata from Bigdata KG."""
    return await resolve_company(ticker)


async def get_news(ticker: str, limit: int = 10) -> dict[str, Any]:
    """Attempt content search for company news; degrades cleanly on plan limits."""
    import asyncio

    ticker = (ticker or "").strip().upper()
    if not ticker:
        raise ValueError("ticker must be a non-empty string")
    limit = max(1, min(int(limit), 25))

    def _sync() -> dict[str, Any]:
        from bigdata_client.daterange import RollingDateRange
        from bigdata_client.models.advanced_search_query import Entity
        from bigdata_client.models.search import DocumentType, SortBy

        bd = _client()
        company = None
        for hit in bd.knowledge_graph.autosuggest(ticker, limit=10):
            if str(getattr(hit, "ticker", "") or "").upper() == ticker:
                company = hit
                break
        if company is None:
            return {
                "ticker": ticker,
                "items": [],
                "source": "bigdata",
                "note": f"no Bigdata entity for {ticker}",
            }

        try:
            search = bd.search.new(
                Entity(company.id),
                date_range=RollingDateRange.LAST_SEVEN_DAYS,
                sortby=SortBy.DATE,
                scope=DocumentType.ALL,
            )
            docs = search.run(limit=limit)
        except Exception as exc:  # plan / network
            return {
                "ticker": ticker,
                "items": [],
                "source": "bigdata",
                "note": f"bigdata content search unavailable: {exc}",
            }

        items = []
        for doc in docs or []:
            headline = (
                getattr(doc, "headline", None)
                or getattr(doc, "title", None)
                or getattr(doc, "headline_text", None)
                or ""
            )
            headline = str(headline).strip()
            if not headline:
                # sometimes first chunk text
                text = str(getattr(doc, "text", "") or "").strip()
                headline = text[:180] if text else ""
            if not headline:
                continue
            items.append(
                {
                    "headline": headline,
                    "datetime": str(
                        getattr(doc, "timestamp", None)
                        or getattr(doc, "ts", None)
                        or getattr(doc, "date", None)
                        or ""
                    ),
                    "source": str(
                        getattr(doc, "source", None)
                        or getattr(doc, "provider", None)
                        or "bigdata"
                    ),
                    "url": str(getattr(doc, "url", None) or getattr(doc, "link", None) or ""),
                }
            )
        out: dict[str, Any] = {
            "ticker": ticker,
            "items": items,
            "source": "bigdata",
            "entity_id": getattr(company, "id", None),
        }
        if not items:
            out["note"] = f"no Bigdata documents for {ticker}"
        return out

    return await asyncio.to_thread(_sync)
