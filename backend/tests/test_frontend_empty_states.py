from pathlib import Path


FRONTEND_HTML = (
    Path(__file__).resolve().parents[2] / "frontend" / "index.html"
).read_text(encoding="utf-8")


def test_frontend_defines_empty_state_shells_for_all_result_tabs():
    assert 'id="emptyExplain"' in FRONTEND_HTML
    assert 'id="emptyDebug"' in FRONTEND_HTML
    assert 'id="emptySuggest"' in FRONTEND_HTML


def test_render_results_syncs_each_tab_with_empty_state_helper():
    assert "setResultPaneState('explain', Boolean(result.explanation));" in FRONTEND_HTML
    assert "setResultPaneState('debug', Boolean(result.debugging));" in FRONTEND_HTML
    assert "setResultPaneState('suggest', Boolean(result.suggestions));" in FRONTEND_HTML


def test_empty_state_helper_restores_placeholder_when_result_data_is_missing():
    assert "function setResultPaneState(kind, hasData) {" in FRONTEND_HTML
    assert "emptyState.style.display = 'flex';" in FRONTEND_HTML
    assert "resultPane.style.display = 'none';" in FRONTEND_HTML
    assert "resultPane.innerHTML = '';" in FRONTEND_HTML
    assert "if (badge) badge.textContent = '';" in FRONTEND_HTML


def test_loading_and_reset_paths_keep_empty_states_in_sync():
    assert "function showShimmers() {" in FRONTEND_HTML
    assert "['emptyExplain', 'emptyDebug', 'emptySuggest'].forEach(id => {" in FRONTEND_HTML
    assert "function resetResults() {" in FRONTEND_HTML
