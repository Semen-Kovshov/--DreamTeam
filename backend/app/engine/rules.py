"""Правила: как ходы игрока меняют состояние оппонента.

Каждый эффект несёт причину — из них складывается аннотированная стенограмма
и разбор. Ядро намеренно детерминированное: одна и та же партия воспроизводится
один в один, любую цифру можно объяснить.
"""

from __future__ import annotations

from ..scenarios.models import Scenario
from .moves import Move, MoveType
from .outcome import player_utility
from .state import PERSONAS, Effect, OpponentState, PersonaParams


def _decay(base: float, uses: int, rate: float = 0.6) -> float:
    """Повторение одного приёма даёт всё меньше: rate^uses."""
    return base * (rate ** uses)


def apply_moves(scenario: Scenario, state: OpponentState, moves: list[Move],
                turn: int) -> list[Effect]:
    persona = PERSONAS[scenario.opponent.persona]
    state.last_revealed = None
    effects: list[Effect] = [Effect("patience", -1, "Ход разговора")]

    for move in moves:
        effects += _apply_one(scenario, state, persona, move, turn)

    state.apply(effects)
    for move in moves:
        key = move.type.value
        state.move_counts[key] = state.move_counts.get(key, 0) + 1
        state.closed_streak = (state.closed_streak + 1
                               if move.type == MoveType.CLOSED_QUESTION else 0)
    return effects


def _apply_one(scenario: Scenario, state: OpponentState, persona: PersonaParams,
               move: Move, turn: int) -> list[Effect]:
    opponent = scenario.opponent
    uses = state.move_counts.get(move.type.value, 0)
    out: list[Effect] = []

    if move.type == MoveType.SMALL_TALK:
        gain = _decay(4 if turn <= 2 else 1.5, uses)
        if gain >= 0.5:
            out.append(Effect("trust", gain, "Раппорт: разговор о человеке, не о позиции"))

    elif move.type in (MoveType.OPEN_QUESTION, MoveType.CLOSED_QUESTION):
        out += _question_effects(state, persona, move, uses)

    elif move.type == MoveType.ACTIVE_LISTENING:
        out.append(Effect("trust", _decay(5, uses), "Активное слушание: оппонент чувствует, что услышан"))
        if state.tension > 25:
            out.append(Effect("tension", -_decay(6, uses), "Пересказ снижает накал"))

    elif move.type == MoveType.EMPATHY:
        out.append(Effect("tension", -_decay(8, uses), "Признание позиции гасит напряжение"))
        out.append(Effect("trust", _decay(3, uses), "Эмпатия укрепляет контакт"))

    elif move.type == MoveType.ARGUMENT:
        out += _argument_effects(scenario, state, persona, move)

    elif move.type == MoveType.CRITERIA:
        drop = _decay(0.05 * persona.criteria_mult, state.criteria_count, 0.5)
        out.append(Effect("aspiration", -drop,
                          "Объективный критерий: спорить с рынком труднее, чем с человеком"))
        out.append(Effect("trust", _decay(3, state.criteria_count, 0.5),
                          "Разговор ушёл от «хочу» к проверяемым основаниям"))
        state.criteria_count += 1

    elif move.type == MoveType.OFFER:
        out += _offer_effects(scenario, state, persona, move)

    elif move.type == MoveType.BATNA:
        out += _batna_effects(state, persona, move, turn)

    elif move.type == MoveType.ULTIMATUM:
        out.append(Effect("tension", 15 * persona.tension_sensitivity,
                          "Ультиматум: угроза вместо аргумента"))
        sign = "Жёсткость упёрлась в жёсткость" if persona.ultimatum_aspiration > 0 \
            else "Оппонент поддался давлению — но запомнил его"
        out.append(Effect("aspiration", persona.ultimatum_aspiration, sign))

    elif move.type == MoveType.PRESSURE:
        out.append(Effect("tension", 8 * persona.tension_sensitivity,
                          "Давление без аргументов подогревает конфликт"))
        if abs(persona.pressure_aspiration) > 1e-9:
            reason = ("Попытку продавить встречают упрямством"
                      if persona.pressure_aspiration > 0
                      else "Оппонент избегает конфликта и подаётся назад")
            out.append(Effect("aspiration", persona.pressure_aspiration, reason))

    elif move.type == MoveType.RUDENESS:
        out.append(Effect("tension", 18 * persona.tension_sensitivity,
                          "Грубость бьёт по отношениям"))
        out.append(Effect("trust", -10, "Личный выпад не забудется"))

    elif move.type == MoveType.OFF_TOPIC:
        out.append(Effect("patience", -1, "Разговор ушёл в сторону — время горит"))

    # Интерес выходит на стол с любым ходом, который его коснулся: вопросом,
    # эмпатией по больной теме, аргументом рядом с ней. Вопросные бонусы SPIN
    # начисляются в _question_effects.
    if move.interest_id and move.interest_id not in state.revealed \
            and move.type not in (MoveType.OPEN_QUESTION, MoveType.CLOSED_QUESTION):
        state.revealed.append(move.interest_id)
        state.last_revealed = move.interest_id
        out.append(Effect("aspiration", -0.04,
                          "Скрытый интерес вышел на стол — о нём можно торговаться"))

    if move.irritant_id:
        irritant = next((i for i in opponent.irritants if i.id == move.irritant_id), None)
        if irritant:
            out.append(Effect("tension", irritant.tension_add * persona.tension_sensitivity,
                              f"Больная мозоль: {irritant.text.lower()}"))
    return out


