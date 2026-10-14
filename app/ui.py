"""Streamlit chat UI (standalone, talks to the RAG code directly).

Usage:
  streamlit run app/ui.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.rag import answer_question  # noqa: E402
from app.vectorstore import get_vectorstore  # noqa: E402

st.set_page_config(page_title="Northwind Assistant", page_icon="💬")
settings = get_settings()


@st.cache_resource
def load_store():
    return get_vectorstore(settings)


if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.history = []

with st.sidebar:
    st.header("Settings")
    st.write(f"**Source:** {settings.docs_source}")
    st.write(f"**LLM:** {settings.llm_provider}")
    st.write(f"**Embeddings:** {settings.embedding_provider}")
    st.write(f"**Top K:** {settings.top_k} | **Min relevance:** {settings.min_relevance}")
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.session_state.history = []
        st.rerun()

st.title("💬 Northwind Assistant")
st.caption("Answers come only from public and internal wiki pages, with citations.")


def show_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander(f"Sources ({len(sources)})"):
        for s in sources:
            name = s["title"] or s["source"]
            label = f"[{s['id']}] {name}" + (f" - {s['section']}" if s["section"] else "")
            st.markdown(f"[{label}]({s['url']}) (score {s['score']})" if s["url"]
                        else f"{label} (score {s['score']})")


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        show_sources(message.get("sources", []))

if prompt := st.chat_input("Ask about leave, incidents, deployments, security..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Searching the wiki..."):
            result = answer_question(prompt, st.session_state.history, settings, load_store())
        st.markdown(result["answer"])
        show_sources(result["sources"])
        st.caption(f"Tokens: {result['usage']['total_tokens']}")

    st.session_state.messages.append(
        {"role": "assistant", "content": result["answer"], "sources": result["sources"]})
    st.session_state.history = (st.session_state.history + [
        {"question": prompt, "answer": result["answer"]}])[-settings.history_turns:]
