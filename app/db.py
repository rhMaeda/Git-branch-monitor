from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS branches (
    name TEXT PRIMARY KEY,
    last_head_sha TEXT,
    last_commit_date TEXT,
    synced_at TEXT,
    etag TEXT,
    commit_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS commits (
    sha TEXT PRIMARY KEY,
    branch TEXT NOT NULL,
    author_name TEXT,
    author_email TEXT,
    committer_name TEXT,
    committer_email TEXT,
    message TEXT,
    short_message TEXT,
    html_url TEXT,
    api_url TEXT,
    commit_date TEXT,
    additions INTEGER DEFAULT 0,
    deletions INTEGER DEFAULT 0,
    total_changes INTEGER DEFAULT 0,
    changed_files_count INTEGER DEFAULT 0,
    parents_json TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_commits_branch_commit_date ON commits(branch, commit_date DESC);
CREATE INDEX IF NOT EXISTS idx_commits_author_name ON commits(author_name);

CREATE TABLE IF NOT EXISTS commit_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    commit_sha TEXT NOT NULL,
    filename TEXT,
    status TEXT,
    additions INTEGER DEFAULT 0,
    deletions INTEGER DEFAULT 0,
    changes INTEGER DEFAULT 0,
    patch TEXT,
    previous_filename TEXT,
    UNIQUE(commit_sha, filename),
    FOREIGN KEY(commit_sha) REFERENCES commits(sha) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sync_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS webhook_events (
    delivery_id TEXT PRIMARY KEY,
    event_name TEXT NOT NULL,
    received_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn() -> Iterable[sqlite3.Connection]:
    db_path = Path(settings.database_file)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        for branch in settings.monitored_branches:
            conn.execute(
                "INSERT OR IGNORE INTO branches(name, synced_at, commit_count) VALUES (?, ?, 0)",
                (branch, utc_now_iso()),
            )


def set_state(key: str, value: Any) -> None:
    serialized = json.dumps(value) if not isinstance(value, str) else value
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO sync_state(key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, serialized, utc_now_iso()),
        )


def get_state(key: str, default: Any = None) -> Any:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM sync_state WHERE key = ?", (key,)).fetchone()
        if not row:
            return default
        value = row["value"]
    try:
        return json.loads(value)
    except Exception:
        return value


def save_webhook_event(delivery_id: str, event_name: str, payload: dict[str, Any]) -> bool:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT delivery_id FROM webhook_events WHERE delivery_id = ?", (delivery_id,)
        ).fetchone()
        if existing:
            return False
        conn.execute(
            "INSERT INTO webhook_events(delivery_id, event_name, received_at, payload_json) VALUES (?, ?, ?, ?)",
            (delivery_id, event_name, utc_now_iso(), json.dumps(payload)),
        )
        return True


def upsert_commit(branch: str, commit: dict[str, Any]) -> None:
    now = utc_now_iso()
    commit_data = commit.get("commit", {})
    author = commit_data.get("author") or {}
    committer = commit_data.get("committer") or {}
    stats = commit.get("stats") or {}
    files = commit.get("files") or []
    parents = [p.get("sha") for p in commit.get("parents", []) if p.get("sha")]
    message = commit_data.get("message", "")
    short_message = message.splitlines()[0] if message else ""

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO commits(
                sha, branch, author_name, author_email, committer_name, committer_email,
                message, short_message, html_url, api_url, commit_date, additions, deletions,
                total_changes, changed_files_count, parents_json, raw_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sha) DO UPDATE SET
                branch = excluded.branch,
                author_name = excluded.author_name,
                author_email = excluded.author_email,
                committer_name = excluded.committer_name,
                committer_email = excluded.committer_email,
                message = excluded.message,
                short_message = excluded.short_message,
                html_url = excluded.html_url,
                api_url = excluded.api_url,
                commit_date = excluded.commit_date,
                additions = excluded.additions,
                deletions = excluded.deletions,
                total_changes = excluded.total_changes,
                changed_files_count = excluded.changed_files_count,
                parents_json = excluded.parents_json,
                raw_json = excluded.raw_json,
                updated_at = excluded.updated_at
            """,
            (
                commit.get("sha"),
                branch,
                author.get("name") or (commit.get("author") or {}).get("login"),
                author.get("email"),
                committer.get("name") or (commit.get("committer") or {}).get("login"),
                committer.get("email"),
                message,
                short_message,
                commit.get("html_url"),
                commit.get("url"),
                author.get("date") or committer.get("date"),
                stats.get("additions", 0),
                stats.get("deletions", 0),
                stats.get("total", 0),
                len(files),
                json.dumps(parents),
                json.dumps(commit),
                now,
                now,
            ),
        )

        if files:
            conn.execute("DELETE FROM commit_files WHERE commit_sha = ?", (commit.get("sha"),))
            conn.executemany(
                """
                INSERT OR REPLACE INTO commit_files(
                    commit_sha, filename, status, additions, deletions, changes, patch, previous_filename
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        commit.get("sha"),
                        file.get("filename"),
                        file.get("status"),
                        file.get("additions", 0),
                        file.get("deletions", 0),
                        file.get("changes", 0),
                        file.get("patch"),
                        file.get("previous_filename"),
                    )
                    for file in files
                ],
            )

        conn.execute(
            """
            INSERT INTO branches(name, last_head_sha, last_commit_date, synced_at, commit_count)
            VALUES (?, ?, ?, ?, COALESCE((SELECT COUNT(*) FROM commits WHERE branch = ?), 0))
            ON CONFLICT(name) DO UPDATE SET
                last_head_sha = COALESCE(excluded.last_head_sha, branches.last_head_sha),
                last_commit_date = COALESCE(excluded.last_commit_date, branches.last_commit_date),
                synced_at = excluded.synced_at,
                commit_count = (SELECT COUNT(*) FROM commits WHERE branch = excluded.name)
            """,
            (
                branch,
                commit.get("sha"),
                author.get("date") or committer.get("date"),
                now,
                branch,
            ),
        )


