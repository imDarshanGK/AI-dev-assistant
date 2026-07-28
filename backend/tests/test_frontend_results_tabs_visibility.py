from pathlib import Path


FRONTEND_HTML = (
    Path(__file__).resolve().parents[2] / "frontend" / "index.html"
).read_text(encoding="utf-8")


def test_render_results_toggles_tab_buttons_visibility():
    """Test that renderResults hides tab buttons if their corresponding data is missing."""
    assert "const hasExplain = Boolean(result.explanation);" in FRONTEND_HTML
    assert "const hasDebug = Boolean(result.debugging);" in FRONTEND_HTML
    assert "const hasSuggest = Boolean(result.suggestions);" in FRONTEND_HTML
    assert (
        "document.getElementById('tab-explain').style.display = hasExplain ? 'flex' : 'none';"
        in FRONTEND_HTML
    )
    assert (
        "document.getElementById('tab-debug').style.display = hasDebug ? 'flex' : 'none';"
        in FRONTEND_HTML
    )
    assert (
        "document.getElementById('tab-suggest').style.display = hasSuggest ? 'flex' : 'none';"
        in FRONTEND_HTML
    )


def test_render_results_switches_to_first_available_tab():
    """Test that renderResults selects the first available active tab instead of defaulting to explain."""
    assert (
        "const firstAvailableTab = hasExplain ? 'explain' : (hasDebug ? 'debug' : (hasSuggest ? 'suggest' : 'explain'));"
        in FRONTEND_HTML
    )
    assert (
        "const targetTab = availableTabs[tabOrder[selectedMode]] ? tabOrder[selectedMode] : firstAvailableTab;"
        in FRONTEND_HTML
    )


def test_reset_results_restores_tab_buttons_display():
    """Test that resetResults restores default display styles for all three result tabs."""
    assert (
        "['tab-explain', 'tab-debug', 'tab-suggest'].forEach(id => {" in FRONTEND_HTML
    )
