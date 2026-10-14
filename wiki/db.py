"""SQLite storage for spaces and pages, with group-based visibility."""

import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("WIKI_DB_PATH", str(BASE / "data" / "wiki.db")))
SEED_DIR = BASE / "seed"
CLASSIFICATIONS = ("public", "internal", "confidential")

SPACES = [
    ("HR", "People & Culture", "Leave, onboarding, reviews and HR processes", "👥"),
    ("ENG", "Engineering", "Architecture, runbooks and delivery practices", "⚙️"),
    ("SEC", "Security", "Security policies, reporting and assessments", "🛡️"),
    ("FIN", "Finance", "Expenses, travel and budgets", "💰"),
    ("IT", "IT Help Desk", "Laptops, accounts and network access", "💻"),
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _query(sql: str, params: tuple = ()) -> list[dict]:
    with closing(_connect()) as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _execute(sql: str, params: tuple = ()) -> None:
    with closing(_connect()) as conn:
        with conn:
            conn.execute(sql, params)


def _split(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _page(row: dict) -> dict:
    page = dict(row)
    page["labels"] = _split(page["labels"])
    page["restricted_to"] = _split(page["restricted_to"])
    return page


def init_db() -> None:
    with closing(_connect()) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS spaces (
                key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                icon TEXT
            );
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                space_key TEXT NOT NULL REFERENCES spaces(key),
                slug TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                classification TEXT NOT NULL DEFAULT 'internal',
                restricted_to TEXT NOT NULL DEFAULT '',
                labels TEXT NOT NULL DEFAULT '',
                author TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                UNIQUE (space_key, slug)
            );
        """)
        conn.commit()


def parse_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    _, header, body = text.split("---", 2)
    meta = {}
    for line in header.strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, body.strip() + "\n"


def seed_if_empty() -> None:
    if _query("SELECT COUNT(*) AS n FROM pages")[0]["n"]:
        return
    with closing(_connect()) as conn:
        with conn:
            for space in SPACES:
                conn.execute("INSERT OR IGNORE INTO spaces VALUES (?, ?, ?, ?)", space)
            for path in sorted(SEED_DIR.glob("*/*.md")):
                meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO pages (space_key, slug, title, body, classification, "
                    "restricted_to, labels, author, updated_at, version) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                    (path.parent.name, path.stem, meta.get("title", path.stem), body,
                     meta.get("classification", "internal"), meta.get("restricted_to", ""),
                     meta.get("labels", ""), meta.get("author", "admin"),
                     meta.get("updated_at", _now())),
                )


def can_view(page: dict, user: dict) -> bool:
    if page["classification"] != "confidential":
        return True
    return bool(set(page["restricted_to"]) & set(user["groups"]))


def _visible(rows: list[dict], user: dict) -> list[dict]:
    return [p for p in map(_page, rows) if can_view(p, user)]


def list_spaces() -> list[dict]:
    return _query("SELECT * FROM spaces ORDER BY name")


def get_space(key: str) -> dict | None:
    rows = _query("SELECT * FROM spaces WHERE key = ?", (key,))
    return rows[0] if rows else None


def list_pages(space_key: str, user: dict) -> list[dict]:
    rows = _query("SELECT * FROM pages WHERE space_key = ? ORDER BY title", (space_key,))
    return _visible(rows, user)


def get_page(space_key: str, slug: str) -> dict | None:
    rows = _query("SELECT * FROM pages WHERE space_key = ? AND slug = ?", (space_key, slug))
    return _page(rows[0]) if rows else None


def recent_pages(user: dict, limit: int = 8) -> list[dict]:
    rows = _query("SELECT p.*, s.name AS space_name FROM pages p "
                  "JOIN spaces s ON s.key = p.space_key ORDER BY p.updated_at DESC")
    return _visible(rows, user)[:limit]


def search(query: str, user: dict) -> list[dict]:
    like = f"%{query}%"
    rows = _query("SELECT p.*, s.name AS space_name FROM pages p "
                  "JOIN spaces s ON s.key = p.space_key "
                  "WHERE p.title LIKE ? OR p.body LIKE ? ORDER BY p.updated_at DESC",
                  (like, like))
    results = _visible(rows, user)
    for page in results:
        body = re.sub(r"<!--.*?-->|[#*_`|>]", "", page["body"])
        index = body.lower().find(query.lower())
        start = max(0, index - 80) if index >= 0 else 0
        page["snippet"] = " ".join(body[start:start + 220].split())
    return results


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "page"


def unique_slug(space_key: str, title: str) -> str:
    base = slug = slugify(title)
    counter = 2
    while get_page(space_key, slug):
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def save_page(space_key: str, slug: str, title: str, body: str, classification: str,
              labels: str, restricted_to: str, author: str) -> None:
    existing = get_page(space_key, slug)
    if existing:
        _execute(
            "UPDATE pages SET title = ?, body = ?, classification = ?, restricted_to = ?, "
            "labels = ?, author = ?, updated_at = ?, version = version + 1 WHERE id = ?",
            (title, body, classification, restricted_to, labels, author, _now(), existing["id"]),
        )
    else:
        _execute(
            "INSERT INTO pages (space_key, slug, title, body, classification, restricted_to, "
            "labels, author, updated_at, version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (space_key, slug, title, body, classification, restricted_to, labels, author, _now()),
        )


def api_pages() -> list[dict]:
    """Pages the AI service account may read: never confidential ones."""
    rows = _query("SELECT p.*, s.name AS space_name FROM pages p "
                  "JOIN spaces s ON s.key = p.space_key "
                  "WHERE p.classification != 'confidential' ORDER BY p.space_key, p.slug")
    return [
        {
            "id": p["id"], "space": p["space_key"], "space_name": p["space_name"],
            "slug": p["slug"], "title": p["title"], "classification": p["classification"],
            "labels": p["labels"], "author": p["author"], "updated_at": p["updated_at"],
            "version": p["version"], "body": p["body"],
        }
        for p in map(_page, rows)
    ]
