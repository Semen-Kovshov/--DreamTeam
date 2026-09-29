"""Контур администратора: генерация, валидация, сохранение, удаление."""

from __future__ import annotations

import json
import shutil

import pytest
from fastapi.testclient import TestClient

from app.config import SCENARIOS_DIR
from app.scenarios.generate import GenerationContext, generate_scenario
from app.scenarios.models import Scenario


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Каталог сценариев — во временной копии: админ пишет и удаляет файлы."""
    import app.api.admin as admin
    import app.scenarios.loader as loader
    from app.main import app

    scenarios_dir = tmp_path / "scenarios"
    shutil.copytree(SCENARIOS_DIR, scenarios_dir)
    monkeypatch.setattr(loader, "SCENARIOS_DIR", scenarios_dir)
    monkeypatch.setattr(admin, "SCENARIOS_DIR", scenarios_dir)
    with TestClient(app) as test_client:
        yield test_client


def _draft(client) -> dict:
    """Валидный черновик: копия встроенного сценария под новым id."""
    draft = json.loads((SCENARIOS_DIR / "salary.json").read_text(encoding="utf-8"))
    draft["id"] = "custom-case"
    draft["title"] = "Кастомный кейс"
    return draft


def test_admin_list_marks_builtin(client):
    rows = client.get("/api/admin/scenarios").json()
    assert {r["id"] for r in rows} >= {"salary", "supplier", "discount", "rent"}
    assert all(r["builtin"] for r in rows if r["id"] == "salary")


def test_validate_reports_errors(client):
    bad = {"id": "x", "title": "т"}
    result = client.post("/api/admin/scenarios/validate",
                         json={"scenario": bad}).json()
    assert not result["ok"] and result["errors"]

    good = client.post("/api/admin/scenarios/validate",
                       json={"scenario": _draft(client)}).json()
    assert good["ok"] and good["card"]["id"] == "custom-case"


def test_save_appears_in_player_catalog_and_deletes(client):
    draft = _draft(client)
    saved = client.post("/api/admin/scenarios", json={"scenario": draft}).json()
    assert saved["ok"]

    # Настройка администратора немедленно влияет на каталог игрока.
    cards = client.get("/api/scenarios").json()
    assert "custom-case" in {c["id"] for c in cards}

    # Партия по кастомному сценарию запускается.
    start = client.post("/api/sessions", json={
        "scenario_id": "custom-case", "mode": "free", "use_llm": False}).json()
    assert start["opening"]

    # Повторное сохранение без overwrite — конфликт; с overwrite — ок.
    assert client.post("/api/admin/scenarios",
                       json={"scenario": draft}).status_code == 409
    assert client.post("/api/admin/scenarios",
                       json={"scenario": draft, "overwrite": True}).json()["ok"]

    assert client.delete("/api/admin/scenarios/custom-case").json()["ok"]
    cards = client.get("/api/scenarios").json()
    assert "custom-case" not in {c["id"] for c in cards}


def test_builtin_protected(client):
    draft = _draft(client)
    draft["id"] = "salary"
    assert client.post("/api/admin/scenarios",
                       json={"scenario": draft, "overwrite": True}).status_code == 409
    assert client.delete("/api/admin/scenarios/salary").status_code == 409
    assert client.delete("/api/admin/scenarios/no-such").status_code == 404


# --- генератор: фиксеры чинят типовые ошибки модели ----------------------


class FakeLLM:
    def __init__(self, core: dict, templates: dict):
        self.replies = [core, templates]

    def complete_json(self, messages, schema, max_tokens=0):
        return self.replies.pop(0)


def _fake_core() -> dict:
    return {
        "title": "Аренда склада под маркетплейс",
        "summary": "Согласовать ставку аренды склада.",
        "setting": "Офис логопарка, обсуждение договора аренды склада 2000 м².",
        "opponent_name": "Пётр",
        "opponent_voice": "деловой, суховатый",
        "opening": "Слушаю вас. Ставка вам известна.",
        "player_goal": "Снизить ставку и получить каникулы",
        "batna_text": "Склад дальше от города",
        "batna_score": 120,                       # вне диапазона — зажмётся
        "facts": ["ф1", "ф2", "ф3", "ф4"],
        "criteria": ["критерий 1", "критерий 2"],
        "main_issue": {
            "name": "Ставка аренды", "unit": "₽/м²",
            "direction": "higher_better",         # неверно: числа говорят lower
            "step": 10,
            "player_target": 480, "player_limit": 560,
            "opponent_start": 520, "opponent_limit": 640,  # перепутаны местами
        },
        "options": [
            {"id": "long", "name": "Договор на 3 года", "player_value": -5,
             "opponent_cost": -15, "ask_phrase": "договор на три года"},
            {"id": "long", "name": "Дубль id", "player_value": 0,
             "opponent_cost": 0, "ask_phrase": "дубль"},
        ],
        "interests": [
            {"id": "vacancy", "text": "боится простоя", "reveal_line": "Пустует…",
             "topics": ["просто", "пусту"], "probe": "Как с заполняемостью?"},
            {"id": "cash", "text": "кассовый разрыв", "reveal_line": "Кредит…",
             "topics": ["кредит"], "probe": "Как с финансированием?"},
            {"id": "ops", "text": "устал от заявок", "reveal_line": "Заявки…",
             "topics": ["заявк"], "probe": "Что даёт хлопоты?"},
        ],
        "levers": [
            {"id": "l1", "text": "якорный арендатор", "phrase": "Мы якорь.",
             "interest_id": "nope", "aspiration_drop": 0.9, "keywords": ["якор"]},
            {"id": "l2", "text": "долгий договор", "phrase": "Три года.",
             "interest_id": "cash", "aspiration_drop": 0.15, "keywords": ["три года"]},
            {"id": "l3", "text": "своя эксплуатация", "phrase": "Сами обслуживаем.",
             "interest_id": "ops", "aspiration_drop": 0.12, "keywords": ["сами"]},
        ],
        "irritants": [
            {"id": "cheap", "text": "обесценивание объекта",
             "keywords": ["сарай"], "tension_add": 50},
        ],
        "events": [
            {"turn": 20, "title": "Звонок", "text": "Звонит брокер.",
             "aspiration_add": -0.5, "patience_add": -5, "tension_add": 30},
        ],
    }


def _fake_templates() -> dict:
    from app.engine.npc import INTENT_KINDS
    templates = {kind: [f"Реплика {kind}.", f"Вариант {kind}."]
                 for kind in INTENT_KINDS}
    templates["counter_offer"] = ["Моё встречное без плейсхолдера."]  # починится
    templates["answer_disclose"] = ["своими словами"]                 # заменится
    return templates


def test_generator_fixers_produce_valid_scenario():
    ctx = GenerationContext(
        sphere="Логистика", topic="аренда склада 2000 м² под маркетплейс",
        player_role="Операционный директор", opponent_role="Владелец логопарка",
        persona="positional", difficulty=3)
    draft, warnings = generate_scenario(FakeLLM(_fake_core(), _fake_templates()),
                                        ctx, taken_ids={"salary"})
    scenario = Scenario.model_validate(draft)

    main = scenario.main_issue
    assert main.direction == "lower_better"          # по числам игрока
    assert main.has_zopa                             # пределы пересекаются
    assert scenario.opponent.levers[0].interest_id in \
        {i.id for i in scenario.opponent.interests}  # битая ссылка починена
    assert all(0 < l.aspiration_drop <= 0.3 for l in scenario.opponent.levers)
    assert scenario.opponent.templates["answer_disclose"] == ["{reveal}"]
    assert all("{offer}" in t for t in scenario.opponent.templates["counter_offer"])
    assert scenario.max_turns == 14                  # сложность 3
    assert scenario.player.batna_score <= 60
    assert len({i.id for i in scenario.issues}) == len(scenario.issues)
    assert warnings, "фиксеры обязаны отчитаться о правках"


def test_generator_respects_admin_numbers():
    ctx = GenerationContext(
        sphere="Логистика", topic="аренда склада: ставка за квадратный метр",
        player_role="Директор", opponent_role="Владелец",
        persona="hard", difficulty=1, unit="₽/м²",
        player_target=450, player_limit=540, opponent_start=600,
        opponent_limit=500)
    draft, _ = generate_scenario(FakeLLM(_fake_core(), _fake_templates()),
                                 ctx, taken_ids=set())
    scenario = Scenario.model_validate(draft)
    main = scenario.main_issue
    assert (main.player_target, main.player_limit) == (450, 540)
    assert (main.opponent_start, main.opponent_limit) == (600, 500)
    assert main.unit == "₽/м²"
    assert scenario.opponent.persona == "hard"
    assert scenario.max_turns == 10
