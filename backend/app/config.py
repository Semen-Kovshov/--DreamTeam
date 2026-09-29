"""Конфигурация из `.env` в корне проекта.

Файл читается сами — ради одной задачи не тянем python-dotenv. Переменные
окружения процесса важнее файла: так тесты и CI подменяют настройки, не трогая
`.env` разработчика.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
SCENARIOS_DIR = DATA_DIR / "scenarios"
ACTIONS_FILE = DATA_DIR / "actions.json"
SESSIONS_DIR = DATA_DIR / "sessions"
HISTORY_FILE = DATA_DIR / "history.jsonl"
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


@dataclass(frozen=True)
class LLMConfig:
    provider: str          # openai | off
    base_url: str
    api_key: str
    model: str
    timeout: float

    @property
    def enabled(self) -> bool:
        return self.provider == "openai" and bool(self.base_url and self.model)


def load_llm_config() -> LLMConfig:
    file_values = _read_env_file(PROJECT_ROOT / ".env")

    def get(name: str, default: str = "") -> str:
        return os.environ.get(name, file_values.get(name, default))

    base_url = get("NEGO_LLM_BASE_URL")
    provider = get("NEGO_LLM_PROVIDER", "openai" if base_url else "off")
    return LLMConfig(
        provider=provider,
        base_url=base_url,
        api_key=get("NEGO_LLM_API_KEY", "ollama"),
        model=get("NEGO_LLM_MODEL"),
        timeout=float(get("NEGO_LLM_TIMEOUT", "120")),
    )
