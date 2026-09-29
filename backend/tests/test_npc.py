from __future__ import annotations

from app.engine.moves import Move, MoveType
from app.engine.npc import decide
from app.engine.state import initial_state, opponent_target


def test_anchor_appears_when_talk_stalls(salary):
    state = initial_state(salary)
    intent = decide(salary, state, [Move(type=MoveType.ARGUMENT)], turn=2)
    assert intent.kind == "counter_offer"
    assert intent.offer["salary"] == salary.main_issue.opponent_start


def test_counter_moves_toward_player_but_not_past_target(salary):
    state = initial_state(salary)
    state.opp_offer = {"salary": 160}
    state.player_offer = {"salary": 200}
    state.aspiration = 0.7    # разговор уже сбил аппетит — есть куда двигаться
    intent = decide(salary, state,
                    [Move(type=MoveType.OFFER, offer={"salary": 200})], turn=3)
    assert intent.kind == "counter_offer"
    value = intent.offer["salary"]
    assert 160 < value <= opponent_target(salary.main_issue, state.aspiration)


def test_full_appetite_means_no_movement(salary):
    state = initial_state(salary)
    state.opp_offer = {"salary": 160}
    state.player_offer = {"salary": 200}
    intent = decide(salary, state,
                    [Move(type=MoveType.OFFER, offer={"salary": 200})], turn=3)
    assert intent.kind == "hold_firm"    # аппетит 1.0: двигаться некуда


def test_early_ambitious_offer_gets_anchor_not_empty_hold(scenarios):
    # Игрок сразу просит около предела оппонента: тому некуда «уступать»,
    # но и держать пустоту нельзя — он обязан поставить свой якорь.
    rent = scenarios["rent"]
    state = initial_state(rent)
    intent = decide(rent, state,
                    [Move(type=MoveType.OFFER, offer={"rent": 500},
                          conditional=True)], turn=1)
    assert intent.offer.get("rent") == rent.main_issue.opponent_start
    assert intent.kind == "counter_offer"


def test_counter_never_leaves_step_grid(salary):
    # Цель 169.15 лежит между шагами: оппонент держит позицию, а не предлагает
    # «продвинуться на 4.15».
    state = initial_state(salary)
    state.opp_offer = {"salary": 165}
    state.player_offer = {"salary": 200}
    state.aspiration = (169.15 - 190) / (160 - 190)
    intent = decide(salary, state,
                    [Move(type=MoveType.OFFER, offer={"salary": 200})], turn=5)
    value = intent.offer["salary"]
    assert value % salary.main_issue.step == 0
    assert intent.kind == "hold_firm"


def test_acceptance_when_offer_meets_lowered_appetite(salary):
    state = initial_state(salary)
    state.aspiration = 0.2      # аргументы и вопросы сбили аппетит
    state.trust = 60
    intent = decide(salary, state,
                    [Move(type=MoveType.OFFER, offer={"salary": 186},
                          conditional=True)], turn=8)
    assert intent.kind == "accept" and intent.closes == "deal"


def test_no_acceptance_beyond_limit(salary):
    state = initial_state(salary)
    state.aspiration = 0.05
    intent = decide(salary, state,
                    [Move(type=MoveType.OFFER, offer={"salary": 205})], turn=8)
    assert intent.closes is None    # 205 за пределом 190 — никогда


def test_walk_away_on_tension(supplier):
    state = initial_state(supplier)
    state.tension = 85
    intent = decide(supplier, state, [Move(type=MoveType.PRESSURE)], turn=4)
    assert intent.kind == "walk_away" and intent.closes == "walked_away"


def test_soft_persona_walks_earlier_and_without_warning(discount):
    state = initial_state(discount)
    state.tension = 73
    intent = decide(discount, state, [Move(type=MoveType.PRESSURE)], turn=4)
    assert intent.kind == "walk_away"


def test_final_offer_on_last_patience(salary):
    state = initial_state(salary)
    state.patience = 1
    intent = decide(salary, state, [Move(type=MoveType.ARGUMENT)], turn=11)
    assert intent.kind == "final_offer"
    assert intent.offer


def test_reveal_intent_for_fresh_interest(salary):
    from app.engine.rules import apply_moves
    state = initial_state(salary)
    moves = [Move(type=MoveType.OPEN_QUESTION, interest_id="release_risk")]
    apply_moves(salary, state, moves, 2)
    intent = decide(salary, state, moves, turn=2)
    assert intent.kind == "answer_disclose"
    assert intent.reveal_id == "release_risk"


def test_no_re_disclosure_for_known_interest(salary):
    from app.engine.rules import apply_moves
    state = initial_state(salary)
    state.revealed.append("release_risk")
    moves = [Move(type=MoveType.OPEN_QUESTION, interest_id="release_risk")]
    apply_moves(salary, state, moves, 4)
    intent = decide(salary, state, moves, turn=4)
    assert intent.kind != "answer_disclose"    # себя не пересказывает


def test_supplier_attaches_ask_to_counter(supplier):
    state = initial_state(supplier)
    state.opp_offer = {"price": 1480}
    state.player_offer = {"price": 1250}
    state.revealed.append("cashflow")
    state.aspiration = 0.8
    intent = decide(supplier, state,
                    [Move(type=MoveType.OFFER, offer={"price": 1250},
                          conditional=True)], turn=5)
    assert intent.kind == "counter_offer"
    asks = [k for k, v in intent.offer.items() if k != "price" and v]
    assert asks, "встречное без условия — оппонент упускает размен"
