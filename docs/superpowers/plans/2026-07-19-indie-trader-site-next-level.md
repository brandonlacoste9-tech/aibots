# Indie Trader Site Next-Level Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a beginner-focused vertical slice: conversion homepage + desk chrome + trust layer on static Netlify HTML, driving first successful desk question via Render API.

**Architecture:** Keep Netlify static `site/*.html` + Render `aibots.api`. No API contract changes. Landing becomes a funnel; desk keeps single-column chat with better chrome, first-run, and cold-start UX. Secrets stay off Netlify.

**Tech Stack:** Static HTML/CSS/JS, Netlify (`netlify.toml`), Render API `https://indie-trader-api.onrender.com`, existing FastAPI chat endpoint.

**Spec:** `docs/superpowers/specs/2026-07-19-indie-trader-site-next-level-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `site/index.html` | Landing funnel: hero, how, safety, preview, footer |
| `site/desk.html` | Desk UI + client JS for chat against public/local API |
| `site/404.html` | Branded not-found |
| `tests/test_site_content.py` | Lightweight content contracts (required ids/copy/CTAs) |
| `README.md` | One-line try-the-desk pointer (optional, Task 6) |
| `netlify.toml` | Unchanged redirects unless broken |

**Do not modify for this plan:** `aibots/api.py` chat contract, agent loop, tool providers (unless a bug blocks smoke).

---

### Task 1: Content contract tests (fail first)

**Files:**
- Create: `tests/test_site_content.py`

These tests lock the activation funnel so redesigns cannot drop critical CTAs or API defaults.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_site_content.py`:

```python
"""Content contracts for Indie Trader static site (vertical slice)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


def _read(name: str) -> str:
    return (SITE / name).read_text(encoding="utf-8")


def test_landing_has_desk_cta_and_sections():
    html = _read("index.html")
    assert 'href="/desk"' in html
    assert 'id="how"' in html
    assert 'id="safety"' in html
    assert "Open desk" in html or "Open market desk" in html
    assert "paper" in html.lower()
    assert "not financial advice" in html.lower() or "Not a broker" in html or "not a broker" in html.lower()


def test_landing_beginner_promise_copy():
    html = _read("index.html")
    # Primary beginner message (allow slight wording variants already in page)
    assert "you still decide" in html.lower() or "you decide" in html.lower()
    assert "paper" in html.lower()


def test_desk_defaults_to_public_render_api():
    html = _read("desk.html")
    assert "indie-trader-api.onrender.com" in html
    assert "PUBLIC_API" in html or "indie-trader-api.onrender.com" in html


def test_desk_has_composer_and_paper_framing():
    html = _read("desk.html")
    assert 'id="form"' in html
    assert 'id="input"' in html
    assert 'id="sendBtn"' in html
    assert "paper" in html.lower()
    assert 'id="thread"' in html


def test_desk_has_beginner_suggestion_chips_source():
    html = _read("desk.html")
    assert "PE ratio" in html or "P/E" in html or "pe ratio" in html.lower()
    assert "SUGGESTIONS" in html
```

- [ ] **Step 2: Run tests to see current baseline**

Run:

```bash
cd C:\Users\north\aibots
.\.venv\Scripts\python.exe -m pytest tests/test_site_content.py -v
```

Expected: Most may PASS already; any FAIL shows gaps to fix in later tasks. If all pass, still proceed — later tasks will extend assertions in Task 5.

- [ ] **Step 3: Commit**

```bash
git add tests/test_site_content.py
git commit -m "test: site content contracts for landing and desk funnel"
```

---

### Task 2: Landing page — nav + hero funnel

**Files:**
- Modify: `site/index.html`

- [ ] **Step 1: Update nav**

In `site/index.html` nav links, use this structure (replace existing `.nav-links` contents):

```html
<div class="nav-links">
  <a href="#how">How it works</a>
  <a href="#safety">Safety</a>
  <a href="/desk" class="btn btn-primary" style="padding: 8px 14px; font-size: 0.9rem">Open desk</a>
</div>
```

Remove competing primary CTAs from nav (GitHub can move to footer only, or stay as muted text link after Desk).

Recommended nav with GitHub muted:

```html
<div class="nav-links">
  <a href="#how">How it works</a>
  <a href="#safety">Safety</a>
  <a href="https://github.com/brandonlacoste9-tech/aibots">GitHub</a>
  <a href="/desk" class="btn btn-primary" style="padding: 8px 14px; font-size: 0.9rem">Open desk</a>
</div>
```

- [ ] **Step 2: Rewrite hero copy and CTAs**

Replace the hero left column content with beginner-focused funnel copy:

