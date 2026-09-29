"""HTTP-клиент OpenAI-совместимого endpoint'а (Ollama, API организаторов).

Два вида запросов под две задачи тренажёра:
- `complete_json` — классификация реплики: строгая схема, температура 0,
  повтор с текстом ошибки, если ответ не разобрался;
- `complete_text` — озвучка оппонента: свободный текст, температура повыше.

Лестница structured outputs как в slide-designer: `json_schema` →
`json_object` → схема в промпте; что endpoint принял — запоминаем.
"""

from __future__ import annotations

from typing import Any

import httpx

from .base import LLMError, LLMUnavailable, Message, extract_json, render_schema_hint


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str,
                 timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._structured_mode: str | None = None

    @property
    def name(self) -> str:
        return f"openai/{self.model}"

    # --- транспорт ------------------------------------------------------

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            # trust_env=False: endpoint задан явно, и системный прокси здесь
            # только мешает — на машине с V2Ray запросы к localhost уходили
            # в прокси и возвращались как 503 с пустым телом.
            with httpx.Client(timeout=self.timeout, trust_env=False) as client:
                response = client.post(f"{self.base_url}/chat/completions",
                                       json=body, headers=headers)
        except httpx.HTTPError as error:
            raise LLMUnavailable(f"endpoint недоступен: {error}") from error
        if response.status_code >= 400:
            raise LLMError(f"HTTP {response.status_code}: {response.text[:300]}")
        return response.json()

    def _content(self, raw: dict[str, Any]) -> str:
        try:
            return raw["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as error:
            raise LLMError(f"неожиданная форма ответа: {error}") from error

    # --- свободный текст ------------------------------------------------

    def complete_text(self, messages: list[Message], max_tokens: int = 400,
                      temperature: float = 0.7) -> str:
        raw = self._post({
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        text = self._content(raw).strip()
        if not text:
            raise LLMError("пустой ответ")
        return text

    # --- строгий JSON ---------------------------------------------------

    def _json_body(self, messages: list[Message], schema: dict[str, Any],
                   mode: str, max_tokens: int) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": 0,
        }
        if mode == "json_schema":
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "result", "schema": schema, "strict": True},
            }
        elif mode == "json_object":
            body["response_format"] = {"type": "json_object"}
        return body

    def complete_json(self, messages: list[Message], schema: dict[str, Any],
                      max_tokens: int = 700, retries: int = 1) -> dict[str, Any]:
        modes = [self._structured_mode] if self._structured_mode else \
            ["json_schema", "json_object", "prompt"]

        last_error: LLMError | None = None
        for mode in modes:
            attempt_messages = list(messages)
            if mode == "prompt":
                attempt_messages.append(Message("user", render_schema_hint(schema)))

            for attempt in range(retries + 1):
                try:
                    raw = self._post(self._json_body(attempt_messages, schema,
                                                     mode, max_tokens))
                except LLMUnavailable:
                    raise
                except LLMError as error:
                    last_error = error
                    break            # режим не принят endpoint'ом — следующий
                try:
                    data = extract_json(self._content(raw))
                except LLMError as error:
                    last_error = error
                    # Показываем модели её же ошибку — надёжнее слепого повтора.
                    attempt_messages = attempt_messages + [Message(
                        "user", f"Предыдущий ответ не подошёл: {error}. "
                                "Верни только валидный JSON по схеме.")]
                    continue
                self._structured_mode = mode
                return data

        raise last_error or LLMError("не удалось получить JSON")
