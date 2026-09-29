from __future__ import annotations

from app.engine.moves import Move, MoveType
from app.engine.rules import apply_moves
from app.engine.state import initial_state


def _apply(scenario, state, move, turn=3):
    return apply_moves(scenario, state, [move], turn)


def test_rapport_raises_trust(salary, state):
    before = state.trust
    _apply(salary, state, Move(type=MoveType.SMALL_TALK), turn=1)
    assert state.trust > before


def test_ultimatum_effects_depend_on_persona(salary, supplier, discount):
    for scenario, sign in ((salary, 1), (supplier, 1), (discount, -1)):
        st = initial_state(scenario)
        aspiration = st.aspiration
        _apply(scenario, st, Move(type=MoveType.ULTIMATUM))
        assert st.tension > 20
        if sign > 0:
            assert st.aspiration >= aspiration    # упёрся
        else:
            assert st.aspiration < aspiration     # мягкий поддался


def test_unconditional_concession_feeds_appetite(salary, state):
    state.player_offer = {"salary": 200}
    aspiration = state.aspiration
    _apply(salary, state, Move(type=MoveType.OFFER, offer={"salary": 190}))
    assert state.aspiration > aspiration
    assert state.unconditional_concessions == 1


def test_conditional_offer_is_not_concession(salary, state):
    state.player_offer = {"salary": 200}
    aspiration = state.aspiration
    _apply(salary, state, Move(type=MoveType.OFFER, offer={"salary": 190},
                               conditional=True))
    assert state.aspiration <= aspiration + 1e-9
    assert state.unconditional_concessions == 0
    assert state.conditional_offers == 1


def test_lever_halved_until_interest_revealed(salary):
    hidden = initial_state(salary)
    apply_moves(salary, hidden, [Move(type=MoveType.ARGUMENT,
                                      lever_id="release_value")], 3)
    drop_hidden = 1.0 - hidden.aspiration

    revealed = initial_state(salary)
    revealed.revealed.append("release_risk")
    apply_moves(salary, revealed, [Move(type=MoveType.ARGUMENT,
                                        lever_id="release_value")], 3)
    drop_revealed = 1.0 - revealed.aspiration
    assert drop_revealed > drop_hidden * 1.5


def test_repeated_lever_does_not_stack(salary, state):
    move = Move(type=MoveType.ARGUMENT, lever_id="market_data")
    _apply(salary, state, move)
    aspiration = state.aspiration
    _apply(salary, state, move)
    assert state.aspiration == aspiration    # повтор не двигает позицию


def test_question_reveals_interest_and_drops_aspiration(salary, state):
    aspiration = state.aspiration
    effects = _apply(salary, state, Move(type=MoveType.OPEN_QUESTION,
                                         interest_id="budget_review", spin="N"))
    assert "budget_review" in state.revealed
    assert state.aspiration < aspiration
    assert any("интерес" in e.reason.lower() for e in effects)


def test_batna_timing(salary):
    early = initial_state(salary)
    apply_moves(salary, early, [Move(type=MoveType.BATNA)], 1)
    assert early.tension > 20    # с порога — угроза

    late = initial_state(salary)
    late.trust = 55
    apply_moves(salary, late, [Move(type=MoveType.BATNA)], 6)
    assert late.tension == 20    # к месту — без обострения
    assert late.aspiration < 1.0


def test_every_effect_has_reason(salary, state):
    effects = _apply(salary, state, Move(type=MoveType.CRITERIA))
    assert effects and all(e.reason for e in effects)


def test_patience_ticks_every_turn(salary, state):
    patience = state.patience
    _apply(salary, state, Move(type=MoveType.OFF_TOPIC))
    assert state.patience == patience - 2    # ход + не по делу
