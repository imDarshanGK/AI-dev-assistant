import os

from dataclasses import dataclass
from dotenv import find_dotenv, load_dotenv

# Load .env from current directory or parent directories if present.
load_dotenv(find_dotenv(filename=".env", usecwd=True), override=False)


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
    cache_max_entries: int = _int_env("CACHE_MAX_ENTRIES", 100)
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
    llm_max_retries: int = _int_env("LLM_MAX_RETRIES", 3)
    llm_retry_backoff: float = _float_env("LLM_RETRY_BACKOFF", 1.0)

    # ── Email / Digest ──────────────────────────────────────────
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = _int_env("SMTP_PORT", 587)
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_pass: str = os.getenv("SMTP_PASS", "")
    email_from: str = os.getenv("EMAIL_FROM", "noreply@qyverixai.app")
    digest_enabled: bool = _bool_env("DIGEST_ENABLED", False)
    digest_base_url: str = os.getenv(
        "DIGEST_BASE_URL", "https://qyverixai.onrender.com"
    )


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""
    api_key: str
    base_url: str
    model: str
    priority: int = 1

def _load_providers() -> list[ProviderConfig]:
    """Load ordered LLM providers from environment variables.

    Supports legacy LLM_API_KEY (becomes provider 1) and numbered
    LLM_PROVIDER_N_* vars. Deduplicates by api_key.
    """
    providers = []

    legacy_key = os.getenv("LLM_API_KEY")
    if legacy_key:
        providers.append(ProviderConfig(
            api_key=legacy_key,
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            priority=1,
        ))

    i = 1
    while True:
        key = os.getenv(f"LLM_PROVIDER_{i}_API_KEY")
        if not key:
            break
        providers.append(ProviderConfig(
            api_key=key,
            base_url=os.getenv(f"LLM_PROVIDER_{i}_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            model=os.getenv(f"LLM_PROVIDER_{i}_MODEL", "gpt-4o-mini"),
            priority=i,
        ))
        i += 1

    seen = set()
    unique = []
    for p in sorted(providers, key=lambda x: x.priority):
        if p.api_key not in seen:
            seen.add(p.api_key)
            unique.append(p)
    return unique


settings = Settings()
settings.llm_providers = _load_providers()
