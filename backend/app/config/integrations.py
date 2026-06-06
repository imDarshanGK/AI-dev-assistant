import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class AIConfig:
    enabled: bool = _bool_env("LLM_ENABLED", False)
    api_key: str | None = os.getenv("LLM_API_KEY")
    base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    timeout_seconds: int = _int_env("LLM_TIMEOUT_SECONDS", 30)
    max_retries: int = _int_env("LLM_MAX_RETRIES", 3)
    retry_backoff: float = _float_env("LLM_RETRY_BACKOFF", 1.0)


@dataclass
class EmailConfig:
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = _int_env("SMTP_PORT", 587)
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_pass: str = os.getenv("SMTP_PASS", "")
    email_from: str = os.getenv("EMAIL_FROM", "noreply@qyverixai.app")


@dataclass
class AnalyticsConfig:
    sentry_dsn: str | None = os.getenv("SENTRY_DSN")
    traces_sample_rate: float = _float_env(
        "SENTRY_TRACES_SAMPLE_RATE", 0.0
    )


class Integrations:
    ai = AIConfig()
    email = EmailConfig()
    analytics = AnalyticsConfig()


integrations = Integrations()

def validate_integrations() -> None:
    """
    Validate third-party integration configuration.
    """

    if integrations.ai.enabled and not integrations.ai.api_key:
        raise ValueError(
            "LLM_ENABLED=true but LLM_API_KEY is not configured."
        )

    if integrations.email.smtp_host and not integrations.email.email_from:
        raise ValueError(
            "EMAIL_FROM must be configured when SMTP is enabled."
        )