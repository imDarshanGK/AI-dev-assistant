import logging

from app.config import settings

logger = logging.getLogger("ai_assistant.api")


def init_error_tracking() -> bool:
    if not settings.sentry_dsn:
        logger.info("sentry_disabled reason=no_dsn")
        return False

    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=settings.sentry_traces_sample_rate,
        )
        logger.info("sentry_enabled")
        return True
    except Exception as exc:
        logger.warning("sentry_init_failed detail=%s", str(exc))
        return False
