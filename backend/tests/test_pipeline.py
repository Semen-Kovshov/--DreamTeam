"""Слияние LLM-разметки с эвристиками: факты побеждают галлюцинации."""

from __future__ import annotations

from app.engine.moves import MoveType
from app.engine.rules import apply_moves
from app.engine.moves import Move
from app.engine.state import initial_state
from app.nlu.pipeline import classify


class FakeClient:
    """Дуck-тип LLMClient: отдаёт заранее заданный JSON классификатора."""

    def __init__(self, data):
        self.data = data

    def complete_json(self, messages, schema, max_tokens=500):
        return self.data


def test_conditional_recovered_from_text(salary):
    # Модель увидела предложение, но потеряла условность и опцию пакета.
    client = FakeClient({"moves": [
        {"type": "offer", "offer_value": 190, "conditional": False},
    ]})
    moves = classify("Если зафиксируем пересмотр через полгода — готов на 190.",
                     salary, initial_state(salary), client)
    offer = next(m for m in moves if m.type == MoveType.OFFER)
    assert offer.conditional, "условность обязана вернуться из текста"
    assert offer.offer.get("review") is True
    assert offer.offer["salary"] == 190


def test_llm_batna_requires_lexicon_confirmation(salary):
    client = FakeClient({"moves": [
        {"type": "offer", "offer_value": 190},
        {"type": "batna"},
    ]})
    moves = classify("Предлагаю 190.", salary, initial_state(salary), client)
    assert MoveType.BATNA not in {m.type for m in moves}


def test_lever_rehomed_into_argument(salary):
    # Модель повесила рычаг на эмпатию — правила считают аргументом только ARGUMENT.
    client = FakeClient({"moves": [
        {"type": "empathy", "lever_id": "market_data"},
    ]})
    moves = classify("Понимаю вас. Кстати, по рынку вилка совсем другая.",
                     salary, initial_state(salary), client)
    argument = next((m for m in moves if m.type == MoveType.ARGUMENT), None)
    assert argument is not None and argument.lever_id == "market_data"


def test_missed_ultimatum_restored(salary):
    client = FakeClient({"moves": [{"type": "offer", "offer_value": 200}]})
    moves = classify("Или 200 — или я ухожу.", salary, initial_state(salary), client)
    assert MoveType.ULTIMATUM in {m.type for m in moves}


def test_llm_failure_falls_back_to_heuristics(salary):
    class BrokenClient:
        def complete_json(self, *args, **kwargs):
            raise RuntimeError("нет сети")

    from app.llm import LLMError

    class Broken:
        def complete_json(self, *args, **kwargs):
            raise LLMError("нет сети")

    moves = classify("Что вам нужно, чтобы согласовать пересмотр с финдиром?",
                     salary, initial_state(salary), Broken())
    assert any(m.type == MoveType.OPEN_QUESTION for m in moves)


def test_interest_revealed_by_non_question_move(salary):
    state = initial_state(salary)
    apply_moves(salary, state,
                [Move(type=MoveType.EMPATHY, interest_id="budget_review")], 3)
    assert "budget_review" in state.revealed


def test_lost_question_restored_with_interest(salary):
    # Модель увидела в вопросе только аргумент — вопросная механика не должна
    # пропасть: интерес обязан открыться.
    client = FakeClient({"moves": [
        {"type": "argument", "lever_id": "release_value"},
    ]})
    moves = classify("Что будет с релизом, если мою позицию придётся закрывать наймом?",
                     salary, initial_state(salary), client)
    question = next((m for m in moves if m.type == MoveType.OPEN_QUESTION), None)
    assert question is not None and question.interest_id == "release_risk"


def test_interest_backfilled_into_llm_question(salary):
    client = FakeClient({"moves": [
        {"type": "open_question", "spin": "P"},
    ]})
    moves = classify("Что вам нужно, чтобы согласовать пересмотр с финдиром?",
                     salary, initial_state(salary), client)
    question = next(m for m in moves if m.type == MoveType.OPEN_QUESTION)
    assert question.interest_id == "budget_review"
    assert question.spin == "P"      # разметка модели не затирается


def test_batna_number_not_turned_into_offer(salary):
    client = FakeClient({"moves": [
        {"type": "batna"},
        {"type": "offer", "offer_value": 185},
    ]})
    moves = classify("У меня есть оффер на 185, но я хочу остаться.",
                     salary, initial_state(salary), client)
    got = {m.type for m in moves}
    assert MoveType.BATNA in got
    assert MoveType.OFFER not in got


def test_batna_backfilled_when_llm_missed(salary):
    client = FakeClient({"moves": [{"type": "argument"}]})
    moves = classify("У меня есть оффер на 185, но я хочу остаться.",
                     salary, initial_state(salary), client)
    assert MoveType.BATNA in {m.type for m in moves}
