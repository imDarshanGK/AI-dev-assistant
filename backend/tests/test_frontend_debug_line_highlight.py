from pathlib import Path


FRONTEND_HTML = (
    Path(__file__).resolve().parents[2] / "frontend" / "index.html"
).read_text(encoding="utf-8")


def test_frontend_exposes_editor_line_highlight_shell():
    assert 'id="editorLineHighlight"' in FRONTEND_HTML
    assert "const editorLineHighlight = document.getElementById('editorLineHighlight');" in FRONTEND_HTML


def test_update_editor_marks_the_active_debug_line_number():
    assert "const active = line === activeDebugLine ? ' active' : '';" in FRONTEND_HTML
    assert 'return `<span class="line-number${active}" data-line-number="${line}">${line}</span>`;' in FRONTEND_HTML
    assert "syncEditorLineHighlight();" in FRONTEND_HTML


def test_jump_to_line_selects_and_focuses_the_requested_editor_line():
    assert "function jumpToLine(lineNumber) {" in FRONTEND_HTML
    assert "activeDebugLine = safeLine;" in FRONTEND_HTML
    assert "document.querySelector('[data-rtab=\"debug\"]')?.click();" in FRONTEND_HTML
    assert "editor.setSelectionRange(lineStart, lineEnd || lineStart);" in FRONTEND_HTML


def test_debug_issue_cards_wire_click_and_keyboard_navigation_to_jump_helper():
    assert '`data-line=\"${issue.line}\" role=\"button\" aria-label=\"Jump to line ${issue.line}\"`' in FRONTEND_HTML
    assert "el.querySelectorAll('.issue-card[data-line]').forEach((card) => {" in FRONTEND_HTML
    assert "card.addEventListener('click', () => jumpToLine(card.dataset.line));" in FRONTEND_HTML
    assert "if (event.key === 'Enter' || event.key === ' ') {" in FRONTEND_HTML


def test_reset_results_clears_any_active_debug_line_state():
    assert "activeDebugLine = null;" in FRONTEND_HTML
    assert "syncEditorLineHighlight();" in FRONTEND_HTML
