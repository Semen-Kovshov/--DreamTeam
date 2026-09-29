"""Действия-мелочи: невербальный слой переговоров.

Глотнуть воды, раскрыть блокнот, взглянуть на часы — маленькие жесты, которые
двигают атмосферу, не тратя реплику. Контент жестов (подписи, ремарки, реплики
персон, лимиты) — данные в `data/actions.json`, как и сценарии; в коде — только
эффекты: они ветвятся по персонам и контексту партии.

Пауза с водой или блокнотом заодно «оправдывает» задержку ответа — в режиме
со счётом времени это легальный способ взять раздумье (см. session).
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from ..config import ACTIONS_FILE
from ..scenarios.models import Persona, Scenario
from .state import Effect, OpponentState


class GameAction(BaseModel):
    id: str
    label: str             # полная подпись (тултип)
    word: str              # короткое слово на кнопке лотка
    hint: str              # что это даёт по смыслу
    narrative: str         # ремарка «от камеры»
    cooldown: int = Field(ge=1)
    max_uses: int = Field(ge=1)
    remarks: dict[Persona, list[str]]   # реакции по персонам; "" — молчит


def _load_actions() -> dict[str, GameAction]:
    raw = json.loads(ACTIONS_FILE.read_text(encoding="utf-8"))
    actions = {item["id"]: GameAction.model_validate(item) for item in raw}
    if not actions:
        raise RuntimeError(f"в {ACTIONS_FILE} нет ни одного действия")
    return actions


ACTIONS: dict[str, GameAction] = _load_actions()

# После каких намерений оппонента «пауза» действительно давит: он только что
# назвал условия и ждёт реакции.
PRESSURE_POINTS = {"counter_offer", "hold_firm", "partial_concede", "final_offer"}


def action_catalog() -> list[dict]:
    return [{"id": a.id, "label": a.label, "word": a.word, "hint": a.hint,
             "cooldown": a.cooldown, "max_uses": a.max_uses}
            for a in ACTIONS.values()]


def apply_action(scenario: Scenario, state: OpponentState, action_id: str,
                 turn: int, uses: int, last_intent_kind: str | None) -> tuple[list[Effect], str]:
    """Эффекты действия + короткая реакция оппонента (шаблон по персоне)."""
    persona = scenario.opponent.persona
    effects: list[Effect] = []

    if action_id == "water":
        effects.append(Effect("tension", -4, "Пауза с водой сбивает темп и остужает разговор"))
    elif action_id == "notebook":
        effects.append(Effect("trust", 3, "Записи показывают: слова собеседника имеют вес"))
    elif action_id == "phone":
        if persona == "soft":
            effects.append(Effect("tension", 6, "Телефон посреди разговора — мягкий человек обижается молча"))
            effects.append(Effect("trust", -2, "Внимание ушло — контакт просел"))
        elif persona == "positional":
            effects.append(Effect("tension", 4, "Отвлечение на телефон читается как неуважение к процессу"))
        else:
            effects.append(Effect("aspiration", -0.02, "Демонстративное безразличие: жёсткий видит, что вы не цепляетесь"))
            effects.append(Effect("tension", 3, "Но жест на грани — градус подрос"))
    elif action_id == "pause":
        if last_intent_kind in PRESSURE_POINTS:
            effects.append(Effect("aspiration", -0.02, "Тишина после названных условий давит на того, кто их назвал"))
        else:
            effects.append(Effect("patience", -1, "Пауза без повода просто тянет время"))
    elif action_id == "watch":
        effects.append(Effect("aspiration", -0.015, "Взгляд на часы: у вас есть дедлайн и альтернативы"))
        effects.append(Effect("tension", 4, "Жест торопит — собеседнику это не нравится"))
    elif action_id == "treat":
        if turn <= 3:
            effects.append(Effect("trust", 5, "Маленькая забота в начале — быстрый раппорт"))
        else:
            effects.append(Effect("trust", 2, "Жест внимания принят"))
            effects.append(Effect("tension", -2, "Атмосфера чуть теплее"))
    else:
        raise ValueError(f"неизвестное действие: {action_id}")

    # Повторение приедается: вторая вода — вдвое слабее.
    if uses > 0:
        for effect in effects:
            effect.delta = round(effect.delta * (0.5 ** uses), 3)

    remarks = ACTIONS[action_id].remarks[persona]
    remark = remarks[uses % len(remarks)]
    return effects, remark
