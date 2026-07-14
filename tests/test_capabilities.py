"""Tests for token classification and the capability cache."""

from __future__ import annotations

from gman.capabilities import CapabilityCache, TokenInfo, classify_token


def test_classify_token_prefixes() -> None:
    assert classify_token("ghp_abc123") == "classic"
    assert classify_token("gho_abc123") == "classic"  # gh CLI OAuth token
    assert classify_token("github_pat_abc123") == "fine-grained"
    assert classify_token("ghs_something") == "unknown"
    assert classify_token(None) == "unknown"


def test_apply_scopes_header_parses_and_upgrades_kind() -> None:
    info = TokenInfo(kind="unknown")
    info.apply_scopes_header("repo, read:org, gist")
    assert info.scopes == {"repo", "read:org", "gist"}
    assert info.kind == "classic"  # header presence implies classic


def test_apply_scopes_header_absent_is_noop() -> None:
    info = TokenInfo(kind="fine-grained")
    info.apply_scopes_header(None)
    assert info.scopes is None
    assert info.kind == "fine-grained"


def test_classic_repo_scope_resolves_families() -> None:
    info = TokenInfo(kind="classic", scopes={"repo", "read:org"})
    cache = CapabilityCache(info)
    assert cache.resolve("contents.read") is True
    assert cache.resolve("actions.read") is True
    assert cache.resolve("pages.read") is True
    assert cache.resolve("admin.write") is True
    assert cache.resolve("delete") is False  # needs delete_repo, repo is not enough


def test_classic_delete_repo_scope_enables_delete() -> None:
    info = TokenInfo(kind="classic", scopes={"repo", "delete_repo"})
    cache = CapabilityCache(info)
    assert cache.resolve("delete") is True


def test_fine_grained_starts_unknown_and_learns() -> None:
    cache = CapabilityCache(TokenInfo(kind="fine-grained"))
    assert cache.resolve("actions.read") is None
    cache.mark("actions.read", False)
    assert cache.resolve("actions.read") is False
    cache.mark("contents.read", True)
    assert cache.resolve("contents.read") is True


def test_observed_403_overrides_classic_scopes() -> None:
    # e.g. SSO/org restrictions: a real 403 beats what the scopes claim
    cache = CapabilityCache(TokenInfo(kind="classic", scopes={"repo"}))
    cache.mark("actions.read", False)
    assert cache.resolve("actions.read") is False


def test_hints_exist_for_all_families() -> None:
    from gman.capabilities import ALL_FAMILIES

    cache = CapabilityCache(TokenInfo())
    for family in ALL_FAMILIES:
        assert cache.hint(family)  # non-empty string
