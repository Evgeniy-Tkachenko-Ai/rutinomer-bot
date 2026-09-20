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
