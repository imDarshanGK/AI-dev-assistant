from pathlib import Path


FRONTEND_HTML = (
    Path(__file__).resolve().parents[2] / "frontend" / "index.html"
).read_text(encoding="utf-8")


def test_render_markdown_escapes_html_before_formatting():
    assert "function renderMarkdown(s) {" in FRONTEND_HTML
    assert "return escHtml(s ?? '')" in FRONTEND_HTML


def test_debug_issue_cards_escape_dynamic_fields():
    assert "sanitizeToken(issue.severity, 'info')" in FRONTEND_HTML
    assert "${escHtml(issue.severity)}" in FRONTEND_HTML
    assert "${escHtml(issue.type)}" in FRONTEND_HTML
    assert "${renderMarkdown(issue.description)}" in FRONTEND_HTML
    assert "${renderMarkdown(issue.suggestion)}" in FRONTEND_HTML


def test_suggestion_cards_escape_dynamic_fields():
    assert "sanitizeToken(s.priority, 'medium')" in FRONTEND_HTML
    assert "${escHtml(s.category)}" in FRONTEND_HTML
    assert "getTranslation('suggest_priority').replace('{priority}', escHtml(s.priority))" in FRONTEND_HTML
    assert "${renderMarkdown(s.description)}" in FRONTEND_HTML


def test_explain_summary_and_meta_escape_user_controlled_values():
    assert "${renderMarkdown(exp.summary)}" in FRONTEND_HTML
    assert "${escHtml(exp.language)}" in FRONTEND_HTML
    assert "${getTranslation('meta_lines').replace('{count}', escHtml(exp.line_count))}" in FRONTEND_HTML
    assert "${getTranslation('meta_functions').replace('{count}', escHtml(exp.function_count))}" in FRONTEND_HTML
