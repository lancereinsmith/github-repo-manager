# Usage

```bash
gman [--token TOKEN] [--api-url URL] {list,delete,archive,describe,excel,tui} [...]
```

If `--token` is omitted, `GITHUB_TOKEN` is used; failing that, the token
stored by `gh auth login` is used. `--api-url` (or `GITHUB_API_URL`) points
`gman` at a GitHub Enterprise Server instance, e.g.
`https://ghe.example.com/api/v3`.

## `list`

Print a Rich table to stdout, sorted by Last Updated descending.

```bash
gman list
gman list --detailed
gman list --json
gman list --include-orgs
```

- `--detailed` adds Language, Stars, and Forks columns.
- `--json` emits a machine-readable array to stdout (progress is written to
  stderr, so the JSON stays pipeable).
- `--affiliation` sets the raw API filter (default `owner`); `--include-orgs`
  is a shortcut for `owner,collaborator,organization_member`.

## `excel`

Export every repo to an `.xlsx` file.

```bash
gman excel
gman excel --output ~/Desktop/repos.xlsx
gman excel --include-orgs
```

The output file has a header row, banded even rows, frozen pane on row 1,
an autofilter, and landscape page setup that fits to width when printed.
See [Excel export](excel.md) for the full layout.

## `describe`

Set a repo's description. Pass an empty string to clear it.

```bash
gman describe username/project "A short, useful tagline"
gman describe username/project ""
```

## `delete`

Delete a repo by full name. You'll be prompted to retype the name unless
`--force` is supplied.

```bash
gman delete username/old-project
gman delete username/old-project --force
```

!!! warning
    Deletion is permanent. Even with `--force` there is no recycle bin.

!!! note "Token scope: `delete_repo`"
    Deletion requires the `delete_repo` scope, which `gh auth login` does
    **not** request by default. If GitHub returns "Must have admin rights
    to Repository", run `gh auth refresh -h github.com -s delete_repo`.
    A PAT in `GITHUB_TOKEN` must likewise be issued with `delete_repo`.

## `archive`

Archive (or unarchive) a repo. A `y/N` confirmation is shown unless
`--force` is supplied. Archive is reversible — pass `--unarchive` to
flip a repo back.

```bash
gman archive username/old-project
gman archive username/old-project --unarchive
gman archive username/old-project --force
```

## `tui`

Launch the interactive Textual UI (`gman-tui` is a shortcut for this).

```bash
gman tui
```

See the [TUI](tui.md) page for keybindings.
