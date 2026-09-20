"""Сравнение моделей на одних и тех же нишах: python -m bot.compare

Отвечает на вопрос "не просела ли осмысленность после перехода на Sonnet".
Гоняет одну и ту же диагностику двумя моделями и печатает рядом, плюс
время и токены. Решение принимаешь глазами - автоматически "осмысленность"
не измерить.

    python -m bot.compare                          # sonnet low vs opus high
    python -m bot.compare claude-sonnet-5:low claude-sonnet-5:high
"""
from __future__ import annotations

import asyncio
import sys
import time

from .config import Config
from .llm import Claude, score_to_ten
from .prompts import QUIZ_TASK, RESULT_TASK, SYSTEM_PROMPT

NICHES = [
    ("барбершоп в Батуми, 3 мастера, записи через инстаграм", "теряю заявки ночью"),
    ("оптовая продажа стройматериалов, 400 постоянных клиентов, менеджеры "
     "сидят в 1С и вручную дублируют заявки в почту", ""),
]

DEFAULT = ["claude-sonnet-5:low", "claude-opus-5:high"]


class Probe(Claude):
    """Claude с фиксированным effort и подсчетом токенов."""

    def __init__(self, api_key: str, model: str, effort: str) -> None:
        super().__init__(api_key, model)
        self._effort = effort
        self.tokens_in = 0
        self.tokens_out = 0

    async def _create(self, **kwargs):
        kwargs["output_config"] = {**kwargs.get("output_config", {}),
                                   "effort": self._effort}
        response = await super()._create(**kwargs)
        usage = getattr(response, "usage", None)
        if usage:
            self.tokens_in += getattr(usage, "input_tokens", 0) or 0
            self.tokens_out += getattr(usage, "output_tokens", 0) or 0
        return response


async def probe(api_key: str, spec: str) -> None:
    model, _, effort = spec.partition(":")
    effort = effort or "high"
    claude = Probe(api_key, model, effort)
    print("=" * 78)
    print(f"МОДЕЛЬ: {model}   effort={effort}")
    print("=" * 78)
    try:
        for niche, pain in NICHES:
            print(f"\n--- ниша: {niche[:62]}")
            started = time.monotonic()
            quiz = await claude.generate_quiz(niche, pain)
            for i, question in enumerate(quiz.questions, 1):
                print(f"  {i}. {question.q}")
                for option in question.options:
                    print(f"      [{option.score}] {option.text}")

            answers, score = [], 0
            for question in quiz.questions:
                # Берем средний вариант: так результат содержит и похвалу,
                # и провалы, а не только одно из двух.
                chosen = question.options[len(question.options) // 2]
                answers.append({"q": question.q, "answer": chosen.text,
                                "score": chosen.score})
                score += chosen.score
            max_score = sum(max(o.score for o in q.options) for q in quiz.questions)
            score10 = score_to_ten(score, max_score)

            result = await claude.generate_result(
                niche, pain, answers, score, max_score, score10
            )
            print(f"\n  РЕЗУЛЬТАТ ({score}/{max_score} -> {score10}/10):\n")
            for line in result.splitlines():
                print(f"   {line}")
            print(f"\n  время: {time.monotonic() - started:.1f} с")

        print(f"\nИТОГО {model}:{effort} - токенов на входе {claude.tokens_in}, "
              f"на выходе {claude.tokens_out}")
    except Exception as exc:
        print(f"  ОШИБКА на {model}: {type(exc).__name__}: {exc}")
    finally:
        try:
            await claude.close()
        except Exception:
            pass


async def run() -> int:
    config = Config.load()
    specs = sys.argv[1:] or DEFAULT
    print("Сравниваю. Это несколько вызовов модели, стоит копейки, но не ноль.\n")
    for spec in specs:
        await probe(config.anthropic_api_key, spec)
        print()
    print("Смотри сам: вопросы привязаны к нише или общие? Результат называет\n"
          "конкретные процессы или льет воду? Если Sonnet заметно хуже -\n"
          "поднимай EFFORT в bot/llm.py или верни CLAUDE_MODEL=claude-opus-5.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
