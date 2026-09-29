"""Эвристический распознаватель ходов — запасной путь без LLM.

Лексиконы уже неплохо ловят типовые формулировки, а словарь конкретного
сценария (темы интересов, ключи рычагов, фразы опций) добирает предметную
часть. Точность ниже, чем у модели, но нулевая задержка и полная офлайновость.
"""

from __future__ import annotations

import re

from ..engine.moves import Move, MoveType
from ..engine.state import OpponentState
from ..scenarios.models import BooleanIssue, NumericIssue, Scenario

NUMBER = re.compile(r"\d[\d\s ]*(?:[.,]\d+)?")

STOPWORDS = {"через", "вместо", "чтобы", "который", "которая", "будет", "есть"}


def norm(text: str) -> str:
    return text.lower().replace("ё", "е")


def _contains(text: str, phrases: list[str]) -> bool:
    return any(norm(p) in text for p in phrases)


GREETINGS = ["здравствуйте", "добрый день", "добрый вечер", "привет",
             "как дела", "как ваши", "рад встрече", "спасибо, что нашли время",
             "спасибо за встречу", "как добрались"]
LISTENING = ["правильно понимаю", "правильно ли я", "то есть вы", "то есть вам",
             "если я вас правильно", "резюмиру", "подытожу", "я услышал, что",
             "вам важно, чтобы", "звучит так, будто"]
EMPATHY = ["понимаю вас", "понимаю, что", "понимаю, как", "на вашем месте",
           "это правда непросто", "вижу, что для вас", "слышу вас",
           "спасибо за откровенность", "ценю вашу прямоту"]
CRITERIA = ["по рынку", "рыночн", "медиан", "вилка", "статистик", "по данным",
            "исследовани", "биржа", "индекс", "средняя цена", "средняя ставка",
            "в среднем по", "политик", "отчет hh", "отчет хх",
            "бенчмарк", "норма для", "аналитик", "циан"]
BATNA = ["у меня есть оффер", "есть оффер", "другое предложение", "есть предложение от",
         "мне предлагают", "есть альтернатива", "другой вариант у меня",
         "другой поставщик готов", "конкурент предлагает", "коммерческое от",
         "запасной вариант", "могу уйти к", "образцы от"]
ULTIMATUM = ["или я ухожу", "иначе я ухожу", "иначе я уйду", "или мы расходимся",
             "иначе уйду", "иначе мы уходим", "последний раз предлагаю",
             "это мое последнее", "или подписываем сейчас", "или сейчас, или",
             "ставлю вопрос ребром", "иначе разговора не будет",
             "или соглашайтесь, или"]
PRESSURE = ["вы обязаны", "вам придется", "не оставляете мне выбора", "имейте в виду",
            "пожалеете", "подключу руководство", "буду жаловаться", "вы потеряете",
            "без нас вы", "посмотрим, как вы без", "я потребую"]
RUDENESS = ["издеваетесь", "чушь", "ерунда", "бред", "смешно слушать", "некомпетент",
            "жадн", "обнагл", "стыдно", "да кто вы такой", "не смешите"]
ACCEPT = ["согласен", "согласна", "по рукам", "договорились", "принимаю",
          "беру", "меня устраивает", "нас устраивает", "да, давайте так",
          "подходит, оформляем"]
ACCEPT_NEGATION = ["не согласен", "не согласна", "несогласен", "не принимаю",
                   "не договорились", "не устраивает"]
REJECT = ["не подходит", "не устраивает", "этого мало", "недостаточно",
          "не пойдет", "так не годится", "слишком мало", "слишком дорого",
          "нет, это не"]
OFFER_VERBS = ["предлагаю", "готов", "готова", "давайте", "могу предложить",
               "мое предложение", "остановимся на", "согласен на", "согласна на",
               "сойдемся", "зафиксируем", "прошу", "рассчитываю на", "устроит",
               "финальн", "по рукам", "фиксируем", "подписываем"]
CONDITIONAL = ["если", "при условии", "взамен", "в обмен", "то я", "тогда я"]

QUESTION_WORDS = ["что ", "как ", "почему", "зачем", "какой", "какая", "какие",
                  "сколько", "когда ", "где ", "кто ", "чем ", "куда ",
                  "расскажи", "поделитесь"]
CLOSED_MARKERS = [" ли ", "ли?", "готовы ли", "можете ли", "есть ли", "верно?",
                  "правильно?", "так?", "да или нет"]
SPIN_P = ["что мешает", "какие сложности", "что беспокоит", "что болит",
          "в чем проблема", "что не устраивает", "что грызет", "какая боль"]
