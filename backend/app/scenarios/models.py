"""Модель сценария. Сценарий — данные, ядро не знает ни одного по имени.

Числовые вопросы торга описываются с двух сторон: цель и предел игрока,
стартовая позиция и предел оппонента. Пересечение пределов даёт ZOPA, по ней
меряется итог. Булевые вопросы — разменные монеты пакета: у сторон разная
ценность «да», на этом строятся выгодные обмены.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Persona = Literal["soft", "positional", "hard"]

# Секунды «нормального» раздумья на ход — из них считается оценка длительности
# партии для брифа (та же величина, что мягкий порог таймера в session).
THINK_SECONDS_PER_TURN = 75


class ScenePalette(BaseModel):
    """Два тона сцены — для подложек карточки, брифа и фолбэка фона."""
    model_config = ConfigDict(populate_by_name=True)
    start: str = Field(alias="from", default="#e8e6df")
    end: str = Field(alias="to", default="#f4f3ef")


class NumericIssue(BaseModel):
    id: str
    name: str
    kind: Literal["numeric"] = "numeric"
    unit: str = ""
    step: float = 1.0
    direction: Literal["higher_better", "lower_better"]  # с точки зрения игрока
    player_target: float
    player_limit: float        # хуже этого игроку нельзя (граница его BATNA)
    opponent_start: float      # с чего начинает оппонент
    opponent_limit: float      # дальше оппонент не пойдёт (его граница)
    weight_player: float = 1.0
    weight_opponent: float = 1.0

    @model_validator(mode="after")
    def check_orientation(self) -> "NumericIssue":
        better = max if self.direction == "higher_better" else min
        if better(self.player_target, self.player_limit) != self.player_target:
            raise ValueError(f"{self.id}: цель игрока хуже его предела")
        if better(self.opponent_limit, self.opponent_start) != self.opponent_limit:
            raise ValueError(f"{self.id}: предел оппонента хуже его старта — "
                             "торг не имеет направления")
        return self

    @property
    def has_zopa(self) -> bool:
        if self.direction == "higher_better":
            return self.opponent_limit >= self.player_limit
        return self.opponent_limit <= self.player_limit


class BooleanIssue(BaseModel):
    id: str
    name: str
    kind: Literal["boolean"] = "boolean"
    player_value: float        # сколько «да» стоит игроку (в баллах утилиты)
    opponent_cost: float       # во сколько «да» обходится оппоненту
    ask_phrase: str            # как игрок обычно это просит (лексика для NLU)


Issue = NumericIssue | BooleanIssue


class Interest(BaseModel):
    """Скрытый интерес оппонента. Раскрывается вопросами по своим темам."""
    id: str
    text: str                  # формулировка для разбора
    reveal_line: str           # как оппонент проговаривает интерес при раскрытии
    topics: list[str]          # ключевые слова вопросов, которые его вскрывают
    probe: str                 # готовый вопрос игрока (подсказка + словарь NLU)


class Lever(BaseModel):
    """Аргумент, который действительно работает на этого оппонента."""
    id: str
    text: str                  # суть аргумента (для классификатора и подсказок)
    phrase: str                # готовая формулировка (подсказка)
    interest_id: str | None = None   # какой интерес закрывает
    aspiration_drop: float = Field(gt=0, le=0.3)  # сила: насколько сбивает аппетит
    keywords: list[str]        # эвристический запасной путь


class Irritant(BaseModel):
    """Что выводит оппонента из равновесия (помимо универсальной грубости)."""
    id: str
    text: str
    keywords: list[str]
    tension_add: float = Field(gt=0, le=30)


class Event(BaseModel):
    """Вводная посреди переговоров — двигает параметры, оживляет партию."""
    turn: int                  # после какого хода игрока случается
    title: str
    text: str                  # что видит игрок
    aspiration_add: float = 0.0
    patience_add: int = 0
    tension_add: float = 0.0


class OpponentProfile(BaseModel):
    name: str
    role: str
    persona: Persona
    voice: str                 # стиль речи для промпта озвучки
    portrait: str = "🙂"       # эмодзи-аватар
    opening: str               # первая реплика сцены
    interests: list[Interest]
    levers: list[Lever]
    irritants: list[Irritant] = []
    # Шаблоны фраз по видам намерений — запасной путь озвучки без LLM.
    # Плейсхолдеры: {offer} — текст предложения, {reveal} — реплика интереса.
    templates: dict[str, list[str]]


class PlayerBrief(BaseModel):
    role: str
    goal: str
    batna_text: str            # альтернатива игрока словами
    batna_score: float         # её ценность в баллах утилиты игрока
    facts: list[str]           # карточка подготовки: что игрок знает и может использовать
    criteria: list[str] = []   # объективные критерии в его распоряжении


class Scenario(BaseModel):
    id: str
    title: str
    category: str
    difficulty: int = Field(ge=1, le=3)
    summary: str               # карточка каталога
    setting: str               # контекст сцены (бриф + промпты)
    player: PlayerBrief
    opponent: OpponentProfile
    issues: list[Issue]
    max_turns: int = 12
    events: list[Event] = []
    palette: ScenePalette = ScenePalette()

    @model_validator(mode="after")
    def check_links(self) -> "Scenario":
        interest_ids = {i.id for i in self.opponent.interests}
        for lever in self.opponent.levers:
            if lever.interest_id and lever.interest_id not in interest_ids:
                raise ValueError(f"рычаг {lever.id} ссылается на неизвестный "
                                 f"интерес {lever.interest_id}")
        numeric = [i for i in self.issues if i.kind == "numeric"]
        if not numeric:
            raise ValueError("нужен хотя бы один числовой вопрос торга")
        if len({i.id for i in self.issues}) != len(self.issues):
            raise ValueError("id вопросов торга повторяются")
        return self

    @property
    def main_issue(self) -> NumericIssue:
        return next(i for i in self.issues if i.kind == "numeric")

    def issue(self, issue_id: str) -> Issue | None:
        return next((i for i in self.issues if i.id == issue_id), None)

    def card(self) -> dict:
        """Карточка каталога — без скрытых полей оппонента.

        Цель и предел игрока публичны (это его собственный мандат) — бриф 4b
        показывает их до старта партии.
        """
        main = self.main_issue
        return {
            "id": self.id, "title": self.title, "category": self.category,
            "difficulty": self.difficulty, "summary": self.summary,
            "opponent_name": self.opponent.name,
            "opponent_role": self.opponent.role,
            "portrait": self.opponent.portrait,
            "persona": self.opponent.persona,
            "max_turns": self.max_turns,
            "skills": self.skills(),
            "goal_value": main.player_target,
            "limit_value": main.player_limit,
            "unit": main.unit,
            "palette": {"from": self.palette.start, "to": self.palette.end},
            "est_minutes": round(self.max_turns * THINK_SECONDS_PER_TURN / 60),
        }

    def skills(self) -> list[str]:
        """Чему учит сценарий — выводится из содержимого, не задаётся руками."""
        tags = ["Выявление интересов", "Аргументация"]
        if len(self.issues) > 1:
            tags.append("Пакетные размены")
        if self.player.criteria:
            tags.append("Объективные критерии")
        persona_skill = {
            "soft": "Экология давления",
            "positional": "Работа с позиционным торгом",
            "hard": "Устойчивость к давлению",
        }
        tags.append(persona_skill[self.opponent.persona])
        return tags
