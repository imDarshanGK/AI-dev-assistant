import os


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
        if value <= 0:
            return default
        return value
    except ValueError:
        return default


class Settings:
    """Application settings loaded from environment variables."""

    ai_provider: str = os.getenv("AI_PROVIDER", "rule-based")
    ai_model: str = os.getenv("AI_MODEL", "local-rule-engine-v1")
    max_code_chars: int = _int_env("MAX_CODE_CHARS", 20000)
    max_request_bytes: int = _int_env("MAX_REQUEST_BYTES", 1048576)
    rate_limit_requests: int = _int_env("RATE_LIMIT_REQUESTS", 120)
    rate_limit_window_seconds: int = _int_env("RATE_LIMIT_WINDOW_SECONDS", 60)


settings = Settings()
