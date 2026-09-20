"""Проверка тела запроса без сети: подменяем HTTP-транспорт.

Смысл: убедиться, что модель и effort уходят в оба вызова, а не просто
лежат в константах. И что в схеме нет ключевых слов, которых API не ест.
"""
from __future__ import annotations

import json

import httpx2
import pytest
from anthropic import AsyncAnthropic

from bot.llm import EFFORT, Claude

MODEL = "claude-sonnet-5"

FAKE_QUIZ = {
    "questions": [
        {
            "q": f"Вопрос {i}?",
            "options": [
                {"text": "руками", "score": 0},
                {"text": "криво", "score": 1},
                {"text": "автоматом", "score": 2},
            ],
        }
        for i in range(4)
    ]
}


def _client(captured: list[dict], reply: str):
    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(json.loads(request.content))
        return httpx2.Response(
            200,
            json={
                "id": "msg_1", "type": "message", "role": "assistant", "model": MODEL,
                "content": [{"type": "text", "text": reply}],
                "stop_reason": "end_turn", "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    claude = Claude.__new__(Claude)
    claude._client = AsyncAnthropic(
        api_key="sk-ant-fake",
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    claude._model = MODEL
    claude._fallbacks = True
    return claude


@pytest.mark.asyncio
async def test_quiz_request_carries_model_and_effort() -> None:
    captured: list[dict] = []
    claude = _client(captured, json.dumps(FAKE_QUIZ, ensure_ascii=False))
    await claude.generate_quiz("барбершоп", "теряю заявки")
    body = captured[0]
    assert body["model"] == MODEL
    assert body["output_config"]["effort"] == EFFORT == "low"
    assert body["output_config"]["format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_result_request_carries_model_and_effort() -> None:
    captured: list[dict] = []
    claude = _client(captured, "Твой уровень автоматизации: 4 из 10")
    await claude.generate_result(
        "барбершоп", "", [{"q": "a", "answer": "b", "score": 0}], 0, 8, 0
    )
    body = captured[0]
    assert body["model"] == MODEL
    assert body["output_config"]["effort"] == EFFORT


@pytest.mark.asyncio
async def test_freeform_request_carries_effort() -> None:
    captured: list[dict] = []
    claude = _client(captured, "Это обсуждается с Евгением на созвоне.")
    await claude.answer_freeform("барбершоп", 4, "а CRM внедряете?")
    assert captured[0]["output_config"]["effort"] == EFFORT


@pytest.mark.asyncio
async def test_no_forbidden_schema_keywords_on_the_wire() -> None:
    """Страховка от бага, который ронял selftest: API не ест maxItems."""
    forbidden = {
        "maxItems", "minLength", "maxLength", "pattern",
        "minimum", "maximum", "multipleOf", "uniqueItems",
    }
    captured: list[dict] = []
    claude = _client(captured, json.dumps(FAKE_QUIZ, ensure_ascii=False))
    await claude.generate_quiz("барбершоп", "")
    raw = json.dumps(captured[0])
    found = [word for word in forbidden if f'"{word}"' in raw]
    assert not found, f"В запросе запрещенные ключевые слова: {found}"
    assert '"minItems"' not in raw or '"minItems": 1' in raw
