"""LLM как языковой слой: классификация реплик и озвучка оппонента.

Ядро переговоров от модели не зависит — поэтому клиент может отсутствовать
(`get_client()` вернёт None), и вызывающий код обязан уметь работать без него.
"""

from .base import LLMError, LLMUnavailable, Message
from .client import LLMClient
from .factory import get_client, llm_status

__all__ = ["LLMClient", "LLMError", "LLMUnavailable", "Message",
           "get_client", "llm_status"]
