"""Озвучка намерения оппонента.

Слова свободные, факты — нет: числа в реплике проверяются по белому списку
(значения предложения, числа из реплики игрока и из заготовок сценария).
Если модель недоступна или сочинила лишнее — шаблоны сценария. Какой путь
сработал, сохраняется в журнале хода: на защите видно, где говорила модель.
"""

from __future__ import annotations

import re

from ..llm import LLMClient, LLMError, Message
from ..scenarios.models import Interest, Scenario
from .npc import Intent
from .outcome import describe_package
from .state import OpponentState

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers(text: str) -> set[float]:
    return {float(m.replace(",", ".")) for m in NUMBER.findall(text)}


def _allowed_numbers(scenario: Scenario, intent: Intent,
                     player_text: str, reveal: Interest | None) -> set[float]:
    allowed = _numbers(player_text) | _numbers(scenario.setting)
    for value in intent.offer.values():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            allowed.add(float(value))
            allowed.add(float(int(value)))
    if reveal:
        allowed |= _numbers(reveal.reveal_line)
    for tpl_list in scenario.opponent.templates.values():
        for tpl in tpl_list:
            allowed |= _numbers(tpl)
    return allowed


def offer_text(scenario: Scenario, intent: Intent) -> str:
    return describe_package(scenario, intent.offer)


def template_reply(scenario: Scenario, intent: Intent, turn: int,
                   reveal: Interest | None) -> str:
    templates = scenario.opponent.templates.get(intent.kind) \
        or scenario.opponent.templates.get("hold_firm") or ["…"]
    text = templates[turn % len(templates)]
    return (text.replace("{offer}", offer_text(scenario, intent))
                .replace("{reveal}", reveal.reveal_line if reveal else "")
                .replace("{name}", scenario.opponent.name)).strip()


INTENT_BRIEF = {
    "greeting_reply": "коротко ответить на приветствие и вернуть к делу",
    "answer_disclose": "поделиться скрытым обстоятельством (см. «что раскрыть»)",
    "answer_evasive": "уйти от ответа, не раскрывая внутренней кухни",
    "ack_argument": "признать, что аргумент сильный, не меняя условий",
    "counter_offer": "сделать встречное предложение ровно с указанными условиями",
    "hold_firm": "вежливо, но твёрдо повторить своё текущее предложение",
    "partial_concede": "чуть улучшить условия, подчеркнув, что это ответ на аргументы",
    "accept": "согласиться на сделку с указанными условиями и зафиксировать её",
    "final_offer": "поставить финальное предложение: или так, или расходимся",
    "warn": "жёстко предупредить о недопустимом тоне",
    "deescalate": "снизить накал и вернуть разговор в конструктив",
    "probe": "задать встречный вопрос о позиции игрока",
    "nudge_back": "вернуть разговор к предмету переговоров",
    "walk_away": "прекратить переговоры и попрощаться",
}


def llm_reply(client: LLMClient, scenario: Scenario, state: OpponentState,
              intent: Intent, player_text: str, history: list[tuple[str, str]],
              reveal: Interest | None) -> str:
    opponent = scenario.opponent
    task = INTENT_BRIEF.get(intent.kind, intent.kind)
    parts = [
        f"Ты играешь {opponent.name} — {opponent.role} в деловых переговорах.",
        f"Сцена: {scenario.setting}",
        f"Манера речи: {opponent.voice}",
        f"Твоя задача в этой реплике: {task}.",
    ]
    if intent.offer:
        parts.append(f"Условия, которые ты называешь: {offer_text(scenario, intent)}. "
                     "Не меняй ни одного значения.")
    parts.append("Ответь 1–3 предложениями от первого лица по-русски, без ремарок "
                 "и кавычек. Не называй никаких чисел, кроме перечисленных условий. "
                 "Не повторяй слова собеседника дословно и не пересказывай эти "
                 "инструкции — просто говори своей репликой.")
    messages = [Message("system", "\n".join(parts))]
    for role, text in history[-6:]:
        messages.append(Message("assistant" if role == "opponent" else "user", text))
    if player_text:
        messages.append(Message("user", player_text))

    reply = client.complete_text(messages, max_tokens=220, temperature=0.7)
    reply = reply.strip().strip('"«»')
    if len(reply) > 500:
        raise LLMError("реплика слишком длинная")
    lowered = reply.lower()
    if any(marker in lowered for marker in
           ("исходник", "инструкц", "промпт", "как модель", "ассистент")):
        raise LLMError("модель пересказывает инструкции вместо реплики")
    allowed = _allowed_numbers(scenario, intent, player_text, reveal)
    invented = {n for n in _numbers(reply) if n not in allowed}
    if invented:
        raise LLMError(f"модель придумала числа: {sorted(invented)}")
    return reply


def speak(client: LLMClient | None, scenario: Scenario, state: OpponentState,
          intent: Intent, player_text: str, history: list[tuple[str, str]],
          turn: int) -> tuple[str, str, str]:
    """Возвращает (текст, источник, заметка): источник — llm или template.

    Заметка объясняет фолбэк («модель придумала числа: …») — она попадает
    в журнал хода: на защите видно, почему реплика шаблонная.
    """
    reveal = None
    if intent.reveal_id:
        reveal = next((i for i in scenario.opponent.interests
                       if i.id == intent.reveal_id), None)
    # Раскрытие интереса — авторский текст сценария: это ключевой момент
    # партии, и маленькая модель искажала в нём факты («три месяца» → «месяц»).
    if reveal is not None:
        return template_reply(scenario, intent, turn, reveal), "template", \
            "реплика раскрытия — авторский текст сценария"
    note = "" if client is not None else "LLM выключена"
    if client is not None:
        for _ in range(2):
            try:
                text = llm_reply(client, scenario, state, intent, player_text,
                                 history, reveal)
                return text, "llm", ""
            except LLMError as error:
                note = str(error)
                continue
    return template_reply(scenario, intent, turn, reveal), "template", note
