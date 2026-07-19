# Indie Trader website — next-level vertical slice

**Date:** 2026-07-19  
**Status:** Implemented (vertical slice shipped on main; Netlify redeploy from push)  
**Product:** Indie Trader (`brandonlacoste9-tech/aibots`)  
**Primary metric:** Visitor opens the desk and successfully asks a first market question  

---

## 1. Problem

The product brain (forced research, market chat, tools, Render API) is ahead of the website. The current static site is clear but thin: marketing and desk feel like two engineer pages, not a beginner-ready funnel from “what is this?” → “I asked my first question.”

## 2. Goals

### In scope (this slice)

A **thin vertical slice** of three pillars, optimized for **retail beginners**:

1. **Conversion landing** — Premium-feeling homepage that sells the control-plane story and drives **Open desk**.
2. **Product desk chrome** — Desk feels like a real (simple) app shell: status, paper badge, beginner first-run, better empty/error states.
3. **Trust layer** — Paper-only, no silent orders, tool-backed numbers, human gate — without a legal CMS.

### Success

A new visitor can:

1. Land on `/`
2. Understand in ~30 seconds: AI proposes, human decides, paper only
3. Click **Open desk**
4. Send a first question and receive an assistant reply via the public Render API

### Out of scope (explicit)

- Auth / signup / billing  
- Full multi-panel trading terminal (watchlist, charts, blotter)  
- Wiring bull/bear preflight into tradingbot control plane  
- Domain DNS for `indie-trader.com`  
- Next.js / Vite rewrite  
- Live brokerage connections  
- Fake testimonials or guaranteed-return marketing  
- Full legal suite (privacy/terms beyond footer disclaimer)  
- Playwright E2E suite (optional later)

## 3. Constraints

| Constraint | Choice |
|------------|--------|
| Audience | Retail beginners (copy tilts simple) |
| Stack | Static HTML on Netlify + Render API (`aibots.api`) |
| Files | Primarily `site/index.html`, `site/desk.html`, `site/404.html` |
| API | Keep `POST /api/chat` contract; no backend redesign required |
| Secrets | Never on Netlify; Render / local `.env` only |
| Brand | Extend existing dark terminal system (IBM Plex, accent/good/bad) |

## 4. Approaches considered

| Approach | Summary | Decision |
|----------|---------|----------|
| 1. Story strip landing + light desk chrome | Funnel + thin trust + desk polish | **Chosen** |
| 2. Split-screen desk first | App-heavy, marketing light | Deferred (weaker activation) |
| 3. Long-form trust site | Deep content, desk unchanged | Deferred (weaker activation) |

## 5. Information architecture

### Surfaces

| Surface | Path | Host | Role |
|---------|------|------|------|
| Landing | `/` → `index.html` | Netlify | Funnel + trust |
| Desk | `/desk` → `desk.html` | Netlify | First question |
| API | `https://indie-trader-api.onrender.com` | Render | Chat + tools |

Local same-origin desk (`http://127.0.0.1:8080/desk`) remains supported for development.

### Landing scroll order

1. Nav (logo, How it works, Safety, Desk primary)  
2. Hero + CTAs  
3. Control-plane 3 steps (`#how`)  
4. Trust strip (`#safety`)  
5. Desk preview mock + CTA  
6. Get started (desk primary; CLI secondary)  
7. Footer disclaimer  

### Desk regions

1. Top bar (brand, status, paper badge, Home)  
2. Dismissible first-run strip (`localStorage`)  
3. Message thread  
4. Suggestion chips  
5. Composer  
6. Collapsed API settings (power users)  

## 6. Homepage design

### Voice

- Plain, calm, confident  
- No guaranteed profits; no casino energy  
- Primary message: **Ask anything about the stock market. The AI proposes — you decide. Paper only.**

### Visual system

- Dark background (`#070b10`), panels, line borders  
- Accent blue, good green, bad red, gold for TTL-style accents  
- Larger type and more spacing than current dense layout  
- Soft radial hero glows only  

### Sections

**Hero**

- Badge: paper practice · no live orders  
- H1 + short subcopy for beginners  
- Primary CTA: Open desk → `/desk`  
- Secondary CTA: How it works → `#how`  
- Microcopy: Free to try · Educational · Not a broker  

**Control plane (`#how`)**

Three cards:

1. Forced tools (price, indicators, news when needed)  
2. Bull + bear style balance (desk Q&A + future research framing)  
3. Human confirm / paper only  

Supporting line: proposals/journal mindset; nothing silent-submits.

**Trust (`#safety`)**

Four points:

