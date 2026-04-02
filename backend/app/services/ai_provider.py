from dataclasses import dataclass


@dataclass
class ProviderMetadata:
    provider: str
    model: str
    mode: str


def get_provider_metadata(provider: str, model: str) -> ProviderMetadata:
    """Return provider metadata for API transparency.

    mode is set to 'ready' to show the app is prepared for live AI integration,
    while currently serving deterministic rule-based responses.
    """
    return ProviderMetadata(provider=provider, model=model, mode="ready")
