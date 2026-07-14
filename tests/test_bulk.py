"""Tests for topic validation and the bulk-op registry."""

from __future__ import annotations

import pytest
import responses
from conftest import make_repo

from gman.bulk import (
    TUI_BULK_MENU,
    add_topic_op,
    build_menu_op,
    fields_op,
    normalize_topics,
    remove_topic_op,
)
from gman.client import DEFAULT_API_URL, GitHubClient


@pytest.fixture
def client() -> GitHubClient:
    return GitHubClient(token="fake-token")


def test_normalize_topics_parses_and_dedupes() -> None:
    valid, errors = normalize_topics("CLI, github cli,  tui")
    assert valid == ["cli", "github", "tui"]
    assert errors == []


def test_normalize_topics_rejects_bad_charset_and_length() -> None:
    valid, errors = normalize_topics("good, Bad_Topic!, -leading, " + "x" * 51)
    assert valid == ["good"]
    assert len(errors) == 3


def test_normalize_topics_rejects_too_many() -> None:
    raw = ",".join(f"t{i}" for i in range(21))
    valid, errors = normalize_topics(raw)
    assert len(valid) == 21  # parsed, but flagged
    assert any("at most 20" in e for e in errors)


@responses.activate
def test_add_topic_op_appends_to_current(client: GitHubClient) -> None:
    responses.add(responses.PUT, f"{DEFAULT_API_URL}/repos/octocat/r/topics", json={}, status=200)
    repo = make_repo("r", topics=["existing"])

    ok, _ = add_topic_op("new").apply(client, repo)

    assert ok
    import json as jsonlib

    assert jsonlib.loads(responses.calls[0].request.body) == {"names": ["existing", "new"]}


def test_add_topic_op_noop_when_present(client: GitHubClient) -> None:
    repo = make_repo("r", topics=["existing"])
    ok, msg = add_topic_op("existing").apply(client, repo)
    assert ok and "already" in msg  # no HTTP call registered — would error if attempted


def test_remove_topic_op_noop_when_absent(client: GitHubClient) -> None:
    repo = make_repo("r", topics=["other"])
    ok, msg = remove_topic_op("gone").apply(client, repo)
    assert ok and "does not have" in msg


@responses.activate
def test_fields_op_patches(client: GitHubClient) -> None:
    responses.add(responses.PATCH, f"{DEFAULT_API_URL}/repos/octocat/r", json={}, status=200)
    op = fields_op({"delete_branch_on_merge": True}, "DBOM on")

    ok, _ = op.apply(client, make_repo("r"))

    assert ok and op.label == "DBOM on"


def test_build_menu_op_covers_every_menu_key() -> None:
    for key, _label, needs_topic in TUI_BULK_MENU:
        op = build_menu_op(key, "sometopic" if needs_topic else None)
        assert op.label


def test_build_menu_op_errors() -> None:
    with pytest.raises(ValueError):
        build_menu_op("nonsense")
    with pytest.raises(ValueError):
        build_menu_op("add_topic", None)  # missing required topic
