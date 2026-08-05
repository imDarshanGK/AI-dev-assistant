import sys
from unittest.mock import MagicMock, patch

sys.modules["sentry_sdk"] = MagicMock()

from app.services.error_tracking import init_error_tracking


def test_error_tracking_disabled_when_no_dsn():
    """Verify init_error_tracking returns False when sentry_dsn is not set."""
    with patch("app.services.error_tracking.settings") as mock_settings:
        mock_settings.sentry_dsn = None

        result = init_error_tracking()

        assert result is False


def test_error_tracking_enabled_when_dsn_present():
    """Verify init_error_tracking returns True when sentry_dsn is set."""
    with patch("app.services.error_tracking.settings") as mock_settings:
        mock_settings.sentry_dsn = "https://fake@sentry.io/123"
        mock_settings.sentry_traces_sample_rate = 1.0

        result = init_error_tracking()

        assert result is True


def test_error_tracking_returns_false_on_init_failure():
    """Verify init_error_tracking returns False when sentry init raises exception."""
    with patch("app.services.error_tracking.settings") as mock_settings:
        mock_settings.sentry_dsn = "https://fake@sentry.io/123"
        mock_settings.sentry_traces_sample_rate = 1.0

        sys.modules["sentry_sdk"].init.side_effect = Exception("Sentry failed")

        result = init_error_tracking()

        assert result is False

        sys.modules["sentry_sdk"].init.side_effect = None