def _question_effects(state: OpponentState, persona: PersonaParams,
                      move: Move, uses: int) -> list[Effect]:
    out: list[Effect] = []
    if move.type == MoveType.OPEN_QUESTION:
        out.append(Effect("trust", _decay(2.5, uses, 0.75),
                          "Открытый вопрос: интерес к позиции собеседника"))
    else:
        if state.closed_streak >= 2:
            out.append(Effect("tension", 4, "Серия закрытых вопросов похожа на допрос"))
            out.append(Effect("patience", -1, "Закрытые вопросы не двигают разговор"))

    if move.interest_id and move.interest_id not in state.revealed:
        state.revealed.append(move.interest_id)
        state.last_revealed = move.interest_id
        out.append(Effect("aspiration", -0.04,
                          "Скрытый интерес вышел на стол — о нём можно торговаться"))
        if move.spin == "I":
            out.append(Effect("aspiration", -0.02,
                              "Извлекающий вопрос: оппонент сам ощутил цену проблемы"))
        if move.spin == "N":
            out.append(Effect("aspiration", -0.04,
                              "Направляющий вопрос: оппонент сам проговорил ценность решения"))
    return out


def _argument_effects(scenario: Scenario, state: OpponentState,
                      persona: PersonaParams, move: Move) -> list[Effect]:
    out: list[Effect] = []
    lever = next((l for l in scenario.opponent.levers if l.id == move.lever_id), None)
    if lever:
        if lever.id in state.levers_used:
            out.append(Effect("tension", 2, f"Аргумент «{lever.text[:40]}…» уже прозвучал — повтор утомляет"))
            return out
        state.levers_used.append(lever.id)
        drop = lever.aspiration_drop * persona.argument_mult
        reason = f"Аргумент попал в интерес: {lever.text.lower()}"
        if lever.interest_id and lever.interest_id not in state.revealed:
            drop *= 0.5
            reason += " (но боль ещё не вскрыта вопросами — эффект вполсилы)"
        out.append(Effect("aspiration", -drop, reason))
        out.append(Effect("trust", 2, "Предметный разговор укрепляет доверие"))
    elif move.has_number:
        out.append(Effect("aspiration", -0.02, "Довод с цифрой: считаемое трудно отмахнуть"))
    else:
        uses = state.move_counts.get(MoveType.ARGUMENT.value, 0)
        if uses >= 2:
            out.append(Effect("tension", 2, "Повтор общих доводов без новых фактов"))
        else:
            out.append(Effect("aspiration", -0.005, "Общий довод без опоры на факты"))
    return out


def _offer_effects(scenario: Scenario, state: OpponentState,
                   persona: PersonaParams, move: Move) -> list[Effect]:
    out: list[Effect] = []
    main = scenario.main_issue
    value = move.offer.get(main.id)

    if state.made_first_offer is None:
        state.made_first_offer = "player"
        if value is not None:
            better = max if main.direction == "higher_better" else min
            beyond_target = better(float(value), main.player_target) == float(value) \
                and float(value) != main.player_target
            if beyond_target:
                span = abs(main.player_target - main.player_limit)
                overshoot = abs(float(value) - main.player_target)
                if overshoot > span:
                    out.append(Effect("tension", 6, "Якорь оторван от реальности — выглядит несерьёзно"))
                else:
                    out.append(Effect("aspiration", -0.03,
                                      "Уверенный якорь: точка отсчёта сместилась к вам"))

    if move.conditional:
        state.conditional_offers += 1
        out.append(Effect("trust", 2, "Условное предложение — размен, а не отступление"))
    elif _is_concession(scenario, state, move):
        state.unconditional_concessions += 1
        step = 0.04 + 0.02 * (state.unconditional_concessions - 1)
        if scenario.opponent.persona == "hard":
            step += 0.02
        out.append(Effect("aspiration", step,
                          "Односторонняя уступка: дают — значит, можно просить ещё"))

    if move.offer:
        state.player_offer = dict(move.offer)
    return out


def _is_concession(scenario: Scenario, state: OpponentState, move: Move) -> bool:
    """Предложение хуже для игрока, чем его же предыдущее, без условий."""
    if not state.player_offer or not move.offer:
        return False
    return (player_utility(scenario, move.offer)
            < player_utility(scenario, state.player_offer) - 1e-9)


def _batna_effects(state: OpponentState, persona: PersonaParams,
                   move: Move, turn: int) -> list[Effect]:
    out: list[Effect] = []
    state.batna_mentions += 1
    if state.batna_mentions > 1:
        out.append(Effect("tension", 4, "Повторное махание альтернативой звучит как шантаж"))
        return out
    if turn <= 2:
        out.append(Effect("tension", 8, "Альтернатива с порога — угроза, а не информация"))
        out.append(Effect("aspiration", -0.02, "Но услышал: вариант у вас есть"))
    elif state.trust >= 40 or state.levers_used:
        out.append(Effect("aspiration", -0.06,
                          "Альтернатива прозвучала спокойно и по делу — она реальна"))
    else:
        out.append(Effect("tension", 5, "Альтернатива при низком доверии слышится как давление"))
        out.append(Effect("aspiration", -0.03, "Хотя вариант, видимо, есть"))
    return out
