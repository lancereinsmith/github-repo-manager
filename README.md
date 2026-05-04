# github-repo-manager

List, manage, and export your GitHub repositories from the terminal.

- **CLI** — `list`, `delete`, `excel` subcommands
- **TUI** — interactive [Textual](https://textual.textualize.io/) table with filter, open-in-browser, delete, and Excel export
- **Excel export** — landscape `.xlsx` with banded rows, frozen header, and autofilter, sorted by Last Updated descending

## Quick start

```bash
uv sync
gh auth login                        # or: export GITHUB_TOKEN=ghp_xxx
uv run github-repo-manager tui       # or: list, excel, delete username/repo
```

The token is resolved from `--token`, then `$GITHUB_TOKEN`, then
`gh auth token`. For `delete`, the gh CLI token needs the extra
`delete_repo` scope: `gh auth refresh -h github.com -s delete_repo`.

See the [docs](docs/index.md) for full usage and configuration.

## Development

```bash
uv sync
uv run ruff check .
uv run ty check
uv run zensical serve
```
