"""Объединение путей распознавания.

Основной путь — LLM, но маленькой модели нельзя доверять структурные детали:
она теряет условность и вопросы, путает числа BATNA с предложением, дорисовывает
лишние ходы. Поэтому слияние полевое: семантика (тип хода, SPIN, интерес) — от
модели, факты (числа, опции, «если…, то…», тон, вопросная форма) — от эвристик.
Без модели работает чисто эвристический путь.
"""

from __future__ import annotations

from ..engine.moves import Move, MoveType
from ..engine.state import OpponentState
from ..llm import LLMClient, LLMError
from ..scenarios.models import Scenario
from .heuristics import _match_irritant, classify_heuristic, context_flags, norm
from .llm_classify import classify_llm

QUESTION_TYPES = (MoveType.OPEN_QUESTION, MoveType.CLOSED_QUESTION)


def _clean_llm_moves(moves: list[Move]) -> list[Move]:
    """Модель любит продублировать предложение и повесить SPIN не на вопрос."""
    seen_offer = False
    cleaned: list[Move] = []
    for move in moves:
        if move.type == MoveType.OFFER:
            if seen_offer:
                continue
            seen_offer = True
        if move.type not in QUESTION_TYPES:
            move.spin = None
        cleaned.append(move)
    return cleaned


def _drop_phantom_offer(moves: list[Move], flags: dict,
                        heur_offer: Move | None) -> list[Move]:
    """Число из BATNA или критерия («оффер на 185») — не предложение игрока."""
    if heur_offer is not None or not (flags["batna"] or flags["criteria"]):
        return moves
    return [m for m in moves if m.type != MoveType.OFFER]


def _merge_offer(moves: list[Move], heur_offer: Move | None,
                 conditional: bool) -> list[Move]:
    """Числа и условность решают регулярки, состав пакета — обе стороны."""
    llm_offer = next((m for m in moves if m.type == MoveType.OFFER), None)
    if llm_offer is None and heur_offer is not None:
        heur_offer.conditional = heur_offer.conditional or conditional
        return moves + [heur_offer]
    if llm_offer is not None:
        merged = dict(llm_offer.offer)
        if heur_offer is not None:
            merged.update(heur_offer.offer)   # у эвристики числа точнее
        llm_offer.offer = merged
        llm_offer.conditional = (llm_offer.conditional or conditional
                                 or bool(heur_offer and heur_offer.conditional))
        llm_offer.has_number = any(
            not isinstance(v, bool) for v in merged.values())
    return moves


def _restore_question(moves: list[Move], heuristic: list[Move],
                      flags: dict) -> list[Move]:
    """Вопрос — двигатель SPIN-механики: модель не вправе его терять."""
    heur_question = next((m for m in heuristic if m.type in QUESTION_TYPES), None)
    llm_question = next((m for m in moves if m.type in QUESTION_TYPES), None)
    if heur_question is None:
        return moves
    if llm_question is None:
        if flags["is_question"]:
            moves = moves + [heur_question]
        return moves
    # Вопрос есть у обеих сторон — добираем интерес и SPIN из лексиконов.
    if llm_question.interest_id is None:
        llm_question.interest_id = heur_question.interest_id
    if llm_question.spin is None:
        llm_question.spin = heur_question.spin
    return moves


def classify(text: str, scenario: Scenario, state: OpponentState,
             client: LLMClient | None, npc_last: str = "") -> list[Move]:
    heuristic = classify_heuristic(text, scenario, state)
    if client is None:
        return heuristic

    try:
        moves = classify_llm(client, text, scenario, state, npc_last)
    except LLMError:
        return heuristic

    flags = context_flags(text, scenario)
    heur_offer = next((m for m in heuristic if m.type == MoveType.OFFER), None)

    moves = _clean_llm_moves(moves)
    moves = _drop_phantom_offer(moves, flags, heur_offer)
    moves = _merge_offer(moves, heur_offer, flags["conditional"])
    moves = _restore_question(moves, heuristic, flags)

    llm_types = {m.type for m in moves}
    heur_types = {m.type for m in heuristic}

    # Тон и BATNA дешевле перебдеть: пропущенный ультиматум сломал бы
    # честность правил, а BATNA имеет цену в разборе. Галлюцинацию BATNA,
    # наоборот, не пускаем без подтверждения лексикона.
    moves = [m for m in moves
             if m.type != MoveType.BATNA or MoveType.BATNA in heur_types]
    for backfill in (MoveType.ULTIMATUM, MoveType.RUDENESS, MoveType.BATNA):
        if backfill not in llm_types and backfill in heur_types:
            moves.append(next(m for m in heuristic if m.type == backfill))

    # Модель часто вешает рычаг на эмпатию или критерий — правила же считают
    # аргументом только ход ARGUMENT. Переносим рычаг в явный аргумент.
    lever_ids = [m.lever_id for m in moves if m.lever_id] \
        + [m.lever_id for m in heuristic if m.lever_id]
    if lever_ids and not any(m.type == MoveType.ARGUMENT for m in moves):
        moves.append(Move(type=MoveType.ARGUMENT, lever_id=lever_ids[0],
                          has_number=any(ch.isdigit() for ch in text)))

    if not moves:
        return heuristic
    if irritant := _match_irritant(scenario, norm(text)):
        if not any(m.irritant_id for m in moves):
            moves[0].irritant_id = irritant
    return moves[:4]
