"""Tests for the CLI layer."""

from __future__ import annotations

import json

import pytest
from conftest import make_repo

from gman import cli


def test_resolve_affiliation() -> None:
    assert cli._resolve_affiliation("owner", include_orgs=False) == "owner"
    assert cli._resolve_affiliation("owner", include_orgs=True) == (
        "owner,collaborator,organization_member"
    )


def test_parser_has_all_commands() -> None:
    parser = cli.build_parser()
    argv_by_cmd = {
        "list": ["list"],
        "delete": ["delete", "o/r"],
        "archive": ["archive", "o/r"],
        "describe": ["describe", "o/r", "a description"],
        "excel": ["excel"],
        "tui": ["tui"],
    }
    for cmd, argv in argv_by_cmd.items():
        assert parser.parse_args(argv).command == cmd


def test_main_without_token_errors(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(
        cli.GitHubClient, "__init__", lambda self, **kw: setattr(self, "token", None)
    )

    rc = cli.main(["list"])

    assert rc == 1
    assert "no GitHub token" in capsys.readouterr().err


def test_list_json_output(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    repos = [make_repo("alpha"), make_repo("beta", archived=True)]

    class FakeClient:
        token = "t"

        def list_repos(self, **kw):
            return repos

    rc = cli.cli_list(FakeClient(), detailed=False, as_json=True, affiliation="owner")

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert [r["name"] for r in payload] == ["alpha", "beta"]
    assert payload[1]["archived"] is True
    # Only the curated field set is emitted.
    assert set(payload[0]) == set(cli._JSON_FIELDS)


def test_describe_reports_result(capsys) -> None:
    class FakeClient:
        def set_description(self, full_name, description):
            return True, f"Updated description for {full_name}"

    rc = cli.cli_describe(FakeClient(), "octocat/x", "hello")

    assert rc == 0
    assert "Updated description" in capsys.readouterr().out


def test_info_json_output(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from gman.details import RepoDetails

    repo = make_repo("alpha")
    details = RepoDetails(repo=repo, open_prs=2, hints={"traffic": "needs Administration: read"})

    class FakeClient:
        token = "t"

        def get_repo(self, full_name):
            return repo

    monkeypatch.setattr(cli, "fetch_details", lambda c, r: details)
    rc = cli.cli_info(FakeClient(), "octocat/alpha", as_json=True)

    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["full_name"] == "octocat/alpha"
    assert payload["open_prs"] == 2
    assert payload["traffic"] is None


def test_info_hints_go_to_stderr(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from gman.details import RepoDetails

    repo = make_repo("alpha")
    details = RepoDetails(repo=repo, hints={"traffic": "needs Administration: read"})

    class FakeClient:
        def get_repo(self, full_name):
            return repo

    monkeypatch.setattr(cli, "fetch_details", lambda c, r: details)
    cli.cli_info(FakeClient(), "octocat/alpha", as_json=True)

    captured = capsys.readouterr()
    assert json.loads(captured.out)  # stdout is clean JSON
    assert "traffic" in captured.err  # hint on stderr


def test_parser_accepts_info() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["info", "o/r", "--json"])
    assert args.command == "info" and args.as_json is True


def test_auth_shows_token_facts(capsys) -> None:
    from gman.capabilities import CapabilityCache, TokenInfo

    class FakeClient:
        token = "t"
        token_source = "GITHUB_TOKEN env"
        token_info = TokenInfo(kind="classic", scopes={"repo", "delete_repo"})

        def __init__(self):
            self.capabilities = CapabilityCache(self.token_info)

        def whoami(self):
            return "octocat"

    rc = cli.cli_auth(FakeClient(), probe=False)
    out = capsys.readouterr().out

    assert rc == 0
    assert "octocat" in out
    assert "classic" in out
    assert "delete_repo" in out
    assert "✅" in out  # repo scope resolves read families to available


def test_auth_rejected_token(capsys) -> None:
    class FakeClient:
        token = "t"

        def whoami(self):
            return None

    rc = cli.cli_auth(FakeClient(), probe=False)
    assert rc == 1
    assert "rejected" in capsys.readouterr().err


def test_parser_accepts_auth() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["auth", "--probe"])
    assert args.command == "auth" and args.probe is True


def test_delete_prints_warnings(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    repo = make_repo("r", forks_count=3, private=False)

    class FakeClient:
        def get_repo(self, full_name):
            return repo

        def get_pinned_repos(self):
            return set()

        def delete_repo(self, full_name):
            return True, f"Deleted {full_name}"

    monkeypatch.setattr("builtins.input", lambda _prompt: "octocat/r")
    rc = cli.cli_delete(FakeClient(), "octocat/r", force=False)

    out = capsys.readouterr().out
    assert rc == 0
    assert "3 forks" in out
    assert "public" in out


def test_delete_backup_failure_aborts(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path) -> None:
    from gman.client import GitHubError

    deleted = []

    class FakeClient:
        def get_repo(self, full_name):
            return make_repo("r")

        def delete_repo(self, full_name):
            deleted.append(full_name)
            return True, "Deleted"

    def boom(client, repo, dest_dir):
        raise GitHubError("Tarball download failed: HTTP 500")

    monkeypatch.setattr(cli, "backup_repo", boom)
    with pytest.raises(GitHubError):
        cli.cli_delete(FakeClient(), "octocat/r", force=True, backup=True, backup_dir=str(tmp_path))
    assert deleted == []  # deletion never attempted


def test_delete_backup_success_then_delete(
    monkeypatch: pytest.MonkeyPatch, capsys, tmp_path
) -> None:
    deleted = []

    class FakeClient:
        def get_repo(self, full_name):
            return make_repo("r")

        def delete_repo(self, full_name):
            deleted.append(full_name)
            return True, f"Deleted {full_name}"

    monkeypatch.setattr(cli, "backup_repo", lambda c, r, d: d / "r-main.tar.gz")
    rc = cli.cli_delete(
        FakeClient(), "octocat/r", force=True, backup=True, backup_dir=str(tmp_path)
    )

    assert rc == 0
    assert deleted == ["octocat/r"]
    assert "Backed up" in capsys.readouterr().out
