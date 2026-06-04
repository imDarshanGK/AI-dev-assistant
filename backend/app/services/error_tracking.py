import logging

from ..config import settings

logger = logging.getLogger("ai_assistant.api")


def init_error_tracking() -> bool:
    if not settings.sentry_dsn:
        logger.info("sentry_disabled reason=no_dsn")
        return False

    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.sentry_environment,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            profiles_sample_rate=settings.sentry_profiles_sample_rate,
        )

        # Set default context & tags without leaking secrets
        sentry_sdk.set_tag("app_name", "ai-dev-assistant")
        sentry_sdk.set_tag("ai_provider", settings.ai_provider)
        sentry_sdk.set_tag("ai_model", settings.ai_model)
        sentry_sdk.set_tag("llm_enabled", str(settings.llm_enabled))

        sentry_sdk.set_context("app_settings", {
            "max_code_chars": settings.max_code_chars,
            "max_request_bytes": settings.max_request_bytes,
            "rate_limit_requests": settings.rate_limit_requests,
            "rate_limit_window_seconds": settings.rate_limit_window_seconds,
            "cache_enabled": settings.cache_enabled,
            "enable_docs": settings.enable_docs,
            "llm_model": settings.llm_model,
        })

        logger.info("sentry_enabled environment=%s", settings.sentry_environment)
        return True
    except Exception as exc:
        logger.warning("sentry_init_failed detail=%s", str(exc))
        return False
