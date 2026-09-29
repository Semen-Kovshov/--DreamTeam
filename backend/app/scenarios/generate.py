"""Генерация сценария из контекста администратора (ТЗ «Арена переговоров» §2.2).

Админ задаёт сферу, тему, роли, тон собеседника и сложность — полный сценарий
по нашей схеме собирает LLM в два шага (ядро → шаблоны реплик), после чего
детерминированные фиксеры приводят числа и связи в порядок, а pydantic-схема
даёт финальную гарантию. Модель может ошибаться в мелочах — фиксеры чинят
типовое (ориентация чисел, ZOPA, диапазоны сил, потерянные плейсхолдеры),
чтобы админ получал валидный черновик, а не стену ошибок.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from ..engine.npc import INTENT_KINDS
from ..llm import LLMClient, Message
from .models import Persona, Scenario


class GenerationContext(BaseModel):
    """Форма администратора: контекст симуляции."""
    sphere: str = Field(min_length=2, max_length=80)          # сфера/категория
    topic: str = Field(min_length=5, max_length=300)          # тема переговоров
    player_role: str = Field(min_length=3, max_length=120)
    opponent_role: str = Field(min_length=3, max_length=120)
    opponent_name: str = Field(default="", max_length=60)
    persona: Persona = "positional"                           # тон собеседника
    difficulty: int = Field(default=2, ge=1, le=4)
    unit: str = Field(default="", max_length=30)              # ед. главного вопроса
    player_target: float | None = None
    player_limit: float | None = None
    opponent_start: float | None = None
    opponent_limit: float | None = None
    wishes: str = Field(default="", max_length=600)           # свободные пожелания


MAX_TURNS_BY_DIFFICULTY = {1: 10, 2: 12, 3: 14, 4: 14}

PERSONA_HINT = {
    "soft": "мягкий, вежливый, избегает конфликта, копит обиду молча",
    "positional": "позиционный торг, любит цифры и объективные критерии",
    "hard": "напористый, давит статусом, уважает твёрдость и расчёт",
}

_CORE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "setting": {"type": "string"},
        "opponent_name": {"type": "string"},
        "opponent_voice": {"type": "string"},
        "opening": {"type": "string"},
        "player_goal": {"type": "string"},
        "batna_text": {"type": "string"},
        "batna_score": {"type": "number"},
        "facts": {"type": "array", "items": {"type": "string"}},
        "criteria": {"type": "array", "items": {"type": "string"}},
        "main_issue": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "unit": {"type": "string"},
                "direction": {"type": "string", "enum": ["higher_better", "lower_better"]},
                "step": {"type": "number"},
                "player_target": {"type": "number"},
                "player_limit": {"type": "number"},
                "opponent_start": {"type": "number"},
                "opponent_limit": {"type": "number"},
            },
            "required": ["name", "direction", "step", "player_target",
                          "player_limit", "opponent_start", "opponent_limit"],
        },
        "options": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "player_value": {"type": "number"},
                    "opponent_cost": {"type": "number"},
                    "ask_phrase": {"type": "string"},
                },
                "required": ["id", "name", "player_value", "opponent_cost", "ask_phrase"],
            },
        },
        "interests": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "reveal_line": {"type": "string"},
                    "topics": {"type": "array", "items": {"type": "string"}},
                    "probe": {"type": "string"},
                },
                "required": ["id", "text", "reveal_line", "topics", "probe"],
            },
        },
        "levers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "phrase": {"type": "string"},
                    "interest_id": {"type": "string"},
                    "aspiration_drop": {"type": "number"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "text", "phrase", "interest_id",
                              "aspiration_drop", "keywords"],
            },
        },
        "irritants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "tension_add": {"type": "number"},
                },
                "required": ["id", "text", "keywords", "tension_add"],
            },
        },
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "turn": {"type": "integer"},
                    "title": {"type": "string"},
                    "text": {"type": "string"},
                    "aspiration_add": {"type": "number"},
                    "patience_add": {"type": "integer"},
                    "tension_add": {"type": "number"},
                },
                "required": ["turn", "title", "text"],
            },
        },
    },
    "required": ["title", "summary", "setting", "opponent_name", "opponent_voice",
                  "opening", "player_goal", "batna_text", "batna_score", "facts",
                  "criteria", "main_issue", "options", "interests", "levers",
                  "irritants", "events"],
}

_TEMPLATES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {kind: {"type": "array", "items": {"type": "string"},
                          "minItems": 1, "maxItems": 2}
                   for kind in sorted(INTENT_KINDS)},
    "required": sorted(INTENT_KINDS),
}

_CORE_GUIDE = """Ты — методист тренажёра деловых переговоров. По контексту от
администратора собери СЦЕНАРИЙ ПЕРЕГОВОРОВ строго в JSON по схеме.

