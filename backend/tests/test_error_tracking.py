import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from app.config import settings
from app.services.error_tracking import init_error_tracking


class TestErrorTracking(unittest.TestCase):
    def setUp(self):
        # Store original settings
        self.original_dsn = settings.sentry_dsn
        self.original_env = settings.sentry_environment
        self.original_traces = settings.sentry_traces_sample_rate
        self.original_profiles = settings.sentry_profiles_sample_rate

    def tearDown(self):
        # Restore settings
        settings.sentry_dsn = self.original_dsn
        settings.sentry_environment = self.original_env
        settings.sentry_traces_sample_rate = self.original_traces
        settings.sentry_profiles_sample_rate = self.original_profiles

    @patch("sentry_sdk.init")
    def test_init_sentry_disabled_when_no_dsn(self, mock_init):
        settings.sentry_dsn = None
        result = init_error_tracking()
        self.assertFalse(result)
        mock_init.assert_not_called()

    @patch("sentry_sdk.set_context")
    @patch("sentry_sdk.set_tag")
    @patch("sentry_sdk.init")
    def test_init_sentry_enabled_with_correct_params(self, mock_init, mock_set_tag, mock_set_context):
        settings.sentry_dsn = "https://example_pubkey@sentry.io/example_project"
        settings.sentry_environment = "test-env"
        settings.sentry_traces_sample_rate = 0.5
        settings.sentry_profiles_sample_rate = 0.25

        result = init_error_tracking()

        self.assertTrue(result)
        mock_init.assert_called_once_with(
            dsn="https://example_pubkey@sentry.io/example_project",
            environment="test-env",
            traces_sample_rate=0.5,
            profiles_sample_rate=0.25,
        )

        # Verify default tags are set
        mock_set_tag.assert_any_call("app_name", "ai-dev-assistant")
        mock_set_tag.assert_any_call("ai_provider", settings.ai_provider)

        # Verify settings context is attached
        mock_set_context.assert_any_call("app_settings", {
            "max_code_chars": settings.max_code_chars,
            "max_request_bytes": settings.max_request_bytes,
            "rate_limit_requests": settings.rate_limit_requests,
            "rate_limit_window_seconds": settings.rate_limit_window_seconds,
            "cache_enabled": settings.cache_enabled,
            "enable_docs": settings.enable_docs,
            "llm_model": settings.llm_model,
        })

    @patch("sentry_sdk.capture_exception")
    def test_global_exception_handler_captures_to_sentry(self, mock_capture_exception):
        # Create a test client with app where an endpoint triggers an unhandled exception
        from app.main import app

        @app.get("/test-error-trigger-sentry")
        def trigger_error():
            raise ValueError("Test error for Sentry tracking")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-error-trigger-sentry")

        # Verify global handler caught exception and returned 500
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "Internal server error. Please try again."})

        # Verify sentry captured it
        mock_capture_exception.assert_called_once()
        args, kwargs = mock_capture_exception.call_args
        self.assertIsInstance(args[0], ValueError)
        self.assertEqual(str(args[0]), "Test error for Sentry tracking")
