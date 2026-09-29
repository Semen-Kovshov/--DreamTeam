"""Корпус реплик: эвристика должна узнавать типовые формулировки."""

from __future__ import annotations

import pytest

from app.engine.moves import MoveType
from app.engine.state import initial_state
from app.nlu.heuristics import classify_heuristic


def types(scenario, text, state=None):
    state = state or initial_state(scenario)
    return {m.type for m in classify_heuristic(text, scenario, state)}


def test_greeting(salary):
    assert MoveType.SMALL_TALK in types(salary, "Здравствуйте! Как добрались?")


def test_open_question_hits_interest(salary):
    moves = classify_heuristic(
        "Что вам нужно, чтобы согласовать пересмотр с финансовым директором?",
        salary, initial_state(salary))
    q = next(m for m in moves if m.type == MoveType.OPEN_QUESTION)
    assert q.interest_id == "budget_review"


def test_closed_question(salary):
    assert MoveType.CLOSED_QUESTION in types(
        salary, "Есть ли у вас бюджет на этот год?")


def test_active_listening(salary):
    assert MoveType.ACTIVE_LISTENING in types(
        salary, "Правильно понимаю, что вам важно не сорвать релиз?")


def test_empathy(discount):
    assert MoveType.EMPATHY in types(
        discount, "Понимаю вас, урезание бюджета — это правда непросто.")


def test_criteria_numbers_are_not_offer(salary):
    got = types(salary, "По рынку вилка для моего грейда — 190–220, вот отчёт HH.")
    assert MoveType.CRITERIA in got
    assert MoveType.OFFER not in got


def test_batna_number_is_not_offer(salary):
    got = types(salary, "У меня есть оффер на 185, но я хочу остаться в команде.")
    assert MoveType.BATNA in got
    assert MoveType.OFFER not in got


def test_conditional_package_offer(salary):
    moves = classify_heuristic(
        "Если зафиксируем пересмотр через полгода — готов на 190.",
        salary, initial_state(salary))
    offer = next(m for m in moves if m.type == MoveType.OFFER)
    assert offer.conditional
    assert offer.offer["salary"] == 190
    assert offer.offer.get("review") is True


def test_ultimatum_with_number(salary):
    got = types(salary, "Или 200 — или я ухожу.")
    assert MoveType.ULTIMATUM in got
    assert MoveType.OFFER in got


def test_rudeness(supplier):
    assert MoveType.RUDENESS in types(supplier, "Вы издеваетесь? Это чушь.")


def test_accept_needs_offer_on_table(salary):
    state = initial_state(salary)
    assert MoveType.ACCEPT not in types(salary, "Согласен, по рукам.", state)
    state.opp_offer = {"salary": 180}
    assert MoveType.ACCEPT in types(salary, "Согласен, по рукам.", state)


def test_lever_argument(supplier):
    moves = classify_heuristic(
        "В следующем году мы открываем шесть точек — это плюс сорок процентов объёма.",
        supplier, initial_state(supplier))
    assert any(m.lever_id == "volume_growth" for m in moves)


def test_irritant_attached(supplier):
    moves = classify_heuristic("Ну просто скиньте цену и всё.",
                               supplier, initial_state(supplier))
    assert any(m.irritant_id == "naked_haggle" for m in moves)


def test_off_topic_short_noise(salary):
    assert types(salary, "Ну ок.") == {MoveType.OFF_TOPIC}


@pytest.mark.parametrize("text,spin", [
    ("Как у вас сейчас устроено согласование бюджета?", "S"),
    ("Что мешает закрыть вопрос с наймом?", "P"),
    ("Что будет, если позиция останется пустой три месяца?", "I"),
    ("Что для вас изменится, если релиз выйдет вовремя?", "N"),
])
def test_spin_typing(salary, text, spin):
    moves = classify_heuristic(text, salary, initial_state(salary))
    q = next(m for m in moves
             if m.type in (MoveType.OPEN_QUESTION, MoveType.CLOSED_QUESTION))
    assert q.spin == spin
