"""GitHub REST API client for the authenticated user's repositories."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

import requests

GITHUB_API = "https://api.github.com"


def _gh_cli_token() -> str | None:
    """Return the token stored by `gh auth login`, or `None` if unavailable."""
    if not shutil.which("gh"):
        return None
    try:
        r = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    return r.stdout.strip() or None


class GitHubClient:
    """Thin wrapper around the GitHub REST API for the authenticated user.

    The token is resolved in this order: constructor argument, `GITHUB_TOKEN`
    environment variable, then `gh auth token` from the GitHub CLI.
    """

    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN") or _gh_cli_token()
        self.session = requests.Session()
        if self.token:
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                }
            )

    def whoami(self) -> str | None:
        """Return the authenticated user's login, or `None` on failure."""
        r = self.session.get(f"{GITHUB_API}/user", timeout=30)
        if r.status_code == 200:
            return r.json().get("login")
        return None

    def list_repos(self, include_archived: bool = True) -> list[dict[str, Any]]:
        """Fetch all repositories owned by the authenticated user.

        Pages through `/user/repos?affiliation=owner` 100 at a time. Repos
        are returned in `updated_at` descending order (the API default),
        with archived repos pushed to the end of the list.
        """
        repos: list[dict[str, Any]] = []
        page = 1
        while True:
            r = self.session.get(
                f"{GITHUB_API}/user/repos",
                params={
                    "per_page": 100,
                    "page": page,
                    "affiliation": "owner",
                    "sort": "updated",
                    "direction": "desc",
                },
                timeout=30,
            )
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            for repo in batch:
                if not include_archived and repo.get("archived"):
                    continue
                repos.append(repo)
            if len(batch) < 100:
                break
            page += 1
        repos.sort(key=lambda r: bool(r.get("archived")))
        return repos

    def delete_repo(self, full_name: str) -> tuple[bool, str]:
        """Delete a repository. Returns `(ok, message)`."""
        r = self.session.delete(f"{GITHUB_API}/repos/{full_name}", timeout=30)
        if r.status_code == 204:
            return True, f"Deleted {full_name}"
        return False, f"HTTP {r.status_code}: {r.text[:160]}"
