"""البحث الصوتي — one voice layer, injected everywhere, owned by no single page.

The requirement was "the OS supports voice search at every stage". The failure
mode that phrasing invites is a mic added to three screens and forgotten on the
fourth, which is worse than none: people stop trying it. So the layer is
injected in `_serve()`, and these tests assert it reaches every page that
function serves — including pages that do not exist yet.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.catalog import get_connector, get_endpoint
from app.main import app
from app.routers import tools

client = TestClient(app)

VOICE_JS = Path(tools.__file__).resolve().parent.parent.parent / "modules" / "platform" / "voice.js"


def _served_pages() -> list[str]:
    """Every HTML page the platform serves, taken off the catalogue rather than
    off a list kept here — a page added tomorrow is covered without anyone
    remembering to add it.

    Both renderers are represented: `_serve()` (authored module pages) and
    `html_page()` (generated pages like /systems and the library).
    """
    from app import catalog
    pages = [e.path for e in catalog.ENDPOINTS
             if e.kind == "page" and "{" not in e.path and not e.path.endswith(".js")]
    return pages + ["/", "/systems", "/connectors", "/api/v1/ideas"]


def test_there_are_pages_to_check():
    assert len(_served_pages()) >= 8, "the page list parse is wrong, not the pages"


def test_every_served_page_carries_the_voice_layer():
    """Injected in one place, so a new page gets it without a decision."""
    missing = []
    for path in _served_pages():
        body = client.get(path, headers={"Accept": "text/html"}).text
        if "/tools/voice.js" not in body:
            missing.append(path)
    assert not missing, f"pages served without the voice layer: {missing}"


def test_the_layer_is_served_as_javascript():
    r = client.get("/tools/voice.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert "ar-EG" in r.text


def test_the_chat_keeps_its_own_mic_and_the_global_one_stays_out():
    """Two microphones on one screen is worse than either alone."""
    body = client.get("/tools/expert").text
    assert "data-voice-local" in body
    assert "webkitSpeechRecognition" in body


def test_a_page_is_never_given_the_script_twice():
    body = client.get("/tools/platform").text
    assert body.count("/tools/voice.js") == 1


def test_it_dispatches_input_so_live_filters_actually_react():
    """The hub and the ideas board filter on `input`. Setting `.value` alone
    leaves them showing results for text they never saw — which reads as the
    search being broken."""
    js = VOICE_JS.read_text(encoding="utf-8")
    assert 'new Event("input"' in js
    assert "bubbles: true" in js


def test_it_will_not_dictate_into_a_password_field():
    """Saying a secret out loud is not a feature, and it would also land in the
    interim-results caption."""
    js = VOICE_JS.read_text(encoding="utf-8")
    types = re.search(r'var TEXTY = "([^"]+)"', js)
    assert types, "the allow-list is gone — check what replaced it"
    assert "password" not in types.group(1)
    assert "data-no-voice" in js, "no way for a field to opt out"


def test_it_renders_nothing_when_the_browser_cannot_hear():
    """A mic that does nothing when pressed is worse than no mic."""
    js = VOICE_JS.read_text(encoding="utf-8")
    assert re.search(r"if \(!SR \|\|.*\) return;", js)


def test_the_layer_holds_no_secret_and_calls_nobody():
    js = VOICE_JS.read_text(encoding="utf-8")
    assert "__GATEWAY_API_KEY__" not in js
    assert not re.findall(r'fetch\(', js), "the voice layer must not call anything"


def test_voice_is_on_the_map_as_live():
    """It shipped without the external Arabic STT the backlog assumed it needed,
    because the recogniser is the browser's own."""
    c = get_connector("voice")
    assert c.live is True and c.system == "ai"
    assert get_endpoint("/tools/voice.js") is not None
