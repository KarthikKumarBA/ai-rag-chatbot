"""Chroma vector store (persisted to disk)."""

from app.config import Settings
from app.llm import get_embeddings


def get_vectorstore(settings: Settings, embeddings=None):
    from langchain_chroma import Chroma

    return Chroma(
        collection_name=settings.collection_name,
        embedding_function=embeddings or get_embeddings(settings),
        persist_directory=str(settings.vectorstore_dir),
        collection_metadata={"hnsw:space": "cosine"},  # relevance score = cosine similarity
    )
