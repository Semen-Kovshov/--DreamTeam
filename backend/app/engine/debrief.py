"""Разбор партии: компетенции, ключевые моменты, рекомендации.

Каждый балл выводится из журнала ходов и объясняется словами — «почему такая
оценка» важнее самой оценки, это и есть обучающая часть тренажёра.
"""

from __future__ import annotations

from ..scenarios.models import Scenario
from .moves import MoveType
from .outcome import (Package, describe_package, left_on_table, player_utility,
                      opponent_utility, zopa_bounds, zopa_capture)
from .state import OpponentState


def _clamp(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _best_offer_on_table(scenario: Scenario, turns: list[dict]) -> Package | None:
    """Лучший для игрока пакет, который оппонент реально предлагал."""
    best, best_u = None, float("-inf")
    for turn in turns:
        offer = (turn.get("intent") or {}).get("offer") or {}
        if not offer:
            continue
        u = player_utility(scenario, offer)
        if u > best_u:
            best, best_u = offer, u
    return best


def _score_preparation(scenario: Scenario, state: OpponentState, status: str,
                       deal: Package | None, turns: list[dict]) -> tuple[int, str]:
    batna = scenario.player.batna_score
    if status == "deal" and deal is not None:
        u = player_utility(scenario, deal)
        if u < batna:
            return 15, (f"Сделка ({u:.0f} б.) хуже вашей альтернативы ({batna:.0f} б.) — "
                        "BATNA существует ровно затем, чтобы такого не подписывать")
        score = 70.0
        comment = f"Сделка ({u:.0f} б.) лучше альтернативы ({batna:.0f} б.) — порог выдержан"
        if (capture := zopa_capture(scenario, deal)) and capture >= 0.5:
            score += 15
            comment += "; взяли больше половины ZOPA"
        if state.batna_mentions == 1:
            score += 15
            comment += "; альтернатива прозвучала один раз и к месту"
        elif state.batna_mentions > 1:
            score -= 10
            comment += "; альтернативой размахивали повторно — это уже шантаж"
        return _clamp(score), comment

    best = _best_offer_on_table(scenario, turns)
    best_u = player_utility(scenario, best) if best else None
    if status == "walked_away":
        return 20, "Оппонент прервал переговоры — отношения дороже одного раунда"
    if best_u is not None and best_u >= batna:
        return 25, (f"Вы ушли, хотя на столе лежало {best_u:.0f} б. — лучше вашей "
                    f"альтернативы ({batna:.0f} б.)")
    return 80, ("Правильный выход: всё предложенное было хуже вашей альтернативы, "
                "уйти — тоже результат")


def _score_interests(scenario: Scenario, state: OpponentState,
                     turns: list[dict]) -> tuple[int, str]:
    total = len(scenario.opponent.interests)
    revealed = len(state.revealed)
    open_questions = sum(1 for t in turns for m in t["moves"]
                         if m["type"] == MoveType.OPEN_QUESTION.value)
    score = 70 * revealed / max(1, total) + min(30, 10 * open_questions)
    comment = f"Раскрыто интересов: {revealed} из {total}; открытых вопросов: {open_questions}"
    if revealed == total:
        comment += " — вся карта интересов на столе"
    elif revealed == 0:
        comment = ("Ни один скрытый интерес не вскрыт — торг шёл вслепую, "
                   "только о цифре")
    return _clamp(score), comment


def _score_argumentation(scenario: Scenario, state: OpponentState,
                         turns: list[dict]) -> tuple[int, str]:
    total = len(scenario.opponent.levers)
    used = len(state.levers_used)
    numeric_args = sum(1 for t in turns for m in t["moves"]
                       if m["type"] == MoveType.ARGUMENT.value and m["has_number"])
    score = 60 * used / max(1, total)
    parts = [f"аргументов-попаданий: {used} из {total}"]
    if state.criteria_count:
        score += 25
        parts.append("объективные критерии прозвучали")
    if numeric_args:
        score += 15
        parts.append("доводы подкреплены цифрами")
    return _clamp(score), "; ".join(parts).capitalize()


def _score_relations(turns: list[dict]) -> tuple[int, str]:
    trusts = [40.0] + [t["meters"]["trust"] for t in turns if t.get("meters")]
    tensions = [20.0] + [t["meters"]["tension"] for t in turns if t.get("meters")]
    avg_trust = sum(trusts) / len(trusts)
    peak = max(tensions)
    score = 0.6 * avg_trust + 0.4 * (100 - peak)
    comment = f"Среднее доверие {avg_trust:.0f}, пик напряжения {peak:.0f}"
    if peak >= 70:
        comment += " — разговор побывал на грани разрыва"
    elif peak <= 35 and avg_trust >= 55:
        comment += " — партнёрская атмосфера всю партию"
    return _clamp(score), comment


def _score_bargaining(scenario: Scenario, state: OpponentState, status: str,
                      deal: Package | None) -> tuple[int, str]:
    if status != "deal" or deal is None:
        if status == "expired":
            return 20, "Время вышло без сделки — торг не дошёл до развязки"
        return (55, "Сделки нет, но выход был обоснован") if status == "no_deal" \
            else (15, "Торг закончился разрывом отношений")

    capture = zopa_capture(scenario, deal) or 0.0
    score = 25 + 50 * capture
    parts = [f"взято {capture * 100:.0f}% зоны возможного соглашения"]
    if state.conditional_offers:
        score += 10
        parts.append("уступки шли с условиями")
    if state.made_first_offer == "player":
        score += 10
        parts.append("якорь поставили вы")
    if state.unconditional_concessions:
        score -= 12 * state.unconditional_concessions
        parts.append(f"односторонних уступок: {state.unconditional_concessions}")
    return _clamp(score), "; ".join(parts).capitalize()


GRADES = [(85, "Мастер сделки"), (70, "Уверенный переговорщик"),
          (50, "Крепкая база"), (0, "Начало пути")]

MOMENT_WEIGHTS = {"trust": 1.0, "tension": 1.2, "aspiration": 600.0, "patience": 0.0}


def _moments(turns: list[dict], status: str) -> list[dict]:
    scored: list[tuple[float, dict]] = []
    for turn in turns:
        at = turn.get("at_seconds")
        for effect in turn["effects"]:
            weight = abs(effect["delta"]) * MOMENT_WEIGHTS.get(effect["meter"], 0)
            if weight >= 5:
                title = "Позиция дрогнула" if effect["meter"] == "aspiration" \
                    and effect["delta"] < 0 else (
                    "Аппетит оппонента вырос" if effect["meter"] == "aspiration"
                    else ("Обострение" if effect["meter"] == "tension"
                          and effect["delta"] > 0 else "Контакт"))
                scored.append((weight, {"turn": turn["n"], "at_seconds": at,
                                        "title": title, "text": effect["reason"]}))
        if turn.get("event"):
            scored.append((30, {"turn": turn["n"], "at_seconds": at,
                                "title": f"Событие: {turn['event']['title']}",
                                "text": turn["event"]["text"]}))
    scored.sort(key=lambda pair: -pair[0])
    picked = [moment for _, moment in scored[:5]]
    picked.sort(key=lambda m: m["turn"])
    if turns:
        closing = {"deal": "Сделка закрыта", "no_deal": "Вы вышли из переговоров",
                   "walked_away": "Оппонент прервал переговоры",
                   "expired": "Время истекло"}.get(status)
        if closing:
            picked.append({"turn": turns[-1]["n"],
                           "at_seconds": turns[-1].get("at_seconds"),
                           "title": "Финал", "text": closing})
    return picked


def _recommendations(scenario: Scenario, state: OpponentState, status: str,
                     deal: Package | None, turns: list[dict]) -> list[dict]:
    """Советы с метками-тегами (эталон 4i): «вопросы», «аргументы», «торг»…"""
    recs: list[dict] = []
    hidden = [i for i in scenario.opponent.interests if i.id not in state.revealed]
    if hidden:
        recs.append({"tag": "вопросы", "text":
                     "Осталось скрытым: " +
                     "; ".join(i.text.lower() for i in hidden) +
                     f". Такие вещи вскрываются открытым вопросом, например: «{hidden[0].probe}»"})
    unused = [l for l in scenario.opponent.levers if l.id not in state.levers_used]
    if unused:
        recs.append({"tag": "аргументы", "text":
                     f"Не прозвучал сильный аргумент: {unused[0].text.lower()}. "
                     f"Формулировка на следующий раз: «{unused[0].phrase}»"})
    if state.unconditional_concessions >= 2:
        recs.append({"tag": "торг", "text":
                     f"Уступок без встречных условий — {state.unconditional_concessions}. "
                     "Каждая учит оппонента просить ещё. Рабочая формула: «если вы…, то я…»"})
    if not state.criteria_count and scenario.player.criteria:
        recs.append({"tag": "рынок", "text":
                     "Ни разу не прозвучали объективные критерии, хотя они были в брифе: "
                     f"«{scenario.player.criteria[0]}». С рынком спорить труднее, чем с вами"})
    peaks = [t["meters"]["tension"] for t in turns if t.get("meters")]
    if peaks and max(peaks) >= 60:
        recs.append({"tag": "темп", "text":
                     "Напряжение поднималось в красную зону: пара реплик активного "
                     "слушания или эмпатии в такие моменты стоит дешевле, чем сорванная сделка"})
    if status == "deal" and deal is not None:
        gain, better = left_on_table(scenario, deal)
        if gain >= 5 and better:
            recs.append({"tag": "варианты", "text":
                         "Пакет можно было улучшить, ничего не забирая у оппонента: "
                         f"{describe_package(scenario, better)} — ищите размены, "
                         "а не только цифру"})
    return recs[:4]


def build_debrief(scenario: Scenario, state: OpponentState, status: str,
                  deal: Package | None, turns: list[dict],
                  llm_used: bool) -> dict:
    scores = {
        "preparation": _score_preparation(scenario, state, status, deal, turns),
        "interests": _score_interests(scenario, state, turns),
        "argumentation": _score_argumentation(scenario, state, turns),
        "relations": _score_relations(turns),
        "bargaining": _score_bargaining(scenario, state, status, deal),
    }
    names = {"preparation": "Подготовка", "interests": "Выявление интересов",
             "argumentation": "Аргументация", "relations": "Отношения",
             "bargaining": "Торг"}
    competencies = [{"id": key, "name": names[key], "score": score, "comment": comment}
                    for key, (score, comment) in scores.items()]
    overall = round(sum(score for score, _ in scores.values()) / len(scores))
    grade = next(label for threshold, label in GRADES if overall >= threshold)

    result: dict = {
        "status": status,
        "deal": deal,
        "deal_text": describe_package(scenario, deal) if deal else None,
        "competencies": competencies,
        "overall": {"score": overall, "grade": grade},
        "moments": _moments(turns, status),
        "recommendations": _recommendations(scenario, state, status, deal, turns),
        "llm_used": llm_used,
    }

    # Якоря партии для подписей на шкале ZOPA (эталон 4i): первое предложение
    # оппонента и первый запрос игрока.
    main_id = scenario.main_issue.id
    opponent_first = next(
        (t["intent"]["offer"].get(main_id) for t in turns
         if ((t.get("intent") or {}).get("offer") or {}).get(main_id) is not None),
        None)
    player_anchor = next(
        (m["offer"].get(main_id) for t in turns for m in t.get("moves", [])
         if (m.get("offer") or {}).get(main_id) is not None),
        None)

    if deal is not None:
        u_player = player_utility(scenario, deal)
        capture = zopa_capture(scenario, deal)
        gain, better = left_on_table(scenario, deal)
        edge_player, edge_opponent = zopa_bounds(scenario)
        result["economics"] = {
            "utility_player": u_player,
            "utility_opponent": opponent_utility(scenario, deal),
            "batna": scenario.player.batna_score,
            "vs_batna": round(u_player - scenario.player.batna_score, 1),
            "zopa": {"player_edge": edge_player, "opponent_edge": edge_opponent,
                     "capture": capture},
            "left_on_table": {"points": gain,
                              "package": describe_package(scenario, better)
                              if better else None},
        }
    else:
        best = _best_offer_on_table(scenario, turns)
        result["economics"] = {
            "utility_player": scenario.player.batna_score,
            "batna": scenario.player.batna_score,
            "best_offer_seen": describe_package(scenario, best) if best else None,
            "best_offer_utility": player_utility(scenario, best) if best else None,
        }
    result["economics"]["opponent_first_offer"] = opponent_first
    result["economics"]["player_anchor"] = player_anchor
    result["economics"]["unit"] = scenario.main_issue.unit
    return result