Правила содержания:
- Всё по-русски, деловым живым языком. Игрок — «вы», оппонент — персонаж.
- main_issue: числовой предмет торга. У игрока цель (player_target) и предел
  (player_limit — хуже нельзя), у оппонента стартовая позиция (opponent_start)
  и предел (opponent_limit — дальше не пойдёт). Пределы сторон ОБЯЗАНЫ
  пересекаться (зона возможного соглашения). step — шаг торга (например 5 или 10).
- options: 2-3 разменные опции пакета. player_value — ценность «да» игроку
  в баллах (может быть отрицательной: это уступка, которую игрок продаёт);
  opponent_cost — цена «да» оппоненту (отрицательная = оппоненту выгодно).
  Полезны опции с разными знаками: на них строится взаимовыгодный размен.
- interests: ровно 3 СКРЫТЫХ интереса оппонента (его настоящие боли).
  reveal_line — реплика, которой он раскрывает боль (от первого лица, живая).
  probe — готовый вопрос игрока, вскрывающий интерес.
- levers: ровно 3 аргумента игрока, каждый бьёт в один interest_id.
  aspiration_drop — сила 0.10–0.22. phrase — готовая формулировка игрока.
- topics и keywords — СТЕМЫ русских слов (обрубленные основы без окончаний:
  «команд», «бюджет», «загрузк», «предоплат»), 4-6 штук, чтобы совпадать с
  любыми словоформами. Двусловные ключи допустимы («рынок офисов»).
- irritants: 1-2 больные мозоли персоны (что выводит из равновесия),
  tension_add 8-14.
- events: 1-2 события посреди партии (turn 4-9): звонок, письмо, новость.
  aspiration_add от -0.06 до 0.04, patience_add 0 или -1, tension_add 0-8.
- batna_score: ценность альтернативы игрока в баллах 5-45 (0 = предел, 100 = цель).
- facts: 4 факта в распоряжении игрока; criteria: 2 объективных критерия
  (рынок, статистика, нормы) с конкретикой.
Не добавляй полей вне схемы. Числа пиши числами, не строками."""

_TEMPLATES_GUIDE = """Ты — сценарист реплик персонажа деловых переговоров.
Собери JSON с шаблонами реплик по видам намерений (по 2 варианта на вид,
каждый 1-2 предложения, от первого лица, в голосе персонажа).

Плейсхолдеры: в counter_offer, hold_firm, partial_concede, accept, final_offer
ОБЯЗАТЕЛЬНО вставь {offer} — на его место подставятся условия. В answer_disclose
единственный вариант — ровно строка "{reveal}".

