from __future__ import annotations

import pytest

from app.engine.state import initial_state
from app.scenarios.loader import load_all


@pytest.fixture(scope="session")
def scenarios():
    return load_all()


@pytest.fixture(scope="session")
def salary(scenarios):
    return scenarios["salary"]


@pytest.fixture(scope="session")
def supplier(scenarios):
    return scenarios["supplier"]


@pytest.fixture(scope="session")
def discount(scenarios):
    return scenarios["discount"]


@pytest.fixture
def state(salary):
    return initial_state(salary)


@pytest.fixture(autouse=True)
def _storage_to_tmp(tmp_path, monkeypatch):
    """Журнал игр и снимки сессий — во временные файлы, не в data/ разработчика."""
    import app.api.routes as routes
    import app.engine.session as session
    target = tmp_path / "history.jsonl"
    monkeypatch.setattr(session, "HISTORY_FILE", target)
    monkeypatch.setattr(routes, "HISTORY_FILE", target)
    monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path / "sessions")
    yield
