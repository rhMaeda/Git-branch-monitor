from __future__ import annotations

import time
from typing import Any

import requests

from .config import settings
from .db import get_state, set_state

BASE_URL = "https://api.github.com"


class GitHubAPIError(Exception):
    pass


class GitHubClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {settings.github_token}",
                "X-GitHub-Api-Version": settings.github_api_version,
                "User-Agent": "github-branch-monitor",
            }
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        etag_state_key: str | None = None,
    ) -> tuple[Any, requests.Response]:
        headers = {}
        if etag_state_key:
            etag = get_state(etag_state_key)
            if isinstance(etag, str) and etag:
                headers["If-None-Match"] = etag

        url = f"{BASE_URL}{path}"
        response = self.session.request(method, url, params=params, headers=headers, timeout=30)
        self._store_rate_limit(response)

        if response.status_code == 304:
            return None, response

        if response.status_code in (403, 429):
            remaining = response.headers.get("X-RateLimit-Remaining")
            reset = response.headers.get("X-RateLimit-Reset")
            message = response.text
            raise GitHubAPIError(
                f"GitHub limit/block hit. Remaining={remaining}, Reset={reset}, Response={message}"
            )

        if not response.ok:
            raise GitHubAPIError(f"GitHub API error {response.status_code}: {response.text}")

        if etag_state_key and response.headers.get("ETag"):
            set_state(etag_state_key, response.headers["ETag"])

        if response.content:
            return response.json(), response
        return None, response

    @staticmethod
    def _store_rate_limit(response: requests.Response) -> None:
        rate = {
            "limit": response.headers.get("X-RateLimit-Limit"),
            "remaining": response.headers.get("X-RateLimit-Remaining"),
            "used": response.headers.get("X-RateLimit-Used"),
            "reset": response.headers.get("X-RateLimit-Reset"),
            "resource": response.headers.get("X-RateLimit-Resource"),
            "retrieved_at": int(time.time()),
        }
        set_state("github_rate_limit", rate)

    def get_rate_limit(self) -> dict[str, Any]:
        data, _ = self._request("GET", "/rate_limit")
        return data

    def list_branch_commits(self, branch: str, per_page: int = 30, page: int = 1) -> list[dict[str, Any]]:
        data, _ = self._request(
            "GET",
            f"/repos/{settings.github_owner}/{settings.github_repo}/commits",
            params={"sha": branch, "per_page": per_page, "page": page},
            etag_state_key=f"etag_commits_{branch}_page_{page}",
        )
        return data or []

    def get_commit(self, sha: str) -> dict[str, Any]:
        data, _ = self._request(
            "GET",
            f"/repos/{settings.github_owner}/{settings.github_repo}/commits/{sha}",
        )
        return data or {}

    def compare_branches(self, base: str, head: str) -> dict[str, Any]:
        data, _ = self._request(
            "GET",
            f"/repos/{settings.github_owner}/{settings.github_repo}/compare/{base}...{head}",
            etag_state_key=f"etag_compare_{base}_{head}",
        )
        return data or {}
