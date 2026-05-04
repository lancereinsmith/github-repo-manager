"""Command-line entry point: `list`, `delete`, `excel`, `tui`."""

from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.table import Table

from github_repo_manager.client import GitHubClient
from github_repo_manager.excel import DEFAULT_EXCEL_FILE, write_excel


def cli_list(client: GitHubClient, detailed: bool) -> int:
    console = Console()
    repos = client.list_repos()
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


def cli_excel(client: GitHubClient, path: str) -> int:
    repos = client.list_repos()
    if not repos:
        print("No repositories returned.", file=sys.stderr)
        return 1
    write_excel(repos, path)
    print(f"Wrote {len(repos)} repos to {path}")
    return 0


def cli_tui(client: GitHubClient) -> int:
    from github_repo_manager.tui import GitHubRepoApp

    GitHubRepoApp(client).run()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="github-repo-manager",
        description="List, manage, and export your GitHub repositories.",
    )
    parser.add_argument("--token", "-t", help="GitHub PAT (overrides $GITHUB_TOKEN).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="Print repos to stdout.")
    p_list.add_argument("--detailed", "-d", action="store_true")

    p_del = sub.add_parser("delete", help="Delete a repo.")
    p_del.add_argument("repo_name", help="username/repo")
    p_del.add_argument("--force", "-f", action="store_true")

    p_xl = sub.add_parser("excel", help="Export repos to xlsx.")
    p_xl.add_argument("--output", "-o", default=DEFAULT_EXCEL_FILE)

    sub.add_parser("tui", help="Launch the interactive Textual TUI.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = GitHubClient(token=args.token)
    if not client.token:
        print(
            "Error: no GitHub token found. Provide --token, set GITHUB_TOKEN, "
            "or run `gh auth login`.",
            file=sys.stderr,
        )
        return 1

    if args.command == "list":
        return cli_list(client, args.detailed)
    if args.command == "delete":
        return cli_delete(client, args.repo_name, args.force)
    if args.command == "excel":
        return cli_excel(client, args.output)
    if args.command == "tui":
        return cli_tui(client)
    return 1


if __name__ == "__main__":
    sys.exit(main())
