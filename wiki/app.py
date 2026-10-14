"""Northwind Wiki: a small Confluence-like wiki with a REST API and an AI chat widget.

Run:
  python -m uvicorn wiki.app:app --port 8088 --reload
"""

import os
import re
import secrets
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

import httpx
import markdown
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from wiki import db
from wiki.ratelimit import RateLimiter
from wiki.users import USERS, can_use_assistant, get_user, is_employee

BASE = Path(__file__).resolve().parent
load_dotenv(BASE.parent / ".env")

WIKI_API_TOKEN = os.getenv("WIKI_API_TOKEN", "")
RAG_API_URL = os.getenv("RAG_API_URL", "http://127.0.0.1:8000").rstrip("/")
RAG_API_TOKEN = os.getenv("RAG_API_TOKEN", "")
AUTO_SYNC = os.getenv("WIKI_AUTO_SYNC", "true").lower() == "true"
SESSION_COOKIE = "wiki_user"
SESSION_HOURS = 8

# Every chat question costs LLM tokens: limit per user + IP
chat_limiter = RateLimiter(
    per_minute=int(os.getenv("CHAT_RATE_PER_MINUTE", "10")),
    per_day=int(os.getenv("CHAT_RATE_PER_DAY", "200")),
)

templates = Jinja2Templates(directory=str(BASE / "templates"))


class LoginRequired(Exception):
    def __init__(self, next_url: str):
        self.next_url = next_url


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    db.seed_if_empty()
    yield


app = FastAPI(title="Northwind Wiki", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")


@app.exception_handler(LoginRequired)
async def login_redirect(_: Request, exc: LoginRequired):
    return RedirectResponse(f"/login?next={quote(exc.next_url)}", status_code=303)


# ---------- Helpers ----------
def current_user(request: Request) -> dict | None:
    return get_user(request.cookies.get(SESSION_COOKIE))


def require_user(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise LoginRequired(request.url.path)
    return user


def render(request: Request, template: str, user: dict | None, status_code: int = 200, **context):
    base = {
        "request": request,
        "user": user,
        "spaces": db.list_spaces() if user else [],
        "assistant_enabled": bool(user and can_use_assistant(user)),
    }
    return templates.TemplateResponse(request, template, {**base, **context},
                                      status_code=status_code)


def _safe_next(url: str) -> str:
    """Only allow local paths after login (prevents open redirects)."""
    if url.startswith("/") and not url.startswith("//") and not url.startswith("/\\"):
        return url
    return "/"


def render_markdown(body: str) -> str:
    """Show sensitive sections inside a highlighted box (they are hidden from the AI)."""
    prepared = re.sub(
        r"<!--\s*sensitive\s*-->",
        '\n<div class="sensitive-block" markdown="1">\n\n'
        '<span class="sensitive-tag">🔒 Sensitive - excluded from the AI assistant</span>\n\n',
        body, flags=re.I)
    prepared = re.sub(r"<!--\s*/sensitive\s*-->", "\n\n</div>\n", prepared, flags=re.I)
    return markdown.markdown(prepared,
                             extensions=["tables", "fenced_code", "md_in_html", "sane_lists"])


def _post_ingest() -> None:
    headers = {"Authorization": f"Bearer {RAG_API_TOKEN}"} if RAG_API_TOKEN else {}
    try:
        httpx.post(f"{RAG_API_URL}/ingest", headers=headers, timeout=180)
    except httpx.HTTPError:
        pass  # the assistant may be offline; the next ingest will pick up the change


def trigger_sync() -> None:
    """Webhook-style re-ingest after a page changes."""
    if AUTO_SYNC:
        threading.Thread(target=_post_ingest, daemon=True).start()


def _restriction_for(classification: str, restricted_to: str, user: dict) -> str:
    if classification != "confidential":
        return ""
    groups = restricted_to.strip() or ",".join(
        g for g in user["groups"] if g not in ("employees", "admins"))
    return groups or "admins"


def _client_key(request: Request, user: dict) -> str:
    """User + client IP. Behind a load balancer, the first X-Forwarded-For entry is the client."""
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else "unknown")
    return f"{user['username']}|{ip}"


# ---------- Sign in / sign out (demo: no passwords; production uses SSO) ----------
@app.get("/health")
def health() -> dict:
    return {"status": "healthy"}


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/"):
    return render(request, "login.html", current_user(request),
                  users=list(USERS.values()), next=_safe_next(next))


@app.post("/login")
def login(username: str = Form(...), next: str = Form("/")):
    if username not in USERS:
        raise HTTPException(400, "Unknown user")
    response = RedirectResponse(_safe_next(next), status_code=303)
    response.set_cookie(SESSION_COOKIE, username, httponly=True, samesite="lax",
                        max_age=SESSION_HOURS * 3600)
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


# ---------- Pages ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    user = require_user(request)
    return render(request, "home.html", user, recent=db.recent_pages(user))


@app.get("/spaces/{key}", response_class=HTMLResponse)
def space_view(key: str, request: Request):
    user = require_user(request)
    space = db.get_space(key)
    if not space:
        raise HTTPException(404, "Space not found")
    return render(request, "space.html", user, space=space,
                  pages=db.list_pages(key, user), can_create=is_employee(user))


@app.get("/spaces/{key}/pages/{slug}", response_class=HTMLResponse)
def page_view(key: str, slug: str, request: Request):
    user = require_user(request)
    space, page = db.get_space(key), db.get_page(key, slug)
    if not space or not page:
        raise HTTPException(404, "Page not found")
    if not db.can_view(page, user):
        return render(request, "forbidden.html", user, status_code=403)
    return render(request, "page.html", user, space=space, page=page,
                  html=render_markdown(page["body"]), can_edit=db.can_edit(page, user))


@app.get("/spaces/{key}/new", response_class=HTMLResponse)
def new_page_form(key: str, request: Request):
    user = require_user(request)
    space = db.get_space(key)
    if not space:
        raise HTTPException(404, "Space not found")
    if not is_employee(user):
        return render(request, "forbidden.html", user, status_code=403)
    return render(request, "edit.html", user, space=space, page=None,
                  classifications=db.CLASSIFICATIONS)


@app.post("/spaces/{key}/new")
def create_page(key: str, request: Request, title: str = Form(...), body: str = Form(...),
                classification: str = Form("internal"), labels: str = Form(""),
                restricted_to: str = Form("")):
    user = require_user(request)
    if not db.get_space(key):
        raise HTTPException(404, "Space not found")
    if not is_employee(user):
        raise HTTPException(403, "Not allowed")
    classification = classification if classification in db.CLASSIFICATIONS else "internal"
    slug = db.unique_slug(key, title)
    db.save_page(key, slug, title.strip(), body, classification, labels,
                 _restriction_for(classification, restricted_to, user), user["username"])
    trigger_sync()
    return RedirectResponse(f"/spaces/{key}/pages/{slug}", status_code=303)


@app.get("/spaces/{key}/pages/{slug}/edit", response_class=HTMLResponse)
def edit_page_form(key: str, slug: str, request: Request):
    user = require_user(request)
    space, page = db.get_space(key), db.get_page(key, slug)
    if not space or not page:
        raise HTTPException(404, "Page not found")
    if not db.can_edit(page, user):
        return render(request, "forbidden.html", user, status_code=403)
    return render(request, "edit.html", user, space=space, page=page,
                  classifications=db.CLASSIFICATIONS)


@app.post("/spaces/{key}/pages/{slug}/edit")
def update_page(key: str, slug: str, request: Request, title: str = Form(...),
                body: str = Form(...), classification: str = Form("internal"),
                labels: str = Form(""), restricted_to: str = Form("")):
    user = require_user(request)
    page = db.get_page(key, slug)
    if not page:
        raise HTTPException(404, "Page not found")
    if not db.can_edit(page, user):
        raise HTTPException(403, "Not allowed")
    classification = classification if classification in db.CLASSIFICATIONS else "internal"
    db.save_page(key, slug, title.strip(), body, classification, labels,
                 _restriction_for(classification, restricted_to, user), user["username"])
    trigger_sync()
    return RedirectResponse(f"/spaces/{key}/pages/{slug}", status_code=303)


@app.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str = ""):
    user = require_user(request)
    results = db.search(q.strip(), user) if q.strip() else []
    return render(request, "search.html", user, q=q, results=results)


