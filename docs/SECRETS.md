# Secrets hygiene

## Never

- Paste Netlify PATs, API keys, or Clerk secrets into chat, commits, or screenshots.
- Commit `.env`, `.env.local`, or live keys.
- Reuse a token after it has been exposed in a transcript.

## Netlify personal access token (if leaked)

1. Netlify → User settings → Applications → Personal access tokens  
2. **Delete / revoke** the exposed token immediately  
3. Create a new token only if needed  
4. Store only as:
   - local env: `$env:NETLIFY_AUTH_TOKEN = "..."` (session only), or  
   - CI secret: `NETLIFY_AUTH_TOKEN`  
5. Prefer `netlify login` over long-lived PATs when possible  

## App secrets (research brain)

| Secret | Where |
|--------|--------|
| `XAI_API_KEY` | Local `.env` / API host (Render etc.) — **not** Netlify static site |
| `FINNHUB_API_KEY` | Optional news; same host as above |
| `ALPHA_VANTAGE_API_KEY` | Optional news fallback + quotes; free tier is rate-limited |
| `MASSIVE_API_KEY` | Optional Massive/Polygon news + prev-close |
| `MASSIVE_BASE_URL` | Optional; default `https://api.polygon.io` |
| `BIGDATA_API_KEY` | Optional RavenPack Bigdata (`bd_v2_…`) company KG / news |
| `AIBOTS_JOURNAL_PATH` | Optional path; no secret |

If a key was pasted into chat, treat it as exposed: rotate at the provider when practical.
Marketing site on Netlify is static HTML only — **no** LLM keys required there.

## Repo guards

- `.env` / `.env.*` gitignored (`.env.example` kept)
- `journal.jsonl` gitignored
- `.venv/` gitignored
