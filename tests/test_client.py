"""Tests for the GitHub API client."""

from __future__ import annotations

import pytest
import responses
from conftest import make_repo

from gman.client import DEFAULT_API_URL, GitHubClient, RateLimitError


@pytest.fixture
def client() -> GitHubClient:
    return GitHubClient(token="fake-token")


@responses.activate
def test_list_repos_paginates_and_sorts_archived_last(client: GitHubClient) -> None:
    page1 = [make_repo(f"repo{i}") for i in range(100)]
    page2 = [make_repo("active"), make_repo("old", archived=True)]
    responses.add(responses.GET, f"{DEFAULT_API_URL}/user/repos", json=page1, status=200)
    responses.add(responses.GET, f"{DEFAULT_API_URL}/user/repos", json=page2, status=200)

    repos = client.list_repos()

    assert len(repos) == 102
    # A second page was fetched because page 1 was full.
    assert len(responses.calls) == 2
    # Archived repos are pushed to the end.
    assert repos[-1]["name"] == "old"
    assert all(not r["archived"] for r in repos[:-1])


@responses.activate
def test_list_repos_can_exclude_archived(client: GitHubClient) -> None:
    batch = [make_repo("active"), make_repo("old", archived=True)]
    responses.add(responses.GET, f"{DEFAULT_API_URL}/user/repos", json=batch, status=200)

    repos = client.list_repos(include_archived=False)

    assert [r["name"] for r in repos] == ["active"]


@responses.activate
def test_list_repos_reports_progress(client: GitHubClient) -> None:
    responses.add(responses.GET, f"{DEFAULT_API_URL}/user/repos", json=[make_repo("a")], status=200)
    seen: list[int] = []

    client.list_repos(progress=seen.append)

    assert seen == [1]


@responses.activate
def test_list_repos_passes_affiliation(client: GitHubClient) -> None:
    responses.add(responses.GET, f"{DEFAULT_API_URL}/user/repos", json=[], status=200)

    client.list_repos(affiliation="owner,organization_member")

    assert "affiliation=owner%2Corganization_member" in str(responses.calls[0].request.url)


@responses.activate
def test_rate_limit_raises(client: GitHubClient) -> None:
    responses.add(
        responses.GET,
        f"{DEFAULT_API_URL}/user/repos",
        json={"message": "rate limited"},
        status=403,
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1893456000"},
    )

    with pytest.raises(RateLimitError, match="rate limit exceeded"):
        client.list_repos()


@responses.activate
def test_retries_transient_5xx(monkeypatch: pytest.MonkeyPatch, client: GitHubClient) -> None:
    monkeypatch.setattr("gman.client.time.sleep", lambda _s: None)
    responses.add(responses.GET, f"{DEFAULT_API_URL}/user", status=502)
    responses.add(responses.GET, f"{DEFAULT_API_URL}/user", json={"login": "octocat"}, status=200)

    assert client.whoami() == "octocat"
    assert len(responses.calls) == 2


@responses.activate
def test_delete_repo_success(client: GitHubClient) -> None:
    responses.add(responses.DELETE, f"{DEFAULT_API_URL}/repos/octocat/x", status=204)

    ok, msg = client.delete_repo("octocat/x")

    assert ok
    assert "Deleted" in msg


@responses.activate
def test_delete_repo_failure_returns_tuple(client: GitHubClient) -> None:
    responses.add(
        responses.DELETE,
        f"{DEFAULT_API_URL}/repos/octocat/x",
        json={"message": "Not Found"},
        status=404,
    )

    ok, msg = client.delete_repo("octocat/x")

    assert not ok
    assert "404" in msg


@responses.activate
def test_set_archived_and_description(client: GitHubClient) -> None:
    responses.add(responses.PATCH, f"{DEFAULT_API_URL}/repos/octocat/x", json={}, status=200)
    responses.add(responses.PATCH, f"{DEFAULT_API_URL}/repos/octocat/x", json={}, status=200)

    ok1, _ = client.set_archived("octocat/x", archived=True)
    ok2, msg2 = client.set_description("octocat/x", "new")

    assert ok1 and ok2
    assert "description" in msg2


@responses.activate
def test_enterprise_api_url() -> None:
    enterprise = "https://ghe.example.com/api/v3"
    client = GitHubClient(token="t", api_url=enterprise + "/")  # trailing slash trimmed
    responses.add(responses.GET, f"{enterprise}/user", json={"login": "me"}, status=200)

    assert client.whoami() == "me"
    assert client.api_url == enterprise


def test_api_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_API_URL", "https://ghe.example.com/api/v3")
    monkeypatch.setenv("GITHUB_TOKEN", "t")

    assert GitHubClient().api_url == "https://ghe.example.com/api/v3"


@responses.activate
def test_scopes_captured_from_first_response(client: GitHubClient) -> None:
    responses.add(
        responses.GET,
        f"{DEFAULT_API_URL}/user",
        json={"login": "octocat"},
        status=200,
        headers={"X-OAuth-Scopes": "repo, delete_repo"},
    )
    client.whoami()
    assert client.token_info.scopes == {"repo", "delete_repo"}
    assert client.token_info.kind == "classic"
    assert client.capabilities.resolve("delete") is True


@responses.activate
def test_no_scopes_header_leaves_scopes_none(client: GitHubClient) -> None:
    responses.add(responses.GET, f"{DEFAULT_API_URL}/user", json={"login": "o"}, status=200)
    client.whoami()
    assert client.token_info.scopes is None


@responses.activate
def test_get_optional_403_marks_denied(client: GitHubClient) -> None:
    responses.add(
        responses.GET,
        f"{DEFAULT_API_URL}/repos/o/r/actions/runs",
        json={"message": "Resource not accessible by personal access token"},
        status=403,
    )
    r = client._get_optional("actions.read", "/repos/o/r/actions/runs")
    assert r is None
    assert client.capabilities.resolve("actions.read") is False


@responses.activate
def test_get_optional_404_marks_allowed(client: GitHubClient) -> None:
    responses.add(responses.GET, f"{DEFAULT_API_URL}/repos/o/r/pages", status=404)
    r = client._get_optional("pages.read", "/repos/o/r/pages")
    assert r is None
    assert client.capabilities.resolve("pages.read") is True


def test_token_source_flag() -> None:
    assert GitHubClient(token="t").token_source == "--token flag"


def test_token_source_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    assert GitHubClient().token_source == "GITHUB_TOKEN env"


@responses.activate
def test_scopes_still_captured_after_failed_first_request(client: GitHubClient) -> None:
    """A dead first response must not latch the capture flag."""
    responses.add(responses.GET, f"{DEFAULT_API_URL}/repos/o/r", status=404)
    responses.add(
        responses.GET,
        f"{DEFAULT_API_URL}/user",
        json={"login": "o"},
        status=200,
        headers={"X-OAuth-Scopes": "repo"},
    )
    client._request("GET", "/repos/o/r")  # 404: not ok, must not latch
    client.whoami()
    assert client.token_info.scopes == {"repo"}
