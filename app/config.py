from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "GitHub Branch Monitor")
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    debug: bool = _as_bool(os.getenv("DEBUG"), True)
    secret_key: str = os.getenv("SECRET_KEY", "change-me")
    database_path: str = os.getenv("DATABASE_PATH", "./data/monitor.db")

    github_owner: str = os.getenv("GITHUB_OWNER", "")
    github_repo: str = os.getenv("GITHUB_REPO", "")
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    github_api_version: str = os.getenv("GITHUB_API_VERSION", "2022-11-28")

    monitored_branches_raw: str = os.getenv("MONITORED_BRANCHES", "dev,alekss,Sasha")
    default_compare_base: str = os.getenv("DEFAULT_COMPARE_BASE", "dev")

    sync_on_startup: bool = _as_bool(os.getenv("SYNC_ON_STARTUP"), True)
    scheduled_sync_enabled: bool = _as_bool(os.getenv("SCHEDULED_SYNC_ENABLED"), True)
    scheduled_sync_minutes: int = int(os.getenv("SCHEDULED_SYNC_MINUTES", "60"))
    max_commits_per_branch: int = int(os.getenv("MAX_COMMITS_PER_BRANCH", "100"))
    max_files_per_commit: int = int(os.getenv("MAX_FILES_PER_COMMIT", "300"))

    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "")

    @property
    def monitored_branches(self) -> list[str]:
        return [branch.strip() for branch in self.monitored_branches_raw.split(",") if branch.strip()]

    @property
    def database_file(self) -> Path:
        return Path(self.database_path).resolve()

    @property
    def repo_full_name(self) -> str:
        return f"{self.github_owner}/{self.github_repo}" if self.github_owner and self.github_repo else ""


settings = Settings()
settings.database_file.parent.mkdir(parents=True, exist_ok=True)
