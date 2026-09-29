from __future__ import annotations

import pytest

from app.engine.outcome import (left_on_table, opponent_utility, pareto_frontier,
                                player_utility, zopa_capture)


def test_player_utility_grows_toward_target(salary):
    low = player_utility(salary, {"salary": 175})
    mid = player_utility(salary, {"salary": 185})
    top = player_utility(salary, {"salary": 200})
    assert low < mid < top
    assert low == 0 and top == 100


def test_boolean_adds_value_both_sides(salary):
    base = player_utility(salary, {"salary": 185})
    with_review = player_utility(salary, {"salary": 185, "review": True})
    assert with_review == base + 20
    # Оппоненту «да» по пересмотру стоит 8 баллов.
    assert opponent_utility(salary, {"salary": 185, "review": True}) == \
        pytest.approx(opponent_utility(salary, {"salary": 185}) - 8)


def test_lower_better_direction(supplier):
    cheap = player_utility(supplier, {"price": 1300})
    expensive = player_utility(supplier, {"price": 1400})
    assert cheap > expensive
    # А оппоненту наоборот.
    assert opponent_utility(supplier, {"price": 1300}) < \
        opponent_utility(supplier, {"price": 1400})


def test_zopa_capture_orientation(salary, supplier):
    assert zopa_capture(salary, {"salary": 175}) == 0
    assert zopa_capture(salary, {"salary": 190}) == 1
    assert 0.6 < zopa_capture(salary, {"salary": 185}) < 0.7
    assert zopa_capture(supplier, {"price": 1400}) == 0
    assert zopa_capture(supplier, {"price": 1300}) == 1


def test_pareto_frontier_nonempty_and_sorted(scenarios):
    for scenario in scenarios.values():
        frontier = pareto_frontier(scenario)
        assert frontier
        utilities = [p.u_player for p in frontier]
        assert utilities == sorted(utilities)


def test_left_on_table_positive_for_bad_package(discount):
    # Сделка без разменов: премиум-поддержку (дорога клиенту, дёшева нам)
    # не отдали — на столе остались очевидные баллы.
    gain, better = left_on_table(discount, {"discount": 14})
    assert gain > 0 and better is not None


def test_left_on_table_zero_on_frontier(salary):
    frontier = pareto_frontier(salary)
    best = max(frontier, key=lambda p: p.u_player)
    gain, _ = left_on_table(salary, best.package)
    assert gain == 0
