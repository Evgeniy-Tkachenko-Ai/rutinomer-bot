"""Обертка над Claude API.

Тест-часть приходит структурой (structured outputs), результат - текстом.
Как и договорено в брифе.
"""
from __future__ import annotations

import json
import logging
import math
from typing import Any, Optional

import anthropic
from pydantic import BaseModel, Field, field_validator

from .prompts import FREEFORM_TASK, QUIZ_TASK, RESULT_TASK, SYSTEM_PROMPT

log = logging.getLogger(__name__)

# Длинное тире и его родня в промпте запрещены, но модель иногда все равно
# их вставляет. Чистим на выходе - дешевле, чем надеяться.
_DASHES = {"—": "-", "–": "-", "−": "-", "‒": "-"}

FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Глубина размышления. low = дешевле и быстрее; для этой задачи (собрать
# 4-6 вопросов и написать короткий разбор) высокая глубина не нужна.
# Поднять до "medium"/"high", если вопросы станут общими.
EFFORT = "low"


def strip_dashes(text: str) -> str:
    for bad, good in _DASHES.items():
        text = text.replace(bad, good)
    return text


class Option(BaseModel):
    # Без max_length: длинный текст обрезает normalize_quiz, а не роняет
    # разбор ответа целиком.
    text: str
    score: int

    @field_validator("score")
    @classmethod
    def _score_range(cls, v: int) -> int:
        if v not in (0, 1, 2):
            raise ValueError("score должен быть 0, 1 или 2")
        return v


class Question(BaseModel):
    q: str
    options: list[Option]


class Quiz(BaseModel):
    questions: list[Question]


# Границы теста. В JSON-схему их положить нельзя (см. QUIZ_SCHEMA),
# поэтому они живут здесь и проверяются после ответа модели.
MIN_QUESTIONS = 3
GOOD_QUESTIONS = 4
MAX_QUESTIONS = 6
MIN_OPTIONS = 2
MAX_OPTIONS = 4
MAX_Q_LEN = 300
MAX_OPTION_LEN = 100   # больше в кнопку Telegram все равно не влезет


# Anthropic API принимает не весь JSON Schema. Запрещены, среди прочего,
# maxItems, minLength/maxLength, pattern, minimum/maximum, а minItems
# допускает только 0 или 1. Поэтому количество вопросов и вариантов
# схемой не ограничиваем - просим словами в промпте и проверяем кодом
# в normalize_quiz. Список поддерживаемого:
# https://platform.claude.com/docs/en/build-with-claude/structured-outputs
QUIZ_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "q": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "score": {"type": "integer", "enum": [0, 1, 2]},
                            },
                            "required": ["text", "score"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["q", "options"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}


def normalize_quiz(quiz: Quiz) -> Quiz:
    """Приводит ответ модели к тому, что бот умеет показать.

    Схема количества не гарантирует, так что чиним здесь: чистим тире,
    обрезаем длинные строки, выкидываем вопросы без выбора, режем хвост
    сверх максимума. Падаем только если вопросов совсем мало.
    """
    good: list[Question] = []
    for question in quiz.questions:
        options = []
        seen: set[str] = set()
        for option in question.options:
            text = strip_dashes(option.text).strip()[:MAX_OPTION_LEN]
            if not text or text.lower() in seen:
                continue
            seen.add(text.lower())
            options.append(Option(text=text, score=option.score))
        text_q = strip_dashes(question.q).strip()[:MAX_Q_LEN]
        if not text_q or len(options) < MIN_OPTIONS:
            log.warning("Выкидываю негодный вопрос: %r", question.q[:60])
            continue
        good.append(Question(q=text_q, options=options[:MAX_OPTIONS]))

    if len(good) < MIN_QUESTIONS:
        raise ValueError(
            f"Модель вернула годных вопросов: {len(good)}, "
            f"нужно минимум {MIN_QUESTIONS}"
        )
    if len(good) < GOOD_QUESTIONS:
        log.warning("Вопросов меньше желаемых %s: %s", GOOD_QUESTIONS, len(good))
    return Quiz(questions=good[:MAX_QUESTIONS])


def score_to_ten(score: int, max_score: int) -> int:
    """Баллы -> шкала 0..10. Считает бот, не модель: в брифе это требование."""
    if max_score <= 0:
        return 0
    return int(math.floor(score / max_score * 10 + 0.5))


class Claude:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        # Серверный фолбэк на случай отказа классификатора. Если прокси или
        # площадка его не понимает - выключаем и работаем дальше.
        self._fallbacks = True

    async def _create(self, **kwargs: Any) -> Any:
        # Фолбэк живет только в beta-namespace и только там принимает betas.
        if self._fallbacks:
            try:
                return await self._client.beta.messages.create(
                    betas=[FALLBACK_BETA], fallbacks="default", **kwargs
                )
            except anthropic.BadRequestError as exc:
                # Прокси или площадка не знают про этот бета-флаг. Не повод
                # падать: выключаем фолбэк и работаем на обычном эндпоинте.
                log.warning("Серверный фолбэк не принят (%s), отключаю его", exc)
                self._fallbacks = False
        return await self._client.messages.create(**kwargs)

    async def _text(self, task: str, max_tokens: int = 4000) -> str:
        response = await self._create(
            model=self._model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            output_config={"effort": EFFORT},
            messages=[{"role": "user", "content": task}],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("Модель отказалась отвечать")
        parts = [b.text for b in response.content if b.type == "text" and b.text]
        return strip_dashes("\n".join(parts).strip())

    async def generate_quiz(self, niche: str, pain: str) -> Quiz:
        task = QUIZ_TASK.format(niche=niche or "не сказал", pain=pain or "не сказал")
        response = await self._create(
            model=self._model,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": task}],
            output_config={
                "effort": EFFORT,
                "format": {"type": "json_schema", "schema": QUIZ_SCHEMA},
            },
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("Модель отказалась генерировать тест")
        raw = next(b.text for b in response.content if b.type == "text")
        return normalize_quiz(Quiz.model_validate(json.loads(raw)))

    async def generate_result(
        self,
        niche: str,
        pain: str,
        answers: list[dict[str, Any]],
        score: int,
        max_score: int,
        score10: int,
    ) -> str:
        lines = [
            f"{i}. {a['q']}\n   ответ: {a['answer']} (балл {a['score']} из 2)"
            for i, a in enumerate(answers, 1)
        ]
        return await self._text(
            RESULT_TASK.format(
                niche=niche or "не сказал",
                pain=pain or "не сказал",
                answers="\n".join(lines),
                score=score,
                max_score=max_score,
                score10=score10,
            )
        )

    async def answer_freeform(
        self, niche: str, score10: Optional[int], question: str
    ) -> str:
        return await self._text(
            FREEFORM_TASK.format(
                niche=niche or "не сказал",
                score10=score10 if score10 is not None else "не считали",
                question=question,
            ),
            max_tokens=2000,
        )

    async def close(self) -> None:
        await self._client.close()