```html
<div>
  <div class="pill">
    <span class="dot" aria-hidden="true"></span>
    paper practice · no live orders
  </div>
  <h1>Ask the market. <em>You</em> stay in control.</h1>
  <p class="lead">
    <strong>Indie Trader</strong> is an AI desk for learning the stock market on paper.
    Ask any question — or get a tool-backed take on a ticker.
    The AI can propose ideas; <strong>it never places live orders.</strong>
  </p>
  <div class="actions">
    <a class="btn btn-primary" href="/desk">Open desk</a>
    <a class="btn btn-ghost" href="#how">How it works</a>
  </div>
  <p class="fine">Free to try · Educational · Not a broker · Not financial advice</p>
</div>
```

Keep the right-side preflight mock panel (bull/bear example) — it already teaches the product.

- [ ] **Step 3: Visual check**

Open `site/index.html` in a browser (or via Netlify preview / local API `/`). Confirm:
- One clear primary CTA above the fold
- No `http://127.0.0.1` as the main CTA

- [ ] **Step 4: Commit**

```bash
git add site/index.html
git commit -m "feat(site): beginner hero and nav CTA funnel to desk"
```

---

### Task 3: Landing page — how + safety + sample journal + preview

**Files:**
- Modify: `site/index.html`

- [ ] **Step 1: Control-plane section (`#how`)**

Replace or reshape `#how` so it is three clear cards for beginners (not only a pipeline of tool names):

Required content (structure can match existing `.grid3` / `.card` classes):

1. **Look up real context** — prices, indicators, headlines when needed  
2. **See both sides** — constructive take and risks (bull/bear framing)  
3. **You decide** — paper practice; nothing silent-submits  

Include supporting line:

```html
<p>Ideas can be journaled for review. The desk answers questions; it does not trade your brokerage account.</p>
```

- [ ] **Step 2: Trust section (`#safety`)**

Ensure `id="safety"` section includes four points:

- Paper only  
- No silent fills / no live order submission from this site  
- Market numbers from tools when the desk cites data  
- You stay in control  

Add one **Example only** static sample journal card, e.g.:

```html
<div class="card" style="margin-top: 14px">
  <h3>Example journal entry <span class="pill" style="margin-left: 8px">Example only</span></h3>
  <p class="fine">Illustrative — not live account data.</p>
  <pre style="margin-top: 10px">tools: get_price_history, compute_indicators, get_news
bull: "Trend constructive on paper; small size."
bear: "Extended into resistance; wait for pullback risk."
human_decision: pending</pre>
</div>
```

- [ ] **Step 3: Desk preview section**

Add or rename a section (e.g. `id="preview"`) with non-interactive mock chat:

- User: “What is a PE ratio?”  
- Assistant: one short plain-English answer  
- CTA: `Open desk` → `/desk` with label **Ask your first question**

- [ ] **Step 4: Footer + get started**

- Footer must include not financial advice / not a broker  
- Get started (`#cli`) can remain but **desk CTA first**; CLI secondary for power users  
- Remove “Local desk” as a primary marketing CTA (optional fine-print for developers only)

- [ ] **Step 5: Commit**

```bash
git add site/index.html
git commit -m "feat(site): how/safety/preview sections for beginner trust funnel"
```

---

### Task 4: Desk chrome — first-run, paper badge, welcome, chips

**Files:**
- Modify: `site/desk.html`

- [ ] **Step 1: Top bar paper badge**

In the header next to status, add a visible paper chip:

```html
<span class="pill" style="border:1px solid rgba(61,214,140,.4);color:#3dd68c;font-size:11px;padding:4px 10px;border-radius:999px;text-transform:uppercase;letter-spacing:.04em">Paper</span>
```

(Adapt to existing CSS variables if cleaner.)

- [ ] **Step 2: First-run strip**

Add HTML above `#thread`:

```html
<div id="firstRun" class="first-run" style="display:none;margin:12px 16px 0;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--panel)">
  <p style="margin:0 0 8px;color:var(--muted);font-size:0.92rem">
    Ask anything about stocks — concepts or tickers. Educational paper practice. Never places live orders.
  </p>
  <button type="button" id="firstRunDismiss" class="chip">Got it</button>
</div>
```

Add JS after element refs:

```javascript
const FIRST_RUN_KEY = "indie_trader_first_run_v1";
const firstRun = document.getElementById("firstRun");
const firstRunDismiss = document.getElementById("firstRunDismiss");
if (firstRun && !localStorage.getItem(FIRST_RUN_KEY)) {
  firstRun.style.display = "block";
}
if (firstRunDismiss) {
  firstRunDismiss.onclick = () => {
    localStorage.setItem(FIRST_RUN_KEY, "1");
    firstRun.style.display = "none";
  };
}
```

- [ ] **Step 3: Welcome system message**

Replace the long system `addMsg("system", ...)` string with:

```javascript
addMsg(
  "system",
  "Ask any stock-market question — how things work, or a ticker look. Educational paper practice only. Never places live orders."
);
```

- [ ] **Step 4: Beginner suggestion chips**

Replace `SUGGESTIONS` array with:

```javascript
const SUGGESTIONS = [
  "What moves stock prices day to day?",
  "What is a PE ratio?",
  "Explain RSI simply",
  "How does NVDA look on daily technicals?",
  "What should I paper-trade first?",
  "What is diversification?",
];
```

