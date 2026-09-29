"""Скриншоты работающего стенда для презентации.

Запуск (стенд должен быть поднят на 8030, фронт собран):

    backend/.venv/Scripts/python.exe docs/presentation/shots.py docs/presentation/shots

Скрипт проходит партию через интерфейс (реплики — сильная линия из
docs/05-demo-script.md), поэтому разбор на снимке настоящий, а не нарисованный.
С живой LLM ход считается десятки секунд — отсюда большие таймауты.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8030"
DESK = {"width": 1440, "height": 900}
PHONE = {"width": 390, "height": 844}
TURN_TIMEOUT = 240_000  # ход с живой 4B-моделью: два вызова, десятки секунд

# Сильная линия: вопросы вскрывают интересы, аргумент бьёт по рычагу,
# условная уступка разменивает пакет (docs/05-demo-script.md §3).
LINE = [
    "Ирина, здравствуйте. Прежде чем говорить о цифрах — что сейчас для вас "
    "самое узкое место в команде?",
    "А как на это смотрит финансовый директор? Что для него важнее — фонд "
    "оплаты или сроки релиза?",
    "Тогда посчитаем честно: замена моей роли перед релизом — это найм, "
    "три месяца погружения и риск сдвинуть дату. Рынок по моей позиции — "
    "185–200.",
    "Давайте так: если пересмотр вернётся к вопросу через полгода по "
    "измеримым критериям, я готов остановиться на 188.",
]


def shot(page, out: Path, name: str, full: bool = False) -> None:
    page.wait_for_timeout(1400)  # печатающаяся реплика и анимации входа
    path = out / name
    page.screenshot(path=str(path), full_page=full)
    print("снят", name)


def wait_ready(page) -> None:
    """Ход обработан: поле ввода снова активно — или партия уже закончилась
    (тогда поля с этим placeholder'ом на странице просто нет)."""
    page.wait_for_function(
        """() => {
            const field = document.querySelector('input[placeholder="Ваша реплика…"]');
            return !field || !field.disabled;
        }""",
        timeout=TURN_TIMEOUT)


def game_over(page) -> bool:
    """Партия закончилась — поля для реплики больше нет.

    Проверка с ожиданием: во время перерисовки экрана поле на мгновение
    пропадает из DOM, и мгновенный `count()` соврал бы.
    """
    try:
        page.wait_for_selector("input[placeholder='Ваша реплика…']", timeout=8_000)
        return False
    except Exception:
        return True


def send(page, text: str) -> None:
    """Отправить реплику и дождаться ответа.

    Между кликом и появлением «занято» есть окно в пару кадров: если сразу
    ждать активное поле, проверка проходит мгновенно и следующий ход
    отправляется в уже заблокированное поле. Поэтому сначала ждём, что
    интерфейс ушёл в ожидание ответа.
    """
    page.fill("input[placeholder='Ваша реплика…']", text)
    tap(page, "Сказать")
    try:
        page.wait_for_selector("input[placeholder='Дождитесь ответа…']",
                               timeout=15_000)
    except Exception:
        pass            # ход успел обработаться раньше, чем мы посмотрели
    wait_ready(page)


def tap(page, label: str, timeout: int = 30_000):
    """Клик по видимой кнопке: у экрана партии есть скрытые копии кнопок
    (мобильная полоса `md:hidden` и боковые панели `hidden md:flex`)."""
    button = page.locator("button:visible", has_text=label).first
    button.click(timeout=timeout)
    return button


# Сильная линия — та же, что в тесте `test_good_game_reaches_deal`
# (backend/tests/test_session.py): вопросы вскрывают все три интереса, аргументы
# бьют по рычагам, размен идёт условной уступкой. Её разбор на слайде стоит
# рядом с разбором слабой партии — видно, что исход определяет стратегия.
LINE_STRONG = [
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


def current_offer(page) -> int:
    """Число из карточки «На столе» — сколько сейчас предлагает оппонент."""
    match = re.search(r"(\d{2,4})\s*тыс", page.inner_text("body"))
    return int(match.group(1)) if match else 0


def play_strong(browser, out: Path) -> None:
    """Вторая партия — сильная линия, разбор для сравнения на слайде.

    Партия играется в офлайн-режиме (`use_llm: false`): распознавание берут
    эвристики, реплики — шаблоны сценария. Так линия из теста воспроизводится
    ход в ход и закрывается сделкой внутри ZOPA, а снимок не зависит от того,
    как в этот раз сработала локальная 4B. Режим переключается подменой тела
    запроса — в интерфейсе такого тумблера нет и не нужно.
    """
    page = browser.new_page(viewport=DESK, device_scale_factor=2)

    def offline(route, request):
        if request.method == "POST" and request.url.endswith("/api/sessions"):
            body = json.loads(request.post_data or "{}")
            body["use_llm"] = False
            route.continue_(post_data=json.dumps(body))
        else:
            route.continue_()

    page.route("**/api/sessions", offline)
    page.goto(BASE, wait_until="networkidle")
    page.get_by_text("Разговор о повышении").first.click()
    page.wait_for_selector("text=Начать переговоры", timeout=30_000)
    page.get_by_text("Начать переговоры").click()
    wait_ready(page)

    accept = page.locator("button:visible", has_text="Принять").first
    for number, line in enumerate(LINE_STRONG, start=1):
        if game_over(page):
            print("партия закончилась сама на ходе", number)
            break
        send(page, line)
        print(f"ход {number}: на столе {current_offer(page)}")

    if game_over(page):
        # Движок закрыл партию сам: показана карточка финала с итогом сделки.
        shot(page, out, "18-game-final.png")
        tap(page, "Разбор партии")
    elif accept.is_enabled():
        accept.click()
    else:
        tap(page, "Выйти")
    page.wait_for_selector("text=Компетенции", timeout=TURN_TIMEOUT)
    shot(page, out, "17-debrief-strong.png")
    page.close()


def main(out_dir: str, mode: str = "all") -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if mode == "strong":
        with sync_playwright() as p:
            browser = p.chromium.launch()
            play_strong(browser, out)
            browser.close()
        print("готово:", out)
        return

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=DESK, device_scale_factor=2)
        page.goto(BASE, wait_until="networkidle")

        # 1. Каталог сценариев
        shot(page, out, "01-catalog.png")

        # 2. Бриф: цель, BATNA, козыри, режимы
        page.get_by_text("Разговор о повышении").first.click()
        page.wait_for_selector("text=Начать переговоры", timeout=30_000)
        shot(page, out, "02-brief.png")

        # 3. Партия: сцена, оппонент, индикаторы, действия-мелочи
        page.get_by_text("Начать переговоры").click()
        wait_ready(page)
        shot(page, out, "03-game-opening.png")

        for i, line in enumerate(LINE, start=1):
            send(page, line)
            if i == 2:
                shot(page, out, "04-game-turn.png")

        shot(page, out, "05-game-offer.png")

        # 4. Журнал партии — провенанс каждого эффекта
        tap(page, "Журнал")
        shot(page, out, "06-game-log.png")
        page.locator(".scrim").first.click()          # оверлей закрывается по затемнению
        page.locator(".scrim").first.wait_for(state="detached", timeout=15_000)

        # 5. Финал: принять предложение. Если оппонент ещё не назвал условия,
        # добираем ходы — «Принять» включается только когда есть что принимать.
        accept = page.locator("button:visible", has_text="Принять").first
        nudges = ["Что мешает закрыть на этих условиях сегодня?",
                  "Назовите вашу цифру — и решим.",
                  "Если по критериям, то 188 и пересмотр через полгода."]
        for nudge in nudges:
            if accept.is_enabled():
                break
            send(page, nudge)
        if accept.is_enabled():
            accept.click()
        else:
            tap(page, "Выйти")
        page.wait_for_selector("text=Компетенции", timeout=TURN_TIMEOUT)
        shot(page, out, "07-debrief.png")
        shot(page, out, "08-debrief-full.png", full=True)

        # 6. Контур администратора: контекст симуляции и черновик сценария
        tap(page, "Админ")
        page.wait_for_timeout(1200)
        shot(page, out, "09-admin.png")
        tap(page, "Заполнить пример")
        shot(page, out, "10-admin-filled.png")

        # Готовый черновик (собран генератором заранее — на 4B это минуты)
        draft = Path("docs/demo/crm-srok-draft.json").read_text(encoding="utf-8")
        editor = page.locator("textarea:visible").last
        editor.fill(draft)
        tap(page, "Проверить")
        page.wait_for_timeout(1500)
        editor.scroll_into_view_if_needed()
        shot(page, out, "11-admin-draft.png")
        shot(page, out, "12-admin-full.png", full=True)

        # 7. Мобильный сценарий использования (приоритет ТЗ §3.1)
        phone = browser.new_context(viewport=PHONE, device_scale_factor=3,
                                    is_mobile=True, has_touch=True)
        mob = phone.new_page()
        mob.goto(BASE, wait_until="networkidle")
        shot(mob, out, "13-mobile-catalog.png")
        mob.get_by_text("Разговор о повышении").first.click()
        mob.wait_for_selector("text=Начать переговоры", timeout=30_000)
        shot(mob, out, "14-mobile-brief.png")
        mob.get_by_text("Начать переговоры").click()
        mob.wait_for_selector("input[placeholder='Ваша реплика…']:not([disabled])",
                              timeout=TURN_TIMEOUT)
        shot(mob, out, "15-mobile-game.png")
        tap(mob, "Журнал")          # оверлей вместо боковой панели — так на узком экране
        shot(mob, out, "16-mobile-log.png")

        browser.close()
    print("готово:", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/presentation/shots",
         sys.argv[2] if len(sys.argv) > 2 else "all")
