"""Wiki connector: respects classifications and strips sensitive data before indexing."""

from dataclasses import replace

import httpx
import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from app.config import get_settings
from app.ingest import build_index
from app.sources.wiki import load_wiki
from app.vectorstore import get_vectorstore

PAGES = [
    {
        "id": 1, "space": "HR", "slug": "annual-leave-policy", "title": "Annual Leave Policy",
        "classification": "internal", "labels": ["leave"], "author": "ravi",
        "updated_at": "2026-09-12", "version": 1,
        "body": ("## Annual Leave\n\nEmployees get 24 days.\n\n<!-- sensitive -->\n"
                 "Admin password: hunter2\n<!-- /sensitive -->\n\n"
                 "Escalate to Kiran on +91 98450 12345."),
    },
    {
        "id": 2, "space": "HR", "slug": "salary-bands-2026", "title": "Salary Bands 2026",
        "classification": "confidential", "labels": ["salary"], "author": "ravi",
        "updated_at": "2026-04-02", "version": 1, "body": "L5: 41,50,000 - 58,00,000",
    },
]


@pytest.fixture
def settings(tmp_path):
    return replace(get_settings(), docs_source="wiki", wiki_base_url="http://wiki.test",
                   wiki_public_url="http://wiki.local", wiki_api_token="wiki-token",
                   vectorstore_dir=tmp_path / "vs", collection_name="test_wiki",
                   chunk_size=300, chunk_overlap=20)


@pytest.fixture
def client():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("Authorization") != "Bearer wiki-token":
            return httpx.Response(401, json={"detail": "unauthorized"})
        assert request.url.path == "/rest/api/pages"
        return httpx.Response(200, json={"size": len(PAGES), "results": PAGES})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_wiki_loader_skips_confidential_and_builds_urls(settings, client):
    documents, report = load_wiki(settings, client)

    assert len(documents) == 1
    assert report["skipped_restricted"] == ["Salary Bands 2026"]
    meta = documents[0].metadata
    assert meta["source"] == "HR/annual-leave-policy"
    assert meta["url"] == "http://wiki.local/spaces/HR/pages/annual-leave-policy"
    assert documents[0].page_content.startswith("# Annual Leave Policy")


def test_wiki_loader_sends_token(settings, client):
    with pytest.raises(httpx.HTTPStatusError):
        load_wiki(replace(settings, wiki_api_token="wrong"), client)


def test_index_from_wiki_contains_no_sensitive_data(settings, client):
    embeddings = DeterministicFakeEmbedding(size=64)
    stats = build_index(settings, embeddings, client)

    assert stats["skipped_restricted"] == ["Salary Bands 2026"]
    assert stats["sensitive_blocks_removed"] == 1
    assert stats["redactions"] >= 1

    indexed = " ".join(get_vectorstore(settings, embeddings).get(include=["documents"])["documents"])
    assert "24 days" in indexed
    for secret in ["hunter2", "98450", "41,50,000"]:
        assert secret not in indexed
