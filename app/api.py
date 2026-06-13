import logging
import os
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from openai import OpenAI
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.models import Document

from config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "sentence-transformers/all-minilm-l6-v2"


class AskRequest(BaseModel):
    question: str = Field(..., min_length=10, max_length=1000)


class Source(BaseModel):
    title: str
    tags: str
    score: float
    question_id: int


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: List[Source]


class HealthResponse(BaseModel):
    status: str
    qdrant: str


qdrant_client = QdrantClient(
    url=settings.qdrant_url,
    api_key=settings.qdrant_api_key or None,
    cloud_inference=True,
    check_compatibility=False,
)

llm_client = OpenAI(
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url
)

app = FastAPI(title="Python Q&A RAG API", version="0.1.0")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
INDEX_HTML = os.path.join(STATIC_DIR, "index.html")


@app.get("/")
async def root():
    return FileResponse(INDEX_HTML)


@app.get("/health", response_model=HealthResponse)
async def health():
    try:
        qdrant_client.get_collection(settings.collection)
        qdrant_status = "connected"
    except Exception:
        qdrant_status = "unavailable"
    return HealthResponse(status="ok", qdrant=qdrant_status)


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    try:
        search_result = qdrant_client.query_points(
            collection_name=settings.collection,
            query=Document(
                text=request.question,
                model=EMBEDDING_MODEL,
            ),
            limit=settings.top_k,
            with_payload=True,
        )
    except Exception as e:
        logger.error("Qdrant query failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Retrieval failed: {e}")

    if not search_result.points:
        raise HTTPException(status_code=404, detail="No relevant documents found")

    contexts = []
    sources = []
    for point in search_result.points:
        payload = point.payload
        contexts.append(payload.get("document") or "")
        sources.append(Source(
            title=payload.get("title") or "",
            tags=payload.get("tags") or "",
            score=point.score,
            question_id=payload.get("question_id") or 0,
        ))

    context_text = "\n\n---\n\n".join(contexts)

    system_prompt = (
        "You are a helpful Python expert assistant. Use the provided Stack Overflow Q&A context "
        "to answer the user's question accurately. If the context doesn't contain enough information "
        "to answer, say so clearly. Cite relevant details from the context."
    )
    user_prompt = (
        f"Context from Stack Overflow:\n{context_text}\n\n"
        f"Question: {request.question}\n\n"
        f"Answer based on the context above:"
    )

    try:
        completion = llm_client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
            top_p=settings.top_p,
        )
        answer = completion.choices[0].message.content or ""
    except Exception as e:
        logger.error("LLM generation failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Generation failed: {e}")

    return AskResponse(
        question=request.question,
        answer=answer,
        sources=sources,
    )
