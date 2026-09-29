"""Полные партии без LLM: детерминированность и структура разбора."""

from __future__ import annotations

from app.engine.session import Session

GOOD_GAME = [
    "Здравствуйте! Спасибо, что нашли время.",
    "Что вам нужно, чтобы согласовать пересмотр с финансовым директором?",
    "Что будет с релизом, если мою позицию придётся закрывать наймом?",
    "Как сделать так, чтобы пересмотр не выглядел прецедентом для команды и коллег?",
    "По свежему отчёту HH вилка для моего грейда — 190–220, могу передать исследование.",
    "Замена на моей позиции — это месяца три найма и передачи дел прямо перед релизом.",
    "У меня единственная зона ответственности с внешними партнёрами — это не прецедент для сетки.",
    "У меня есть оффер на 185, но я хочу остаться и довести релиз.",
    "Если зафиксируем пересмотр через полгода — готов на 188.",
    "Предлагаю сойтись на 185.",
]


def _play(scenario, replies, mode="free"):
    session = Session(scenario, mode=mode, use_llm=False)
    payload = None
    for text in replies:
        payload = session.apply_turn(text)
        if payload["status"] != "active":
            break
    return session, payload


def test_good_game_reaches_deal(salary):
    session, payload = _play(salary, GOOD_GAME)
    if session.status == "active":
        session.finish("accept")
    assert session.status == "deal"
    assert session.deal is not None
    value = session.deal["salary"]
    assert 175 <= value <= 190, "сделка обязана лежать в ZOPA"


def test_determinism_same_game_same_result(salary):
    first, _ = _play(salary, GOOD_GAME)
    second, _ = _play(salary, GOOD_GAME)
    assert first.status == second.status
    assert first.deal == second.deal
    assert [t["intent"]["kind"] for t in first.turns] == \
        [t["intent"]["kind"] for t in second.turns]


def test_rude_game_breaks_relations(supplier):
    session, payload = _play(supplier, [
        "Ваш прайс — это чушь, вы обнаглели.",
        "Вы обязаны снизить цену, иначе я уйду и вы пожалеете.",
        "Или 1250 — или я ухожу к конкурентам, посмотрим, как вы без нас.",
        "Да вы издеваетесь, это просто ерунда, а не позиция!",
        "Хватит, это стыдно слушать. Вы жадничаете и всё.",
        "Последний раз предлагаю: 1250, иначе разговора не будет.",
    ])
    assert session.status in ("walked_away", "no_deal")


def test_expired_when_player_stalls(salary):
    session = Session(salary, use_llm=False)
    for _ in range(salary.max_turns + 3):
        payload = session.apply_turn("Ну, надо подумать ещё немного…")
        if payload["status"] != "active":
            break
    assert session.status in ("expired", "walked_away")


def test_debrief_structure(salary):
    session, _ = _play(salary, GOOD_GAME)
    if session.status == "active":
        session.finish("accept")
    report = session.debrief()
    ids = {c["id"] for c in report["competencies"]}
    assert ids == {"preparation", "interests", "argumentation",
                   "relations", "bargaining"}
    for competency in report["competencies"]:
        assert 0 <= competency["score"] <= 100
        assert competency["comment"]
    assert 0 <= report["overall"]["score"] <= 100
    assert report["moments"]
    assert report["transcript"]
    assert "vs_batna" in report["economics"]
    assert report["economics"]["utility_player"] > 0


def test_debrief_annotations_have_provenance(salary):
    session, _ = _play(salary, GOOD_GAME)
    if session.status == "active":
        session.finish("accept")
    transcript = session.debrief()["transcript"]
    reasons = [e["reason"] for t in transcript for e in t["effects"]]
    assert all(reasons), "каждый эффект обязан объяснять себя"
    assert any("интерес" in r.lower() for r in reasons)


