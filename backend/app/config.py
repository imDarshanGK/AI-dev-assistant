import os


class Settings:
    """Application settings loaded from environment variables."""

    ai_provider: str = os.getenv("AI_PROVIDER", "rule-based")
    ai_model: str = os.getenv("AI_MODEL", "local-rule-engine-v1")


settings = Settings()
