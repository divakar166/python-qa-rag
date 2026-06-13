import os
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.api import app


def _make_point(payload: dict, score: float = 0.95):
    point = MagicMock()
    point.payload = payload
    point.score = score
    return point


def _make_search_result(points: list):
    result = MagicMock()
    result.points = points
    return result


def _make_completion(text: str):
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    return completion


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


SAMPLE_PAYLOAD = {
    "title": "How to sort a list in Python?",
    "tags": "python, list, sorting",
    "question_id": 123,
    "document": "Use sorted() or list.sort(). The sorted() function returns a new sorted list.",
}

# GET /

@pytest.mark.asyncio
async def test_root_returns_html(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# GET /health

@pytest.mark.asyncio
async def test_health_qdrant_connected(client):
    with patch("app.api.qdrant_client.get_collection") as mock:
        mock.return_value = None
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["qdrant"] == "connected"


@pytest.mark.asyncio
async def test_health_qdrant_unavailable(client):
    with patch("app.api.qdrant_client.get_collection") as mock:
        mock.side_effect = Exception("Connection refused")
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["qdrant"] == "unavailable"


# POST /ask

@pytest.mark.asyncio
async def test_ask_success(client):
    qdrant_result = _make_search_result(
        [_make_point(dict(SAMPLE_PAYLOAD), score=0.95)]
    )
    llm_answer = "You can use sorted() or list.sort()."

    with (
        patch("app.api.qdrant_client.query_points", return_value=qdrant_result),
        patch("app.api.llm_client.chat.completions.create",
              return_value=_make_completion(llm_answer)),
    ):
        response = await client.post("/ask", json={"question": "How do I sort a list?"})

    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "How do I sort a list?"
    assert data["answer"] == llm_answer
    assert len(data["sources"]) == 1
    src = data["sources"][0]
    assert src["title"] == "How to sort a list in Python?"
    assert src["tags"] == "python, list, sorting"
    assert src["score"] == 0.95
    assert src["question_id"] == 123


@pytest.mark.asyncio
async def test_ask_multiple_sources(client):
    points = [
        _make_point({"title": "A", "tags": "a", "question_id": 1,
                      "document": "Content A"}, 0.95),
        _make_point({"title": "B", "tags": "b", "question_id": 2,
                      "document": "Content B"}, 0.87),
        _make_point({"title": "C", "tags": "c", "question_id": 3,
                      "document": "Content C"}, 0.76),
    ]

    with (
        patch("app.api.qdrant_client.query_points",
              return_value=_make_search_result(points)),
        patch("app.api.llm_client.chat.completions.create",
              return_value=_make_completion("Combined answer.")),
    ):
        response = await client.post("/ask", json={"question": "test"})

    assert response.status_code == 200
    data = response.json()
    assert len(data["sources"]) == 3
    assert data["sources"][0]["question_id"] == 1
    assert data["sources"][2]["score"] == 0.76


@pytest.mark.asyncio
async def test_ask_no_documents_found(client):
    with (
        patch("app.api.qdrant_client.query_points",
              return_value=_make_search_result([])),
    ):
        response = await client.post("/ask", json={"question": "unknown topic"})

    assert response.status_code == 404
    assert response.json()["detail"] == "No relevant documents found"


@pytest.mark.asyncio
async def test_ask_qdrant_query_fails(client):
    with patch("app.api.qdrant_client.query_points",
               side_effect=Exception("Qdrant timeout")):
        response = await client.post("/ask", json={"question": "hello"})

    assert response.status_code == 502
    assert "Retrieval failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_ask_llm_generation_fails(client):
    qdrant_result = _make_search_result(
        [_make_point(dict(SAMPLE_PAYLOAD), score=0.95)]
    )

    with (
        patch("app.api.qdrant_client.query_points", return_value=qdrant_result),
        patch("app.api.llm_client.chat.completions.create",
              side_effect=Exception("LLM unavailable")),
    ):
        response = await client.post("/ask", json={"question": "hello"})

    assert response.status_code == 502
    assert "Generation failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_ask_empty_question(client):
    response = await client.post("/ask", json={"question": ""})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ask_question_too_long(client):
    long_q = "x" * 1001
    response = await client.post("/ask", json={"question": long_q})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ask_missing_field(client):
    response = await client.post("/ask", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ask_handles_null_payload_fields(client):
    point = MagicMock()
    point.payload = {"title": None, "tags": None, "question_id": None,
                     "document": None}
    point.score = 0.9
    qdrant_result = _make_search_result([point])

    with (
        patch("app.api.qdrant_client.query_points", return_value=qdrant_result),
        patch("app.api.llm_client.chat.completions.create",
              return_value=_make_completion("answer")),
    ):
        response = await client.post("/ask", json={"question": "hello"})

    assert response.status_code == 200
    src = response.json()["sources"][0]
    assert src["title"] == ""
    assert src["tags"] == ""
    assert src["question_id"] == 0


@pytest.mark.asyncio
async def test_ask_empty_context_still_generates(client):
    qdrant_result = _make_search_result(
        [_make_point({"title": "T", "tags": "t", "question_id": 1,
                       "document": ""}, score=0.9)]
    )

    with (
        patch("app.api.qdrant_client.query_points", return_value=qdrant_result),
        patch("app.api.llm_client.chat.completions.create",
              return_value=_make_completion("Generated without context")),
    ):
        response = await client.post("/ask", json={"question": "hello"})

    assert response.status_code == 200
    assert response.json()["answer"] == "Generated without context"
