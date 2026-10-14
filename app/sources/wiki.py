"""Connector for the Northwind Wiki REST API (works like a Confluence connector)."""

import httpx
from langchain_core.documents import Document

from app.config import Settings

# Defense in depth: even if the wiki API ever returned a confidential page, skip it here
ALLOWED_CLASSIFICATIONS = {"public", "internal"}


def fetch_pages(settings: Settings, client: httpx.Client | None = None) -> list[dict]:
    headers = {"Authorization": f"Bearer {settings.wiki_api_token}"} if settings.wiki_api_token else {}
    owns_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        response = client.get(f"{settings.wiki_base_url}/rest/api/pages", headers=headers)
        response.raise_for_status()
        return response.json()["results"]
    finally:
        if owns_client:
            client.close()


def load_wiki(settings: Settings, client: httpx.Client | None = None) -> tuple[list[Document], dict]:
    pages = fetch_pages(settings, client)
    documents, skipped = [], []

    for page in pages:
        if page.get("classification") not in ALLOWED_CLASSIFICATIONS:
            skipped.append(page.get("title", "?"))
            continue

        documents.append(Document(
            # Title as the top heading so every chunk's section starts with the page title
            page_content=f"# {page['title']}\n\n{page['body']}",
            metadata={
                "source": f"{page['space']}/{page['slug']}",
                "title": page["title"],
                "space": page["space"],
                "url": f"{settings.wiki_public_url}/spaces/{page['space']}/pages/{page['slug']}",
                "classification": page["classification"],
                "labels": ", ".join(page.get("labels", [])),
                "updated_at": page.get("updated_at", ""),
                "format": "markdown",
            },
        ))

    return documents, {"fetched": len(pages), "skipped_restricted": skipped}
