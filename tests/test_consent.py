"""Первый экран. Он отпугивает людей быстрее всего, поэтому под тестом.

Правило: приветствие короткое, все подробности про данные - за кнопкой.
"""
from __future__ import annotations

from bot import keyboards as kb
from bot import texts

MAX_CONSENT_LEN = 300


def _labels() -> list[str]:
    return [b.text for row in kb.consent_kb().inline_keyboard for b in row]


def test_consent_is_short() -> None:
    assert len(texts.CONSENT) <= MAX_CONSENT_LEN, (
        f"Первый экран разросся до {len(texts.CONSENT)} символов"
    )


def test_consent_has_two_buttons() -> None:
    assert _labels() == ["Поехали", "Что за данные?"], _labels()


def test_consent_mentions_both_buttons_exactly() -> None:
    """Подписи в тексте и на кнопках не должны разъехаться."""
    for label in _labels():
        assert label in texts.CONSENT, f"Кнопка {label!r} не упомянута в тексте"


def test_consent_says_it_is_consent() -> None:
    assert "согласие на обработку данных" in texts.CONSENT


def test_consent_introduces_the_bot() -> None:
    """Человек должен понять, кто с ним говорит и зачем."""
    assert "Рутиномер" in texts.CONSENT
    assert "Евгения Ткаченко" in texts.CONSENT
    assert "5 минут" in texts.CONSENT


def test_consent_has_no_details() -> None:
    """Подробности переехали в PRIVACY. На первом экране их быть не должно."""
    for word in ("удалить", "/delete", "Anthropic", "не продаю", "Сколько храню"):
        assert word not in texts.CONSENT, f"{word!r} должен быть за кнопкой"


def test_privacy_keeps_all_details() -> None:
    """Убрали с первого экрана - значит обязаны показать по кнопке."""
    for fragment in ("Что храню", "Зачем", "никому", "/delete", "Anthropic"):
        assert fragment in texts.PRIVACY, f"В PRIVACY потерялось: {fragment!r}"


def test_privacy_gives_a_reachable_contact() -> None:
    """Отправлять с вопросами в никуда нельзя - нужен живой аккаунт."""
    assert "@aixors" in texts.PRIVACY


def test_no_long_dashes_on_first_screens() -> None:
    assert "—" not in texts.CONSENT
    assert "—" not in texts.PRIVACY


def test_privacy_screen_has_only_go_button() -> None:
    """На экране подробностей не предлагаем те же подробности снова."""
    labels = [b.text for row in kb.privacy_kb().inline_keyboard for b in row]
    assert labels == ["Поехали"], labels


def test_greeting_does_not_greet_again() -> None:
    """Здороваемся один раз - на экране согласия. Повтор выглядит как сбой."""
    assert "приветствую" not in texts.GREETING.lower()
    assert "Категорически" not in texts.GREETING


def test_greeting_does_not_repeat_the_pitch() -> None:
    """Про 5 минут и потерю времени сказано на первом экране."""
    assert "теряет время и деньги" not in texts.GREETING


def test_greeting_keeps_price_and_first_question() -> None:
    """Но то, чего на первом экране не было, обязано остаться."""
    assert "3$" in texts.GREETING
    assert "звездах Telegram" in texts.GREETING
    assert "Напиши про свой бизнес" in texts.GREETING


def test_start_screen_always_has_buttons() -> None:
    """Стартовый экран один и тот же всегда, и на нем есть кнопки."""
    labels = [b.text for row in kb.consent_kb().inline_keyboard for b in row]
    assert labels == ["Поехали", "Что за данные?"]


def test_greeting_asks_the_first_question() -> None:
    assert "Напиши про свой бизнес" in texts.GREETING
    assert "3$" in texts.GREETING


def test_consent_and_returning_start_share_the_wording() -> None:
    """Приветствие и представление не должны разъехаться между экранами."""
    assert texts.HELLO in texts.CONSENT
    assert texts.INTRO in texts.CONSENT
