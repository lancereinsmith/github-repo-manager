# Choosing a token

gman works with any GitHub token and **degrades gracefully**: features the
token can't perform hide themselves (TUI) or explain what's missing (CLI).
Run `gman auth` to see what your current token can do.

## Fine-grained PAT recipes (recommended for least privilege)

Create at <https://github.com/settings/personal-access-tokens/new>, choose
repository access (all repos or selected), and grant one of these permission
sets:

| Tier | Permissions | What works |
| --- | --- | --- |
| Read-only inventory | Metadata: read (automatic) + Contents: read | list, excel, info (partial), README preview, backup download |
| Dashboard | + Actions: read, Pages: read, Pull requests: read, Administration: read | full detail panel incl. CI status, Pages, traffic, issue/PR split |
| Manager | + Administration: write | archive, describe, **delete** — fine-grained tokens bundle delete under Administration: write |

Fine-grained tokens cannot be introspected (GitHub sends no scope header), so
`gman auth` shows `unknown` until a feature is used or you run
`gman auth --probe`.

## Classic PATs and the gh CLI

Classic tokens announce their scopes, so `gman auth` reports availability
immediately.

- `repo` scope covers every read feature and all writes **except delete**.
- `delete_repo` is a separate scope required for `gman delete`.
- `gh auth token` (gman's fallback) is always a classic token with
  `repo, read:org, gist` — add delete with
  `gh auth refresh -h github.com -s delete_repo`.

## Known gaps

Repo **transfer** and the **notifications** API do not work with fine-grained
tokens at all (GitHub limitation) — they are not part of gman today.
Traffic stats additionally require push access to the repo.
