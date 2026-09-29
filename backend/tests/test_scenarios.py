"""Сценарии — данные, поэтому их целостность проверяется как код."""

from __future__ import annotations

from app.engine.npc import INTENT_KINDS as NPC_INTENTS


def test_three_scenarios_with_distinct_personas(scenarios):
    assert len(scenarios) >= 3
    personas = {s.opponent.persona for s in scenarios.values()}
    assert personas == {"soft", "positional", "hard"}


def test_zopa_exists_everywhere(scenarios):
    for scenario in scenarios.values():
        assert scenario.main_issue.has_zopa, scenario.id


def test_templates_cover_every_intent(scenarios):
    for scenario in scenarios.values():
        missing = NPC_INTENTS - set(scenario.opponent.templates)
        assert not missing, f"{scenario.id}: нет шаблонов {missing}"
        for kind, variants in scenario.opponent.templates.items():
            assert variants, f"{scenario.id}/{kind}: пустой список"


def test_offer_templates_carry_placeholder(scenarios):
    for scenario in scenarios.values():
        for kind in ("counter_offer", "final_offer", "accept", "hold_firm",
                     "partial_concede"):
            for tpl in scenario.opponent.templates[kind]:
                assert "{offer}" in tpl, f"{scenario.id}/{kind}: без {{offer}}"
        for tpl in scenario.opponent.templates["answer_disclose"]:
            assert "{reveal}" in tpl


def test_interests_have_probes_and_topics(scenarios):
    for scenario in scenarios.values():
        for interest in scenario.opponent.interests:
            assert interest.topics and interest.probe and interest.reveal_line


def test_cards_do_not_leak_hidden_fields(scenarios):
    for scenario in scenarios.values():
        card = scenario.card()
        text = str(card)
        assert "opponent_limit" not in text
        assert "reveal_line" not in text
        assert "aspiration" not in text
