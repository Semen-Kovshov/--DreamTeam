"""Тактика оппонента: что он делает в ответ — детерминированное дерево решений.

Намерение (intent) — структура «что сказать», ещё без слов: вид реплики,
пакет предложения, раскрываемый интерес, причина выбора. Слова подбирает
`phrasing`, и если LLM недоступна — шаблоны сценария. Поэтому поведение
оппонента одинаково объяснимо в обоих режимах.
"""

from __future__ import annotations

from pydantic import BaseModel

from ..scenarios.models import BooleanIssue, NumericIssue, Scenario
from .moves import Move, MoveType
from .outcome import Package, opponent_utility
from .state import PERSONAS, OpponentState, PersonaParams, opponent_target


# Все виды намерений, которые способно выдать дерево тактик, — сценарий обязан
# иметь шаблон озвучки на каждый (проверяется тестами и генератором сценариев).
INTENT_KINDS = frozenset({
    "greeting_reply", "answer_disclose", "answer_evasive", "ack_argument",
    "counter_offer", "hold_firm", "partial_concede", "accept", "final_offer",
    "warn", "deescalate", "probe", "nudge_back", "walk_away",
})


class Intent(BaseModel):
    kind: str                       # ключ шаблона озвучки
    offer: Package = {}
    reveal_id: str | None = None
    note: str = ""                  # причина выбора — в журнал и разбор
    closes: str | None = None       # deal | no_deal | walked_away


def decide(scenario: Scenario, state: OpponentState, moves: list[Move],
           turn: int) -> Intent:
    persona = PERSONAS[scenario.opponent.persona]
    move_types = {m.type for m in moves}

    # 1. Игрок согласился на предложение на столе — сделка.
    if MoveType.ACCEPT in move_types and state.opp_offer:
        return Intent(kind="accept", offer=dict(state.opp_offer), closes="deal",
                      note="Игрок принял предложение оппонента")

    # 2. Отношения порваны — оппонент выходит.
    if state.tension >= persona.walk_threshold:
        return Intent(kind="walk_away", closes="walked_away",
                      note=f"Напряжение {state.tension:.0f} выше порога "
                           f"{persona.walk_threshold:.0f} этой персоны")

    # 3. Предупреждение о тоне (мягкая персона не предупреждает — копит).
    if persona.warn_threshold is not None and state.tension >= persona.warn_threshold \
            and move_types & {MoveType.ULTIMATUM, MoveType.PRESSURE, MoveType.RUDENESS}:
        return Intent(kind="warn", note="Тон на грани: последнее предупреждение")

    # 4. Мягкая персона гасит конфликт сама.
    if scenario.opponent.persona == "soft" and state.tension >= 55:
        return Intent(kind="deescalate", note="Избегание конфликта: попытка вернуть разговор в мирное русло")

    # 5. Предложение игрока разбирается даже на флажке — вдруг оно проходное.
    offer_move = next((m for m in moves if m.type == MoveType.OFFER and m.offer), None)
    if offer_move:
        return _respond_to_offer(scenario, state, persona, offer_move)

    # 6. Терпение кончилось — финальный аккорд.
    if state.patience <= 1:
        return _final_offer(scenario, state, persona)

    # 7. Ход вскрыл новый интерес — раскрытие. Вопросы по уже раскрытым темам
    # идут обычной веткой: пересказывать себя оппонент не станет.
    if state.last_revealed:
        return Intent(kind="answer_disclose", reveal_id=state.last_revealed,
                      note="Ход попал в скрытый интерес — оппонент делится")

    # 8. Сильный аргумент или объективный критерий — признать; если
    # накопилось, самому улучшить условия.
    lever_hit = any(m.lever_id for m in moves)
    if lever_hit or MoveType.CRITERIA in move_types:
        dropped = state.aspiration_at_last_offer - state.aspiration
        if state.opp_offer and dropped >= 0.06:
            return _concede(scenario, state, persona, reciprocity=True,
                            kind="partial_concede",
                            note=f"Аргументы сбили аппетит на {dropped:.2f} — "
                                 "оппонент двигается сам")
        return Intent(kind="ack_argument", note="Аргумент принят к сведению")

    if MoveType.OFF_TOPIC in move_types:
        return Intent(kind="nudge_back", note="Возврат к теме")

    if MoveType.SMALL_TALK in move_types and turn <= 2:
        return Intent(kind="greeting_reply", note="Обмен любезностями в начале")

    if move_types & {MoveType.OPEN_QUESTION, MoveType.CLOSED_QUESTION}:
        if state.trust >= 55:
            return Intent(kind="probe", note="Доверие есть — оппонент спрашивает в ответ")
        return Intent(kind="answer_evasive",
                      note="Вопрос мимо интересов, доверие невысокое — уход от ответа")

    if MoveType.REJECT in move_types and state.opp_offer:
        return Intent(kind="probe", note="Отказ без встречного — оппонент требует конкретику")

    # 9. Разговор без предложений затянулся — оппонент ставит якорь сам.
    if not state.opp_offer and turn >= 2:
        return _anchor(scenario, state)

    if state.opp_offer:
        return Intent(kind="hold_firm", offer=dict(state.opp_offer),
                      note="Новых оснований двигаться не прозвучало")
    return Intent(kind="probe", note="Оппонент ждёт конкретики")


