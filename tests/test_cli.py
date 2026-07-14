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
