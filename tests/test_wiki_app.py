"""Wiki app: group permissions, REST API filtering, chat proxy."""

import pytest
from fastapi.testclient import TestClient

from wiki import app as wiki_app
from wiki import db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "wiki.db")
    monkeypatch.setattr(wiki_app, "WIKI_API_TOKEN", "wiki-token")
    monkeypatch.setattr(wiki_app, "AUTO_SYNC", False)
    db.init_db()
    db.seed_if_empty()
    return TestClient(wiki_app.app)


def login(client: TestClient, username: str) -> None:
    client.cookies.set("wiki_user", username)


def test_home_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Northwind Wiki" in response.text


def test_employee_cannot_open_confidential_page(client):
    login(client, "asha")
    response = client.get("/spaces/HR/pages/salary-bands-2026")
    assert response.status_code == 403
    assert "41,50,000" not in response.text


def test_hr_can_open_confidential_page(client):
    login(client, "ravi")
    response = client.get("/spaces/HR/pages/salary-bands-2026")
    assert response.status_code == 200
    assert "Salary Bands 2026" in response.text


def test_search_hides_confidential_pages(client):
    login(client, "asha")
    response = client.get("/search", params={"q": "salary"})
    assert "Salary Bands 2026" not in response.text


def test_sensitive_section_is_marked_on_page(client):
    login(client, "asha")
    response = client.get("/spaces/ENG/pages/payments-db-runbook")
    assert response.status_code == 200
    assert "excluded from the AI assistant" in response.text


def test_rest_api_requires_token(client):
    assert client.get("/rest/api/pages").status_code == 401
    assert client.get("/rest/api/pages",
                      headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_rest_api_never_returns_confidential_pages(client):
    response = client.get("/rest/api/pages", headers={"Authorization": "Bearer wiki-token"})
    pages = response.json()["results"]
    titles = {p["title"] for p in pages}

    assert response.status_code == 200
    assert len(pages) == 13
    assert {p["classification"] for p in pages} <= {"public", "internal"}
    assert not titles & {"Salary Bands 2026", "Penetration Test Report 2026", "Budget FY2026"}


def test_chat_proxy_forwards_to_rag(client, monkeypatch):
    monkeypatch.setattr(wiki_app, "_ask_rag", lambda payload: {
        "answer": f"echo: {payload['question']}", "sources": [], "session_id": "s1"})
    response = client.post("/chat", json={"question": "hello"})

    assert response.status_code == 200
    assert response.json() == {"answer": "echo: hello", "sources": [], "session_id": "s1"}


def test_edit_page_bumps_version(client):
    login(client, "asha")
    response = client.post("/spaces/IT/pages/laptop-setup/edit", data={
        "title": "Laptop Setup Guide", "body": "Updated content.",
        "classification": "public", "labels": "it", "restricted_to": ""},
        follow_redirects=False)

    assert response.status_code == 303
    assert db.get_page("IT", "laptop-setup")["version"] == 2