# ---------- AI chat proxy (token never reaches the browser) ----------
class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


def _ask_rag(payload: dict) -> dict:
    headers = {"Authorization": f"Bearer {RAG_API_TOKEN}"} if RAG_API_TOKEN else {}
    response = httpx.post(f"{RAG_API_URL}/ask", json=payload, headers=headers, timeout=60)
    response.raise_for_status()
    return response.json()


def _chat_error(status_code: int, message: str, session_id: str | None,
                headers: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, headers=headers,
                        content={"answer": message, "sources": [], "session_id": session_id})


@app.post("/chat")
def chat(req: ChatRequest, request: Request):
    user = current_user(request)
    if not user:
        return _chat_error(401, "Please sign in to use the assistant.", req.session_id)
    if not can_use_assistant(user):
        return _chat_error(403, "The AI assistant is available to employees only.", req.session_id)

    allowed, retry_after = chat_limiter.check(_client_key(request, user))
    if not allowed:
        return _chat_error(429, f"You're asking questions too quickly. "
                                f"Please try again in {retry_after} seconds.",
                           req.session_id, headers={"Retry-After": str(retry_after)})

    try:
        result = _ask_rag({"question": req.question, "session_id": req.session_id})
    except httpx.HTTPError:
        return _chat_error(503, "The AI assistant is not available right now. "
                                "Please try again later.", req.session_id)
    return {"answer": result["answer"], "sources": result.get("sources", []),
            "session_id": result.get("session_id")}


# ---------- REST API for integrations (like the Confluence REST API) ----------
def require_api_token(authorization: str | None = Header(default=None)) -> None:
    if not WIKI_API_TOKEN:
        raise HTTPException(503, "WIKI_API_TOKEN is not configured")
    if not authorization or not secrets.compare_digest(authorization, f"Bearer {WIKI_API_TOKEN}"):
        raise HTTPException(401, "Missing or invalid API token")


@app.get("/rest/api/spaces", dependencies=[Depends(require_api_token)])
def api_spaces() -> dict:
    return {"results": db.list_spaces()}


@app.get("/rest/api/pages", dependencies=[Depends(require_api_token)])
def api_pages() -> dict:
    pages = db.api_pages()
    return {"size": len(pages), "results": pages}
