from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


class LLMError(Exception):
    """Ответ пришёл, но не подходит (не JSON, не по схеме, HTTP-ошибка)."""


class LLMUnavailable(LLMError):
    """Endpoint недоступен — сеть, таймаут. Сигнал перейти на запасной путь."""


@dataclass
class Message:
    role: str      # system | user | assistant
    content: str


FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> dict[str, Any]:
    """Достаёт объект из ответа: модель любит обернуть JSON в markdown."""
    candidate = text.strip()
    if match := FENCE.search(candidate):
        candidate = match.group(1).strip()
    if not candidate.startswith("{"):
        start, end = candidate.find("{"), candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start:end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise LLMError(f"ответ не разбирается как JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise LLMError("ожидался объект JSON")
    return parsed


def render_schema_hint(schema: dict[str, Any]) -> str:
    return ("Ответь только JSON-объектом строго по схеме, без пояснений "
            "и без markdown:\n" + json.dumps(schema, ensure_ascii=False))
