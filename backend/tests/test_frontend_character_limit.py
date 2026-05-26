import unittest
from pathlib import Path


class FrontendCharacterLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        html = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
        cls.source = html.read_text(encoding="utf-8")

    def test_frontend_enforces_character_limit_before_submit(self):
        self.assertIn("const CODE_CHAR_LIMIT = 50000;", self.source)
        self.assertIn("const CODE_CHAR_WARNING = 45000;", self.source)
        self.assertIn("function syncAnalyzeButtonState(", self.source)
        self.assertIn("if (!selectedZipFile && code.length > CODE_CHAR_LIMIT)", self.source)
        self.assertIn("toast(getTranslation('toast_code_too_large'), 'error');", self.source)
        self.assertIn("editorFooter.classList.toggle('limit-exceeded', overLimit);", self.source)
        self.assertIn("analyzeBtn.disabled = shouldDisable;", self.source)

    def test_frontend_exposes_limit_warning_copy(self):
        self.assertIn("toast_code_too_large", self.source)
        self.assertIn("Code exceeds the 50,000 character limit.", self.source)


if __name__ == "__main__":
    unittest.main()
