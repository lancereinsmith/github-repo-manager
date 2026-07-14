# TUI

The TUI is a Textual app showing a sortable, zebra-striped `DataTable` of
your repos.

## Layout

- **Header** — app title and a sub-title showing `username — visible/total`
  plus the current filter, if any
- **Table** — eight columns: ✓ (selection), Name, Vis. (🔒/🌐), Description, Lang,
  Stars, Open (open issues + PRs), Updated
- **Footer** — keybinding hints

## Keybindings

| Key | Action |
| --- | --- |
| `q` | Quit |
| `r` | Refresh from GitHub |
| `e` | Export the current list to `github_repos.xlsx` |
| `x` | Open `github_repos.xlsx` in your default spreadsheet app |
| `o` | Open the selected repo in your browser |
| `i` / `Enter` | Open the detail panel (languages, release, CI, traffic, …) |
| `a` | Archive the selected repo, or unarchive it if already archived |
| `c` | Change the description of the selected repo |
| `t` | Edit the selected repo's topics |
| `h` | Edit the selected repo's homepage URL |
| `space` | Select/deselect the current repo (for bulk actions) |
| `ctrl+a` | Select all visible repos (again to deselect) |
| `b` | Bulk-action menu for the selected repos |
| `d` | Delete the selected repo (modal asks you to retype the full name) |
| `v` (in detail panel) | View the rendered README |
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
    token is missing the `delete_repo` scope. For `gh auth login` users,
    run `gh auth refresh -h github.com -s delete_repo`. A PAT in
    `GITHUB_TOKEN` must likewise be issued with `delete_repo`.

### Filter

A simple text input. Submit empty to clear the filter; `Esc` keeps the
previous value.

### Edit description

A text input pre-populated with the current description. Submit to send
the new value to GitHub via PATCH; submit empty to clear the description.
`Esc` cancels without making a request.

### Detail panel

`Enter` or `i` opens a lazy-loaded panel for the selected repo. Each row is
fetched independently — fields your token can't access show `—` with a hint
instead of failing. Results are cached until the repo changes or you refresh.

### Delete confirmation extras

The delete modal lists safety warnings (forks, stars, public, pinned) and has
a "Backup tarball first" checkbox. If the backup download fails, the deletion
is aborted.

### Bulk actions

`space` marks repos (✓ column); the subtitle shows the count. `b` opens the
bulk menu — archive/unarchive, feature toggles, delete-branch-on-merge,
add/remove a topic, and Dependabot alert/fix toggles. A confirmation screen
shows the operation and target list (`y` to proceed). Operations run one repo
at a time; the subtitle tracks progress and a notification summarizes
ok/failed/skipped. The list refreshes when done.
