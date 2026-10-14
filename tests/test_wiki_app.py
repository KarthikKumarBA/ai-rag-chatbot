"""Wiki app: sign-in, group permissions, REST API filtering, chat proxy, rate limiting."""

import pytest
from fastapi.testclient import TestClient

from wiki import app as wiki_app
from wiki import db
from wiki.ratelimit import RateLimiter

CONFIDENTIAL_PAGES = ["/spaces/HR/pages/salary-bands-2026",
                      "/spaces/SEC/pages/pentest-report-2026",
                      "/spaces/FIN/pages/budget-fy2026"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "wiki.db")
    monkeypatch.setattr(wiki_app, "WIKI_API_TOKEN", "wiki-token")
    monkeypatch.setattr(wiki_app, "AUTO_SYNC", False)
    monkeypatch.setattr(wiki_app, "chat_limiter", RateLimiter(per_minute=100, per_day=1000))
    db.init_db()
    db.seed_if_empty()
    test_client = TestClient(wiki_app.app)
    login(test_client, "asha")
    return test_client


def login(client: TestClient, username: str) -> None:
    client.cookies.set("wiki_user", username)


def fake_rag(monkeypatch) -> None:
    monkeypatch.setattr(wiki_app, "_ask_rag", lambda payload: {
        "answer": f"echo: {payload['question']}", "sources": [], "session_id": "s1"})


# ---------- Sign in / sign out ----------
def test_login_required_redirects(client):
    client.cookies.clear()
    response = client.get("/spaces/HR", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=/spaces/HR"


def test_login_and_logout(client):
    client.cookies.clear()
    response = client.post("/login", data={"username": "ravi", "next": "/spaces/HR"},
                           follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/spaces/HR"
    assert "Ravi Menon" in client.get("/").text

    response = client.get("/logout", follow_redirects=False)
    assert response.headers["location"] == "/login"
    assert client.get("/", follow_redirects=False).status_code == 303


def test_login_blocks_open_redirect(client):
    response = client.post("/login", data={"username": "asha", "next": "https://evil.example"},
                           follow_redirects=False)
    assert response.headers["location"] == "/"


def test_login_rejects_unknown_user(client):
    assert client.post("/login", data={"username": "mallory"}).status_code == 400


def test_login_page_lists_main_user(client):
    response = client.get("/login")
    assert "Karthik Kumar" in response.text
    assert "MAIN USER" in response.text


# ---------- Pages and permissions ----------
def test_home_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Northwind Wiki" in response.text


def test_employee_cannot_open_confidential_page(client):
    response = client.get("/spaces/HR/pages/salary-bands-2026")
    assert response.status_code == 403
    assert "41,50,000" not in response.text


def test_hr_can_open_salary_page(client):
    login(client, "ravi")
    response = client.get("/spaces/HR/pages/salary-bands-2026")
    assert response.status_code == 200
    assert "Salary Bands 2026" in response.text


def test_admin_can_open_all_confidential_pages(client):
    login(client, "karthik")
    for path in CONFIDENTIAL_PAGES:
        assert client.get(path).status_code == 200, path


def test_contractor_sees_only_public_pages(client):
    login(client, "vikram")
    assert client.get("/spaces/SEC/pages/phishing-reporting").status_code == 200
    assert client.get("/spaces/HR/pages/annual-leave-policy").status_code == 403
    assert "Annual Leave Policy" not in client.get("/spaces/HR").text


def test_contractor_cannot_use_assistant(client):
    login(client, "vikram")
    assert "chat-widget.js" not in client.get("/").text
    response = client.post("/chat", json={"question": "hello"})
    assert response.status_code == 403
    assert "employees only" in response.json()["answer"]


def test_search_hides_confidential_pages(client):
    response = client.get("/search", params={"q": "salary"})
    assert "Salary Bands 2026" not in response.text


def test_sensitive_section_is_marked_on_page(client):
    response = client.get("/spaces/ENG/pages/payments-db-runbook")
    assert response.status_code == 200
    assert "excluded from the AI assistant" in response.text


def test_edit_page_bumps_version(client):
    response = client.post("/spaces/IT/pages/laptop-setup/edit", data={
        "title": "Laptop Setup Guide", "body": "Updated content.",
        "classification": "public", "labels": "it", "restricted_to": ""},
        follow_redirects=False)

    assert response.status_code == 303
    assert db.get_page("IT", "laptop-setup")["version"] == 2


def test_contractor_cannot_edit(client):
    login(client, "vikram")
    response = client.post("/spaces/IT/pages/laptop-setup/edit", data={
        "title": "Hacked", "body": "x", "classification": "public"}, follow_redirects=False)
    assert response.status_code == 403
    assert db.get_page("IT", "laptop-setup")["version"] == 1


# ---------- REST API ----------
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


# ---------- Chat proxy ----------
def test_chat_requires_login(client):
    client.cookies.clear()
    response = client.post("/chat", json={"question": "hello"})
    assert response.status_code == 401


def test_chat_proxy_forwards_to_rag(client, monkeypatch):
    fake_rag(monkeypatch)
    response = client.post("/chat", json={"question": "hello"})

    assert response.status_code == 200
    assert response.json() == {"answer": "echo: hello", "sources": [], "session_id": "s1"}


def test_chat_is_rate_limited(client, monkeypatch):
    fake_rag(monkeypatch)
    monkeypatch.setattr(wiki_app, "chat_limiter", RateLimiter(per_minute=2, per_day=100))

    codes = [client.post("/chat", json={"question": f"q{i}"}).status_code for i in range(3)]
    blocked = client.post("/chat", json={"question": "again"})

    assert codes == [200, 200, 429]
    assert "too quickly" in blocked.json()["answer"]
    assert int(blocked.headers["Retry-After"]) > 0


def test_rate_limit_is_per_user(client, monkeypatch):
    fake_rag(monkeypatch)
    monkeypatch.setattr(wiki_app, "chat_limiter", RateLimiter(per_minute=1, per_day=100))

    assert client.post("/chat", json={"question": "q"}).status_code == 200
    assert client.post("/chat", json={"question": "q"}).status_code == 429

    login(client, "ravi")
    assert client.post("/chat", json={"question": "q"}).status_code == 200


# ---------- RateLimiter unit tests ----------
class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_limiter_resets_after_a_minute():
    clock = FakeClock()
    limiter = RateLimiter(per_minute=2, per_day=100, clock=clock)

    assert limiter.check("k")[0] and limiter.check("k")[0]
    allowed, retry = limiter.check("k")
    assert not allowed and 0 < retry <= 61

    clock.now += 61
    assert limiter.check("k")[0]


def test_limiter_enforces_daily_limit():
    clock = FakeClock()
    limiter = RateLimiter(per_minute=0, per_day=3, clock=clock)

    for _ in range(3):
        assert limiter.check("k")[0]
        clock.now += 120
    assert not limiter.check("k")[0]

    clock.now += 86_400
    assert limiter.check("k")[0]