# --- построение предложений ------------------------------------------------


def _snap(value: float, issue: NumericIssue) -> float:
    snapped = round(value / issue.step) * issue.step
    return round(snapped, 6)


def _clamp_toward_target(value: float, target: float, issue: NumericIssue) -> float:
    """Оппонент не предлагает лучше (для игрока), чем его текущая цель."""
    if issue.direction == "higher_better":
        return min(value, target)
    return max(value, target)


def _snap_safe(value: float, target: float, issue: NumericIssue) -> float:
    """Округление к шагу, не перескакивая цель оппонента."""
    snapped = _snap(value, issue)
    if issue.direction == "higher_better" and snapped > target:
        snapped = _snap(snapped - issue.step, issue)
    elif issue.direction == "lower_better" and snapped < target:
        snapped = _snap(snapped + issue.step, issue)
    return snapped


def _beneficial_asks(scenario: Scenario, state: OpponentState) -> list[BooleanIssue]:
    """Опции, выгодные оппоненту, о которых уместно просить."""
    asks = []
    for issue in scenario.issues:
        if isinstance(issue, BooleanIssue) and issue.opponent_cost < 0:
            if state.opp_offer.get(issue.id) or state.player_offer.get(issue.id):
                continue
            related = any(l.interest_id in state.revealed
                          for l in scenario.opponent.levers) or state.revealed
            if related:
                asks.append(issue)
    return asks


def _sweeteners(scenario: Scenario, state: OpponentState) -> list[BooleanIssue]:
    """Дешёвые для оппонента уступки, которыми можно подсластить пакет."""
    return [i for i in scenario.issues
            if isinstance(i, BooleanIssue) and 0 < i.opponent_cost <= 8
            and i.player_value > 0 and not state.opp_offer.get(i.id)]


def _compose(scenario: Scenario, state: OpponentState, main_value: float,
             include_ask: bool, include_sweetener: bool) -> Package:
    package: Package = dict(state.opp_offer)
    package[scenario.main_issue.id] = main_value
    # Опции, которые игрок уже предлагал сам, оппонент охотно фиксирует.
    for issue in scenario.issues:
        if isinstance(issue, BooleanIssue) and state.player_offer.get(issue.id) \
                and issue.opponent_cost < 0:
            package[issue.id] = True
    if include_ask:
        for ask in _beneficial_asks(scenario, state)[:1]:
            package[ask.id] = True
    if include_sweetener:
        for extra in _sweeteners(scenario, state)[:1]:
            package[extra.id] = True
    return package


def _anchor(scenario: Scenario, state: OpponentState) -> Intent:
    main = scenario.main_issue
    package = _compose(scenario, state, main.opponent_start,
                       include_ask=False, include_sweetener=False)
    state.opp_offer = package
    state.made_first_offer = state.made_first_offer or "opponent"
    state.aspiration_at_last_offer = state.aspiration
    return Intent(kind="counter_offer", offer=package,
                  note="Оппонент ставит свой якорь: стартовая позиция")


