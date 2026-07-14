"""Tests for pure TUI logic (no app instantiation)."""

from __future__ import annotations

from conftest import make_repo

from gman.tui import row_for_repo


def test_row_for_repo_basic() -> None:
    repo = make_repo("alpha", stargazers_count=5, open_issues_count=2)
    row = row_for_repo(repo, pinned=set())
    assert row == ("alpha", "🌐", "desc for alpha", "Python", "5", "2", "2026-01-01")


def test_row_for_repo_badges() -> None:
    repo = make_repo("beta", private=True, archived=True)
    row = row_for_repo(repo, pinned={"octocat/beta"})
    assert row[1] == "🔒❌📌"


def test_row_for_repo_truncates_description() -> None:
    repo = make_repo("gamma", description="x" * 100)
    row = row_for_repo(repo, pinned=set())
    assert len(row[2]) == 78 and row[2].endswith("…")


def test_row_for_repo_escapes_markup_in_description() -> None:
    repo = make_repo("delta", description="see [/] notes")
    row = row_for_repo(repo, pinned=set())
    assert row[2] == r"see \[/] notes"
