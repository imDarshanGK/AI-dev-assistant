import unittest

from pydantic import ValidationError

from app.schemas import CodeRequest


class CodeRequestLimitTests(unittest.TestCase):
    def test_accepts_code_at_limit(self):
        req = CodeRequest(code="a" * 50000, language="python")
        self.assertEqual(len(req.code), 50000)

    def test_rejects_code_over_limit(self):
        with self.assertRaises(ValidationError) as ctx:
            CodeRequest(code="a" * 50001, language="python")

        self.assertIn("50,000", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