- [ ] **Step 5: Commit**

```bash
git add site/desk.html
git commit -m "feat(desk): first-run strip, paper badge, beginner chips"
```

---

### Task 5: Desk errors, cold start, content tests green

**Files:**
- Modify: `site/desk.html`
- Modify: `tests/test_site_content.py`

- [ ] **Step 1: Friendlier offline / cold-start errors**

In the chat `catch` block, use message like:

```javascript
addMsg(
  "system",
  "Could not reach the desk API (" +
    (err && err.message ? err.message : String(err)) +
    ").\n\nIf this is the first request in a while, the free API may be waking up — wait 30–60s and try again.\n\nAPI: " +
    getApiBase() +
    mixedContentHint()
);
```

In `ping()` failure path, set status text to something like: `API offline or waking…`

When `fetch` to `/api/chat` is slow, keep existing “Thinking…”; optional: after 8s flip status to `Still working (cold start?)…` via `setTimeout` cleared on response.

Minimal optional timer:

```javascript
let coldTimer = null;
// before fetch:
coldTimer = setTimeout(() => {
  statusText.textContent = "Still working (API may be waking)…";
  dot.className = "dot warn";
}, 8000);
// in finally:
if (coldTimer) clearTimeout(coldTimer);
```

- [ ] **Step 2: Extend content tests for new slice requirements**

Append to `tests/test_site_content.py`:

```python
def test_landing_has_example_journal_or_safety_points():
    html = _read("index.html")
    assert "id=\"safety\"" in html or "id='safety'" in html
    assert "silent" in html.lower() or "live order" in html.lower() or "never" in html.lower()


def test_desk_first_run_hook_present():
    html = _read("desk.html")
    assert "first_run" in html.lower() or "firstRun" in html or "Got it" in html
```

- [ ] **Step 3: Run full relevant tests**

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_site_content.py tests/test_api.py -q
```

Expected: PASS (API tests still green; site contracts green).

- [ ] **Step 4: Commit**

```bash
git add site/desk.html tests/test_site_content.py
git commit -m "feat(desk): cold-start UX and expand site content contracts"
```

---

### Task 6: 404 + README polish

**Files:**
- Modify: `site/404.html`
- Modify: `README.md`

- [ ] **Step 1: Align 404 with brand**

Ensure `site/404.html` says Indie Trader, links to `/` and `/desk`, dark background consistent with site.

Example body:

```html
<p>Page not found.</p>
<p><a href="/">Home</a> · <a href="/desk">Open desk</a></p>
```

- [ ] **Step 2: README try path**

Near the top of `README.md`, ensure a clear line:

```markdown
**Try the desk:** https://spiffy-tiramisu-613b09.netlify.app/desk  
**API:** https://indie-trader-api.onrender.com/health
```

- [ ] **Step 3: Commit**

```bash
git add site/404.html README.md
git commit -m "docs: desk URLs and branded 404"
```

---

### Task 7: Manual production smoke (activation metric)

**Files:** none (verification only)

- [ ] **Step 1: Push if not already on origin**

```bash
git push origin main
```

- [ ] **Step 2: Wait for Netlify deploy** (site linked to `aibots` repo)

Confirm deploy ready for `spiffy-tiramisu-613b09`.

- [ ] **Step 3: Smoke checklist**

1. Open `https://spiffy-tiramisu-613b09.netlify.app/`  
2. Confirm hero **Open desk** goes to `/desk`  
3. On desk, status becomes online (may wait for Render wake)  
4. Send: `What is a PE ratio?` → assistant reply  
5. Send: `How does AAPL look on daily technicals?` → reply; tools line may appear  
6. Dismiss first-run; refresh; strip stays gone  

- [ ] **Step 4: Final commit only if smoke forced copy tweaks**

If copy fixes needed, commit them; otherwise done.

```bash
# only if needed
git add site/
git commit -m "fix(site): smoke-test copy tweaks"
git push origin main
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Beginner landing funnel | 2, 3 |
| Control-plane 3 steps | 3 |
| Trust strip + example journal | 3 |
| Desk preview + CTA | 3 |
| Desk paper badge / first-run | 4 |
| Beginner chips | 4 |
| Public Render API default | already in desk; verified by test Task 1/5 |
| Cold start / error UX | 5 |
| 404 brand | 6 |
| Activation smoke | 7 |
| No API redesign | respected throughout |
| Content contracts | 1, 5 |

## Placeholder scan

No TBD/TODO steps. All steps name files, include copy/code, and commands.

## Type / contract consistency

- Desk API base: `PUBLIC_API = "https://indie-trader-api.onrender.com"`  
- Chat endpoint: `POST {api}/api/chat` with `{ message, history, journal }`  
- First-run key: `indie_trader_first_run_v1`  
- CTA path: `/desk` (Netlify redirect to `desk.html`)

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-19-indie-trader-site-next-level.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — run tasks in this session with checkpoints  

Which approach?
