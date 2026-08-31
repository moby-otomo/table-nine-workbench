from __future__ import annotations

from table_nine.providers.contracts import ModelProvider, ProviderConfigurationError
from table_nine.providers.mock import DeterministicMockProvider


def build_provider(provider_name: str, *, model: str = "") -> ModelProvider:
    if provider_name == "mock":
        return DeterministicMockProvider()
    if provider_name == "openai":
        from table_nine.providers.openai import OpenAIProvider

        return OpenAIProvider(model)
    raise ProviderConfigurationError(f"Unknown assistance provider: {provider_name}")
