# GitHub Repo Manager

A terminal tool for browsing, exporting, and pruning the GitHub repositories
owned by your authenticated user.

## What it does

- **`list`** — print a Rich-formatted table of your repos to stdout
- **`excel`** — export every repo to a landscape `.xlsx` (banded rows, frozen
  header, autofilter, sorted by Last Updated descending)
- **`delete`** — delete a repo by `owner/name` with a confirmation prompt
- **`tui`** — open an interactive Textual table where you can filter, open
  repos in your browser, export, and delete

## Install

The project uses [uv](https://docs.astral.sh/uv/) for everything.

```bash
git clone <repo-url> github-repo-manager
cd github-repo-manager
uv sync
```

A console script `github-repo-manager` (and the shorter alias `grm`) is
installed into the project venv:

```bash
uv run github-repo-manager --help
uv run grm tui
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

See the [Usage](usage.md) page for command-by-command details, or jump
straight to the [TUI](tui.md) walk-through.
