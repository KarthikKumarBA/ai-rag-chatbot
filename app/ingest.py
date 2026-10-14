"""Load documents -> remove sensitive data -> split -> embed -> store in Chroma.

Usage:
  python -m app.ingest
"""

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.config import Settings, get_settings
from app.sanitize import sanitize_text
from app.sources import load_source_documents
from app.vectorstore import get_vectorstore

HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3")]


def _is_markdown(doc: Document) -> bool:
    return doc.metadata.get("format") == "markdown" or doc.metadata["source"].endswith(".md")


def split_documents(documents: list[Document], chunk_size: int, chunk_overlap: int) -> list[Document]:
    """Markdown is split by headings first (keeps the section title), then by size."""
    header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=HEADERS, strip_headers=False)
    size_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    chunks = []
    for doc in documents:
        if _is_markdown(doc):
            sections = header_splitter.split_text(doc.page_content)
            for section in sections:
                title = " > ".join(section.metadata[k] for k in ("h1", "h2", "h3")
                                   if k in section.metadata)
                section.metadata = {**doc.metadata, "section": title}
            parts = size_splitter.split_documents(sections)
        else:
            parts = size_splitter.split_documents([doc])

        for index, part in enumerate(parts):
            part.metadata["chunk"] = index
            part.metadata.setdefault("section", "")
            chunks.append(part)
    return chunks


def chunk_id(chunk: Document) -> str:
    m = chunk.metadata
    return f"{m['source']}:{m.get('page', 0)}:{m['chunk']}"


def build_index(settings: Settings | None = None, embeddings=None, client=None) -> dict:
    """Sync the collection with the source.

    Chunks are upserted by stable IDs and stale chunks are deleted. The collection itself
    is never dropped, so requests that are reading it during a re-ingest keep working.
    """
    settings = settings or get_settings()
    documents, report = load_source_documents(settings, client)
    if not documents:
        raise ValueError(f"No documents found in source '{settings.docs_source}'")

    blocks_removed = redactions = 0
    for doc in documents:
        doc.page_content, stats = sanitize_text(doc.page_content)
        blocks_removed += stats["sensitive_blocks"]
        redactions += stats["redactions"]

    chunks = split_documents(documents, settings.chunk_size, settings.chunk_overlap)
    ids = [chunk_id(c) for c in chunks]

    store = get_vectorstore(settings, embeddings)
    existing_ids = set(store.get(include=[])["ids"])
    store.add_documents(chunks, ids=ids)  # upsert: same ID replaces the old chunk
    stale_ids = sorted(existing_ids - set(ids))
    if stale_ids:
        store.delete(ids=stale_ids)

    sources = sorted({c.metadata["source"] for c in chunks})
    return {
        "source": settings.docs_source,
        "documents": len(sources),
        "chunks": len(chunks),
        "removed_chunks": len(stale_ids),
        "skipped_restricted": report["skipped_restricted"],
        "sensitive_blocks_removed": blocks_removed,
        "redactions": redactions,
        "collection": settings.collection_name,
        "sources": sources,
    }


def main() -> None:
    settings = get_settings()
    print(f"Indexing from '{settings.docs_source}' with {settings.embedding_provider} embeddings ...")
    stats = build_index(settings)
    print(f"Indexed {stats['documents']} documents into {stats['chunks']} chunks "
          f"(collection: {stats['collection']})")
    print(f"Removed stale chunks:       {stats['removed_chunks']}")
    print(f"Skipped restricted pages:   {len(stats['skipped_restricted'])} "
          f"{stats['skipped_restricted'] or ''}")
    print(f"Sensitive sections removed: {stats['sensitive_blocks_removed']}")
    print(f"Pattern redactions:         {stats['redactions']}")
    for source in stats["sources"]:
        print(f"  - {source}")


if __name__ == "__main__":
    main()
