# TUI

The TUI is a Textual app showing a sortable, zebra-striped `DataTable` of
your repos.

## Layout

- **Header** — app title and a sub-title showing `username — visible/total`
  plus the current filter, if any
- **Table** — six columns: Name, Visibility (🔒/🌐), Description, Lang,
  Stars, Updated
- **Footer** — keybinding hints

## Keybindings

| Key | Action |
| --- | --- |
| `q` | Quit |
| `r` | Refresh from GitHub |
| `e` | Export the current list to `github_repos.xlsx` |
| `o` | Open the selected repo in your browser |
| `a` | Toggle archive state of the selected repo |
| `d` | Delete the selected repo (modal asks you to retype the full name) |
| `/` | Open a filter prompt (substring match on name and description) |

The filter is purely client-side; it narrows what's shown but does not
re-query GitHub.

## Modals

### Delete confirmation

A red-bordered modal shows the repo's full name and an `Input`. The
deletion only proceeds if the value you type matches exactly. `Esc`
cancels.

!!! note "Token scope: `delete_repo`"
    If a delete fails with "Must have admin rights to Repository", your
    token is missing the `delete_repo` scope. For `gh auth login` users:

    ```bash
    gh auth refresh -h github.com -s delete_repo
    ```

    A PAT in `GITHUB_TOKEN` must likewise be issued with `delete_repo`.

### Filter

A simple text input. Submit empty to clear the filter; `Esc` keeps the
previous value.
