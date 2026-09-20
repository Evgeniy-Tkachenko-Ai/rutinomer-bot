"""Оффер - статичная часть, значит его можно проверить без сети.

Повод: в выводе selftest оффера не видно (там только вызовы модели), и
легко решить, что бот выдает один вариант вместо двух. Пусть это
проверяет тест, а не глаз.
"""
from __future__ import annotations

from bot import keyboards as kb
from bot import texts
from bot.handlers.offer import OFFER_LABELS


def test_offer_has_exactly_two_buttons() -> None:
    rows = kb.offer_kb().inline_keyboard
    buttons = [b for row in rows for b in row]
    assert len(buttons) == 2, f"Кнопок должно быть 2, а не {len(buttons)}"


def test_offer_button_labels() -> None:
    buttons = [b for row in kb.offer_kb().inline_keyboard for b in row]
    labels = [b.text for b in buttons]
    assert labels == ["Заказать расчет", "Бесплатная консультация"], labels


def test_offer_callbacks_are_handled() -> None:
    """Каждая кнопка должна попадать в хендлер, иначе тык в пустоту."""
    callbacks = {b.callback_data for row in kb.offer_kb().inline_keyboard for b in row}
    assert callbacks == set(OFFER_LABELS), (
        f"Кнопки {callbacks} не совпадают с обработчиками {set(OFFER_LABELS)}"
    )


def test_offer_text_mentions_both_options() -> None:
    assert "расчет стоимости и сроков" in texts.OFFER
    assert "бесплатную консультацию" in texts.OFFER.lower()


def test_offer_text_has_no_long_dashes() -> None:
    assert "—" not in texts.OFFER


def test_result_prompt_forbids_own_cta() -> None:
    """Модель не должна дописывать свой призыв: он спорит с кнопками."""
    from bot.prompts import RESULT_TASK

    assert "Ничего после него не дописывай" in RESULT_TASK
    assert "готов записаться?" in RESULT_TASK
