from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    data = client.get("/api/health").json()
    assert data["ok"] and data["scenarios"] >= 3
    assert "llm" in data


def test_catalog(client):
    cards = client.get("/api/scenarios").json()
    assert {c["id"] for c in cards} >= {"salary", "supplier", "discount", "rent"}
    assert all(c["skills"] for c in cards)
    # Публичный мандат игрока — для мини-карт брифа (эталон 4b).
    assert all("goal_value" in c and "limit_value" in c and "unit" in c
               for c in cards)
    # Оформление и оценка времени — данные сценария, не код фронтенда.
    assert all(c["palette"]["from"].startswith("#")
               and c["palette"]["to"].startswith("#")
               and c["est_minutes"] > 0 for c in cards)


def test_scenario_brief_endpoint(client):
    brief = client.get("/api/scenarios/salary/brief").json()
    assert brief["facts"] and brief["goal"] and brief["issues"]
    assert "reveal_line" not in str(brief), "карта подготовки не течёт скрытым"
    assert client.get("/api/scenarios/nope/brief").status_code == 404


def test_full_flow(client):
    start = client.post("/api/sessions", json={
        "scenario_id": "salary", "mode": "training", "use_llm": False}).json()
    session_id = start["session_id"]
    assert start["opening"]
    assert start["brief"]["issues"]

    hints = client.get(f"/api/sessions/{session_id}/hints").json()["hints"]
    assert len(hints) == 3

    turn = client.post(f"/api/sessions/{session_id}/turns", json={
        "text": "Что вам нужно, чтобы согласовать пересмотр с финдиром?"}).json()
    assert turn["npc_text"]
    assert turn["status"] == "active"
    assert turn["meters"]["trust"] is not None

    finish = client.post(f"/api/sessions/{session_id}/finish",
                         json={"action": "leave"}).json()
    assert finish["status"] == "no_deal"

    debrief = client.get(f"/api/sessions/{session_id}/debrief").json()
    assert debrief["overall"]["grade"]
    assert len(debrief["competencies"]) == 5

    history = client.get("/api/history").json()
    assert history and history[0]["scenario_id"] == "salary"


def test_errors(client):
    assert client.post("/api/sessions", json={
        "scenario_id": "nope", "mode": "free"}).status_code == 404
    assert client.get("/api/sessions/unknown/hints").status_code == 404

    start = client.post("/api/sessions", json={
        "scenario_id": "salary", "use_llm": False}).json()
    sid = start["session_id"]
    assert client.post(f"/api/sessions/{sid}/turns",
                       json={"text": "  "}).status_code == 422
    assert client.get(f"/api/sessions/{sid}/debrief").status_code == 409
