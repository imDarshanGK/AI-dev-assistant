import logging
import os
from logging.handlers import RotatingFileHandler

from ..config import settings

logger = logging.getLogger("ai_assistant.api")


def init_error_tracking() -> bool:
    """Initialize log rotation and optional Sentry integration."""
    try:
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, "app.log")

        max_bytes = settings.log_max_bytes
        backup_count = settings.log_backup_count

        log_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
        )

        rotating_handler = RotatingFileHandler(
            log_file_path, maxBytes=max_bytes, backupCount=backup_count
        )
        rotating_handler.setFormatter(log_formatter)
        rotating_handler.setLevel(logging.INFO)

        app_logger = logging.getLogger("ai_assistant")
        app_logger.addHandler(rotating_handler)
        
        logger.info(
            "log_rotation_enabled file=%s max_bytes=%d backup_count=%d",
            log_file_path,
            max_bytes,
            backup_count,
        )
    except Exception as log_exc:
        logger.error("log_rotation_init_failed detail=%s", str(log_exc))

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