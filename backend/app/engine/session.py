"""Партия переговоров: применение хода, журнал, закрытие, разбор.

Сессия живёт в памяти процесса и после каждого хода сбрасывается на диск
(`data/sessions/*.json`): рестарт бэкенда посреди партии — в том числе на
защите — не обрывает игру, API молча поднимает её с диска. Полный журнал
(включая скрытые эффекты аппетита) хранится для разбора; в живую выдачу идут
только видимые индикаторы — фронтенд физически не может подсмотреть скрытое
состояние.
"""

from __future__ import annotations

import dataclasses
import json
import time
import uuid

from ..config import HISTORY_FILE, SESSIONS_DIR
from ..llm import get_client
from ..nlu.pipeline import classify
from ..scenarios.models import BooleanIssue, NumericIssue, Scenario
from . import npc, phrasing, rules
from .actions import ACTIONS, action_catalog, apply_action
from .debrief import build_debrief
from .hints import build_hints, build_tips
from .moves import MOVE_LABELS, Move
from .npc import Intent
from .outcome import describe_package
from .state import Effect, OpponentState, initial_state

MODES = ("training", "free", "exam")

# Пороги раздумья в режиме со счётом времени (free): колебание заметно,
# затяжка жжёт терпение. Секунды.
THINK_SOFT, THINK_HARD = 75, 150
ACTIONS_PER_GAP = 2     # не больше двух жестов между репликами


def npc_mood(intent_kind: str | None, state: OpponentState) -> str:
    """Эмоция персонажа для сцены: calm | pleased | tense | angry."""
    if intent_kind in ("walk_away", "warn"):
        return "angry"
    if intent_kind == "accept":
        return "pleased"
    if intent_kind in ("final_offer", "deescalate"):
        return "tense"
    if state.tension >= 70:
        return "angry"
    if state.tension >= 50:
        return "tense"
    if state.trust >= 60:
        return "pleased"
    return "calm"


def public_issues(scenario: Scenario) -> list[dict]:
    """Вопросы торга глазами игрока — без пределов и костов оппонента."""
    out = []
    for issue in scenario.issues:
        if isinstance(issue, NumericIssue):
            out.append({"id": issue.id, "kind": "numeric", "name": issue.name,
                        "unit": issue.unit, "direction": issue.direction,
                        "player_target": issue.player_target,
                        "player_limit": issue.player_limit})
        elif isinstance(issue, BooleanIssue):
            out.append({"id": issue.id, "kind": "boolean", "name": issue.name,
                        "ask_phrase": issue.ask_phrase,
                        "good_for_player": issue.player_value > 0})
    return out


