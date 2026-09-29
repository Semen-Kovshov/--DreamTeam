"""Контур администратора (ТЗ «Арена переговоров», §2.2–2.3).

Админ задаёт контекст симуляции — сфера, тема, роли, тон собеседника,
сложность — и получает сценарий: генерацией через LLM или ручной правкой
JSON. Сохранённый сценарий немедленно попадает в каталог игрока: настройки
администратора влияют на симуляцию без перезапуска сервиса.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError

from ..config import SCENARIOS_DIR, load_llm_config
from ..llm import LLMClient, LLMError, get_client
from ..scenarios.generate import GenerationContext, generate_scenario
from ..scenarios.loader import load_all
from ..scenarios.models import Scenario
from . import routes

router = APIRouter(prefix="/api/admin")

# Встроенные сценарии поставки — их нельзя удалить или перезаписать.
BUILTIN_IDS = {"salary", "supplier", "discount", "rent"}


def _reload_catalog() -> None:
    routes.bind(load_all())


@router.get("/scenarios")
def list_scenarios() -> list[dict]:
    return [{"id": s.id, "title": s.title, "category": s.category,
             "persona": s.opponent.persona, "difficulty": s.difficulty,
             "builtin": s.id in BUILTIN_IDS}
            for s in routes._scenarios.values()]


@router.post("/scenarios/generate")
def generate(ctx: GenerationContext) -> dict:
    if get_client() is None:
        raise HTTPException(503, "LLM не подключена: генерация недоступна. "
                                 "Сценарий можно собрать вручную в редакторе ниже.")
    # Полный сценарий на локальной 4B-модели пишется минуты — генерации нужен
    # свой клиент с запасом по таймауту, диалоговые ходы это не замедляет.
    config = load_llm_config()
    client = LLMClient(config.base_url, config.api_key, config.model,
                       timeout=max(config.timeout, 600.0))
    try:
        draft, warnings = generate_scenario(
            client, ctx, taken_ids=set(routes._scenarios))
    except LLMError as error:
        raise HTTPException(502, f"модель не ответила: {error}") from error
    except ValueError as error:
        raise HTTPException(502, str(error)) from error
    return {"draft": draft, "warnings": warnings}


class ScenarioPayload(BaseModel):
    scenario: dict
    overwrite: bool = False


@router.post("/scenarios/validate")
def validate(payload: ScenarioPayload) -> dict:
    try:
        scenario = Scenario.model_validate(payload.scenario)
    except ValidationError as error:
        return {"ok": False, "errors": [
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
            for e in error.errors()[:10]]}
    return {"ok": True, "errors": [], "card": scenario.card()}


@router.post("/scenarios")
def save(payload: ScenarioPayload) -> dict:
    try:
        scenario = Scenario.model_validate(payload.scenario)
    except ValidationError as error:
        raise HTTPException(422, "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
            for e in error.errors()[:10])) from error
    if scenario.id in BUILTIN_IDS:
        raise HTTPException(409, "встроенный сценарий нельзя перезаписать — "
                                 "смените id")
    path = SCENARIOS_DIR / f"{scenario.id}.json"
    if path.exists() and not payload.overwrite:
        raise HTTPException(409, f"сценарий «{scenario.id}» уже есть — "
                                 "сохраните с перезаписью или смените id")
    path.write_text(json.dumps(payload.scenario, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    _reload_catalog()
    return {"ok": True, "id": scenario.id, "card": scenario.card()}


@router.delete("/scenarios/{scenario_id}")
def delete(scenario_id: str) -> dict:
    if scenario_id in BUILTIN_IDS:
        raise HTTPException(409, "встроенный сценарий удалить нельзя")
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.exists() or scenario_id not in routes._scenarios:
        raise HTTPException(404, "сценарий не найден")
    path.unlink()
    _reload_catalog()
    return {"ok": True}
