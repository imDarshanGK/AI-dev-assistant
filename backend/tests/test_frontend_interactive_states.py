from pathlib import Path

import pytest

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
FRONTEND_HTML = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
STYLE_CSS = (FRONTEND_DIR / "style.css").read_text(encoding="utf-8")
SCRIPT_JS = (FRONTEND_DIR / "script.js").read_text(encoding="utf-8")

INLINE_CSS = FRONTEND_HTML.split("<style>", 1)[1].split("</style>", 1)[0]

STYLESHEETS = pytest.mark.parametrize(
    "css", [INLINE_CSS, STYLE_CSS], ids=["index.html", "style.css"]
)


@STYLESHEETS
def test_disabled_state_covers_native_and_aria_disabled_controls(css):
    assert "button:disabled," in css
    assert '[aria-disabled="true"]' in css
    assert "cursor: not-allowed;" in css


@STYLESHEETS
def test_disabled_controls_do_not_animate_on_hover(css):
    assert "button:disabled:hover" in css


@STYLESHEETS
def test_form_controls_have_visible_focus_state(css):
    assert "input:focus-visible," in css
    assert "select:focus-visible," in css
    assert "textarea:focus-visible" in css


@STYLESHEETS
def test_loading_state_uses_aria_busy(css):
    assert '[aria-busy="true"]' in css
    assert "cursor: progress;" in css


@STYLESHEETS
def test_state_animations_respect_reduced_motion(css):
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_analyze_button_announces_busy_state():
    assert "analyzeBtn.setAttribute('aria-busy', 'true');" in FRONTEND_HTML
    assert "analyzeBtn.removeAttribute('aria-busy');" in FRONTEND_HTML


def test_run_button_announces_busy_state():
    assert "runBtn.setAttribute('aria-busy', 'true');" in SCRIPT_JS
    assert "runBtn.removeAttribute('aria-busy');" in SCRIPT_JS


def test_digest_button_announces_busy_state():
    assert (
        "btn.disabled = true;\n        btn.setAttribute('aria-busy', 'true');"
        in FRONTEND_HTML
    )
    assert (
        "btn.disabled = false;\n          btn.removeAttribute('aria-busy');"
        in FRONTEND_HTML
    )
    assert "digestBtn.setAttribute('aria-busy', 'true');" in SCRIPT_JS
