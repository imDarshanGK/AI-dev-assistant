from pathlib import Path


FRONTEND_HTML = (
    Path(__file__).resolve().parents[2] / "frontend" / "index.html"
).read_text(encoding="utf-8")


def test_render_markdown_escapes_before_inserting_formatting_markup():
    assert "function renderMarkdown(s) {" in FRONTEND_HTML
    assert "return escHtml(s ?? '')" in FRONTEND_HTML


def test_explain_renderer_escapes_dynamic_fields_and_sanitizes_css_tokens():
    assert "${renderMarkdown(exp.summary)}" in FRONTEND_HTML
    assert 'complexity-${sanitizeToken(exp.complexity, \'unknown\')}' in FRONTEND_HTML
    assert "${escHtml(exp.complexity)}" in FRONTEND_HTML
    assert "${escHtml(exp.language)}" in FRONTEND_HTML
    assert "risk-${sanitizeToken(exp.complexity_risk || 'Simple', 'simple')}" in FRONTEND_HTML


def test_debug_renderer_escapes_shared_issue_fields():
    assert "${sanitizeToken(issue.severity, 'info')}" in FRONTEND_HTML
    assert "${escHtml(issue.severity)}" in FRONTEND_HTML
    assert "${escHtml(issue.type)}" in FRONTEND_HTML
    assert "${renderMarkdown(issue.description)}" in FRONTEND_HTML
    assert "${renderMarkdown(issue.suggestion)}" in FRONTEND_HTML


def test_suggestion_renderer_escapes_dynamic_fields():
    assert "${sanitizeToken(s.priority, 'medium')}" in FRONTEND_HTML
    assert "${escHtml(s.category)}" in FRONTEND_HTML
    assert "${escHtml(s.priority)} priority" in FRONTEND_HTML
    assert "${renderMarkdown(s.description)}" in FRONTEND_HTML
    assert "${renderMarkdown(sugg.next_step)}" in FRONTEND_HTML
