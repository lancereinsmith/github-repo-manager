# gman

A terminal tool for browsing, exporting, and pruning the GitHub repositories
owned by your authenticated user.

## What it does

- **`list`** — print a Rich-formatted table of your repos to stdout (or JSON
  with `--json`)
- **`excel`** — export every repo to a landscape `.xlsx` (banded rows, frozen
  header, autofilter, sorted by Last Updated descending)
- **`describe`** — set a repo's description from the command line
- **`delete`** — delete a repo by `owner/name` with a confirmation prompt
- **`archive`** — archive (or `--unarchive`) a repo
- **`tui`** — open an interactive Textual table where you can filter, open
  repos in your browser, archive, edit descriptions, export, and delete

## Install

```bash
uv tool install gman     # or: pipx install gman  /  pip install gman
```

Two console scripts are installed:

- `gman` — the full CLI (`gman --help`)
- `gman-tui` — a shortcut that launches the TUI directly

For local development, clone the repo and use [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/lreinsmith/gman
cd gman
uv sync
uv run gman --help
```

## Authentication

Every command needs a GitHub token with `repo` (and, for deletion,
`delete_repo`) scope. The token is resolved in this order:

1. `--token ghp_...` flag
2. `GITHUB_TOKEN` environment variable
3. `gh auth token` from the [GitHub CLI](https://cli.github.com/) (if you've
   run `gh auth login`)

Note: `gh auth login` does not request `delete_repo` by default. To use the
`delete` command with the gh CLI token, add the scope:

```bash
gh auth refresh -h github.com -s delete_repo
```

## GitHub Enterprise

Point `gman` at a GitHub Enterprise Server instance with `--api-url` or the
`GITHUB_API_URL` environment variable:

```bash
gman --api-url https://ghe.example.com/api/v3 list
```

See the [Usage](usage.md) page for command-by-command details, or jump
straight to the [TUI](tui.md) walk-through.
