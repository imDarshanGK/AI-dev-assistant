from pathlib import Path


FRONTEND_HTML = (
    Path(__file__).resolve().parents[2] / "frontend" / "index.html"
).read_text(encoding="utf-8")


def test_saved_entry_ids_are_normalized_before_lookup():
    assert "function normalizeSavedEntryId(id) {" in FRONTEND_HTML
    assert "const normalizedId = Number(id);" in FRONTEND_HTML
    assert "return Number.isNaN(normalizedId) ? null : normalizedId;" in FRONTEND_HTML


def test_history_and_favorites_share_the_same_restore_helper():
    assert "function restoreSavedEntry(entry) {" in FRONTEND_HTML
    assert "restoreSavedEntry(entry);" in FRONTEND_HTML
    assert "const entry = history.find(h => h.id === normalizedId);" in FRONTEND_HTML
    assert "const entry = favorites.find(f => f.id === normalizedId);" in FRONTEND_HTML


def test_restore_helper_rehydrates_language_and_results():
    assert "editor.value = entry.code;" in FRONTEND_HTML
    assert "setLanguage(entry.lang.toLowerCase());" in FRONTEND_HTML
    assert "currentResult = entry.result;" in FRONTEND_HTML
    assert "renderResults(entry.result, entry.code);" in FRONTEND_HTML