class Session:
    def __init__(self, scenario: Scenario, mode: str = "free",
                 use_llm: bool = True):
        if mode not in MODES:
            raise ValueError(f"неизвестный режим: {mode}")
        self.id = uuid.uuid4().hex[:12]
        self.scenario = scenario
        self.mode = mode
        self.use_llm = use_llm
        self.state: OpponentState = initial_state(scenario)
        self.status = "active"
        self.deal: dict | None = None
        self.turns: list[dict] = []
        self.turn_n = 0
        self.llm_turns = 0
        self.started_at = time.time()
        self.finished_at: float | None = None
        self.last_reply_at = time.time()
        self.last_intent_kind: str | None = None
        self.action_counts: dict[str, int] = {}
        self.action_last_turn: dict[str, int] = {}
        self.actions_in_gap = 0
        self.history: list[tuple[str, str]] = [
            ("opponent", scenario.opponent.opening)]

    # --- ход игрока -----------------------------------------------------

    def apply_turn(self, text: str) -> dict:
        if self.status != "active":
            raise ValueError("партия уже завершена")
        thinking = time.time() - self.last_reply_at
        self.turn_n += 1
        self.actions_in_gap = 0
        client = get_client() if self.use_llm else None

        moves = classify(text, self.scenario, self.state, client)
        effects = rules.apply_moves(self.scenario, self.state, moves, self.turn_n)
        self._apply_thinking_time(thinking, effects)
        event = self._fire_event(effects)

        intent = npc.decide(self.scenario, self.state, moves, self.turn_n)
        intent = self._deadline_override(intent)
        npc_text, npc_source, voice_note = phrasing.speak(
            client, self.scenario, self.state, intent, text,
            self.history, self.turn_n)
        if npc_source == "llm":
            self.llm_turns += 1

        if intent.closes:
            self.status = "deal" if intent.closes == "deal" else intent.closes
            if intent.closes == "deal":
                self.deal = dict(intent.offer)
        if self.status != "active":
            self.finished_at = time.time()

        self.history.append(("player", text))
        self.history.append(("opponent", npc_text))
        self.last_intent_kind = intent.kind
        self.last_reply_at = time.time()

        log = {
            "kind": "turn",
            "at_seconds": round(time.time() - self.started_at),
            "n": self.turn_n,
            "player_text": text,
            "moves": [m.model_dump() for m in moves],
            "effects": [e.as_dict() for e in effects],
            "event": event,
            "intent": intent.model_dump(),
            "npc_text": npc_text,
            "npc_source": npc_source,
            "voice_note": voice_note,
            "thinking_seconds": round(thinking),
            "meters": self.state.meters(hide=False),
        }
        self.turns.append(log)
        if self.status != "active":
            self._write_history()
        self._persist()
        return self._turn_payload(log)

    def _apply_thinking_time(self, thinking: float, effects: list[Effect]) -> None:
        """Средний режим считает время: длинная пауза читается как колебание.

        Первый ход не судится (игрок читает бриф и вступление), действия
        обновляют отсчёт — глоток воды легально «покупает» раздумье.
        """
        if self.mode != "free" or self.turn_n < 2:
            return
        extra: list[Effect] = []
        if thinking > THINK_HARD:
            extra.append(Effect("aspiration", 0.03,
                                f"Ответ занял {thinking:.0f} сек — затянувшееся "
                                "молчание читается как слабость позиции"))
            extra.append(Effect("patience", -1,
                                "Долгие раздумья съедают время встречи"))
        elif thinking > THINK_SOFT:
            extra.append(Effect("aspiration", 0.02,
                                f"Пауза {thinking:.0f} сек перед ответом — "
                                "колебание заметно"))
        if extra:
            self.state.apply(extra)
            effects.extend(extra)

    # --- действия-мелочи --------------------------------------------------

    def action_status(self) -> list[dict]:
        out = []
        for action in ACTIONS.values():
            uses = self.action_counts.get(action.id, 0)
            last = self.action_last_turn.get(action.id)
            cooling = last is not None and self.turn_n - last < action.cooldown
            reason = ""
            if uses >= action.max_uses:
                reason = "жест исчерпан"
            elif cooling:
                reason = "слишком часто"
            elif self.actions_in_gap >= ACTIONS_PER_GAP:
                reason = "сначала скажите что-нибудь"
            out.append({"id": action.id, "available": not reason,
                        "reason": reason, "uses_left": action.max_uses - uses})
        return out

    def apply_game_action(self, action_id: str) -> dict:
        if self.status != "active":
            raise ValueError("партия уже завершена")
        action = ACTIONS.get(action_id)
        if action is None:
            raise ValueError(f"неизвестное действие: {action_id}")
        status = next(s for s in self.action_status() if s["id"] == action_id)
        if not status["available"]:
            raise ValueError(f"действие недоступно: {status['reason']}")

        uses = self.action_counts.get(action_id, 0)
        effects, remark = apply_action(self.scenario, self.state, action_id,
                                       self.turn_n, uses, self.last_intent_kind)
        self.state.apply(effects)
        self.action_counts[action_id] = uses + 1
        self.action_last_turn[action_id] = self.turn_n
        self.actions_in_gap += 1
        self.last_reply_at = time.time()    # жест «оправдывает» паузу
        if remark:
            self.history.append(("opponent", remark))

        log = {
            "kind": "action",
            "at_seconds": round(time.time() - self.started_at),
            "n": self.turn_n,
            "action_id": action_id,
            "player_text": "",
            "narrative": action.narrative,
            "moves": [],
            "effects": [e.as_dict() for e in effects],
            "event": None,
            "intent": None,
            "npc_text": remark,
            "npc_source": "template",
            "meters": self.state.meters(hide=False),
        }
        self.turns.append(log)
        self._persist()
        exam = self.mode == "exam"
        return {
            "session_id": self.id,
            "kind": "action",
            "narrative": action.narrative,
            "npc_text": remark,
            "npc_mood": npc_mood(None, self.state),
            "meters": self.state.meters(hide=exam),
            "effects": [] if exam else self._visible_effects(log),
            "actions": self.action_status(),
        }

    def _fire_event(self, effects: list[Effect]) -> dict | None:
        event = next((e for e in self.scenario.events if e.turn == self.turn_n), None)
        if not event:
            return None
        extra: list[Effect] = []
        if event.aspiration_add:
            extra.append(Effect("aspiration", event.aspiration_add,
                                f"Событие: {event.title}"))
        if event.tension_add:
            extra.append(Effect("tension", event.tension_add,
                                f"Событие: {event.title}"))
        if event.patience_add:
            extra.append(Effect("patience", event.patience_add,
                                f"Событие: {event.title}"))
        self.state.apply(extra)
        effects.extend(extra)
        return {"title": event.title, "text": event.text}

    def _deadline_override(self, intent: Intent) -> Intent:
        """Второго «финального предложения» не бывает — дальше только выход."""
        if intent.kind == "final_offer":
            if self.state.final_given:
                self.status = "expired"
                return Intent(kind="walk_away", closes=None,
                              note="Финальное предложение осталось без ответа — время вышло")
            self.state.final_given = True
        return intent

    # --- явное завершение -----------------------------------------------

    def finish(self, action: str) -> dict:
        if self.status != "active":
            raise ValueError("партия уже завершена")
        if action == "accept":
            if not self.state.opp_offer:
                raise ValueError("на столе нет предложения оппонента")
            self.status = "deal"
            self.deal = dict(self.state.opp_offer)
            note = "Игрок принял предложение кнопкой"
        elif action == "leave":
            self.status = "no_deal"
            note = "Игрок вышел из переговоров"
        else:
            raise ValueError(f"неизвестное действие: {action}")
        self.finished_at = time.time()
        self.turns.append({
            "kind": "turn",
            "at_seconds": round(time.time() - self.started_at),
            "n": self.turn_n + 1, "player_text": f"[{note}]", "moves": [],
            "effects": [], "event": None,
            "intent": Intent(kind="accept" if action == "accept" else "walk_away",
                             offer=self.deal or {}, note=note).model_dump(),
            "npc_text": "", "npc_source": "template",
            "meters": self.state.meters(hide=False),
        })
        self._write_history()
        self._persist()
        return {"status": self.status}

    # --- выдача ----------------------------------------------------------

    def _visible_effects(self, log: dict) -> list[dict]:
        return [e for e in log["effects"] if e["meter"] in ("trust", "tension")]

    def _turn_payload(self, log: dict) -> dict:
        exam = self.mode == "exam"
        payload = {
            "session_id": self.id,
            "kind": "turn",
            "turn": log["n"],
            "status": self.status,
            "npc_text": log["npc_text"],
            "npc_source": log["npc_source"],
            "npc_mood": npc_mood((log.get("intent") or {}).get("kind"), self.state),
            "voice_note": log.get("voice_note", ""),
            "event": log["event"],
            "meters": self.state.meters(hide=exam),
            "moves": [] if exam else [
                {"label": MOVE_LABELS[Move(**m).type], **_move_chip(m)}
                for m in log["moves"]],
            "effects": [] if exam else self._visible_effects(log),
            "actions": self.action_status(),
        }
        if self.mode == "free":
            payload["thinking_seconds"] = log.get("thinking_seconds")
        if self.status != "active":
            payload["deal_text"] = (describe_package(self.scenario, self.deal)
                                    if self.deal else None)
            if self.deal:
                payload["deal_value"] = self.deal.get(self.scenario.main_issue.id)
        if self.state.opp_offer and self.status == "active":
            payload["on_table"] = describe_package(self.scenario, self.state.opp_offer)
            payload["on_table_value"] = self.state.opp_offer.get(
                self.scenario.main_issue.id)
        return payload

    def start_payload(self) -> dict:
        player = self.scenario.player
        return {
            "session_id": self.id,
            "mode": self.mode,
            "scenario": self.scenario.card(),
            "setting": self.scenario.setting,
            "brief": {
                "role": player.role, "goal": player.goal,
                "batna": player.batna_text, "facts": player.facts,
                "criteria": player.criteria,
                "issues": public_issues(self.scenario),
            },
            "opening": self.scenario.opponent.opening,
            "meters": self.state.meters(hide=self.mode == "exam"),
            "max_turns": self.scenario.max_turns,
            "npc_mood": "calm",
            "action_catalog": action_catalog(),
            "actions": self.action_status(),
            "timed": self.mode == "free",
            "think_soft": THINK_SOFT,
            "think_hard": THINK_HARD,
        }

    def hints(self) -> list[dict]:
        """Обучение — готовые формулировки; свободный — советы-направления."""
        if self.mode == "training":
            return build_hints(self.scenario, self.state, self.turn_n)
        if self.mode == "free":
            last_event = None
            if self.turns and self.turns[-1].get("event"):
                last_event = self.turns[-1]["event"]["title"]
            return build_tips(self.scenario, self.state, last_event)
        return []

    def debrief(self) -> dict:
        if self.status == "active":
            raise ValueError("партия ещё идёт")
        result = build_debrief(self.scenario, self.state, self.status,
                               self.deal, self.turns, self.llm_turns > 0)
        result["scenario"] = self.scenario.card()
        result["mode"] = self.mode
        result["transcript"] = [self._transcript_turn(t) for t in self.turns]
        result["opening"] = self.scenario.opponent.opening
        result["duration_seconds"] = round(
            (self.finished_at or time.time()) - self.started_at)
        result["finished_at"] = self.finished_at
        return result

    def _transcript_turn(self, log: dict) -> dict:
        return {
            "kind": log.get("kind", "turn"),
            "at_seconds": log.get("at_seconds"),
            "n": log["n"],
            "player_text": log["player_text"],
            "narrative": log.get("narrative", ""),
            "moves": [{"label": MOVE_LABELS[Move(**m).type], **_move_chip(m)}
                      for m in log["moves"]],
            "effects": log["effects"],
            "event": log["event"],
            "npc_text": log["npc_text"],
            "npc_source": log["npc_source"],
            "npc_note": (log.get("intent") or {}).get("note", ""),
            "thinking_seconds": log.get("thinking_seconds"),
            "meters": log["meters"],
        }

    # --- живучесть -------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "scenario_id": self.scenario.id,
            "mode": self.mode,
            "use_llm": self.use_llm,
            "status": self.status,
            "deal": self.deal,
            "turn_n": self.turn_n,
            "llm_turns": self.llm_turns,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "last_intent_kind": self.last_intent_kind,
            "action_counts": self.action_counts,
            "action_last_turn": self.action_last_turn,
            "actions_in_gap": self.actions_in_gap,
            "history": [list(pair) for pair in self.history],
            "turns": self.turns,
            "state": dataclasses.asdict(self.state),
        }

    @classmethod
    def restore(cls, data: dict, scenario: Scenario) -> "Session":
        session = cls(scenario, data["mode"], data["use_llm"])
        session.id = data["id"]
        session.status = data["status"]
        session.deal = data["deal"]
        session.turn_n = data["turn_n"]
        session.llm_turns = data["llm_turns"]
        session.started_at = data["started_at"]
        session.finished_at = data.get("finished_at")
        session.last_intent_kind = data.get("last_intent_kind")
        session.action_counts = data.get("action_counts", {})
        session.action_last_turn = data.get("action_last_turn", {})
        session.actions_in_gap = data.get("actions_in_gap", 0)
        session.history = [(role, text) for role, text in data["history"]]
        session.turns = data["turns"]
        session.state = OpponentState(**data["state"])
        return session

    def _persist(self) -> None:
        try:
            SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
            path = SESSIONS_DIR / f"{self.id}.json"
            path.write_text(json.dumps(self.to_dict(), ensure_ascii=False),
                            encoding="utf-8")
        except Exception:
            pass    # диск — страховка, не условие игры

    def _write_history(self) -> None:
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            economics = self.debrief()
            record = {
                "finished_at": time.time(),
                "session_id": self.id,
                "scenario_id": self.scenario.id,
                "scenario_title": self.scenario.title,
                "mode": self.mode,
                "status": self.status,
                "turns": self.turn_n,
                "overall": economics["overall"],
                "deal_text": economics.get("deal_text"),
            }
            with HISTORY_FILE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass    # журнал — удобство, не функциональность: игру не роняем


def load_session(session_id: str,
                 scenarios: dict[str, Scenario]) -> Session | None:
    """Поднять партию с диска — после рестарта процесса."""
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists() or not session_id.isalnum():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        scenario = scenarios.get(data.get("scenario_id", ""))
        if scenario is None:
            return None
        return Session.restore(data, scenario)
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def _move_chip(move_dict: dict) -> dict:
    chip = {}
    if move_dict.get("spin"):
        chip["spin"] = move_dict["spin"]
    if move_dict.get("conditional"):
        chip["conditional"] = True
    return chip
