"""Проверка связки с Claude одной командой: python -m bot.selftest

Нужна, потому что все остальное можно проверить без сети, а этот запрос -
нет. Тратит один вызов модели, копейки.
"""
from __future__ import annotations

import asyncio
import sys

import anthropic

from .config import Config
from .llm import Claude, score_to_ten

NICHE = "барбершоп в Батуми, 3 мастера, записи приходят в инстаграм"


async def run() -> int:
    config = Config.load()
    claude = Claude(config.anthropic_api_key, config.model)
    try:
        print(f"Модель: {config.model}. Генерирую тест под тестовую нишу...\n")
        quiz = await claude.generate_quiz(NICHE, "")
        answers = []
        for i, question in enumerate(quiz.questions, 1):
            print(f"{i}. {question.q}")
            for option in question.options:
                print(f"   [{option.score}] {option.text}")
            answers.append(
                {
                    "q": question.q,
                    "answer": question.options[0].text,
                    "score": question.options[0].score,
                }
            )

        score = sum(a["score"] for a in answers)
        max_score = sum(max(o.score for o in q.options) for q in quiz.questions)
        score10 = score_to_ten(score, max_score)
        print(f"\nВопросов: {len(quiz.questions)}. Если выбрать худшее: {score10}/10\n")

        print("Генерирую результат...\n")
        print(await claude.generate_result(NICHE, "", answers, score, max_score, score10))
        print(
            "\nВсе работает. Можно запускать бота: python -m bot\n\n"
            "Учти: выше проверены только два вызова модели - тест и результат.\n"
            "Шаг 5 (оффер) в selftest не входит: это статичный текст и две\n"
            "кнопки, их отправляет сам бот сразу после результата. В чате ты\n"
            "увидишь 'Заказать расчет' и 'Бесплатная консультация'."
        )
        return 0
    except anthropic.AuthenticationError:
        print("\nКлюч не принят. Проверь ANTHROPIC_API_KEY в .env", file=sys.stderr)
        return 1
    except anthropic.BadRequestError as exc:
        print(f"\nAPI отклонил запрос: {exc}", file=sys.stderr)
        if "output_config" in str(exc) or "schema" in str(exc):
            print(
                "Похоже на JSON-схему в QUIZ_SCHEMA (bot/llm.py). API принимает\n"
                "не весь JSON Schema: maxItems и minLength/maxLength/pattern\n"
                "запрещены, minItems - только 0 или 1. Количество вопросов\n"
                "ограничивай в normalize_quiz, а не в схеме. Тест на это:\n"
                "python -m pytest tests/test_schema.py",
                file=sys.stderr,
            )
        return 1
    except Exception as exc:
        print(f"\nНе получилось: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("Проверь ANTHROPIC_API_KEY и баланс на аккаунте.", file=sys.stderr)
        return 1
    finally:
        try:
            await claude.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
