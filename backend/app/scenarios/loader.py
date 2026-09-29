"""Загрузка сценариев из data/scenarios/*.json с валидацией."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ..config import SCENARIOS_DIR
from .models import Scenario


class ScenarioError(Exception):
    pass


def load_scenario(path: Path) -> Scenario:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Scenario.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as error:
        raise ScenarioError(f"{path.name}: {error}") from error


def load_all(directory: Path | None = None) -> dict[str, Scenario]:
    directory = directory or SCENARIOS_DIR
    scenarios: dict[str, Scenario] = {}
    for path in sorted(directory.glob("*.json")):
        scenario = load_scenario(path)
        if scenario.id in scenarios:
            raise ScenarioError(f"{path.name}: дублирующийся id {scenario.id}")
        scenarios[scenario.id] = scenario
    if not scenarios:
        raise ScenarioError(f"в {directory} нет ни одного сценария")
    return scenarios