def test_exam_mode_hides_meters(salary):
    session = Session(salary, mode="exam", use_llm=False)
    payload = session.apply_turn("Здравствуйте!")
    assert payload["meters"]["trust"] is None
    assert payload["meters"]["tension"] is None
    assert payload["moves"] == [] and payload["effects"] == []
    assert session.hints() == []


def test_training_mode_gives_three_hints(salary):
    session = Session(salary, mode="training", use_llm=False)
    hints = session.hints()
    assert len(hints) == 3
    assert all(h["text"] and h["why"] and h["tag"] and h["insert"] for h in hints)


def test_free_mode_gives_tips_not_phrases(salary):
    """Эталон 3a/4c: свободный режим подсказывает направления, а не реплики."""
    session = Session(salary, mode="free", use_llm=False)
    tips = session.hints()
    assert 1 <= len(tips) <= 3
    assert all(not tip["insert"] and tip["tag"] for tip in tips)
    assert any(tip["tag"] == "якорь" for tip in tips)

    exam = Session(salary, mode="exam", use_llm=False)
    assert exam.hints() == []


def test_hints_follow_game_state(salary):
    session = Session(salary, mode="training", use_llm=False)
    techniques_before = [h["technique"] for h in session.hints()]
    assert "Открытый вопрос (SPIN)" in techniques_before[0]
    session.apply_turn("Что вам нужно, чтобы защитить пересмотр перед финдиром?")
    session.apply_turn("Что будет с релизом, если позицию придётся закрывать наймом?")
    session.apply_turn("Как сделать пересмотр не прецедентом для команды?")
    hints = session.hints()
    assert all("нераскрыт" not in h["why"] for h in hints)


def test_history_written_on_close(salary, tmp_path):
    import app.engine.session as sessions_module
    session, _ = _play(salary, GOOD_GAME)
    if session.status == "active":
        session.finish("accept")
    content = sessions_module.HISTORY_FILE.read_text(encoding="utf-8")
    assert salary.id in content


def test_session_survives_restart(salary, scenarios):
    from app.engine.session import load_session
    first = Session(salary, use_llm=False)
    first.apply_turn("Что вам нужно, чтобы согласовать пересмотр с финдиром?")
    first.apply_turn("Предлагаю зафиксировать 195 и пересмотр через полгода.")

    # «Рестарт»: поднимаем партию с диска и продолжаем как ни в чём не бывало.
    revived = load_session(first.id, scenarios)
    assert revived is not None
    assert revived.turn_n == 2
    assert revived.state.revealed == first.state.revealed
    assert revived.state.opp_offer == first.state.opp_offer

    payload = revived.apply_turn("Если добавите бюджет на обучение — готов на 188.")
    assert payload["turn"] == 3
    assert revived.history[0] == ("opponent", salary.opponent.opening)


def test_restored_session_debrief_matches(salary, scenarios):
    from app.engine.session import load_session
    original, _ = _play(salary, GOOD_GAME)
    if original.status == "active":
        original.finish("accept")
    revived = load_session(original.id, scenarios)
    assert revived is not None
    assert revived.debrief()["overall"] == original.debrief()["overall"]


def test_load_session_rejects_garbage(scenarios):
    from app.engine.session import load_session
    assert load_session("no-such-id", scenarios) is None
    assert load_session("..\\..\\etc", scenarios) is None


SUPPLIER_GAME = [
    "Как у вас с загрузкой производства после запуска нового цеха?",
    "Как вы финансируете закупку зерна на сезон — платежи вперёд?",
    "В следующем году мы открываем шесть точек — плюс сорок процентов объёма. Вопрос, кто будет жарить эти тонны.",
    "Мы можем говорить о предоплате — вам финансировать закупки, нам важна цена. Честный размен.",
    "По бирже зерно подешевело за полгода, а средняя цена смесей по рынку — 1300–1400.",
    "Если зафиксируем годовой объём и предоплату за квартал — готов обсуждать 1360.",
    "У нас есть предложение от «Северной обжарки» на 1350, но мы хотим остаться с вами.",
    "Хорошо. Тогда финально: 1330 при годовом объёме и предоплате. По рукам?",
]

