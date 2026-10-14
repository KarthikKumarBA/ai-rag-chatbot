"""Retrieval-augmented answering with citations and follow-up support."""

from langchain_core.documents import Document

from app.config import Settings, get_settings
from app.llm import get_chat_model, response_text
from app.vectorstore import get_vectorstore

NO_ANSWER = "I don't know based on the available documents."

SYSTEM_PROMPT = (
    "You are the Northwind internal knowledge assistant. Answer ONLY from the numbered "
    "context. Cite every fact with its source number in square brackets, e.g. [1] or [1][3]. "
    f"If the answer is not in the context, reply exactly: \"{NO_ANSWER}\" "
    "Never guess salaries, credentials, personal data or confidential information. "
    "Be concise and do not invent policies, numbers or names."
)

CONDENSE_PROMPT = (
    "Rewrite the follow-up question as a standalone question that can be understood "
    "without the chat history. Return only the rewritten question."
)


def format_context(results: list[tuple[Document, float]]) -> str:
    blocks = []
    for number, (doc, _score) in enumerate(results, start=1):
        m = doc.metadata
        location = f"page: {m.get('title') or m.get('source')}"
        if m.get("section"):
            location += f", section: {m['section']}"
        if m.get("page"):
            location += f", pdf page: {m['page']}"
        blocks.append(f"[{number}] ({location})\n{doc.page_content}")
    return "\n\n".join(blocks)


def _sources(results: list[tuple[Document, float]]) -> list[dict]:
    return [
        {
            "id": number,
            "source": doc.metadata.get("source"),
            "title": doc.metadata.get("title", ""),
            "section": doc.metadata.get("section", ""),
            "url": doc.metadata.get("url", ""),
            "page": doc.metadata.get("page"),
            "score": round(float(score), 3),
        }
        for number, (doc, score) in enumerate(results, start=1)
    ]


def _add_usage(total: dict, message) -> None:
    usage = getattr(message, "usage_metadata", None) or {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        total[key] += usage.get(key, 0)


def is_refusal(answer: str) -> bool:
    return NO_ANSWER.lower().rstrip(".") in answer.lower()


def condense_question(question: str, history: list[dict], llm, usage: dict) -> str:
    """Turn 'and sick leave?' into 'How many days of sick leave do employees get?'."""
    if not history:
        return question
    transcript = "\n".join(f"User: {t['question']}\nAssistant: {t['answer']}" for t in history)
    message = llm.invoke([
        ("system", CONDENSE_PROMPT),
        ("human", f"Chat history:\n{transcript}\n\nFollow-up question: {question}"),
    ])
    _add_usage(usage, message)
    return response_text(message).strip() or question


def retrieve(question: str, settings: Settings, vectorstore) -> list[tuple[Document, float]]:
    """Top-k chunks with relevance = cosine similarity clamped to 0..1."""
    results = vectorstore.similarity_search_with_score(question, k=settings.top_k)
    scored = [(doc, min(1.0, max(0.0, 1.0 - distance))) for doc, distance in results]
    return [(doc, score) for doc, score in scored if score >= settings.min_relevance]


def answer_question(question: str, history: list[dict] | None = None,
                    settings: Settings | None = None, vectorstore=None, llm=None) -> dict:
    settings = settings or get_settings()
    vectorstore = vectorstore if vectorstore is not None else get_vectorstore(settings)
    history = (history or [])[-settings.history_turns:]
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def chat_model():
        nonlocal llm
        if llm is None:
            llm = get_chat_model(settings)
        return llm

    standalone = condense_question(question, history, chat_model(), usage) if history else question
    results = retrieve(standalone, settings, vectorstore)

    if not results:
        # Nothing relevant: answer without an LLM call (saves tokens, avoids guessing)
        return {"answer": NO_ANSWER, "sources": [], "standalone_question": standalone,
                "usage": usage}

    message = chat_model().invoke([
        ("system", SYSTEM_PROMPT),
        ("human", f"Context:\n{format_context(results)}\n\nQuestion: {standalone}"),
    ])
    _add_usage(usage, message)
    answer = response_text(message).strip()

    return {
        "answer": answer,
        # A refusal has no supporting sources - showing them would be misleading
        "sources": [] if is_refusal(answer) else _sources(results),
        "standalone_question": standalone,
        "usage": usage,
    }
