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


def _float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = float(raw_value)
        if value < 0:
            return default
        return value
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Application settings loaded from environment variables."""

    ai_provider: str = os.getenv("AI_PROVIDER", "rule-based")
    ai_model: str = os.getenv("AI_MODEL", "local-rule-engine-v1")
    max_code_chars: int = _int_env("MAX_CODE_CHARS", 20000)
    max_request_bytes: int = _int_env("MAX_REQUEST_BYTES", 1048576)
    rate_limit_requests: int = _int_env("RATE_LIMIT_REQUESTS", 120)
    rate_limit_window_seconds: int = _int_env("RATE_LIMIT_WINDOW_SECONDS", 60)
    cache_enabled: bool = _bool_env("CACHE_ENABLED", True)
    cache_ttl_seconds: int = _int_env("CACHE_TTL_SECONDS", 300)
    redis_url: str | None = os.getenv("REDIS_URL")
    sentry_dsn: str | None = os.getenv("SENTRY_DSN")
    sentry_traces_sample_rate: float = _float_env("SENTRY_TRACES_SAMPLE_RATE", 0.0)
    enable_docs: bool = _bool_env("ENABLE_DOCS", False)
    public_root_info: bool = _bool_env("PUBLIC_ROOT_INFO", False)
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./assistant.db")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-this-in-production-min-32-bytes")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_minutes: int = _int_env("ACCESS_TOKEN_MINUTES", 720)
    llm_enabled: bool = _bool_env("LLM_ENABLED", False)
    llm_api_key: str | None = os.getenv("LLM_API_KEY")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    llm_timeout_seconds: int = _int_env("LLM_TIMEOUT_SECONDS", 30)


settings = Settings()
