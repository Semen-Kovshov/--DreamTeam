"""Утилиты сторон, ZOPA и Парето-граница.

Шкала утилит — «баллы», заданные весами сценария: у главного числового вопроса
вес обычно 100, булевые опции добавляют/снимают свои баллы. Оценка позиции
нормируется на дистанцию цель–предел, поэтому направление («больше лучше» или
«меньше лучше») учитывается автоматически знаком знаменателя.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from ..scenarios.models import BooleanIssue, NumericIssue, Scenario

Package = dict[str, float | bool]


def _norm(value: float, worst: float, best: float) -> float:
    if best == worst:
        return 0.0
    return max(-0.5, min(1.5, (value - worst) / (best - worst)))


def player_utility(scenario: Scenario, package: Package) -> float:
    total = 0.0
    for issue in scenario.issues:
        if isinstance(issue, NumericIssue):
            value = package.get(issue.id)
            if value is None:
                continue
            total += issue.weight_player * _norm(
                float(value), issue.player_limit, issue.player_target)
        elif isinstance(issue, BooleanIssue) and package.get(issue.id):
            total += issue.player_value
    return round(total, 2)


def opponent_utility(scenario: Scenario, package: Package) -> float:
    total = 0.0
    for issue in scenario.issues:
        if isinstance(issue, NumericIssue):
            value = package.get(issue.id)
            if value is None:
                continue
            total += issue.weight_opponent * _norm(
                float(value), issue.opponent_limit, issue.opponent_start)
        elif isinstance(issue, BooleanIssue) and package.get(issue.id):
            total -= issue.opponent_cost
    return round(total, 2)


def zopa_capture(scenario: Scenario, package: Package) -> float | None:
    """Сколько зоны возможного соглашения по главному вопросу взял игрок."""
    main = scenario.main_issue
    value = package.get(main.id)
    if value is None or not main.has_zopa:
        return None
    share = _norm(float(value), main.player_limit, main.opponent_limit)
    return round(max(0.0, min(1.0, share)), 3)


def zopa_bounds(scenario: Scenario) -> tuple[float, float]:
    """Границы ZOPA в порядке (край игрока, край оппонента)."""
    main = scenario.main_issue
    return main.player_limit, main.opponent_limit


@dataclass
class ParetoPoint:
    package: Package
    u_player: float
    u_opponent: float


def _grid(main: NumericIssue) -> list[float]:
    lo, hi = sorted((main.player_limit, main.opponent_limit))
    steps = max(1, round((hi - lo) / main.step))
    return [round(lo + i * main.step, 6) for i in range(steps + 1)]


def pareto_frontier(scenario: Scenario) -> list[ParetoPoint]:
    """Недоминируемые пакеты в пределах ZOPA главного вопроса."""
    main = scenario.main_issue
    bools = [i for i in scenario.issues if isinstance(i, BooleanIssue)]
    points: list[ParetoPoint] = []
    for value in _grid(main):
        for combo in product([False, True], repeat=len(bools)):
            package: Package = {main.id: value}
            package.update({b.id: on for b, on in zip(bools, combo)})
            points.append(ParetoPoint(
                package, player_utility(scenario, package),
                opponent_utility(scenario, package)))

    frontier = [p for p in points
                if not any(q.u_player >= p.u_player and q.u_opponent >= p.u_opponent
                           and (q.u_player > p.u_player or q.u_opponent > p.u_opponent)
                           for q in points)]
    frontier.sort(key=lambda p: p.u_player)
    return frontier


def left_on_table(scenario: Scenario, deal: Package) -> tuple[float, Package | None]:
    """Сколько баллов игрок недобрал до Парето, не ухудшая оппоненту."""
    u_p = player_utility(scenario, deal)
    u_o = opponent_utility(scenario, deal)
    best_gain, best_package = 0.0, None
    for point in pareto_frontier(scenario):
        if point.u_opponent >= u_o - 1e-9 and point.u_player - u_p > best_gain:
            best_gain, best_package = point.u_player - u_p, point.package
    return round(best_gain, 1), best_package


def describe_package(scenario: Scenario, package: Package) -> str:
    """Пакет словами: «185 тыс. ₽ + пересмотр через полгода»."""
    parts: list[str] = []
    for issue in scenario.issues:
        value = package.get(issue.id)
        if isinstance(issue, NumericIssue) and value is not None:
            number = f"{value:g}"
            parts.append(f"{number} {issue.unit}".strip())
        elif isinstance(issue, BooleanIssue) and value:
            parts.append(issue.name.lower())
    return " + ".join(parts) if parts else "без конкретики"