def _concede(scenario: Scenario, state: OpponentState, persona: PersonaParams,
             reciprocity: bool, kind: str, note: str) -> Intent:
    main = scenario.main_issue
    target = opponent_target(main, state.aspiration)
    current = float(state.opp_offer.get(main.id, main.opponent_start))
    player_ref = state.player_offer.get(main.id)

    rate = persona.concede_rate * (0.7 + 0.006 * state.trust) \
        * max(0.4, 1 - 0.004 * state.tension)
    if reciprocity:
        rate *= 1.25
    if kind == "partial_concede":
        rate *= 0.6

    pull_to = float(player_ref) if player_ref is not None else target
    candidate = current + rate * (pull_to - current)
    candidate = _clamp_toward_target(candidate, target, main)
    candidate = _snap_safe(candidate, target, main)

    if abs(candidate - current) < main.step / 2:
        step_move = current + (main.step if main.direction == "higher_better"
                               else -main.step)
        # Меньше целого шага не двигаются: «продвинуться на 4.15» выглядит
        # торгом на копейки и ломает сетку значений.
        if _clamp_toward_target(step_move, target, main) != step_move:
            if not state.opp_offer:
                # Двигаться некуда, а своего предложения ещё нет — значит,
                # пора поставить якорь, а не «держать» пустоту.
                return _anchor(scenario, state)
            return Intent(kind="hold_firm", offer=dict(state.opp_offer),
                          note="Цель оппонента не даёт двигаться дальше — держит позицию")
        candidate = step_move

    include_ask = reciprocity or bool(state.revealed)
    package = _compose(scenario, state, candidate, include_ask=include_ask,
                       include_sweetener=state.trust >= 60)
    state.opp_offer = package
    state.aspiration_at_last_offer = state.aspiration
    return Intent(kind=kind, offer=package, note=note)


def _respond_to_offer(scenario: Scenario, state: OpponentState,
                      persona: PersonaParams, move: Move) -> Intent:
    main = scenario.main_issue
    value = move.offer.get(main.id)

    # Пакет игрока поверх опций, уже лежащих на столе: «давайте 185» после
    # встречного «170 + пересмотр» означает 185 + пересмотр, а не голые 185.
    package: Package = {key: val for key, val in state.opp_offer.items()
                        if isinstance(val, bool)}
    package.update(move.offer)
    if value is None and state.player_offer.get(main.id) is not None:
        package[main.id] = state.player_offer[main.id]
        value = package[main.id]

    if value is not None:
        beyond = (float(value) > main.opponent_limit
                  if main.direction == "higher_better"
                  else float(value) < main.opponent_limit)
        if beyond:
            return _concede(scenario, state, persona,
                            reciprocity=move.conditional, kind="counter_offer",
                            note=f"Запрос {value:g} за пределом оппонента "
                                 f"({main.opponent_limit:g}) — встречное предложение")

    if value is not None:
        target = opponent_target(main, state.aspiration)
        threshold_package = _compose(scenario, state, _snap(target, main),
                                     include_ask=False, include_sweetener=False)
        closing_pressure = (1 - state.patience / max(1, scenario.max_turns)) * 20
        # Базовый допуск 8 б.: закрыть сделку ценнее, чем дожимать копейки.
        threshold = opponent_utility(scenario, threshold_package) \
            - closing_pressure - persona.accept_margin * 100 - 8
        if opponent_utility(scenario, package) >= threshold:
            state.opp_offer = package
            return Intent(kind="accept", offer=package, closes="deal",
                          note=f"Пакет игрока ({opponent_utility(scenario, package):.0f} б.) "
                               f"не хуже текущей цели оппонента ({threshold:.0f} б.)")

    if state.patience <= 1:
        return _final_offer(scenario, state, persona)
    return _concede(scenario, state, persona, reciprocity=move.conditional,
                    kind="counter_offer",
                    note="Предложение игрока ниже цели оппонента — торг продолжается")


def _final_offer(scenario: Scenario, state: OpponentState,
                 persona: PersonaParams) -> Intent:
    main = scenario.main_issue
    target = opponent_target(main, state.aspiration)
    # Финал вознаграждает отношения: при доверии оппонент отдаёт большую часть
    # остатка до своего предела.
    give = 0.65 if state.trust >= 50 else 0.3
    value = _snap(target + (main.opponent_limit - target) * give, main)
    value = _clamp_toward_target(value, main.opponent_limit, main)
    package = _compose(scenario, state, value, include_ask=False,
                       include_sweetener=state.trust >= 50)
    state.opp_offer = package
    state.aspiration_at_last_offer = state.aspiration
    return Intent(kind="final_offer", offer=package,
                  note="Терпение вышло: последнее предложение, дальше — разрыв")
