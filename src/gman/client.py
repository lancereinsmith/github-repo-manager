"""GitHub REST API client for the authenticated user's repositories."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import requests

DEFAULT_API_URL = "https://api.github.com"


class GitHubError(Exception):
    """Raised when a request to the GitHub API cannot be completed."""


class RateLimitError(GitHubError):
    """Raised when the GitHub API rate limit has been exhausted."""


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


def _rate_limit_message(reset: str | None) -> str:
    if reset:
        try:
            when = datetime.fromtimestamp(int(reset), tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            pass
        else:
            return f"GitHub API rate limit exceeded; resets at {when:%Y-%m-%d %H:%M UTC}."
    return "GitHub API rate limit exceeded."


class GitHubClient:
    """Thin wrapper around the GitHub REST API for the authenticated user.

    The token is resolved in this order: constructor argument, `GITHUB_TOKEN`
    environment variable, then `gh auth token` from the GitHub CLI.

    The API base URL is resolved from the constructor argument, then the
    `GITHUB_API_URL` environment variable, then the public GitHub API. Set it
    to `https://<host>/api/v3` to talk to a GitHub Enterprise Server instance.
    """

    def __init__(
        self,
        token: str | None = None,
        api_url: str | None = None,
        max_retries: int = 3,
    ) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN") or _gh_cli_token()
        self.api_url = (api_url or os.getenv("GITHUB_API_URL") or DEFAULT_API_URL).rstrip("/")
        self.max_retries = max_retries
        self.session = requests.Session()
        if self.token:
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                }
            )

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Perform a request, retrying transient failures and surfacing rate limits.

        Raises `RateLimitError` when the rate limit is exhausted and
        `GitHubError` when the request cannot be completed after retries.
        """
        url = path if path.startswith("http") else f"{self.api_url}{path}"
        kwargs.setdefault("timeout", 30)
        for attempt in range(self.max_retries + 1):
            try:
                r = self.session.request(method, url, **kwargs)
            except requests.RequestException as e:
                if attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue
                raise GitHubError(f"Request to {url} failed: {e}") from e
            if r.status_code in (403, 429) and r.headers.get("X-RateLimit-Remaining") == "0":
                raise RateLimitError(_rate_limit_message(r.headers.get("X-RateLimit-Reset")))
            if r.status_code >= 500 and attempt < self.max_retries:
                time.sleep(2**attempt)
                continue
            return r
        raise GitHubError(f"Request to {url} failed after {self.max_retries} retries")

    def whoami(self) -> str | None:
        """Return the authenticated user's login, or `None` on failure."""
        try:
            r = self._request("GET", "/user")
        except GitHubError:
            return None
        if r.status_code == 200:
            return r.json().get("login")
        return None

    def list_repos(
        self,
        include_archived: bool = True,
        affiliation: str = "owner",
        progress: Callable[[int], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch repositories for the authenticated user.

        Pages through `/user/repos` 100 at a time. `affiliation` is passed
        straight to the API (e.g. `owner`, `collaborator`,
        `organization_member`, or a comma-separated combination). Repos are
        returned in `updated_at` descending order (the API default), with
        archived repos pushed to the end of the list. `progress`, if given, is
        called with the running repo count after each page.
        """
        repos: list[dict[str, Any]] = []
        page = 1
        while True:
            r = self._request(
                "GET",
                "/user/repos",
                params={
                    "per_page": 100,
                    "page": page,
                    "affiliation": affiliation,
                    "sort": "updated",
                    "direction": "desc",
                },
            )
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            for repo in batch:
                if not include_archived and repo.get("archived"):
                    continue
                repos.append(repo)
            if progress is not None:
                progress(len(repos))
            if len(batch) < 100:
                break
            page += 1
        repos.sort(key=lambda r: bool(r.get("archived")))
        return repos

    def delete_repo(self, full_name: str) -> tuple[bool, str]:
        """Delete a repository. Returns `(ok, message)`."""
        try:
            r = self._request("DELETE", f"/repos/{full_name}")
        except GitHubError as e:
            return False, str(e)
        if r.status_code == 204:
            return True, f"Deleted {full_name}"
        return False, f"HTTP {r.status_code}: {r.text[:160]}"

    def set_archived(self, full_name: str, archived: bool) -> tuple[bool, str]:
        """Archive or unarchive a repository. Returns `(ok, message)`."""
        try:
            r = self._request("PATCH", f"/repos/{full_name}", json={"archived": archived})
        except GitHubError as e:
            return False, str(e)
        verb = "Archived" if archived else "Unarchived"
        if r.status_code == 200:
            return True, f"{verb} {full_name}"
        return False, f"HTTP {r.status_code}: {r.text[:160]}"

    def set_description(self, full_name: str, description: str) -> tuple[bool, str]:
        """Update a repository's description. Returns `(ok, message)`."""
        try:
            r = self._request("PATCH", f"/repos/{full_name}", json={"description": description})
        except GitHubError as e:
            return False, str(e)
        if r.status_code == 200:
            return True, f"Updated description for {full_name}"
        return False, f"HTTP {r.status_code}: {r.text[:160]}"
