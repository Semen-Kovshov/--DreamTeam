"""LLM-классификатор реплики игрока — основной путь распознавания.

Модель получает словарь конкретного сценария (интересы, рычаги, вопросы
торга) и возвращает строгий JSON. Валидация — pydantic'ом: неизвестные id
отбрасываются, а не роняют ход.
"""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from ..engine.moves import SPIN, Move, MoveType
from ..engine.state import OpponentState
from ..llm import LLMClient, LLMError, Message
from ..scenarios.models import BooleanIssue, NumericIssue, Scenario

MOVE_TYPES = [m.value for m in MoveType]

SCHEMA = {
    "type": "object",
    "properties": {
        "moves": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": MOVE_TYPES},
                    "spin": {"type": ["string", "null"], "enum": list(SPIN) + [None]},
                    "interest_id": {"type": ["string", "null"]},
                    "lever_id": {"type": ["string", "null"]},
                    "offer_value": {"type": ["number", "null"]},
                    "offer_options": {"type": "array", "items": {"type": "string"}},
                    "conditional": {"type": "boolean"},
                },
                "required": ["type"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["moves"],
    "additionalProperties": False,
}

GUIDE = """Ты — разметчик переговорных приёмов. Классифицируй реплику игрока в 1–3 хода.

Типы ходов:
- small_talk: приветствие, разговор ни о чём для контакта
- open_question / closed_question: вопрос оппоненту (закрытый — с ответом да/нет)
- active_listening: пересказ или резюме слов оппонента
- empathy: признание чувств или позиции оппонента
- argument: довод в свою пользу; если совпадает с рычагом из списка — укажи lever_id
- criteria: ссылка на рынок, статистику, норму, публичную политику
- offer: конкретное предложение; offer_value — число главного вопроса, offer_options — id опций из списка
- batna: игрок упоминает свою альтернативу (другой оффер, другого поставщика)
- ultimatum: «или так — или ухожу», давление с угрозой разрыва
- pressure: давление без прямой угрозы разрыва
- rudeness: грубость, переход на личности
- accept: согласие на текущее предложение оппонента
- reject: отказ без встречного предложения
- off_topic: реплика не о переговорах

Для вопросов определи SPIN: S — о ситуации, P — о проблеме, I — о последствиях
проблемы, N — о ценности решения; иначе null. Если ход касается темы одного
из интересов — укажи interest_id. conditional=true, если предложение обусловлено
(«если…, то…»). Не выдумывай id вне списков и не добавляй ходов, которых нет
в реплике: два-три точных хода лучше четырёх сомнительных.

Примеры (сценарий о цене, интерес cash, рычаг vol, опция prepay):
«Как у вас с загрузкой производства?»
→ {"moves":[{"type":"open_question","spin":"S","interest_id":"cash"}]}
«Если предоплата — готов на 1400.»
→ {"moves":[{"type":"offer","offer_value":1400,"offer_options":["prepay"],"conditional":true}]}
«Понимаю, что кассовый разрыв — это тяжело. Но мы растём на 40% — вам нужны наши объёмы.»
→ {"moves":[{"type":"empathy","interest_id":"cash"},{"type":"argument","lever_id":"vol"}]}"""


class _RawMove(BaseModel):
    type: str
    spin: str | None = None
    interest_id: str | None = None
    lever_id: str | None = None
    offer_value: float | None = None
    offer_options: list[str] = []
    conditional: bool = False


def _context(scenario: Scenario, state: OpponentState, npc_last: str) -> str:
    main = scenario.main_issue
    interests = "\n".join(f"- {i.id}: {i.text}; темы: {', '.join(i.topics)}"
                          for i in scenario.opponent.interests)
    levers = "\n".join(f"- {l.id}: {l.text}" for l in scenario.opponent.levers)
    options = "\n".join(f"- {i.id}: {i.name} («{i.ask_phrase}»)"
                        for i in scenario.issues if isinstance(i, BooleanIssue))
    lines = [
        f"Сценарий: {scenario.title}. {scenario.setting}",
        f"Главный вопрос торга: {main.name}, единица: {main.unit or 'число'}.",
        f"Интересы оппонента:\n{interests}",
        f"Рычаги (сильные аргументы игрока):\n{levers}",
    ]
    if options:
        lines.append(f"Опции пакета:\n{options}")
    if state.opp_offer:
        lines.append("На столе есть предложение оппонента.")
    if npc_last:
        lines.append(f"Последняя реплика оппонента: «{npc_last}»")
    return "\n\n".join(lines)


def classify_llm(client: LLMClient, text: str, scenario: Scenario,
                 state: OpponentState, npc_last: str = "") -> list[Move]:
    messages = [
        Message("system", GUIDE),
        Message("user", _context(scenario, state, npc_last)
                + f"\n\nРеплика игрока: «{text}»"),
    ]
    data = client.complete_json(messages, SCHEMA, max_tokens=500)
    raw_moves = data.get("moves") or []

    interest_ids = {i.id for i in scenario.opponent.interests}
    lever_ids = {l.id for l in scenario.opponent.levers}
    option_ids = {i.id for i in scenario.issues if isinstance(i, BooleanIssue)}
    main = scenario.main_issue

    moves: list[Move] = []
    for item in raw_moves[:3]:
        try:
            raw = _RawMove.model_validate(item)
            move_type = MoveType(raw.type)
        except (ValidationError, ValueError):
            continue
        offer: dict[str, float | bool] = {}
        if move_type == MoveType.OFFER:
            if raw.offer_value is not None:
                offer[main.id] = raw.offer_value
            for opt in raw.offer_options:
                if opt in option_ids:
                    offer[opt] = True
            if not offer:
                continue    # предложение без содержимого бесполезно
        moves.append(Move(
            type=move_type,
            spin=raw.spin if raw.spin in SPIN else None,
            interest_id=raw.interest_id if raw.interest_id in interest_ids else None,
            lever_id=raw.lever_id if raw.lever_id in lever_ids else None,
            offer=offer,
            conditional=raw.conditional,
            has_number=raw.offer_value is not None,
        ))
    if not moves:
        raise LLMError("классификатор не вернул ни одного валидного хода")
    return moves
