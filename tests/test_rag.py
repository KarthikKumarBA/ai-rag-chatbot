"""RAG tests with deterministic fake embeddings and a fake chat model (files source)."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app import api
from app.config import get_settings
from app.ingest import build_index, split_documents
from app.rag import NO_ANSWER, answer_question, format_context, retrieve
from app.sources.files import load_files
from app.vectorstore import get_vectorstore

POLICY = """# Leave Policy

## Annual Leave

Employees receive 24 days of paid annual leave per year.

## Sick Leave

Employees receive 12 days of paid sick leave per year.
"""


@pytest.fixture
def settings(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "policy.md").write_text(POLICY, encoding="utf-8")
    (docs / "notes.txt").write_text("The office opens at 9 AM.", encoding="utf-8")
    return replace(
        get_settings(),
        docs_source="files",
        docs_dir=docs,
        vectorstore_dir=tmp_path / "vectorstore",
        collection_name="test_docs",
        chunk_size=200,
        chunk_overlap=20,
        top_k=3,
        min_relevance=0.5,
        history_turns=3,
    )


@pytest.fixture
def embeddings():
    return DeterministicFakeEmbedding(size=64)


@pytest.fixture
def store(settings, embeddings):
    build_index(settings, embeddings)
    return get_vectorstore(settings, embeddings)


def annual_leave_chunk(settings) -> str:
    chunks = split_documents(load_files(settings.docs_dir), settings.chunk_size,
                             settings.chunk_overlap)
    return next(c.page_content for c in chunks if "24 days" in c.page_content)


class ExplodingLLM:
    def invoke(self, *_args, **_kwargs):
        raise AssertionError("LLM must not be called")


# ---------- Ingestion ----------
def test_load_files_reads_md_and_txt(settings):
    sources = sorted(d.metadata["source"] for d in load_files(settings.docs_dir))
    assert sources == ["notes.txt", "policy.md"]


def test_markdown_chunks_keep_section_titles(settings):
    chunks = split_documents(load_files(settings.docs_dir), 200, 20)
    sections = {c.metadata["section"] for c in chunks if c.metadata["source"] == "policy.md"}
    assert "Leave Policy > Annual Leave" in sections
    assert "Leave Policy > Sick Leave" in sections
    assert all("chunk" in c.metadata for c in chunks)


def test_build_index_is_repeatable(settings, embeddings):
    first = build_index(settings, embeddings)
    second = build_index(settings, embeddings)
    assert first["chunks"] == second["chunks"]
    assert second["removed_chunks"] == 0
    store = get_vectorstore(settings, embeddings)
    assert len(store.get(include=[])["ids"]) == second["chunks"]


def test_reingest_removes_deleted_documents(settings, embeddings):
    build_index(settings, embeddings)
    (settings.docs_dir / "notes.txt").unlink()

    stats = build_index(settings, embeddings)

    store = get_vectorstore(settings, embeddings)
    sources = {m["source"] for m in store.get(include=["metadatas"])["metadatas"]}
    assert sources == {"policy.md"}
    assert stats["removed_chunks"] == 1


def test_open_store_keeps_working_after_reingest(settings, embeddings, store):
    # Regression: re-ingest used to drop the collection and break open handles
    build_index(settings, embeddings)
    results = retrieve(annual_leave_chunk(settings), settings, store)
    assert results and "24 days" in results[0][0].page_content


# ---------- Retrieval ----------
def test_retrieve_finds_matching_chunk(settings, store):
    results = retrieve(annual_leave_chunk(settings), settings, store)
    assert results
    assert "24 days" in results[0][0].page_content
    assert 0.0 <= results[0][1] <= 1.0
    assert results[0][1] >= settings.min_relevance


def test_format_context_numbers_sources(settings, store):
    context = format_context(retrieve(annual_leave_chunk(settings), settings, store))
    assert context.startswith("[1] (page: Policy")


# ---------- Answering ----------
def test_answer_returns_text_and_sources(settings, store):
    llm = FakeListChatModel(responses=["Employees get 24 days of annual leave [1]."])
    result = answer_question(annual_leave_chunk(settings), None, settings, store, llm)

    assert result["answer"] == "Employees get 24 days of annual leave [1]."
    assert result["sources"][0]["source"] == "policy.md"
    assert result["sources"][0]["section"] == "Leave Policy > Annual Leave"


def test_no_relevant_context_skips_llm(settings, store):
    strict = replace(settings, min_relevance=1.01)
    result = answer_question("What is the share price?", None, strict, store, ExplodingLLM())
    assert result["answer"] == NO_ANSWER
    assert result["sources"] == []


def test_refusal_hides_sources(settings, store):
    # Chunks were retrieved, but the LLM refused: no sources should be shown
    llm = FakeListChatModel(responses=[NO_ANSWER])
    result = answer_question(annual_leave_chunk(settings), None, settings, store, llm)

    assert result["answer"] == NO_ANSWER
    assert result["sources"] == []


def test_follow_up_question_is_condensed(settings, store):
    chunk = annual_leave_chunk(settings)
    llm = FakeListChatModel(responses=[chunk, "24 days [1]."])
    history = [{"question": "Tell me about leave", "answer": "There are several types."}]

    result = answer_question("and annual?", history, settings, store, llm)

    assert result["standalone_question"] == chunk
    assert result["answer"] == "24 days [1]."


# ---------- API ----------
def test_api_ask_keeps_session_history(monkeypatch):
    seen_history_lengths = []

    def fake_answer(question, history, settings, vectorstore):
        seen_history_lengths.append(len(history))
        return {"answer": f"answer to {question}", "sources": [],
                "standalone_question": question, "usage": {"total_tokens": 0}}

    monkeypatch.setattr(api, "API_TOKEN", "")
    monkeypatch.setattr(api, "answer_question", fake_answer)
    monkeypatch.setattr(api, "_get_vectorstore", lambda: None)
    client = TestClient(api.app)

    first = client.post("/ask", json={"question": "q1"}).json()
    client.post("/ask", json={"question": "q2", "session_id": first["session_id"]})

    assert first["answer"] == "answer to q1"
    assert seen_history_lengths == [0, 1]


def test_api_requires_token(monkeypatch):
    monkeypatch.setattr(api, "API_TOKEN", "secret-token")
    client = TestClient(api.app)

    assert client.get("/health").status_code == 200
    assert client.post("/ask", json={"question": "q"}).status_code == 401
    assert client.post("/ask", json={"question": "q"},
                       headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_api_rejects_empty_question(monkeypatch):
    monkeypatch.setattr(api, "API_TOKEN", "")
    client = TestClient(api.app)
    assert client.post("/ask", json={"question": ""}).status_code == 422
