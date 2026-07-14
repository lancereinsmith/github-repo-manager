"""Tests for detail fetching, delete warnings, backup helpers, and rendering."""

from __future__ import annotations

from pathlib import Path

import pytest
import responses
from conftest import make_repo

from gman.client import DEFAULT_API_URL, GitHubClient
from gman.details import (
    RepoDetails,
    backup_repo,
    build_delete_warnings,
    details_to_dict,
    fetch_details,
    render_details,
    unique_path,
)


@pytest.fixture
def client() -> GitHubClient:
    return GitHubClient(token="fake-token")


def test_build_delete_warnings() -> None:
    repo = make_repo("r", forks_count=2, stargazers_count=1, private=False)
    warnings = build_delete_warnings(repo, pinned={"octocat/r"})
    joined = "\n".join(warnings)
    assert "2 forks" in joined
    assert "1 star" in joined
    assert "pinned" in joined
    assert "public" in joined


def test_build_delete_warnings_quiet_for_boring_private_repo() -> None:
    repo = make_repo("r", private=True)
    assert build_delete_warnings(repo, pinned=set()) == []


def test_unique_path_suffixes(tmp_path: Path) -> None:
    p = tmp_path / "r-main.tar.gz"
    assert unique_path(p) == p
    p.write_bytes(b"x")
    assert unique_path(p) == tmp_path / "r-main-1.tar.gz"
    (tmp_path / "r-main-1.tar.gz").write_bytes(b"x")
    assert unique_path(p) == tmp_path / "r-main-2.tar.gz"


def test_open_issues_derived() -> None:
    d = RepoDetails(repo=make_repo("r", open_issues_count=10), open_prs=3)
    assert d.open_issues == 7
    d2 = RepoDetails(repo=make_repo("r"), open_prs=None)
    assert d2.open_issues is None


@responses.activate
def test_fetch_details_degrades_per_field(client: GitHubClient) -> None:
    """One denied family must not poison the other fields."""
    full = "octocat/r"
    responses.add(
        responses.GET,
        f"{DEFAULT_API_URL}/repos/{full}/languages",
        json={"Python": 100},
        status=200,
    )
    responses.add(responses.GET, f"{DEFAULT_API_URL}/repos/{full}/releases/latest", status=404)
    responses.add(responses.GET, f"{DEFAULT_API_URL}/repos/{full}/actions/runs", status=403)
    responses.add(responses.GET, f"{DEFAULT_API_URL}/repos/{full}/pages", status=404)
    responses.add(responses.GET, f"{DEFAULT_API_URL}/repos/{full}/traffic/views", status=403)
    responses.add(responses.GET, f"{DEFAULT_API_URL}/repos/{full}/pulls", json=[], status=200)

    details = fetch_details(client, make_repo("r"))

    assert details.languages == {"Python": 100}
    assert details.latest_release is None and "latest_release" not in details.hints
    assert details.latest_run is None and "latest_run" in details.hints  # denied → hinted
    assert details.open_prs == 0
    assert details.open_issues == 0


@responses.activate
def test_backup_repo_names_file(client: GitHubClient, tmp_path: Path) -> None:
    responses.add(
        responses.GET,
        f"{DEFAULT_API_URL}/repos/octocat/r/tarball/main",
        body=b"bytes",
        status=200,
    )
    path = backup_repo(client, make_repo("r"), tmp_path)
    assert path == tmp_path / "r-main.tar.gz"
    assert path.read_bytes() == b"bytes"


def test_render_and_dict_shapes() -> None:
    details = RepoDetails(
        repo=make_repo("r"),
        languages={"Python": 75, "Shell": 25},
        open_prs=1,
        hints={"traffic": "needs Administration: read"},
    )
    table = render_details(details)  # must not raise
    assert table.row_count > 0
    d = details_to_dict(details)
    assert d["full_name"] == "octocat/r"
    assert d["traffic"] is None
    assert d["open_prs"] == 1
