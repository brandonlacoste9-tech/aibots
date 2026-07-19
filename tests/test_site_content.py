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