Виды намерений:
- greeting_reply: ответ на приветствие, вернуть к делу
- answer_disclose: раскрытие скрытого интереса → строго "{reveal}"
- answer_evasive: уход от неудобного вопроса
- ack_argument: признать сильный аргумент, не меняя условий
- counter_offer: встречное предложение {offer}
- hold_firm: твёрдо повторить своё {offer}
- partial_concede: чуть улучшить условия {offer} в ответ на аргументы
- accept: согласиться на сделку {offer}
- final_offer: финальное «или так, или расходимся» {offer}
- warn: предупреждение о недопустимом тоне
- deescalate: самому снизить накал
- probe: встречный вопрос о позиции игрока
- nudge_back: вернуть отвлёкшийся разговор к теме
- walk_away: прекратить переговоры и попрощаться"""

_TRANSLIT = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
})


def slugify(title: str, taken: set[str]) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower().translate(_TRANSLIT)).strip("-")
    slug = slug[:40].strip("-") or "scenario"
    candidate, n = slug, 2
    while candidate in taken:
        candidate, n = f"{slug}-{n}", n + 1
    return candidate


def _context_prompt(ctx: GenerationContext) -> str:
    lines = [
        f"Сфера: {ctx.sphere}",
        f"Тема переговоров: {ctx.topic}",
        f"Роль игрока: {ctx.player_role}",
        f"Оппонент: {ctx.opponent_role}"
        + (f", имя: {ctx.opponent_name}" if ctx.opponent_name else " (имя придумай)"),
        f"Тон оппонента: {PERSONA_HINT[ctx.persona]}",
        f"Сложность: {ctx.difficulty} из 4",
    ]
    if ctx.unit:
        lines.append(f"Единица главного вопроса: {ctx.unit}")
    fixed = {"player_target": ctx.player_target, "player_limit": ctx.player_limit,
             "opponent_start": ctx.opponent_start, "opponent_limit": ctx.opponent_limit}
    given = {k: v for k, v in fixed.items() if v is not None}
    if given:
        lines.append("Заданные числа главного вопроса (использовать как есть): "
                     + ", ".join(f"{k}={v:g}" for k, v in given.items()))
    if ctx.wishes:
        lines.append(f"Пожелания администратора: {ctx.wishes}")
    return "\n".join(lines)


# --- детерминированные фиксеры -------------------------------------------


def _fix_numbers(core: dict, ctx: GenerationContext,
                 warnings: list[str]) -> None:
    main = core["main_issue"]
    for field in ("player_target", "player_limit", "opponent_start", "opponent_limit"):
        given = getattr(ctx, field)
        if given is not None:
            main[field] = given
    if ctx.unit:
        main["unit"] = ctx.unit
    main.setdefault("unit", "")
    step = abs(main.get("step") or 1) or 1
    main["step"] = step

    # Направление определяется числами игрока, а не мнением модели.
    if main["player_target"] == main["player_limit"]:
        main["player_target"] += step * 4
        warnings.append("цель игрока совпадала с пределом — раздвинута")
    direction = "higher_better" if main["player_target"] > main["player_limit"] \
        else "lower_better"
    if main.get("direction") != direction:
        main["direction"] = direction
        warnings.append("направление торга выправлено по числам игрока")

    better = max if direction == "higher_better" else min
    # Предел оппонента должен быть лучше его старта (для игрока).
    if better(main["opponent_limit"], main["opponent_start"]) != main["opponent_limit"]:
        main["opponent_start"], main["opponent_limit"] = \
            main["opponent_limit"], main["opponent_start"]
        warnings.append("старт и предел оппонента поменяны местами")
    # ZOPA обязана существовать.
    if better(main["opponent_limit"], main["player_limit"]) != main["opponent_limit"]:
        nudge = step * 2 if direction == "higher_better" else -step * 2
        main["opponent_limit"] = main["player_limit"] + nudge
        warnings.append("предел оппонента сдвинут: зона соглашения не пересекалась")


def _fix_links(core: dict, warnings: list[str]) -> None:
    def clamp(value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, value))

    interest_ids = []
    for i, interest in enumerate(core.get("interests", [])[:3]):
        interest["id"] = interest.get("id") or f"interest_{i + 1}"
        interest["topics"] = [t for t in interest.get("topics", []) if t][:6] or ["дел"]
        interest_ids.append(interest["id"])
    core["interests"] = core.get("interests", [])[:3]

    for i, lever in enumerate(core.get("levers", [])[:3]):
        lever["id"] = lever.get("id") or f"lever_{i + 1}"
        lever["aspiration_drop"] = clamp(float(lever.get("aspiration_drop", 0.15)),
                                         0.08, 0.25)
        lever["keywords"] = [k for k in lever.get("keywords", []) if k][:6] or [lever["id"]]
        if lever.get("interest_id") not in interest_ids:
            lever["interest_id"] = interest_ids[i % len(interest_ids)] \
                if interest_ids else None
            warnings.append(f"рычаг {lever['id']} привязан к интересу автоматически")
    core["levers"] = core.get("levers", [])[:3]

    for i, irritant in enumerate(core.get("irritants", [])[:2]):
        irritant["id"] = irritant.get("id") or f"irritant_{i + 1}"
        irritant["tension_add"] = clamp(float(irritant.get("tension_add", 10)), 5, 20)
        irritant["keywords"] = [k for k in irritant.get("keywords", []) if k][:6] or ["хамств"]
    core["irritants"] = core.get("irritants", [])[:2]

    seen: set[str] = set()
    options = []
    for i, option in enumerate(core.get("options", [])[:3]):
        option["id"] = option.get("id") or f"option_{i + 1}"
        if option["id"] in seen:
            option["id"] = f"{option['id']}_{i + 1}"
        seen.add(option["id"])
        if not option.get("player_value"):
            option["player_value"] = 10
        if not option.get("opponent_cost"):
            option["opponent_cost"] = 5
        options.append(option)
    core["options"] = options

    max_turns = MAX_TURNS_BY_DIFFICULTY[2]
    for event in core.get("events", [])[:2]:
        event["turn"] = int(clamp(int(event.get("turn", 5)), 3, max_turns - 3))
        event["aspiration_add"] = clamp(float(event.get("aspiration_add", 0)), -0.08, 0.05)
        event["patience_add"] = int(clamp(int(event.get("patience_add", 0)), -1, 0))
        event["tension_add"] = clamp(float(event.get("tension_add", 0)), 0, 8)
    core["events"] = core.get("events", [])[:2]

    core["batna_score"] = clamp(float(core.get("batna_score", 25)), 0, 60)


def _fix_templates(templates: dict, warnings: list[str]) -> dict:
    fixed: dict[str, list[str]] = {}
    for kind in INTENT_KINDS:
        variants = [v.strip() for v in templates.get(kind, []) if v and v.strip()]
        if kind == "answer_disclose":
            fixed[kind] = ["{reveal}"]
            continue
        needs_offer = kind in ("counter_offer", "hold_firm", "partial_concede",
                                "accept", "final_offer")
        cleaned = []
        for variant in variants[:2]:
            if needs_offer and "{offer}" not in variant:
                variant = variant.rstrip(".!…") + ": {offer}."
                warnings.append(f"в шаблон {kind} добавлен плейсхолдер условий")
            cleaned.append(variant)
        if not cleaned:
            cleaned = ["{offer}." if needs_offer else "…"]
            warnings.append(f"шаблон {kind} не сгенерирован — поставлена заглушка")
        fixed[kind] = cleaned
    return fixed


def _assemble(core: dict, templates: dict, ctx: GenerationContext,
              taken_ids: set[str]) -> dict:
    main = core["main_issue"]
    issues: list[dict] = [{
        "id": "main", "kind": "numeric",
        "name": main["name"], "unit": main.get("unit", ""),
        "step": main["step"], "direction": main["direction"],
        "player_target": main["player_target"], "player_limit": main["player_limit"],
        "opponent_start": main["opponent_start"], "opponent_limit": main["opponent_limit"],
        "weight_player": 100, "weight_opponent": 100,
    }]
    for option in core["options"]:
        issues.append({
            "id": option["id"], "kind": "boolean", "name": option["name"],
            "player_value": option["player_value"],
            "opponent_cost": option["opponent_cost"],
            "ask_phrase": option["ask_phrase"],
        })
    return {
        "id": slugify(core["title"], taken_ids),
        "title": core["title"][:80],
        "category": ctx.sphere,
        "difficulty": min(ctx.difficulty, 3),
        "summary": core["summary"],
        "setting": core["setting"],
        "player": {
            "role": ctx.player_role,
            "goal": core["player_goal"],
            "batna_text": core["batna_text"],
            "batna_score": core["batna_score"],
            "facts": core["facts"][:5],
            "criteria": core["criteria"][:3],
        },
        "opponent": {
            "name": (ctx.opponent_name or core["opponent_name"])[:60],
            "role": ctx.opponent_role,
            "persona": ctx.persona,
            "voice": core["opponent_voice"],
            "opening": core["opening"],
            "interests": core["interests"],
            "levers": core["levers"],
            "irritants": core["irritants"],
            "templates": templates,
        },
        "issues": issues,
        "max_turns": MAX_TURNS_BY_DIFFICULTY[ctx.difficulty],
        "events": core["events"],
    }


def generate_scenario(client: LLMClient, ctx: GenerationContext,
                      taken_ids: set[str]) -> tuple[dict, list[str]]:
    """Черновик сценария по контексту. Возвращает (json, предупреждения)."""
    warnings: list[str] = []
    context = _context_prompt(ctx)

    core = client.complete_json(
        [Message("system", _CORE_GUIDE), Message("user", context)],
        _CORE_SCHEMA, max_tokens=3500)
    _fix_numbers(core, ctx, warnings)
    _fix_links(core, warnings)

    persona_note = (f"Персонаж: {ctx.opponent_name or core.get('opponent_name', '')} — "
                    f"{ctx.opponent_role}. Манера речи: {core.get('opponent_voice', '')}. "
                    f"Тон: {PERSONA_HINT[ctx.persona]}.")
    templates_raw = client.complete_json(
        [Message("system", _TEMPLATES_GUIDE),
         Message("user", context + "\n\n" + persona_note)],
        _TEMPLATES_SCHEMA, max_tokens=2200)
    templates = _fix_templates(templates_raw, warnings)

    draft = _assemble(core, templates, ctx, taken_ids)
    try:
        Scenario.model_validate(draft)
    except ValidationError as error:
        raise ValueError(
            "модель собрала невалидный сценарий: "
            + "; ".join(e["msg"] for e in error.errors()[:5])) from error
    return draft, warnings
