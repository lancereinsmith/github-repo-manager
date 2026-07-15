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


def test_info_plain_output_survives_markup(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from gman.details import RepoDetails

    repo = make_repo("alpha", description="see [/] notes [WIP]")

    class FakeClient:
        def get_repo(self, full_name):
            return repo

    monkeypatch.setattr(cli, "fetch_details", lambda c, r: RepoDetails(repo=r, open_prs=0))
    rc = cli.cli_info(FakeClient(), "octocat/alpha", as_json=False)

    assert rc == 0
    assert "WIP" in capsys.readouterr().out


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


def test_build_edit_fields_maps_flags() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "edit",
            "o/r",
            "--homepage",
            "https://x.example",
            "--visibility",
            "private",
            "--rename",
            "newname",
            "--wiki",
            "off",
            "--delete-branch-on-merge",
            "on",
            "--allow-rebase",
            "off",
            "--squash-commit-title",
            "PR_TITLE",
        ]
    )
    assert cli.build_edit_fields(args) == {
        "homepage": "https://x.example",
        "visibility": "private",
        "name": "newname",
        "has_wiki": False,
        "delete_branch_on_merge": True,
        "allow_rebase_merge": False,
        "squash_merge_commit_title": "PR_TITLE",
    }


def test_edit_no_flags_errors(capsys) -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["edit", "o/r"])

    class FakeClient:
        pass

    rc = cli.cli_edit(FakeClient(), args)
    assert rc == 2
    assert "nothing to change" in capsys.readouterr().err


def test_edit_fields_and_add_topic(capsys) -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["edit", "octocat/r", "--wiki", "off", "--add-topic", "NewTopic"])
    calls: list = []

    class FakeClient:
        def update_repo(self, full, fields):
            calls.append(("patch", full, fields))
            return True, f"Updated {full}"

        def get_repo(self, full):
            return make_repo("r", topics=["old"])

        def set_topics(self, full, topics):
            calls.append(("topics", full, topics))
            return True, f"Set {len(topics)} topics on {full}"

    rc = cli.cli_edit(FakeClient(), args)

    assert rc == 0
    assert ("patch", "octocat/r", {"has_wiki": False}) in calls
    assert ("topics", "octocat/r", ["old", "newtopic"]) in calls


def test_edit_topics_conflict_errors(capsys) -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["edit", "o/r", "--topics", "a,b", "--add-topic", "c"])

    class FakeClient:
        pass

    rc = cli.cli_edit(FakeClient(), args)
    assert rc == 2
    assert "cannot be combined" in capsys.readouterr().err


def test_edit_invalid_topic_applies_nothing(capsys) -> None:
    """Exit 2 must always mean nothing was written."""
    parser = cli.build_parser()
    args = parser.parse_args(["edit", "octocat/r", "--wiki", "off", "--add-topic", "Bad_Topic!"])
    calls: list = []

    class FakeClient:
        def update_repo(self, full, fields):
            calls.append(("patch", full, fields))
            return True, f"Updated {full}"

        def get_repo(self, full):
            return make_repo("r")

        def set_topics(self, full, topics):
            calls.append(("topics", full, topics))
            return True, "ok"

    rc = cli.cli_edit(FakeClient(), args)

    assert rc == 2
    assert calls == []  # no write happened
    assert "invalid topic" in capsys.readouterr().err


def _bulk_args(*argv: str):
    return cli.build_parser().parse_args(["bulk", *argv])


class _BulkFakeClient:
    def __init__(self, repos):
        self.repos = repos
        self.patched: list = []
        from gman.capabilities import CapabilityCache, TokenInfo

        self.capabilities = CapabilityCache(TokenInfo(kind="classic", scopes={"repo"}))

    def list_repos(self, **kw):
        return self.repos

    def get_repo(self, full):
        return next(r for r in self.repos if r["full_name"] == full)

    def update_repo(self, full, fields):
        self.patched.append((full, fields))
        return True, f"Updated {full}"


def test_bulk_requires_exactly_one_target_source(capsys) -> None:
    fake = _BulkFakeClient([make_repo("a")])
    rc = cli.cli_bulk(fake, _bulk_args("--wiki", "off"))  # no targets at all
    assert rc == 2
    assert "exactly one" in capsys.readouterr().err


def test_bulk_dry_run_lists_and_changes_nothing(capsys) -> None:
    fake = _BulkFakeClient([make_repo("a"), make_repo("b", description="match me")])
    rc = cli.cli_bulk(fake, _bulk_args("--filter", "match", "--wiki", "off", "--dry-run"))

    out = capsys.readouterr().out
    assert rc == 0
    assert "octocat/b" in out and "octocat/a" not in out
    assert "Dry run" in out
    assert fake.patched == []


