"""Create/update Indie Trader API on Render using RENDER_API_KEY + .env secrets."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

API = "https://api.render.com/v1"
SERVICE_NAME = "indie-trader-api"
OWNER_ID = os.environ.get("RENDER_OWNER_ID", "tea-d9dllkm1a83c73b0a8p0")
REPO = "https://github.com/brandonlacoste9-tech/aibots"


def _key() -> str:
    key = (os.environ.get("RENDER_API_KEY") or "").strip().strip("'\"")
    if not key:
        raise SystemExit("RENDER_API_KEY missing in .env")
    return key


def req(method: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {_key()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as resp:
            raw = resp.read().decode() or "null"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def find_service() -> dict | None:
    code, data = req("GET", "/services?limit=50")
    if code >= 400:
        raise SystemExit(f"list services failed {code}: {data}")
    for row in data or []:
        svc = row.get("service") or row
        if svc.get("name") == SERVICE_NAME:
            return svc
    return None


def create_service() -> dict:
    payload = {
        "type": "web_service",
        "name": SERVICE_NAME,
        "ownerId": OWNER_ID,
        "repo": REPO,
        "autoDeploy": "yes",
        "branch": "main",
        "serviceDetails": {
            "runtime": "python",
            "plan": "free",
            "region": "oregon",
            "healthCheckPath": "/health",
            "envSpecificDetails": {
                "buildCommand": "pip install -r requirements.txt",
                "startCommand": "uvicorn aibots.api:app --host 0.0.0.0 --port $PORT",
            },
        },
    }
    code, data = req("POST", "/services", payload)
    if code >= 400:
        raise SystemExit(f"create failed {code}: {data}")
    return data.get("service") or data


def put_env_vars(service_id: str) -> None:
    vals = dotenv_values(ROOT / ".env")
    wanted = {
        "XAI_API_KEY": vals.get("XAI_API_KEY") or "",
        "XAI_BASE_URL": vals.get("XAI_BASE_URL") or "https://api.x.ai/v1",
        "XAI_MODEL": vals.get("XAI_MODEL") or "grok-4-1-fast-non-reasoning",
        "MASSIVE_API_KEY": vals.get("MASSIVE_API_KEY") or "",
        "ALPHA_VANTAGE_API_KEY": vals.get("ALPHA_VANTAGE_API_KEY") or "",
        "BIGDATA_API_KEY": vals.get("BIGDATA_API_KEY") or "",
        "FINNHUB_API_KEY": vals.get("FINNHUB_API_KEY") or "",
        "PYTHON_VERSION": "3.11.11",
        "CORS_ORIGINS": (
            "https://spiffy-tiramisu-613b09.netlify.app,"
            "https://indie-trader.com,"
            "https://www.indie-trader.com,"
            "http://localhost:8080,"
            "http://127.0.0.1:8080"
        ),
    }
    body = [
        {"key": k, "value": v}
        for k, v in wanted.items()
        if v is not None
    ]
    code, data = req("PUT", f"/services/{service_id}/env-vars", body)
    if code >= 400:
        raise SystemExit(f"env vars failed {code}: {data}")
    print(f"env vars set: {len(body)} keys (values not printed)")


def trigger_deploy(service_id: str) -> dict:
    code, data = req("POST", f"/services/{service_id}/deploys", {"clearCache": "do_not_clear"})
    if code >= 400:
        raise SystemExit(f"deploy failed {code}: {data}")
    return data


def main() -> int:
    svc = find_service()
    if svc:
        print(f"found existing service id={svc.get('id')}")
    else:
        print("creating service…")
        created = create_service()
        # create response may wrap
        svc = created.get("service") if isinstance(created, dict) and "service" in created else created
        print(f"created id={svc.get('id')}")

    service_id = svc["id"]
    details = svc.get("serviceDetails") or {}
    url = details.get("url") or svc.get("url")
    print(f"service_url={url}")

    put_env_vars(service_id)
    deploy = trigger_deploy(service_id)
    deploy_id = None
    if isinstance(deploy, dict):
        deploy_id = deploy.get("id") or (deploy.get("deploy") or {}).get("id")
    print(f"deploy_triggered id={deploy_id} raw_type={type(deploy).__name__}")

    # poll health if url known
    if url:
        health = url.rstrip("/") + "/health"
        print(f"polling {health} …")
        for i in range(36):
            time.sleep(10)
            try:
                with urllib.request.urlopen(health, timeout=15) as r:
                    body = r.read().decode()
                    print(f"health attempt {i+1}: {body[:200]}")
                    if r.status == 200 and "true" in body:
                        print("READY")
                        print(f"DESK_API={url}")
                        return 0
            except Exception as e:
                print(f"health attempt {i+1}: waiting ({e.__class__.__name__})")
        print("deploy still warming; check Render dashboard")
        print(f"DESK_API={url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
