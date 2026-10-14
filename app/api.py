"""HTTP API for the chatbot.

Run:
  python -m uvicorn app.api:app --port 8000

Auth: set RAG_API_TOKEN and send header  Authorization: Bearer <token>
"""

import logging
import os
import secrets
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.ingest import build_index
from app.rag import answer_question
from app.vectorstore import get_vectorstore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("rag-api")

API_TOKEN = os.getenv("RAG_API_TOKEN", "")
INGEST_ON_STARTUP = os.getenv("INGEST_ON_STARTUP", "false").lower() == "true"
WARM_UP_ON_STARTUP = os.getenv("WARM_UP_ON_STARTUP", "true").lower() == "true"

SESSIONS: dict[str, list[dict]] = {}
_vectorstore = None
_lock = threading.Lock()


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


def _get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = get_vectorstore(get_settings())
    return _vectorstore


def _chunk_count(store) -> int:
    return len(store.get(include=[])["ids"])


def _warm_up() -> None:
    """Load Chroma and open the embeddings connection before serving traffic."""
    start = time.perf_counter()
    try:
        _get_vectorstore().similarity_search("warm up", k=1)
        logger.info("Warm-up complete in %.1fs", time.perf_counter() - start)
    except Exception:
        logger.exception("Warm-up failed - first request will be slower")


def require_token(authorization: str | None = Header(default=None)) -> None:
    if not API_TOKEN:
        return
    if not authorization or not secrets.compare_digest(authorization, f"Bearer {API_TOKEN}"):
        raise HTTPException(401, "Missing or invalid API token")


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _vectorstore
    if not API_TOKEN:
        logger.warning("RAG_API_TOKEN is not set - API authentication is DISABLED")
    if INGEST_ON_STARTUP:
        try:
            if _chunk_count(_get_vectorstore()) == 0:
                logger.info("Index is empty - ingesting on startup")
                logger.info("Ingest result: %s", build_index(get_settings()))
                _vectorstore = None
        except Exception:
            logger.exception("Startup ingest failed - call POST /ingest when the source is ready")
    if WARM_UP_ON_STARTUP:
        _warm_up()
    yield


app = FastAPI(title="ai-rag-chatbot", lifespan=lifespan)
protected = APIRouter(dependencies=[Depends(require_token)])


@app.get("/health")
def health() -> dict:
    return {"status": "healthy"}


@protected.post("/ask")
def ask(req: AskRequest) -> dict:
    settings = get_settings()
    session_id = req.session_id or uuid.uuid4().hex[:12]
    history = SESSIONS.get(session_id, [])

    result = answer_question(req.question, history, settings, _get_vectorstore())

    turn = {"question": req.question, "answer": result["answer"]}
    SESSIONS[session_id] = (history + [turn])[-settings.history_turns:]
    return {"session_id": session_id, **result}


@protected.post("/ingest")
def ingest() -> dict:
    global _vectorstore
    with _lock:
        stats = build_index(get_settings())
        _vectorstore = None
    logger.info("Re-ingested: %s chunks from %s documents", stats["chunks"], stats["documents"])
    return stats


@protected.get("/stats")
def stats() -> dict:
    settings = get_settings()
    return {
        "collection": settings.collection_name,
        "chunks": _chunk_count(_get_vectorstore()),
        "docs_source": settings.docs_source,
        "llm_provider": settings.llm_provider,
        "embedding_provider": settings.embedding_provider,
        "active_sessions": len(SESSIONS),
    }


@protected.delete("/sessions/{session_id}")
def clear_session(session_id: str) -> dict:
    SESSIONS.pop(session_id, None)
    return {"cleared": session_id}


app.include_router(protected)
