# Usage

```bash
gman [--token TOKEN] [--api-url URL] {list,delete,archive,describe,edit,bulk,sync,actions,new,info,auth,excel,tui} [...]
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

## `info`

Show a detail panel for one repo: languages, latest release, CI status,
Pages URL, 14-day traffic, and the open issue/PR split.

```bash
gman info username/project
gman info username/project --json   # hints about unavailable fields go to stderr
```

Fields the token can't see render as `—` with a hint (see
[Choosing a token](tokens.md)).

## `auth`

Show what gman knows about your token: source, type, classic scopes, and a
feature-availability table.

```bash
gman auth
gman auth --probe   # resolve unknowns with one cheap read per permission family
```

## `edit`

Change settings and metadata on one repo — all field flags are combined into
a single API call (topics go through their own endpoint).

```bash
gman edit username/project --homepage https://example.com --wiki off
gman edit username/project --rename new-name --visibility private
gman edit username/project --topics python,cli        # replace all topics
gman edit username/project --add-topic tui --remove-topic wip
gman edit username/project --delete-branch-on-merge on --allow-rebase off
```

Flags: `--description`, `--homepage`, `--rename`, `--visibility
{public,private}`, `--topics` (replace) or repeatable
`--add-topic`/`--remove-topic`, `--wiki/--issues/--projects {on,off}`,
`--delete-branch-on-merge {on,off}`,
`--allow-squash/--allow-merge-commit/--allow-rebase/--allow-update-branch
{on,off}`, and the squash/merge commit title/message defaults
(`--squash-commit-title` …). All writes need `Administration: write`
(fine-grained) or the `repo` scope (classic) — see
[Choosing a token](tokens.md).

## `bulk`

Apply the same change to many repos. Targets come from positional names,
`--filter SUBSTR` (name/description substring), or `--all` — exactly one.

```bash
gman bulk --all --delete-branch-on-merge on --dry-run   # list what would change
gman bulk --filter experiment --archive --yes
gman bulk o/r1 o/r2 --add-topic archived-candidate
gman bulk --all --vulnerability-alerts on
```

Bulk-only flags: `--archive`/`--unarchive`, `--vulnerability-alerts {on,off}`,
`--security-fixes {on,off}`, `--sync-fork`, `--clear-artifacts`, `--clear-caches`.
`--rename`, `--description`, and `--topics` (replace-all) are deliberately not available in bulk.

The command lists the operations and targets, then asks `Proceed? [y/N]`
unless `--yes`. `--dry-run` stops after the listing. Writes run one repo at a
time (GitHub throttles concurrent writes); a rate-limit abort marks the
remainder `⏭ skipped`. Exit code is 0 only if every operation succeeded.

## `sync`

Sync a fork with its upstream (the same as GitHub's "Sync fork" button).

```bash
gman sync username/my-fork
gman sync username/my-fork --branch release
```

Defaults to the repo's default branch. A merge conflict returns an error —
resolve it locally. Bulk variant: `gman bulk --all --sync-fork` (non-forks are
skipped). Needs `Contents: write` (fine-grained) or `repo` scope (classic).

## `actions`

Manage GitHub Actions artifacts, caches, and workflow runs. With no flags,
shows the 5 most recent runs, artifact count and total size, and cache count
and total size. Pass one action flag to modify them.

```bash
gman actions username/repo
gman actions username/repo --clear-artifacts
gman actions username/repo --clear-artifacts --older-than 30
gman actions username/repo --clear-caches
gman actions username/repo --rerun RUN_ID
gman actions username/repo --rerun RUN_ID --failed-only
gman actions username/repo --cancel RUN_ID
```

Flags:
- `--clear-artifacts` removes all artifacts (optionally filtered by age).
- `--older-than DAYS` limits `--clear-artifacts` to artifacts older than N days.
- `--clear-caches` removes all caches.
- `--rerun RUN_ID` reruns a workflow run by ID; `--failed-only` reruns only
  failed jobs.
- `--cancel RUN_ID` cancels a workflow run by ID.

Exit code is 0 only if the operation succeeded. Bulk variant:
`gman bulk --all --clear-artifacts` and `gman bulk --all --clear-caches`.
Needs `Actions: write` (fine-grained) — see [Choosing a token](tokens.md).

## `new`

Create a new repository. Choose between direct creation or cloning from a
template repo. The `--list-gitignores` and `--list-licenses` flags list
available templates.

```bash
gman new my-repo
gman new my-repo --private --description "A short description"
gman new my-repo --auto-init --gitignore Python --license MIT
gman new my-repo --template owner/template-repo
gman new my-repo --template owner/template-repo --private
gman new --list-gitignores
gman new --list-licenses
```

**Direct creation** (default):
- `--private` makes the repo private.
- `--description TEXT` sets the description.
- `--homepage URL` sets the homepage URL.
- `--auto-init` initializes with a README.
- `--gitignore TEMPLATE` applies a `.gitignore` template (run
  `gman new --list-gitignores` to see available templates).
- `--license TEMPLATE` applies a license template (run
  `gman new --list-licenses` to see available).

**Template mode** (pass `--template owner/repo`):
- `--private` makes the repo private.
- `--description TEXT` sets the description.
- `--include-all-branches` includes all branches from the template.
- Cannot use `--auto-init`, `--gitignore`, `--license`, or `--homepage`.

After successful creation, a clone hint is printed. Needs `repo` scope
(classic) or fine-grained token with all necessary repo permissions. The
template/license pickers (`--list-gitignores`, `--list-licenses`) require no
special permissions.

## `delete`

Delete a repo by full name. You'll be prompted to retype the name unless
`--force` is supplied.

```bash
gman delete username/old-project
gman delete username/old-project --force
```

`--backup` downloads a `{name}-{branch}.tar.gz` snapshot (git contents only — no
issues/wiki/releases) before deleting; if the download fails, the deletion is
aborted. `--backup-dir` chooses where it lands (default: current directory).

```bash
gman delete username/old-project --backup --backup-dir ~/Backups
```

Before the confirmation prompt, gman warns if the repo has forks or stars, is
public, or is pinned on your profile.

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
