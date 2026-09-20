"""Страховка от того бага, из-за которого selftest падал.

Anthropic API принимает не весь JSON Schema. Один maxItems в схеме - и
генерация теста падает целиком. Поэтому проверяем схему автоматически.
"""
from __future__ import annotations

import pytest

from bot.llm import (
    MAX_OPTIONS,
    MAX_QUESTIONS,
    MIN_OPTIONS,
    MIN_QUESTIONS,
    QUIZ_SCHEMA,
    Option,
    Question,
    Quiz,
    normalize_quiz,
)

# Не поддерживаются structured outputs вообще:
# https://platform.claude.com/docs/en/build-with-claude/structured-outputs
FORBIDDEN = {
    "maxItems", "minLength", "maxLength", "pattern",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "multipleOf", "uniqueItems", "minProperties", "maxProperties",
    "oneOf", "not", "if", "then", "else",
}


def walk(node, path="$"):
    """Обходит схему целиком, отдает пары (путь, ключ, значение)."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield path, key, value
            yield from walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from walk(item, f"{path}[{i}]")


def test_no_forbidden_keywords() -> None:
    found = [
        f"{path}.{key}" for path, key, _ in walk(QUIZ_SCHEMA) if key in FORBIDDEN
    ]
    assert not found, f"В схеме запрещенные ключевые слова: {found}"


def test_min_items_only_zero_or_one() -> None:
    """minItems допускает только 0 и 1. Именно на этом падал selftest."""
    bad = [
        f"{path}.minItems={value}"
        for path, key, value in walk(QUIZ_SCHEMA)
        if key == "minItems" and value not in (0, 1)
    ]
    assert not bad, f"minItems вне допустимого: {bad}"


def test_objects_close_additional_properties() -> None:
    """У каждого object обязателен additionalProperties: false."""
    for path, key, value in walk(QUIZ_SCHEMA):
        if key == "type" and value == "object":
            parent = path
            assert "additionalProperties" in _at(QUIZ_SCHEMA, parent), (
                f"У объекта {parent} нет additionalProperties: false"
            )


def _at(schema, path):
    node = schema
    for part in path.split(".")[1:]:
        if part.endswith("]"):
            name, idx = part[:-1].split("[")
            node = node[name][int(idx)]
        else:
            node = node[part]
    return node


def _q(text="Как приходят заявки?", n_options=3):
    scores = [0, 1, 2, 2][:n_options]
    return Question(
        q=text,
        options=[Option(text=f"вариант {i}", score=s) for i, s in enumerate(scores)],
    )


def test_normalize_keeps_good_quiz() -> None:
    quiz = normalize_quiz(Quiz(questions=[_q() for _ in range(4)]))
    assert len(quiz.questions) == 4


def test_normalize_trims_to_max() -> None:
    quiz = normalize_quiz(Quiz(questions=[_q() for _ in range(9)]))
    assert len(quiz.questions) == MAX_QUESTIONS


def test_normalize_drops_questions_without_choice() -> None:
    """Вопрос с одним вариантом бесполезен: выкидываем, остальные живут."""
    quiz = normalize_quiz(
        Quiz(questions=[_q() for _ in range(4)] + [_q(n_options=1)])
    )
    assert len(quiz.questions) == 4
    assert all(len(q.options) >= MIN_OPTIONS for q in quiz.questions)


def test_normalize_raises_when_too_few() -> None:
    with pytest.raises(ValueError, match="минимум"):
        normalize_quiz(Quiz(questions=[_q(), _q()]))


def test_normalize_survives_three_questions() -> None:
    """3 вопроса - не идеал, но диалог ронять из-за этого не надо."""
    assert len(normalize_quiz(Quiz(questions=[_q() for _ in range(3)])).questions) == 3
    assert MIN_QUESTIONS == 3


def test_normalize_truncates_long_texts() -> None:
    long_option = Question(
        q="я" * 500, options=[Option(text="д" * 300, score=0), Option(text="x", score=2)]
    )
    quiz = normalize_quiz(Quiz(questions=[long_option] + [_q() for _ in range(3)]))
    assert len(quiz.questions[0].q) <= 300
    assert all(len(o.text) <= 100 for o in quiz.questions[0].options)


def test_normalize_strips_dashes_and_dupes() -> None:
    question = Question(
        q="Что — происходит?",
        options=[
            Option(text="руками", score=0),
            Option(text="Руками", score=1),   # дубль по регистру
            Option(text="автоматом — да", score=2),
        ],
    )
    quiz = normalize_quiz(Quiz(questions=[question] + [_q() for _ in range(3)]))
    first = quiz.questions[0]
    assert "—" not in first.q
    assert len(first.options) == 2
    assert "—" not in first.options[1].text


def test_normalize_respects_max_options() -> None:
    question = Question(
        q="Вопрос?",
        options=[Option(text=f"в{i}", score=i % 3) for i in range(7)],
    )
    quiz = normalize_quiz(Quiz(questions=[question] + [_q() for _ in range(3)]))
    assert len(quiz.questions[0].options) == MAX_OPTIONS
