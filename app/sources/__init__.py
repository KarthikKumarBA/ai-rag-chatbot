"""Document sources: the Northwind Wiki REST API or a local folder."""

from langchain_core.documents import Document

from app.config import Settings
from app.sources.files import load_files
from app.sources.wiki import load_wiki


def load_source_documents(settings: Settings, client=None) -> tuple[list[Document], dict]:
    if settings.docs_source == "wiki":
        return load_wiki(settings, client)
    if settings.docs_source == "files":
        documents = load_files(settings.docs_dir)
        return documents, {"fetched": len(documents), "skipped_restricted": []}
    raise ValueError(f"Unknown DOCS_SOURCE '{settings.docs_source}'. Use wiki or files.")