def test_bulk_confirm_decline_makes_no_calls(monkeypatch, capsys) -> None:
    fake = _BulkFakeClient([make_repo("a")])
    monkeypatch.setattr("builtins.input", lambda _p: "n")
    rc = cli.cli_bulk(fake, _bulk_args("--all", "--wiki", "off"))
    assert rc == 1
    assert fake.patched == []


def test_bulk_yes_applies_and_reports(capsys) -> None:
    fake = _BulkFakeClient([make_repo("a"), make_repo("b")])
    rc = cli.cli_bulk(fake, _bulk_args("--all", "--delete-branch-on-merge", "on", "--yes"))

    out = capsys.readouterr().out
    assert rc == 0
    assert fake.patched == [
        ("octocat/a", {"delete_branch_on_merge": True}),
        ("octocat/b", {"delete_branch_on_merge": True}),
    ]
    assert out.count("✅") == 2


def test_bulk_no_op_flags_errors(capsys) -> None:
    fake = _BulkFakeClient([make_repo("a")])
    rc = cli.cli_bulk(fake, _bulk_args("--all"))
    assert rc == 2
    assert "no operation flags" in capsys.readouterr().err


def test_bulk_denied_write_capability_errors(capsys) -> None:
    fake = _BulkFakeClient([make_repo("a")])
    fake.capabilities.mark("admin.write", False)
    rc = cli.cli_bulk(fake, _bulk_args("--all", "--wiki", "off", "--yes"))
    assert rc == 1
    assert "cannot write" in capsys.readouterr().err


def test_bulk_add_topic_applies_normalized(capsys) -> None:
    """--add-topic Python must apply 'python' (and 'a,b' splits into two ops)."""
    fake = _BulkFakeClient([make_repo("a", topics=["old"])])
    fake.topic_calls: list = []

    def set_topics(full, topics):
        fake.topic_calls.append((full, topics))
        return True, f"Set {len(topics)} topics on {full}"

    fake.set_topics = set_topics
    rc = cli.cli_bulk(fake, _bulk_args("--all", "--add-topic", "Python", "--yes"))

    assert rc == 0
    assert fake.topic_calls == [("octocat/a", ["old", "python"])]


def test_bulk_sync_fork_flag(capsys) -> None:
    fake = _BulkFakeClient([make_repo("a"), make_repo("f", fork=True)])
    fake.synced: list = []

    def merge_upstream(full, branch):
        fake.synced.append((full, branch))
        return True, f"Synced {full} with upstream"

    fake.merge_upstream = merge_upstream
    rc = cli.cli_bulk(fake, _bulk_args("--all", "--sync-fork", "--yes"))

    out = capsys.readouterr().out
    assert rc == 0
    assert fake.synced == [("octocat/f", "main")]  # only the fork
    assert "skipped" in out  # the non-fork line


def test_bulk_clear_artifacts_flag(capsys) -> None:
    fake = _BulkFakeClient([make_repo("a")])
    fake.cleared: list = []

    def list_artifacts(full):
        return [{"id": 1, "size_in_bytes": 5_000_000}]

    def delete_artifact(full, artifact_id):
        fake.cleared.append((full, artifact_id))
        return True, "ok"

    fake.list_artifacts = list_artifacts
    fake.delete_artifact = delete_artifact
    rc = cli.cli_bulk(fake, _bulk_args("--all", "--clear-artifacts", "--yes"))

    assert rc == 0
    assert fake.cleared == [("octocat/a", 1)]


def test_sync_happy_path(capsys) -> None:
    class FakeClient:
        def get_repo(self, full):
            return make_repo("f", fork=True, default_branch="dev")

        def merge_upstream(self, full, branch):
            return True, f"Synced {full} with upstream ({branch})"

    rc = cli.cli_sync(FakeClient(), "octocat/f", branch=None)
    out = capsys.readouterr().out
    assert rc == 0 and "dev" in out  # default branch used


def test_sync_not_a_fork(capsys) -> None:
    class FakeClient:
        def get_repo(self, full):
            return make_repo("r")  # fork=False

    rc = cli.cli_sync(FakeClient(), "octocat/r", branch=None)
    assert rc == 1
    assert "not a fork" in capsys.readouterr().err


def test_sync_branch_override(capsys) -> None:
    seen = []

    class FakeClient:
        def get_repo(self, full):
            return make_repo("f", fork=True)

        def merge_upstream(self, full, branch):
            seen.append(branch)
            return True, "ok"

    rc = cli.cli_sync(FakeClient(), "octocat/f", branch="release")
    assert rc == 0 and seen == ["release"]


def test_parser_accepts_sync() -> None:
    args = cli.build_parser().parse_args(["sync", "o/r", "--branch", "main"])
    assert args.command == "sync" and args.branch == "main"
