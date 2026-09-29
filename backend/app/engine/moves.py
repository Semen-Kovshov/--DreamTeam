"""Таксономия ходов игрока — общий язык NLU, правил и разбора.

Одна реплика может содержать несколько ходов («понимаю вас, но по рынку вилка
190+, готов на 195 при пересмотре через полгода» = эмпатия + критерий +
условное предложение). NLU возвращает список, правила применяют каждый.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class MoveType(str, Enum):
    SMALL_TALK = "small_talk"          # приветствие, раппорт
    OPEN_QUESTION = "open_question"
    CLOSED_QUESTION = "closed_question"
    ACTIVE_LISTENING = "active_listening"  # пересказ, резюме услышанного
    EMPATHY = "empathy"                # признание чувств/позиции
    ARGUMENT = "argument"              # довод (сильный, если попал в рычаг)
    CRITERIA = "criteria"              # объективный критерий: рынок, норма, статистика
    OFFER = "offer"                    # предложение по вопросам торга
    BATNA = "batna"                    # упоминание своей альтернативы
    ULTIMATUM = "ultimatum"            # «или так — или ухожу»
    PRESSURE = "pressure"              # давление без ультиматума
    RUDENESS = "rudeness"              # грубость, переход на личности
    ACCEPT = "accept"                  # согласие на предложение оппонента
    REJECT = "reject"                  # отказ без встречного предложения
    OFF_TOPIC = "off_topic"


SPIN = ("S", "P", "I", "N")


class Move(BaseModel):
    type: MoveType
    spin: str | None = None            # S | P | I | N для вопросов
    interest_id: str | None = None     # вопрос попал в тему интереса
    lever_id: str | None = None        # аргумент попал в рычаг
    irritant_id: str | None = None
    offer: dict[str, float | bool] = {}  # issue_id -> значение
    conditional: bool = False          # «если…, то…» — размен, не уступка
    has_number: bool = False
    quote: str = ""                    # фрагмент реплики (для разбора)


# Русские подписи — для стенограммы и разбора.
MOVE_LABELS: dict[MoveType, str] = {
    MoveType.SMALL_TALK: "Раппорт",
    MoveType.OPEN_QUESTION: "Открытый вопрос",
    MoveType.CLOSED_QUESTION: "Закрытый вопрос",
    MoveType.ACTIVE_LISTENING: "Активное слушание",
    MoveType.EMPATHY: "Эмпатия",
    MoveType.ARGUMENT: "Аргумент",
    MoveType.CRITERIA: "Объективный критерий",
    MoveType.OFFER: "Предложение",
    MoveType.BATNA: "Упоминание BATNA",
    MoveType.ULTIMATUM: "Ультиматум",
    MoveType.PRESSURE: "Давление",
    MoveType.RUDENESS: "Грубость",
    MoveType.ACCEPT: "Согласие",
    MoveType.REJECT: "Отказ",
    MoveType.OFF_TOPIC: "Не по теме",
}
