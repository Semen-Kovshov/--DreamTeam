"""Состояние оппонента и параметры персон.

Аппетит (aspiration) — главный рычаг исхода: доля дистанции от предела
оппонента до его стартовой позиции, которую он рассчитывает удержать.
1.0 — верит, что продавит свой старт; чем ниже, тем ближе его цель к пределу.
Хорошие ходы игрока снижают аппетит, слабые (быстрые уступки, слитая BATNA) —
повышают.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..scenarios.models import NumericIssue, Persona, Scenario


@dataclass(frozen=True)
class PersonaParams:
    concede_rate: float          # шаг уступки к предложению игрока
    tension_sensitivity: float   # множитель роста напряжения
    warn_threshold: float | None  # с какого напряжения предупреждает (None — молчит)
    walk_threshold: float        # с какого — уходит
    argument_mult: float         # чувствительность к рычагам
    criteria_mult: float         # чувствительность к объективным критериям
    pressure_aspiration: float   # реакция аппетита на давление (+ упирается)
    ultimatum_aspiration: float
    accept_margin: float         # поблажка при приёмке (+ легче соглашается)


PERSONAS: dict[Persona, PersonaParams] = {
    # Мягкий: поддаётся давлению, не предупреждает — молча копит и обрывает.
    "soft": PersonaParams(concede_rate=0.45, tension_sensitivity=1.3,
                          warn_threshold=None, walk_threshold=72,
                          argument_mult=1.0, criteria_mult=0.8,
                          pressure_aspiration=-0.03, ultimatum_aspiration=-0.05,
                          accept_margin=0.05),
    # Позиционный: торгуется цифрами, уважает критерии, предупреждает о тоне.
    "positional": PersonaParams(concede_rate=0.30, tension_sensitivity=1.0,
                                warn_threshold=65, walk_threshold=85,
                                argument_mult=1.0, criteria_mult=1.6,
                                pressure_aspiration=0.02, ultimatum_aspiration=0.02,
                                accept_margin=0.0),
    # Жёсткий: на давление отвечает упрямством, уступает медленно и по делу.
    "hard": PersonaParams(concede_rate=0.22, tension_sensitivity=0.8,
                          warn_threshold=60, walk_threshold=80,
                          argument_mult=1.1, criteria_mult=1.0,
                          pressure_aspiration=0.03, ultimatum_aspiration=0.05,
                          accept_margin=-0.03),
}


@dataclass
class Effect:
    """Одно изменение состояния с человекочитаемой причиной — провенанс исхода."""
    meter: str        # trust | tension | aspiration | patience
    delta: float
    reason: str

    def as_dict(self) -> dict:
        return {"meter": self.meter, "delta": round(self.delta, 3),
                "reason": self.reason}


@dataclass
class OpponentState:
    trust: float = 40.0
    tension: float = 20.0
    aspiration: float = 1.0
    patience: int = 12
    revealed: list[str] = field(default_factory=list)       # интересы
    levers_used: list[str] = field(default_factory=list)
    criteria_count: int = 0
    batna_mentions: int = 0
    move_counts: dict[str, int] = field(default_factory=dict)
    closed_streak: int = 0
    opp_offer: dict[str, float | bool] = field(default_factory=dict)
    player_offer: dict[str, float | bool] = field(default_factory=dict)
    unconditional_concessions: int = 0
    conditional_offers: int = 0
    made_first_offer: str | None = None    # "player" | "opponent"
    aspiration_at_last_offer: float = 1.0  # для решения о встречном улучшении
    final_given: bool = False              # финальное предложение уже прозвучало
    last_revealed: str | None = None       # интерес, раскрытый на текущем ходе

    def apply(self, effects: list[Effect]) -> None:
        for e in effects:
            if e.meter == "trust":
                self.trust = min(100.0, max(0.0, self.trust + e.delta))
            elif e.meter == "tension":
                self.tension = min(100.0, max(0.0, self.tension + e.delta))
            elif e.meter == "aspiration":
                self.aspiration = min(1.15, max(0.05, self.aspiration + e.delta))
            elif e.meter == "patience":
                self.patience = max(0, self.patience + int(e.delta))

    def meters(self, hide: bool = False) -> dict:
        """Индикаторы для фронтенда; в экзамене скрываются до разбора."""
        if hide:
            return {"trust": None, "tension": None, "patience": self.patience}
        return {"trust": round(self.trust), "tension": round(self.tension),
                "patience": self.patience}


def opponent_target(issue: NumericIssue, aspiration: float) -> float:
    """На какое значение главного вопроса оппонент сейчас рассчитывает."""
    return issue.opponent_limit + aspiration * (issue.opponent_start
                                                - issue.opponent_limit)


def initial_state(scenario: Scenario) -> OpponentState:
    return OpponentState(patience=scenario.max_turns)