SPIN_I = ["что будет, если", "что будет если", "чем это грозит", "как это скажется",
          "во что обходится", "сколько теряете", "к чему приведет", "что случится"]
SPIN_N = ["что даст", "что вам даст", "насколько поможет", "изменится, если",
          "как поможет", "если решить", "если закрыть", "полезно ли будет",
          "что для вас значит"]


def _detect_numbers(text: str) -> list[float]:
    values = []
    for match in NUMBER.findall(text):
        cleaned = match.replace(" ", "").replace(" ", "").replace(",", ".")
        try:
            values.append(float(cleaned))
        except ValueError:
            continue
    return values


def _numeric_offer(scenario: Scenario, text: str) -> tuple[str, float] | None:
    numbers = _detect_numbers(text)
    if not numbers:
        return None
    for issue in scenario.issues:
        if not isinstance(issue, NumericIssue):
            continue
        lo = min(issue.player_limit, issue.player_target,
                 issue.opponent_start, issue.opponent_limit)
        hi = max(issue.player_limit, issue.player_target,
                 issue.opponent_start, issue.opponent_limit)
        pad = (hi - lo) * 0.35 + issue.step
        # Предложение обычно в конце фразы — последнее подходящее число.
        for value in reversed(numbers):
            if lo - pad <= value <= hi + pad:
                return issue.id, value
    return None


# Токены, которые встречаются в любом разговоре о деньгах, — не опознавательные.
NOISY_TOKENS = {"процен", "бюджет", "деньги", "рубл"}


def _distinctive_tokens(phrase: str) -> list[str]:
    tokens = [w for w in re.split(r"\W+", norm(phrase))
              if len(w) >= 4 and w not in STOPWORDS]
    return [w[:6] for w in tokens if w[:6] not in NOISY_TOKENS]


def _boolean_mentions(scenario: Scenario, text: str) -> list[str]:
    """Опция пакета упомянута: токен её типовой формулировки в начале слова.

    Токены берутся только из `ask_phrase` (авторская формулировка просьбы) —
    названия опций слишком общие и дают ложные срабатывания («публичный кейс»
    ловился на слове «публичной политике»).
    """
    found = []
    for issue in scenario.issues:
        if isinstance(issue, BooleanIssue):
            tokens = _distinctive_tokens(issue.ask_phrase)
            if any(re.search(rf"\b{re.escape(t)}", text) for t in tokens):
                found.append(issue.id)
    return found


def _match_interest(scenario: Scenario, text: str,
                    revealed: list[str] | None = None) -> str | None:
    """Из всех совпавших интересов предпочитается ещё не раскрытый: темы
    пересекаются, и вопрос про новую боль не должен цепляться за старую."""
    matched = [i.id for i in scenario.opponent.interests
               if any(norm(topic) in text for topic in i.topics)]
    if not matched:
        return None
    fresh = [m for m in matched if m not in (revealed or [])]
    return (fresh or matched)[0]


def _match_lever(scenario: Scenario, text: str,
                 used: list[str] | None = None) -> str | None:
    matched = [l.id for l in scenario.opponent.levers
               if any(norm(k) in text for k in l.keywords)]
    if not matched:
        return None
    fresh = [m for m in matched if m not in (used or [])]
    return (fresh or matched)[0]


def _match_lever_in_statements(scenario: Scenario, raw: str,
                               used: list[str] | None = None) -> str | None:
    """Рычаг ищется в утвердительных предложениях: «Мы растём на 40%. Вопрос,
    кто будет жарить эти тонны?» — аргумент, а «Что будет с релизом?» — зондаж."""
    statements = [s for s in re.split(r"(?<=[.!?])\s+", raw)
                  if s.strip() and not s.strip().endswith("?")]
    if not statements:
        return None
    return _match_lever(scenario, norm(" ".join(statements)), used)


def _match_irritant(scenario: Scenario, text: str) -> str | None:
    for irritant in scenario.opponent.irritants:
        if any(norm(k) in text for k in irritant.keywords):
            return irritant.id
    return None


def _spin(text: str) -> str | None:
    if _contains(text, SPIN_N):
        return "N"
    if _contains(text, SPIN_I):
        return "I"
    if _contains(text, SPIN_P):
        return "P"
    if _contains(text, ["как у вас устроен", "как сейчас", "сколько сейчас",
                        "как обычно", "как это работает", "как у вас с"]):
        return "S"
    return None