RENT_GAME = [
    "Как у вас сейчас с заполняемостью здания?",
    "Что для вас важнее: максимальная ставка или предсказуемый поток платежей?",
    "Давайте посчитаем честно: если мы съезжаем, у вас рядом с пустым четвёртым встаёт пустой третий этаж.",
    "Мы готовы говорить о договоре на три года — для вашего банка подписанный длинный договор лучше разовой прибавки.",
    "По аналитике ЦИАН средняя ставка класса B в районе — 1500–1600 за метр, для нашего метража это 450–480.",
    "И заметьте: у нас свой офис-менеджер и свои подрядчики, мы вас пять лет не дёргали.",
    "Если подписываем договор на три года — готов на 500.",
    "Хорошо. Если фиксируем три года договора — моё финальное 515, по рукам?",
]

DISCOUNT_GAME = [
    "Какую задачу поставил совет — снизить именно цену подписки или показать экономию в целом?",
    "Как сотрудники работают с платформой — все ли команды её освоили?",
    "Как устроена ваша отчётность для совета — сколько времени она отнимает?",
    "Давайте посчитаем экономию в ваших цифрах: платформа закрывает работу двух специалистов, расчёт для совета я подготовлю.",
    "Про команды: мы бесплатно обучим все отделы — использование вырастет, и вопрос «за что платим» закроется сам.",
    "Модуль отчётов для совета включим вам на три месяца бесплатно — тот самый, который собирает презентацию за вас.",
    "По нашей публичной политике скидок максимум за годовую предоплату — 10 процентов, одинаково для всех.",
    "Понимаю, что совету нужна цифра. Давайте так: скидка 14 — и премиум-поддержка в подарок.",
    "Хорошо, моё финальное: 15 — и включаем премиум-поддержку с модулем отчётов.",
]


def test_supplier_game_closes_inside_zopa(supplier):
    session, payload = _play(supplier, SUPPLIER_GAME)
    assert session.status == "deal", "сильная партия обязана закрываться сделкой"
    price = session.deal["price"]
    assert 1300 <= price <= 1400, "сделка обязана лежать в ZOPA"
    # Сделка закрыта принятием предложения, а не кнопкой на плохих условиях.
    assert session.turns[-1]["intent"]["kind"] == "accept"


def test_rent_game_closes_inside_zopa(scenarios):
    session, payload = _play(scenarios["rent"], RENT_GAME)
    assert session.status == "deal"
    assert 500 <= session.deal["rent"] <= 520
    assert session.deal.get("long_lease") is True, "размен вошёл в пакет"
    assert session.turns[-1]["intent"]["kind"] == "accept"


def test_discount_game_full_recognition(discount):
    session, payload = _play(discount, DISCOUNT_GAME)
    if session.status == "active":
        session.finish("accept")
    assert len(session.state.revealed) == 3, "все интересы Марины вскрыты"
    assert len(session.state.levers_used) == 3, "все рычаги прозвучали"
    assert session.state.criteria_count >= 1
    assert session.status == "deal"
    assert session.deal["discount"] < 30, "торг сдвинул стартовые 30%"


def test_pressure_on_soft_persona_wins_battle_loses_war(discount):
    """Классика: мягкого можно продавить, но напряжение копится и рвёт сделку."""
    session = Session(discount, use_llm=False)
    replies = [
        "Вы обязаны дать нормальные условия, иначе вы потеряете клиента.",
        "Не оставляете мне выбора: буду жаловаться вашему руководству.",
        "Это ваши проблемы, читайте контракт. Мы платим — вы делаете.",
        "Или пять процентов — или мы уходим, посмотрим, как вы без нас.",
        "Я потребую расторжения, вы пожалеете об этом разговоре.",
    ]
    for text in replies:
        payload = session.apply_turn(text)
        if payload["status"] != "active":
            break
    assert session.status == "walked_away", \
        "мягкая персона не предупреждает — она тихо выходит"
