from __future__ import annotations

import logging
from typing import Any

from .config import settings
from .db import get_dashboard_payload, get_state, set_state, update_branch_sync, upsert_commit
from .github_api import GitHubClient, GitHubAPIError

logger = logging.getLogger(__name__)


def _commit_date(commit: dict[str, Any]) -> str | None:
    commit_data = commit.get("commit", {})
    author = commit_data.get("author") or {}
    committer = commit_data.get("committer") or {}
    return author.get("date") or committer.get("date")


def sync_branch(branch: str) -> dict[str, Any]:
    client = GitHubClient()
    max_items = max(1, min(settings.max_commits_per_branch, 100))
    branch_commits = client.list_branch_commits(branch, per_page=max_items, page=1)
    if not branch_commits:
        update_branch_sync(branch, None, None)
        return {"branch": branch, "new_commits": 0, "head_sha": None}

    known_shas = set(get_state(f"known_shas_{branch}", []))
    new_shas: list[str] = []

    for item in branch_commits:
        sha = item.get("sha")
        if sha and sha not in known_shas:
            new_shas.append(sha)

    # Always keep the list refreshed and bounded
    fresh_shas = [item.get("sha") for item in branch_commits if item.get("sha")]
    set_state(f"known_shas_{branch}", fresh_shas)

    for sha in new_shas:
        detailed = client.get_commit(sha)
        upsert_commit(branch, detailed)

    head = branch_commits[0]
    update_branch_sync(branch, head.get("sha"), _commit_date(head))
    logger.info("Synced branch %s with %s new commits", branch, len(new_shas))
    return {"branch": branch, "new_commits": len(new_shas), "head_sha": head.get("sha")}


def sync_all_branches() -> dict[str, Any]:
    results = []
    errors = []
    for branch in settings.monitored_branches:
        try:
            results.append(sync_branch(branch))
        except GitHubAPIError as exc:
            logger.exception("GitHub API error syncing %s", branch)
            errors.append({"branch": branch, "error": str(exc)})
        except Exception as exc:  # pragma: no cover
            logger.exception("Unexpected error syncing %s", branch)
            errors.append({"branch": branch, "error": str(exc)})

    comparisons = build_comparisons(settings.default_compare_base)
    set_state("branch_comparisons", comparisons)

    try:
        client = GitHubClient()
        rate_data = client.get_rate_limit()
        core = (rate_data or {}).get("resources", {}).get("core", {})
        set_state(
            "github_rate_limit",
            {
                "limit": core.get("limit"),
                "remaining": core.get("remaining"),
                "used": core.get("used"),
                "reset": core.get("reset"),
                "resource": "core",
            },
        )
    except Exception as exc:
        logger.warning("Could not refresh rate limit: %s", exc)

    payload = get_dashboard_payload()
    return {"results": results, "errors": errors, "dashboard": payload}


def build_comparisons(base_branch: str) -> dict[str, Any]:
    client = GitHubClient()
    comparisons: dict[str, Any] = {}
    for branch in settings.monitored_branches:
        if branch == base_branch:
            continue
        key = f"{base_branch}...{branch}"
        try:
            data = client.compare_branches(base_branch, branch)
            comparisons[key] = {
                "base_branch": base_branch,
                "head_branch": branch,
                "status": data.get("status"),
                "ahead_by": data.get("ahead_by"),
                "behind_by": data.get("behind_by"),
                "total_commits": data.get("total_commits"),
                "html_url": data.get("html_url"),
            }
        except Exception as exc:
            comparisons[key] = {
                "base_branch": base_branch,
                "head_branch": branch,
                "error": str(exc),
            }
    return comparisons


def process_push_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    ref = payload.get("ref", "")
    branch = ref.replace("refs/heads/", "")
    if branch not in settings.monitored_branches:
        return {"ignored": True, "reason": f"Branch {branch} is not monitored."}

    commits = payload.get("commits", [])
    client = GitHubClient()
    processed = 0

    for item in commits:
        sha = item.get("id") or item.get("sha")
        if not sha:
            continue
        detailed = client.get_commit(sha)
        upsert_commit(branch, detailed)
        processed += 1

    head_sha = payload.get("after")
    head_commit = payload.get("head_commit") or {}
    head_commit_date = (head_commit.get("timestamp") or None)
    update_branch_sync(branch, head_sha, head_commit_date)

    set_state(f"known_shas_{branch}", [head_sha] + get_state(f"known_shas_{branch}", []))
    set_state("branch_comparisons", build_comparisons(settings.default_compare_base))

    return {"ignored": False, "branch": branch, "processed_commits": processed, "head_sha": head_sha}
