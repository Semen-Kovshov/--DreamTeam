"""Действия-мелочи и учёт времени ответа."""

from __future__ import annotations

import pytest

from app.engine.actions import ACTIONS, action_catalog
from app.engine.session import THINK_HARD, THINK_SOFT, Session


def test_actions_content_is_data_driven():
    """Контент жестов приходит из data/actions.json и полон."""
    catalog = action_catalog()
    assert len(catalog) == 6
    assert all(item["word"] and item["label"] and item["hint"]
               for item in catalog)
    for action in ACTIONS.values():
        assert set(action.remarks) == {"soft", "positional", "hard"}, action.id
        assert all(action.remarks.values()), action.id


def test_water_cools_tension(salary):
    session = Session(salary, use_llm=False)
    session.state.tension = 40
    payload = session.apply_game_action("water")
    assert payload["kind"] == "action"
    assert payload["narrative"]
    assert session.state.tension < 40
    assert session.turns[-1]["kind"] == "action"


def test_phone_gesture_depends_on_persona(scenarios):
    soft = Session(scenarios["discount"], use_llm=False)
    soft.apply_game_action("phone")
    assert soft.state.tension > 20, "мягкую персону телефон обижает"

    hard = Session(scenarios["supplier"], use_llm=False)
    aspiration = hard.state.aspiration
    hard.apply_game_action("phone")
    assert hard.state.aspiration < aspiration, "жёсткий читает жест как силу"


def test_pause_presses_only_after_their_offer(salary):
    idle = Session(salary, use_llm=False)
    patience = idle.state.patience
    idle.apply_game_action("pause")
    assert idle.state.patience == patience - 1, "пауза в пустоту тянет время"

    after_offer = Session(salary, use_llm=False)
    after_offer.last_intent_kind = "counter_offer"
    aspiration = after_offer.state.aspiration
    after_offer.apply_game_action("pause")
    assert after_offer.state.aspiration < aspiration, "тишина давит на продавца"


def test_action_cooldown_and_limit(salary):
    session = Session(salary, use_llm=False)
    session.apply_game_action("water")
    with pytest.raises(ValueError, match="недоступно"):
        session.apply_game_action("water")    # кулдаун в тот же ход

    # Два жеста между репликами — можно, третий — нет.
    session.apply_game_action("notebook")
    with pytest.raises(ValueError, match="недоступно"):
        session.apply_game_action("watch")
    session.apply_turn("Здравствуйте!")
    payload = session.apply_game_action("watch")
    assert payload["meters"]


def test_repeat_action_decays(salary):
    session = Session(salary, use_llm=False)
    session.state.tension = 60
    session.apply_game_action("water")
    first_drop = 60 - session.state.tension
    session.apply_turn("Здравствуйте!")
    session.apply_turn("Что вам нужно, чтобы согласовать пересмотр?")
    session.apply_turn("Расскажите про бюджет на этот год.")
    before = session.state.tension
    session.apply_game_action("water")
    second_drop = before - session.state.tension
    assert second_drop < first_drop


def test_actions_survive_restart(salary, scenarios):
    from app.engine.session import load_session
    session = Session(salary, use_llm=False)
    session.apply_game_action("water")
    revived = load_session(session.id, scenarios)
    assert revived.action_counts == {"water": 1}
    with pytest.raises(ValueError, match="недоступно"):
        revived.apply_game_action("water")


def test_thinking_time_counted_in_free_mode(salary):
    session = Session(salary, mode="free", use_llm=False)
    session.apply_turn("Здравствуйте!")
    aspiration = session.state.aspiration
    session.last_reply_at -= THINK_SOFT + 10     # «думали» 85 секунд
    payload = session.apply_turn("Что вам нужно, чтобы согласовать пересмотр?")
    assert session.state.aspiration > aspiration - 0.04, "колебание съело эффект вопроса"
    reasons = [e["reason"] for e in session.turns[-1]["effects"]]
    assert any("Пауза" in r or "колебание" in r.lower() for r in reasons)
    assert payload["thinking_seconds"] >= THINK_SOFT


def test_long_stall_burns_patience(salary):
    session = Session(salary, mode="free", use_llm=False)
    session.apply_turn("Здравствуйте!")
    patience = session.state.patience
    session.last_reply_at -= THINK_HARD + 30
    session.apply_turn("Ну, я подумал ещё немного.")
    assert session.state.patience <= patience - 2    # ход + сгоревшее время


def test_training_mode_ignores_time(salary):
    session = Session(salary, mode="training", use_llm=False)
    session.apply_turn("Здравствуйте!")
    session.last_reply_at -= 500
    session.apply_turn("Что вам нужно, чтобы согласовать пересмотр?")
    reasons = [e["reason"] for e in session.turns[-1]["effects"]]
    assert not any("колебание" in r.lower() for r in reasons)


def test_action_resets_thinking_clock(salary):
    session = Session(salary, mode="free", use_llm=False)
    session.apply_turn("Здравствуйте!")
    session.last_reply_at -= THINK_SOFT + 10
    session.apply_game_action("water")           # жест «оправдывает» паузу
    session.apply_turn("Что вам нужно, чтобы согласовать пересмотр?")
    reasons = [e["reason"] for e in session.turns[-1]["effects"]]
    assert not any("колебание" in r.lower() for r in reasons)