- Paper only  
- No silent fills  
- Numbers from tools when citing markets  
- You approve real trading decisions (desk is Q&A; research path journals)  

One **Example only** static sample journal card (illustrative, not live data).

**Desk preview**

Non-interactive mock conversation (e.g. PE ratio Q&A) + CTA **Ask your first question**.

**Footer**

Indie Trader, GitHub engine link, not financial advice.

## 7. Desk design

### Goal

First question within ~10 seconds of landing on `/desk`.

### API defaults

| Host | Default API base |
|------|------------------|
| Netlify / HTTPS marketing | `https://indie-trader-api.onrender.com` |
| Localhost desk from API | Same origin |
| Override | `?api=` or API settings UI |

Ignore stale `localStorage` values that point at `http://` when the page is HTTPS.

### UI behavior

**Top bar:** brand, connection status pill, PAPER badge, Home.  

**First-run strip:** dismissible once; safety + what to ask.  

**Welcome message:** short; no deploy ops dump unless offline.  

**Chips (beginner-first examples):**

- What moves stock prices?  
- What is a PE ratio?  
- Explain RSI simply  
- How does NVDA look on daily technicals?  
- What should I paper-trade first?  
- (Optional sixth conceptual chip)  

**Messages:** You / Indie Trader labels; optional collapsed tools line; loading and friendly errors.  

**Render cold start:** “Waking the desk…” + retry guidance.  

**Composer:** Enter to send; Shift+Enter newline; large mobile targets.

### Out of scope on desk

Watchlist, charts, auth, journal browser UI, preflight modal, multi-column research layout.

## 8. Trust content rules

| Do | Don't |
|----|--------|
| Paper / educational framing | Imply live brokerage |
| Tool-backed numbers language | Invent live portfolio balances |
| Human control story | “Set and forget auto-trading” |
| Label examples as Example only | Fake user testimonials |

## 9. Technical design

### Data flow

```
Browser (desk.html)
  → POST { message, history, journal } /api/chat
  → Render aibots.api
  → run_market_chat (Grok + optional tools)
  → JSON { assistant_text, tool_calls, history, ... }
  → Render thread
```

### Implementation touchpoints

| File | Change |
|------|--------|
| `site/index.html` | Restructure/copy/layout per §6 |
| `site/desk.html` | Chrome, first-run, chips, errors, API defaults per §7 |
| `site/404.html` | Brand alignment |
| `netlify.toml` | Keep `/desk` → `desk.html`; no secrets |
| `README.md` | Optional one-line “try the desk” |

No required changes to `aibots/api.py` contract for this slice. Optional later: longer timeout messaging only on client.

### Error matrix

| Case | UX |
|------|-----|
| Network / cold start timeout | Status warn + “Waking the desk…” / retry |
| HTTP 503 LLM missing | Desk misconfigured (ops) |
| HTTP 502 model/tool failure | Couldn’t answer — try again |
| Offline | Red status pill + short message |

### Testing

- Manual checklist:  
  1. `/` hero CTA → `/desk`  
  2. Status shows API online (or waking then online)  
  3. Conceptual question returns answer  
  4. Ticker technical question may show tools line  
  5. First-run dismiss persists across refresh  
- CI: existing Python tests remain green (no API break)  
- Automated browser E2E: not required for this slice  

### Deploy

- Push to `main` → Netlify rebuilds static site  
- Render auto-deploys API from repo when server code changes (this slice is mostly static)  
- Free Render sleep: document in desk empty/error copy  

## 10. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Render cold start feels broken | Explicit waking copy + retry |
| Beginners fear auto-trading | PAPER badge + first-run + trust strip |
| Scope creep into full terminal | Out-of-scope list enforced |
| Mixed content regressions | HTTPS pages default to HTTPS API only |

## 11. Rollout

1. Implement static HTML changes on a branch or `main`  
2. Verify locally against public API and local API  
3. Push → Netlify  
4. Smoke production desk on Netlify  
5. Measure qualitatively: first-question completion  

## 12. Future (not this slice)

- Full app shell: watchlist, journal browser, research preflight  
- Auth and multi-tenant journals  
- tradingbot AI Desk integration (bull/bear modal)  
- Framework migration if static HTML becomes limiting  
- Custom domain DNS for `indie-trader.com`  

---

## Decision log

| Decision | Choice |
|----------|--------|
| Scope shape | Hybrid vertical slice (marketing + desk + trust) |
| Audience | Retail beginners |
| Stack | Static Netlify + Render API |
| Primary metric | First desk question answered |
| Approach | Story strip landing + light desk chrome |
