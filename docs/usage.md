# Usage

```bash
github-repo-manager [--token TOKEN] {list,delete,excel,tui} [...]
```

If `--token` is omitted, the value of `GITHUB_TOKEN` is used.

## `list`

Print a Rich table to stdout, sorted by Last Updated descending.

```bash
github-repo-manager list
github-repo-manager list --detailed
```

`--detailed` adds Language, Stars, and Forks columns.

## `excel`

Export every repo to an `.xlsx` file.

```bash
github-repo-manager excel
github-repo-manager excel --output ~/Desktop/repos.xlsx
```

The output file has a header row, banded even rows, frozen pane on row 1,
an autofilter, and landscape page setup that fits to width when printed.
See [Excel export](excel.md) for the full layout.

## `delete`

Delete a repo by full name. You'll be prompted to retype the name unless
`--force` is supplied.

```bash
github-repo-manager delete username/old-project
github-repo-manager delete username/old-project --force
```

!!! warning
    Deletion is permanent. Even with `--force` there is no recycle bin.

## `tui`

Launch the interactive Textual UI.

```bash
github-repo-manager tui
```

See the [TUI](tui.md) page for keybindings.
