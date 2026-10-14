"""Load .md, .txt and .pdf files from a folder."""

from pathlib import Path

from langchain_core.documents import Document

SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}


def load_files(docs_dir: Path) -> list[Document]:
    documents = []
    for path in sorted(docs_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        source = path.relative_to(docs_dir).as_posix()
        base = {"source": source, "title": path.stem.replace("-", " ").title(), "url": ""}

        if path.suffix.lower() == ".pdf":
            from langchain_community.document_loaders import PyPDFLoader

            for page in PyPDFLoader(str(path)).load():
                documents.append(Document(
                    page_content=page.page_content,
                    metadata={**base, "page": page.metadata.get("page", 0) + 1},
                ))
        else:
            documents.append(Document(
                page_content=path.read_text(encoding="utf-8"),
                metadata={**base, "format": "markdown" if path.suffix == ".md" else "text"},
            ))
    return documents
