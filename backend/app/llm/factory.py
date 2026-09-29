"""Создание клиента по конфигу. Клиента может не быть — это штатный режим."""

from __future__ import annotations

from ..config import LLMConfig, load_llm_config
from .client import LLMClient

_cached: tuple[LLMConfig, LLMClient | None] | None = None


def get_client(config: LLMConfig | None = None) -> LLMClient | None:
    global _cached
    config = config or load_llm_config()
    if _cached and _cached[0] == config:
        return _cached[1]
    client = LLMClient(config.base_url, config.api_key, config.model,
                       config.timeout) if config.enabled else None
    _cached = (config, client)
    return client


def llm_status() -> dict:
    config = load_llm_config()
    return {
        "provider": config.provider,
        "model": config.model if config.enabled else None,
        "base_url": config.base_url if config.enabled else None,
        "enabled": config.enabled,
    }
