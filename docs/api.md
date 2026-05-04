# Python API

The package re-exports two top-level objects:

```python
from github_repo_manager import GitHubClient, write_excel
```

## `GitHubClient`

A thin wrapper around the GitHub REST API for the authenticated user.

```python
client = GitHubClient(token="ghp_...")   # falls back to $GITHUB_TOKEN, then `gh auth token`
client.whoami()                           # -> "username" or None
repos = client.list_repos()               # list[dict]
ok, message = client.delete_repo("username/repo")
ok, message = client.set_archived("username/repo", archived=True)
```

`list_repos(include_archived=True)` pages through `/user/repos` 100 at a
time with `affiliation=owner` and returns the raw API objects sorted by
`updated_at` descending, with archived repos pushed to the end. Pass
`include_archived=False` to drop archived repos.

`delete_repo` and `set_archived` both return a `(bool, str)` tuple —
useful for surfacing the HTTP error text if the call fails.

## `write_excel`

```python
write_excel(repos, "github_repos.xlsx")
```

Takes a list of repo dicts (the shape returned by `list_repos`) and writes
the formatted spreadsheet described on the [Excel export](excel.md) page.
