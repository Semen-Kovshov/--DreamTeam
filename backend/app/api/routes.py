"""HTTP-слой поверх движка. Логики здесь нет — только маршрутизация и коды."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import HISTORY_FILE
from ..engine.session import MODES, Session, load_session
from ..llm import llm_status
from ..scenarios.models import Scenario

router = APIRouter(prefix="/api")

_scenarios: dict[str, Scenario] = {}
_sessions: dict[str, Session] = {}


def bind(scenarios: dict[str, Scenario]) -> None:
    _scenarios.clear()
    _scenarios.update(scenarios)
    _sessions.clear()


def _session(session_id: str) -> Session:
    session = _sessions.get(session_id)
    if session is None:
        # Партии переживают рестарт процесса: пробуем поднять с диска.
        session = load_session(session_id, _scenarios)
        if session is not None:
            _sessions[session.id] = session
    if session is None:
        raise HTTPException(404, "сессия не найдена — начните новую партию из каталога")
    return session


@router.get("/health")
def health() -> dict:
    return {"ok": True, "llm": llm_status(), "scenarios": len(_scenarios)}


@router.get("/scenarios")
def scenarios() -> list[dict]:
    return [s.card() for s in _scenarios.values()]


@router.get("/scenarios/{scenario_id}/brief")
def scenario_brief(scenario_id: str) -> dict:
    """Публичная карта подготовки — доступна с брифа, до старта партии."""
    scenario = _scenarios.get(scenario_id)
    if scenario is None:
        raise HTTPException(404, "сценарий не найден")
    from ..engine.session import public_issues
    player = scenario.player
    return {
        "setting": scenario.setting,
        "role": player.role, "goal": player.goal,
        "batna": player.batna_text, "facts": player.facts,
        "criteria": player.criteria,
        "issues": public_issues(scenario),
    }


class StartRequest(BaseModel):
    scenario_id: str
    mode: str = "free"
    use_llm: bool = True


@router.post("/sessions")
def start(request: StartRequest) -> dict:
    scenario = _scenarios.get(request.scenario_id)
    if scenario is None:
        raise HTTPException(404, "сценарий не найден")
    if request.mode not in MODES:
        raise HTTPException(422, f"режим должен быть одним из {MODES}")
    session = Session(scenario, request.mode, request.use_llm)
    _sessions[session.id] = session
    return session.start_payload()


class TurnRequest(BaseModel):
    text: str


@router.post("/sessions/{session_id}/turns")
def turn(session_id: str, request: TurnRequest) -> dict:
    session = _session(session_id)
    text = request.text.strip()
    if not text:
        raise HTTPException(422, "пустая реплика")
    if len(text) > 1000:
        raise HTTPException(422, "реплика слишком длинная (до 1000 знаков)")
    try:
        return session.apply_turn(text)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get("/sessions/{session_id}/hints")
def hints(session_id: str) -> dict:
    return {"hints": _session(session_id).hints()}


class ActionRequest(BaseModel):
    action_id: str


@router.post("/sessions/{session_id}/actions")
def game_action(session_id: str, request: ActionRequest) -> dict:
    try:
        return _session(session_id).apply_game_action(request.action_id)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


class FinishRequest(BaseModel):
    action: str    # accept | leave


@router.post("/sessions/{session_id}/finish")
def finish(session_id: str, request: FinishRequest) -> dict:
    try:
        return _session(session_id).finish(request.action)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get("/sessions/{session_id}/debrief")
def debrief(session_id: str) -> dict:
    try:
        return _session(session_id).debrief()
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get("/history")
def history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    records = []
    for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records[-50:][::-1]
