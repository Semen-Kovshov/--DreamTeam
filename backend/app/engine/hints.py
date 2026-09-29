"""Подсказки режима обучения: три техники под текущее состояние партии.

Подсказки детерминированные — собираются из данных сценария, а не из LLM:
они должны работать мгновенно, офлайн и всегда быть уместными. Каждая
объясняет, почему техника сейчас к месту, — это и есть обучение.
"""

from __future__ import annotations

from ..scenarios.models import BooleanIssue, Scenario
from .outcome import Package, describe_package
from .state import OpponentState, opponent_target


def _question_hint(scenario: Scenario, state: OpponentState, turn: int) -> dict | None:
    hidden = [i for i in scenario.opponent.interests if i.id not in state.revealed]
    if not hidden:
        return None
    interest = hidden[turn % len(hidden)]
    return {
        "technique": "Открытый вопрос (SPIN)",
        "text": interest.probe,
        "why": "У оппонента остались невскрытые интересы. Пока боль не названа, "
               "аргументы бьют вполсилы, а торг идёт только о цифре.",
    }


def _argument_hint(scenario: Scenario, state: OpponentState) -> dict | None:
    ready = [l for l in scenario.opponent.levers
             if l.id not in state.levers_used
             and (l.interest_id is None or l.interest_id in state.revealed)]
    if ready:
        lever = ready[0]
        return {
            "technique": "Аргумент по интересу",
            "text": lever.phrase,
            "why": "Интерес уже на столе — аргумент, который его закрывает, "
                   "двигает позицию оппонента сильнее любого давления.",
        }
    if state.criteria_count == 0 and scenario.player.criteria:
        return {
            "technique": "Объективный критерий",
            "text": scenario.player.criteria[0],
            "why": "Гарвардское правило: спорить с рынком и нормами труднее, "
                   "чем с вашим «хочу». Особенно действует на позиционных.",
        }
    unused = [l for l in scenario.opponent.levers if l.id not in state.levers_used]
    if unused:
        lever = unused[0]
        return {
            "technique": "Аргумент на будущее",
            "text": lever.phrase,
            "why": "Сильный довод, но его интерес ещё не вскрыт вопросами — "
                   "сработает вполсилы. Сначала спросите, потом бейте.",
        }
    return None


def _offer_hint(scenario: Scenario, state: OpponentState) -> dict:
    main = scenario.main_issue
    step = main.step

    if state.opp_offer.get(main.id) is not None:
        current = float(state.opp_offer[main.id])
        midpoint = (current + main.player_target) / 2
        value = round(midpoint / step) * step
        trade = _best_trade(scenario, state)
        package: Package = {main.id: value}
        if trade:
            package[trade.id] = True
            text = (f"Если {trade.ask_phrase} — готов зафиксировать "
                    f"{describe_package(scenario, {main.id: value})}.")
            why = ("Условная уступка — размен, а не отступление: вы отдаёте "
                   "дешёвое для себя и дорогое для оппонента.")
        else:
            text = (f"Предлагаю сойтись на {describe_package(scenario, package)} — "
                    f"и зафиксировать договорённость сегодня.")
            why = "Встречное предложение держит темп торга и проверяет гибкость оппонента."
        return {"technique": "Условное предложение", "text": text, "why": why}

    anchor: Package = {main.id: main.player_target}
    return {
        "technique": "Якорь",
        "text": f"Моё предложение — {describe_package(scenario, anchor)}. "
                "Расскажу, из чего оно складывается.",
        "why": "Первое озвученное число задаёт точку отсчёта всего торга. "
               "Пусть её поставите вы, а не оппонент.",
    }


def _best_trade(scenario: Scenario, state: OpponentState) -> BooleanIssue | None:
    """Самая выгодная разменная монета: дёшево игроку, дорого оппоненту."""
    chips = [i for i in scenario.issues
             if isinstance(i, BooleanIssue) and i.opponent_cost < 0
             and not state.opp_offer.get(i.id) and not state.player_offer.get(i.id)]
    if not chips:
        return None
    return max(chips, key=lambda i: -i.opponent_cost + i.player_value)


TAGS = {
    "Открытый вопрос (SPIN)": "вопрос",
    "Аргумент по интересу": "довод",
    "Объективный критерий": "рынок",
    "Аргумент на будущее": "довод",
    "Условное предложение": "размен",
    "Якорь": "якорь",
}


def build_hints(scenario: Scenario, state: OpponentState, turn: int) -> list[dict]:
    """Режим обучения: готовые формулировки, клик подставляет в поле."""
    hints = [h for h in (
        _question_hint(scenario, state, turn),
        _argument_hint(scenario, state),
        _offer_hint(scenario, state),
    ) if h]
    return [{"tag": TAGS.get(h["technique"], "довод"), "insert": True, **h}
            for h in hints[:3]]


def build_tips(scenario: Scenario, state: OpponentState,
               last_event_title: str | None) -> list[dict]:
    """Свободный режим (эталон 3a/4c): короткие советы-направления без готовых
    реплик — тренажёр подсвечивает «куда смотреть», но не говорит за игрока."""
    tips: list[dict] = []
    if last_event_title:
        tips.append({"tag": "событие",
                     "text": f"«{last_event_title}» меняет расклад — учтите его в следующем ходе."})
    if state.patience <= 4:
        tips.append({"tag": "темп",
                     "text": "Терпение на исходе — пора собирать пакетное предложение."})
    if state.tension >= 45:
        tips.append({"tag": "темп",
                     "text": "Напряжение растёт — снизьте накал: эмпатия, пауза или глоток воды."})
    if not state.opp_offer and not state.player_offer:
        tips.append({"tag": "якорь",
                     "text": "Первое число задаёт точку отсчёта всего торга — пусть его назовёте вы."})
    if state.criteria_count == 0 and scenario.player.criteria:
        tips.append({"tag": "рынок",
                     "text": "Сошлитесь на объективный критерий из брифа — с рынком спорить труднее, чем с вами."})
    if any(i.id not in state.revealed for i in scenario.opponent.interests):
        tips.append({"tag": "вопрос",
                     "text": "Интересы вскрываются вопросами — спросите о его ситуации, прежде чем давить цифрой."})
    return [{"insert": False, **tip} for tip in tips[:3]]