def update_branch_sync(branch: str, head_sha: str | None, commit_date: str | None, etag: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO branches(name, last_head_sha, last_commit_date, synced_at, etag, commit_count)
            VALUES (?, ?, ?, ?, ?, COALESCE((SELECT COUNT(*) FROM commits WHERE branch = ?), 0))
            ON CONFLICT(name) DO UPDATE SET
                last_head_sha = COALESCE(excluded.last_head_sha, branches.last_head_sha),
                last_commit_date = COALESCE(excluded.last_commit_date, branches.last_commit_date),
                synced_at = excluded.synced_at,
                etag = COALESCE(excluded.etag, branches.etag),
                commit_count = (SELECT COUNT(*) FROM commits WHERE branch = excluded.name)
            """,
            (branch, head_sha, commit_date, utc_now_iso(), etag, branch),
        )


def get_dashboard_payload() -> dict[str, Any]:
    with get_conn() as conn:
        branches = [dict(row) for row in conn.execute("SELECT * FROM branches ORDER BY name").fetchall()]
        recent_commits = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    sha,
                    branch,
                    author_name,
                    short_message,
                    message,
                    commit_date,
                    html_url,
                    additions,
                    deletions,
                    total_changes,
                    changed_files_count,
                    CASE
                        WHEN LOWER(COALESCE(short_message, '')) LIKE 'merge branch %'
                        OR LOWER(COALESCE(short_message, '')) LIKE 'merge pull request %'
                        OR LOWER(COALESCE(short_message, '')) LIKE 'merge remote-tracking branch %'
                        THEN 1
                        ELSE 0
                    END AS is_merge
                FROM commits
                ORDER BY commit_date DESC
                LIMIT 100
                """
            ).fetchall()
        ]
        daily_stats = [
            dict(row)
            for row in conn.execute(
                """
                SELECT substr(commit_date, 1, 10) AS day, branch,
                       COUNT(*) AS commits,
                       COUNT(DISTINCT COALESCE(author_name, 'Unknown')) AS authors,
                       COALESCE(SUM(additions), 0) AS additions,
                       COALESCE(SUM(deletions), 0) AS deletions
                FROM commits
                WHERE commit_date IS NOT NULL
                GROUP BY day, branch
                ORDER BY day DESC, branch ASC
                LIMIT 30
                """
            ).fetchall()
        ]
        top_files = [
            dict(row)
            for row in conn.execute(
                """
                SELECT filename,
                       COUNT(*) AS times_changed,
                       COALESCE(SUM(additions), 0) AS additions,
                       COALESCE(SUM(deletions), 0) AS deletions
                FROM commit_files
                GROUP BY filename
                ORDER BY times_changed DESC, additions DESC
                LIMIT 20
                """
            ).fetchall()
        ]
        totals = conn.execute(
            """
            SELECT COUNT(*) AS commits,
                   COUNT(DISTINCT branch) AS branches,
                   COUNT(DISTINCT COALESCE(author_name, 'Unknown')) AS authors,
                   COALESCE(SUM(additions), 0) AS additions,
                   COALESCE(SUM(deletions), 0) AS deletions
            FROM commits
            """
        ).fetchone()
        rate_limit = get_state("github_rate_limit", {})
        comparisons = get_state("branch_comparisons", {})

    return {
        "generated_at": utc_now_iso(),
        "repo": settings.repo_full_name,
        "totals": dict(totals) if totals else {},
        "branches": branches,
        "recent_commits": recent_commits,
        "daily_stats": daily_stats,
        "top_files": top_files,
        "rate_limit": rate_limit,
        "comparisons": comparisons,
    }
