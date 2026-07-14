"""Command-line entry point: `list`, `delete`, `archive`, `describe`, `excel`, `tui`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from gman.bulk import normalize_topics
from gman.capabilities import ALL_FAMILIES
from gman.client import GitHubClient, GitHubError
from gman.details import (
    backup_repo,
    build_delete_warnings,
    details_to_dict,
    fetch_details,
    probe_capabilities,
    render_details,
)
from gman.excel import DEFAULT_EXCEL_FILE, write_excel

_JSON_FIELDS = (
    "name",
    "full_name",
    "private",
    "archived",
    "visibility",
    "description",
    "language",
    "stargazers_count",
    "forks_count",
    "updated_at",
    "html_url",
)

FAMILY_FEATURES = {
    "contents.read": "README preview, releases, tarball backup",
    "actions.read": "CI status",
    "pages.read": "Pages URL",
    "admin.read": "traffic stats",
    "pulls.read": "open PR/issue split",
    "admin.write": "archive, describe, and other writes",
    "delete": "delete repos",
}

_ONOFF = {"on": True, "off": False}

# (flag, argparse dest, PATCH field)
_TOGGLE_FLAGS = [
    ("--wiki", "wiki", "has_wiki"),
    ("--issues", "issues", "has_issues"),
    ("--projects", "projects", "has_projects"),
    ("--delete-branch-on-merge", "delete_branch_on_merge", "delete_branch_on_merge"),
    ("--allow-squash", "allow_squash", "allow_squash_merge"),
    ("--allow-merge-commit", "allow_merge_commit", "allow_merge_commit"),
    ("--allow-rebase", "allow_rebase", "allow_rebase_merge"),
    ("--allow-update-branch", "allow_update_branch", "allow_update_branch"),
]

# (flag, dest, PATCH field, choices)
_ENUM_FLAGS = [
    (
        "--squash-commit-title",
        "squash_commit_title",
        "squash_merge_commit_title",
        ["PR_TITLE", "COMMIT_OR_PR_TITLE"],
    ),
    (
        "--squash-commit-message",
        "squash_commit_message",
        "squash_merge_commit_message",
        ["PR_BODY", "COMMIT_MESSAGES", "BLANK"],
    ),
    (
        "--merge-commit-title",
        "merge_commit_title",
        "merge_commit_title",
        ["PR_TITLE", "MERGE_MESSAGE"],
    ),
    (
        "--merge-commit-message",
        "merge_commit_message",
        "merge_commit_message",
        ["PR_TITLE", "PR_BODY", "BLANK"],
    ),
]


def _resolve_affiliation(affiliation: str, include_orgs: bool) -> str:
    """Return the API `affiliation` filter, widening it when --include-orgs is set."""
    if include_orgs:
        return "owner,collaborator,organization_member"
    return affiliation


def _fetch_repos(client: GitHubClient, affiliation: str, quiet: bool) -> list[dict[str, Any]]:
    """Fetch repos, showing a spinner on stderr unless `quiet`."""
    if quiet:
        return client.list_repos(affiliation=affiliation)
    err = Console(stderr=True)
    with err.status("Fetching repositories…") as status:
        return client.list_repos(
            affiliation=affiliation,
            progress=lambda n: status.update(f"Fetched {n} repositories…"),
        )


def _add_field_flags(p: argparse.ArgumentParser, bulk: bool) -> None:
    """Settings flags shared by `edit` and `bulk` (bulk omits per-repo-only flags)."""
    p.add_argument("--homepage", help="Set the homepage URL.")
    p.add_argument("--visibility", choices=["public", "private"])
    if not bulk:
        p.add_argument("--description", help="Set the description.")
        p.add_argument("--rename", help="Rename the repo (new name).")
        p.add_argument("--topics", help="Replace ALL topics (comma-separated).")
    p.add_argument("--add-topic", action="append", default=[], metavar="TOPIC")
    p.add_argument("--remove-topic", action="append", default=[], metavar="TOPIC")
    for flag, dest, _field in _TOGGLE_FLAGS:
        p.add_argument(flag, dest=dest, choices=["on", "off"])
    for flag, dest, _field, choices in _ENUM_FLAGS:
        p.add_argument(flag, dest=dest, choices=choices)


def build_edit_fields(args: argparse.Namespace) -> dict[str, Any]:
    """Map parsed edit/bulk flags to PATCH fields. Pure, testable."""
    fields: dict[str, Any] = {}
    if getattr(args, "description", None) is not None:
        fields["description"] = args.description
    if args.homepage is not None:
        fields["homepage"] = args.homepage
    if getattr(args, "rename", None):
        fields["name"] = args.rename
    if args.visibility:
        fields["visibility"] = args.visibility
    for _flag, dest, field_name in _TOGGLE_FLAGS:
        value = getattr(args, dest)
        if value is not None:
            fields[field_name] = _ONOFF[value]
    for _flag, dest, field_name, _choices in _ENUM_FLAGS:
        value = getattr(args, dest)
        if value is not None:
            fields[field_name] = value
    return fields


def cli_list(client: GitHubClient, detailed: bool, as_json: bool, affiliation: str) -> int:
    repos = _fetch_repos(client, affiliation, quiet=as_json)
    if as_json:
        trimmed = [{k: repo.get(k) for k in _JSON_FIELDS} for repo in repos]
        json.dump(trimmed, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    console = Console()
    table = Table(title=f"GitHub Repositories ({len(repos)})")
    table.add_column("Name", style="bold")
    table.add_column("Vis.")
    table.add_column("Description", overflow="fold")
    table.add_column("Updated")
    if detailed:
        table.add_column("Lang")
        table.add_column("Stars", justify="right")
        table.add_column("Forks", justify="right")
    for repo in repos:
        name = f"📦 {repo['name']}" if repo.get("archived") else repo["name"]
        row = [
            name,
            "🔒" if repo["private"] else "🌐",
            escape(repo.get("description") or ""),
            (repo.get("updated_at") or "")[:10],
        ]
        if detailed:
            row += [
                repo.get("language") or "",
                str(repo.get("stargazers_count", 0)),
                str(repo.get("forks_count", 0)),
            ]
        table.add_row(*row)
    console.print(table)
    return 0


def cli_delete(
    client: GitHubClient,
    full_name: str,
    force: bool,
    backup: bool = False,
    backup_dir: str = ".",
) -> int:
    repo: dict[str, Any] | None = None
    if not force:
        try:
            repo = client.get_repo(full_name)
            for warning in build_delete_warnings(repo, client.get_pinned_repos()):
                print(warning)
        except GitHubError as e:
            print(f"Warning lookup failed: {e}", file=sys.stderr)
        confirm = input(f"Type '{full_name}' to confirm deletion: ").strip()
        if confirm != full_name:
            print("Cancelled.")
            return 1
    if backup:
        if repo is None:
            repo = client.get_repo(full_name)
        path = backup_repo(client, repo, Path(backup_dir))
        print(f"Backed up to {path}")
    ok, msg = client.delete_repo(full_name)
    print(("✅ " if ok else "❌ ") + msg)
    return 0 if ok else 1


def cli_archive(client: GitHubClient, full_name: str, unarchive: bool, force: bool) -> int:
    verb = "unarchive" if unarchive else "archive"
    if not force:
        confirm = input(f"{verb.capitalize()} {full_name}? [y/N] ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Cancelled.")
            return 1
    ok, msg = client.set_archived(full_name, archived=not unarchive)
    print(("✅ " if ok else "❌ ") + msg)
    return 0 if ok else 1


def cli_describe(client: GitHubClient, full_name: str, description: str) -> int:
    ok, msg = client.set_description(full_name, description)
    print(("✅ " if ok else "❌ ") + msg)
    return 0 if ok else 1


def cli_info(client: GitHubClient, full_name: str, as_json: bool) -> int:
    repo = client.get_repo(full_name)
    details = fetch_details(client, repo)
    if as_json:
        json.dump(details_to_dict(details), sys.stdout, indent=2)
        sys.stdout.write("\n")
        for name, hint in sorted(details.hints.items()):
            print(f"note: {name} unavailable — {hint}", file=sys.stderr)
        return 0
    Console().print(render_details(details))
    return 0


def cli_excel(client: GitHubClient, path: str, affiliation: str) -> int:
    repos = _fetch_repos(client, affiliation, quiet=False)
    if not repos:
        print("No repositories returned.", file=sys.stderr)
        return 1
    write_excel(repos, path)
    print(f"Wrote {len(repos)} repos to {path}")
    return 0


def cli_tui(client: GitHubClient) -> int:
    from gman.tui import GitHubRepoApp

    GitHubRepoApp(client).run()
    return 0


def cli_edit(client: GitHubClient, args: argparse.Namespace) -> int:
    full = args.repo_name
    if args.topics is not None and (args.add_topic or args.remove_topic):
        print(
            "Error: --topics cannot be combined with --add-topic/--remove-topic.",
            file=sys.stderr,
        )
        return 2
    fields = build_edit_fields(args)
    wants_topics = args.topics is not None or args.add_topic or args.remove_topic
    if not fields and not wants_topics:
        print(
            "Error: nothing to change — pass at least one flag (see gman edit --help).",
            file=sys.stderr,
        )
        return 2

    all_ok = True
    if fields:
        ok, msg = client.update_repo(full, fields)
        print(("✅ " if ok else "❌ ") + msg)
        all_ok = all_ok and ok

    if wants_topics:
        if args.topics is not None:
            topics, errors = normalize_topics(args.topics)
        else:
            repo = client.get_repo(full)
            topics = list(repo.get("topics") or [])
            added, errors = normalize_topics(",".join(args.add_topic))
            for t in added:
                if t not in topics:
                    topics.append(t)
            removed, rerrs = normalize_topics(",".join(args.remove_topic))
            errors += rerrs
            topics = [t for t in topics if t not in removed]
        if errors:
            for e in errors:
                print(f"Error: {e}", file=sys.stderr)
            return 2
        ok, msg = client.set_topics(full, topics)
        print(("✅ " if ok else "❌ ") + msg)
        all_ok = all_ok and ok

    return 0 if all_ok else 1


def cli_auth(client: GitHubClient, probe: bool) -> int:
    login = client.whoami()  # also captures X-OAuth-Scopes on the first response
    if login is None:
        print("Error: token was rejected by GitHub.", file=sys.stderr)
        return 1
    if probe:
        probe_capabilities(client)

    console = Console()
    info = client.token_info
    console.print(f"[bold]Login:[/bold] {login}")
    console.print(f"[bold]Token source:[/bold] {client.token_source}")
    console.print(f"[bold]Token type:[/bold] {info.kind}")
    if info.scopes is not None:
        console.print(f"[bold]Classic scopes:[/bold] {', '.join(sorted(info.scopes)) or '(none)'}")

    table = Table(title="Feature availability")
    table.add_column("Permission family")
    table.add_column("Enables")
    table.add_column("Status")
    for family in ALL_FAMILIES:
        avail = client.capabilities.resolve(family)
        if avail is True:
            status = "✅ available"
        elif avail is False:
            status = f"❌ unavailable — {client.capabilities.hint(family)}"
        else:
            status = "❓ unknown (try --probe; writes resolve on first use)"
        table.add_row(family, FAMILY_FEATURES[family], status)
    console.print(table)
    if info.kind == "fine-grained":
        console.print(
            "[dim]Fine-grained tokens can't be introspected; "
            "unknowns resolve as features are used.[/dim]"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gman",
        description="List, manage, and export your GitHub repositories.",
    )
    parser.add_argument("--token", "-t", help="GitHub PAT (overrides $GITHUB_TOKEN).")
    parser.add_argument(
        "--api-url",
        help="GitHub API base URL (overrides $GITHUB_API_URL); "
        "e.g. https://ghe.example.com/api/v3 for Enterprise.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="Print repos to stdout.")
    p_list.add_argument("--detailed", "-d", action="store_true")
    p_list.add_argument("--json", dest="as_json", action="store_true", help="Emit JSON to stdout.")
    p_list.add_argument("--affiliation", default="owner", help="API affiliation filter.")
    p_list.add_argument(
        "--include-orgs",
        action="store_true",
        help="Include collaborator and organization repos.",
    )

    p_del = sub.add_parser("delete", help="Delete a repo.")
    p_del.add_argument("repo_name", help="username/repo")
    p_del.add_argument("--force", "-f", action="store_true")
    p_del.add_argument("--backup", action="store_true", help="Download a tarball before deleting.")
    p_del.add_argument("--backup-dir", default=".", help="Directory for the backup tarball.")

    p_arch = sub.add_parser("archive", help="Archive (or unarchive) a repo.")
    p_arch.add_argument("repo_name", help="username/repo")
    p_arch.add_argument("--unarchive", "-u", action="store_true", help="Unarchive instead.")
    p_arch.add_argument("--force", "-f", action="store_true")

    p_desc = sub.add_parser("describe", help="Set a repo's description.")
    p_desc.add_argument("repo_name", help="username/repo")
    p_desc.add_argument("description", help="New description (empty string clears it).")

    p_edit = sub.add_parser("edit", help="Edit repo settings and metadata.")
    p_edit.add_argument("repo_name", help="username/repo")
    _add_field_flags(p_edit, bulk=False)

    p_info = sub.add_parser("info", help="Show detailed info for one repo.")
    p_info.add_argument("repo_name", help="username/repo")
    p_info.add_argument("--json", dest="as_json", action="store_true")

    p_auth = sub.add_parser("auth", help="Show token type and feature availability.")
    p_auth.add_argument(
        "--probe", action="store_true", help="Make cheap read calls to resolve unknowns."
    )

    p_xl = sub.add_parser("excel", help="Export repos to xlsx.")
    p_xl.add_argument("--output", "-o", default=DEFAULT_EXCEL_FILE)
    p_xl.add_argument("--affiliation", default="owner", help="API affiliation filter.")
    p_xl.add_argument("--include-orgs", action="store_true", help="Include org/collab repos.")

    sub.add_parser("tui", help="Launch the interactive Textual TUI.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = GitHubClient(token=args.token, api_url=args.api_url)
    if not client.token:
        print(
            "Error: no GitHub token found. Provide --token, set GITHUB_TOKEN, "
            "or run `gh auth login`.",
            file=sys.stderr,
        )
        return 1

    try:
        if args.command == "list":
            aff = _resolve_affiliation(args.affiliation, args.include_orgs)
            return cli_list(client, args.detailed, args.as_json, aff)
        if args.command == "delete":
            return cli_delete(client, args.repo_name, args.force, args.backup, args.backup_dir)
        if args.command == "archive":
            return cli_archive(client, args.repo_name, args.unarchive, args.force)
        if args.command == "describe":
            return cli_describe(client, args.repo_name, args.description)
        if args.command == "edit":
            return cli_edit(client, args)
        if args.command == "info":
            return cli_info(client, args.repo_name, args.as_json)
        if args.command == "auth":
            return cli_auth(client, args.probe)
        if args.command == "excel":
            aff = _resolve_affiliation(args.affiliation, args.include_orgs)
            return cli_excel(client, args.output, aff)
        if args.command == "tui":
            return cli_tui(client)
    except GitHubError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 1


def tui_main() -> int:
    """Entry point that launches the TUI directly, skipping argparse."""
    client = GitHubClient()
    if not client.token:
        print(
            "Error: no GitHub token found. Set GITHUB_TOKEN or run `gh auth login`.",
            file=sys.stderr,
        )
        return 1
    return cli_tui(client)


if __name__ == "__main__":
    sys.exit(main())
