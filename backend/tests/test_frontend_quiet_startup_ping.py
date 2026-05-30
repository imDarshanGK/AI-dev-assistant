from pathlib import Path


FRONTEND_HTML = (
    Path(__file__).resolve().parents[2] / "frontend" / "index.html"
).read_text(encoding="utf-8")


def test_ping_api_defaults_to_quiet_mode():
    assert "async function pingApi({ notify = false } = {}) {" in FRONTEND_HTML
    assert "setTimeout(pingApi, 800);" in FRONTEND_HTML


def test_manual_ping_button_enables_notifications():
    assert "const pingBtn = document.getElementById('pingBtn');" in FRONTEND_HTML
    assert "if (pingBtn) pingBtn.addEventListener('click', () => pingApi({ notify: true }));" in FRONTEND_HTML


def test_success_toast_only_fires_for_manual_ping():
    assert "if (notify) {" in FRONTEND_HTML
    assert "toast(getTranslation('toast_api_reachable'), 'success');" in FRONTEND_HTML


def test_unreachable_toast_only_fires_for_manual_ping():
    assert "toast(getTranslation('toast_api_unreachable'), 'error');" in FRONTEND_HTML
    assert "apiStatusText.dataset.status = 'unreachable';" in FRONTEND_HTML
    assert "syncApiStatusText();" in FRONTEND_HTML
