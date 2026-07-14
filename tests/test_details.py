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
    probe_capabilities,
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
    # traffic denied (admin.read) → None + hinted
    assert details.traffic is None and "traffic" in details.hints
    # pages absent (404 = true absence) → None WITHOUT hint
    assert details.pages is None and "pages" not in details.hints


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


@responses.activate
def test_probe_capabilities_marks_read_families(client: GitHubClient) -> None:
    full = "octocat/newest"
    responses.add(
        responses.GET,
        f"{DEFAULT_API_URL}/user/repos",
        json=[make_repo("newest")],
        status=200,
    )
    responses.add(responses.GET, f"{DEFAULT_API_URL}/repos/{full}/readme", body="# x", status=200)
    responses.add(responses.GET, f"{DEFAULT_API_URL}/repos/{full}/actions/runs", status=403)
    responses.add(responses.GET, f"{DEFAULT_API_URL}/repos/{full}/pages", status=404)
    responses.add(responses.GET, f"{DEFAULT_API_URL}/repos/{full}/traffic/views", status=403)
    responses.add(responses.GET, f"{DEFAULT_API_URL}/repos/{full}/pulls", json=[], status=200)

    probe_capabilities(client)

    caps = client.capabilities
    assert caps.resolve("contents.read") is True
    assert caps.resolve("actions.read") is False
    assert caps.resolve("pages.read") is True  # 404 = authz passed
    assert caps.resolve("admin.read") is False
    assert caps.resolve("pulls.read") is True


@responses.activate
def test_probe_capabilities_silent_on_failure(client: GitHubClient) -> None:
    responses.add(responses.GET, f"{DEFAULT_API_URL}/user/repos", status=401)
    probe_capabilities(client)  # must not raise


def test_render_details_survives_markup_in_metadata() -> None:
    from io import StringIO

    from rich.console import Console

    details = RepoDetails(
        repo=make_repo("r", description="see [/] notes [WIP]", topics=["a[b]c"]),
        open_prs=0,
    )
    console = Console(file=StringIO(), width=200)
    console.print(render_details(details))  # must not raise MarkupError
    out = console.file.getvalue()
    assert "[WIP]" in out
    assert "a[b]c" in out


@responses.activate
def test_backup_repo_creates_missing_dir(client: GitHubClient, tmp_path: Path) -> None:
    responses.add(
        responses.GET,
        f"{DEFAULT_API_URL}/repos/octocat/r/tarball/main",
        body=b"bytes",
        status=200,
    )
    dest = tmp_path / "does" / "not" / "exist"
    path = backup_repo(client, make_repo("r"), dest)
    assert path == dest / "r-main.tar.gz"
    assert path.read_bytes() == b"bytes"


@responses.activate
def test_probe_capabilities_silent_on_rate_limit(client: GitHubClient) -> None:
    responses.add(
        responses.GET,
        f"{DEFAULT_API_URL}/user/repos",
        json={"message": "rate limited"},
        status=403,
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1893456000"},
    )
    probe_capabilities(client)  # must not raise