def context_flags(text: str, scenario: Scenario) -> dict:
    """Контекст реплики для слияния с LLM-разметкой."""
    t = norm(text)
    is_question = "?" in text or any(t.startswith(q) for q in QUESTION_WORDS)
    return {
        "is_question": is_question,
        "criteria": _contains(t, CRITERIA),
        "batna": _contains(t, BATNA),
        "conditional": _contains(t, CONDITIONAL),
        "numbers": _detect_numbers(text),
    }


def classify_heuristic(text: str, scenario: Scenario,
                       state: OpponentState) -> list[Move]:
    raw = text
    t = norm(text)
    moves: list[Move] = []
    has_number = bool(_detect_numbers(raw))

    # Тон — прежде всего: он окрашивает весь ход.
    if _contains(t, RUDENESS):
        moves.append(Move(type=MoveType.RUDENESS, quote=raw[:80]))
    if _contains(t, ULTIMATUM):
        moves.append(Move(type=MoveType.ULTIMATUM))
    elif _contains(t, PRESSURE):
        moves.append(Move(type=MoveType.PRESSURE))

    # Приветствие и раппорт распознаются и рядом с вопросом («Как добрались?»).
    if _contains(t, GREETINGS):
        moves.append(Move(type=MoveType.SMALL_TALK))

    # Согласие и отказ.
    if _contains(t, ACCEPT) and not _contains(t, ACCEPT_NEGATION) \
            and state.opp_offer and not has_number \
            and not _contains(t, CONDITIONAL):
        moves.append(Move(type=MoveType.ACCEPT))
        return moves[:4]
    if _contains(t, REJECT) and not has_number:
        moves.append(Move(type=MoveType.REJECT))

    # Вопрос — знак «?» или вопросительное слово в начале. Середина не в счёт:
    # «и вопрос "за что платим" закроется» — утверждение.
    is_question = "?" in raw or any(t.startswith(q) for q in QUESTION_WORDS)

    # Предложение: число в диапазоне вопроса торга или опция пакета.
    # Числа из критериев («вилка 190–220») и BATNA («оффер на 185») —
    # не предложение, если нет глагола предложения.
    offer_verbs = _contains(t, OFFER_VERBS)
    criteria_hit = _contains(t, CRITERIA)
    batna_hit = _contains(t, BATNA)
    numeric = _numeric_offer(scenario, raw)
    booleans = _boolean_mentions(scenario, t)
    conditional = _contains(t, CONDITIONAL)
    numeric_ok = numeric and (offer_verbs
                              or not (criteria_hit or batna_hit or is_question))
    if numeric_ok or (booleans and offer_verbs):
        offer: dict[str, float | bool] = {}
        if numeric_ok and numeric:
            offer[numeric[0]] = numeric[1]
        for b in booleans:
            offer[b] = True
        moves.append(Move(type=MoveType.OFFER, offer=offer,
                          conditional=conditional, has_number=bool(numeric_ok)))

    # Вопросы.
    if is_question:
        closed = _contains(t, CLOSED_MARKERS)
        moves.append(Move(
            type=MoveType.CLOSED_QUESTION if closed else MoveType.OPEN_QUESTION,
            spin=_spin(t),
            interest_id=_match_interest(scenario, t, state.revealed)))

    # Метанавыки и опоры.
    if _contains(t, LISTENING):
        moves.append(Move(type=MoveType.ACTIVE_LISTENING))
    if _contains(t, EMPATHY):
        moves.append(Move(type=MoveType.EMPATHY))
    if criteria_hit:
        moves.append(Move(type=MoveType.CRITERIA, has_number=has_number))
    if batna_hit:
        moves.append(Move(type=MoveType.BATNA))

    # Аргумент по рычагу сценария — только из утвердительной части реплики:
    # чистый вопрос прощупывает боль, а не давит на неё. Уже использованный
    # рычаг рядом с предложением — тоже не аргумент: «если подписываем на три
    # года — готов на 500» это условие пакета, а не повтор довода.
    lever = _match_lever_in_statements(scenario, raw, state.levers_used)
    has_offer_move = any(m.type == MoveType.OFFER for m in moves)
    if lever and not (lever in state.levers_used and has_offer_move):
        moves.append(Move(type=MoveType.ARGUMENT, lever_id=lever,
                          has_number=has_number))

    if not moves:
        if len(t) >= 40:
            moves.append(Move(type=MoveType.ARGUMENT, has_number=has_number))
        else:
            moves.append(Move(type=MoveType.OFF_TOPIC))

    if irritant := _match_irritant(scenario, t):
        moves[0].irritant_id = irritant
    return moves[:4]
