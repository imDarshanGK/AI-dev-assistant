import logging

from ..config import settings

logger = logging.getLogger("ai_assistant.api")

_VALID_DSN_PREFIXES = ("https://", "http://")
_MIN_SAMPLE_RATE = 0.0
_MAX_SAMPLE_RATE = 1.0


def _validate_dsn(dsn: str | None) -> str | None:
    """Return the DSN if it looks valid, otherwise None.

    Rejects None, empty strings, and values that don't start with
    a recognised scheme — catching the most common misconfiguration
    where a placeholder like 'your-dsn-here' is left in .env.
    """
    if not dsn or not dsn.strip():
        return None
    stripped = dsn.strip()
    if not any(stripped.startswith(prefix) for prefix in _VALID_DSN_PREFIXES):
        logger.warning(
            "sentry_dsn_invalid reason=unrecognised_scheme dsn_prefix=%s",
            stripped[:20],
        )
        return None
    return stripped


def _clamp_sample_rate(rate: float) -> float:
    """Clamp traces_sample_rate to the valid [0.0, 1.0] range.

    sentry_sdk raises ValueError for values outside this range, so we
    clamp proactively and log a warning so misconfiguration is visible.
    """
    if rate < _MIN_SAMPLE_RATE:
        logger.warning(
            "sentry_traces_sample_rate_clamped original=%.4f clamped=%.4f",
            rate,
            _MIN_SAMPLE_RATE,
        )
        return _MIN_SAMPLE_RATE
    if rate > _MAX_SAMPLE_RATE:
        logger.warning(
            "sentry_traces_sample_rate_clamped original=%.4f clamped=%.4f",
            rate,
            _MAX_SAMPLE_RATE,
        )
        return _MAX_SAMPLE_RATE
    return rate


def init_error_tracking() -> bool:
    """Initialise Sentry error tracking if a valid DSN is configured.

    Returns True if Sentry was successfully initialised, False otherwise.

    Validation applied before calling sentry_sdk.init():
        - DSN must be a non-empty string starting with https:// or http://.
          Placeholder values or empty strings are rejected gracefully.
        - traces_sample_rate is clamped to [0.0, 1.0] to prevent
          sentry_sdk from raising ValueError on out-of-range values.

    If sentry_sdk is not installed or init() raises any exception, the
    failure is logged as a warning and False is returned — the rest of
    the application continues normally.
    """
    dsn = _validate_dsn(settings.sentry_dsn)

    if not dsn:
        logger.info("sentry_disabled reason=no_dsn")
        return False

    sample_rate = _clamp_sample_rate(settings.sentry_traces_sample_rate)

    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=sample_rate,
        )
        logger.info("sentry_enabled")
        return True
    except Exception as exc:
        logger.warning("sentry_init_failed detail=%s", str(exc))
        return False
