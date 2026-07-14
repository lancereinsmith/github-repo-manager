"""Command-line entry point: `list`, `delete`, `archive`, `describe`, `excel`, `tui`."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from rich.console import Console
from rich.table import Table

from gman.client import GitHubClient, GitHubError
from gman.details import details_to_dict, fetch_details, render_details
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
            repo.get("description") or "",
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


def cli_delete(client: GitHubClient, full_name: str, force: bool) -> int:
    if not force:
        confirm = input(f"Type '{full_name}' to confirm deletion: ").strip()
        if confirm != full_name:
            print("Cancelled.")
            return 1
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

    p_arch = sub.add_parser("archive", help="Archive (or unarchive) a repo.")
    p_arch.add_argument("repo_name", help="username/repo")
    p_arch.add_argument("--unarchive", "-u", action="store_true", help="Unarchive instead.")
    p_arch.add_argument("--force", "-f", action="store_true")

    p_desc = sub.add_parser("describe", help="Set a repo's description.")
    p_desc.add_argument("repo_name", help="username/repo")
    p_desc.add_argument("description", help="New description (empty string clears it).")

    p_info = sub.add_parser("info", help="Show detailed info for one repo.")
    p_info.add_argument("repo_name", help="username/repo")
    p_info.add_argument("--json", dest="as_json", action="store_true")

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
            return cli_delete(client, args.repo_name, args.force)
        if args.command == "archive":
            return cli_archive(client, args.repo_name, args.unarchive, args.force)
        if args.command == "describe":
            return cli_describe(client, args.repo_name, args.description)
        if args.command == "info":
            return cli_info(client, args.repo_name, args.as_json)
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
