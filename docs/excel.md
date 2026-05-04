# Excel export

The export is intentionally simple — four columns, banded rows, optimised
for landscape printing.

## Columns

| # | Header | Source field |
| - | --- | --- |
| 1 | Repository | `name` |
| 2 | Description | `description` |
| 3 | Visibility | `visibility` (capitalised) |
| 4 | Last Updated | `updated_at`, parsed as a real datetime |

Rows are sorted by Last Updated descending — the same default the GitHub
API gives back when querying `/user/repos?sort=updated&direction=desc`.

## Formatting

- Header row: white text on dark blue (`#305496`), bold
- Even rows: light gray fill (`#F2F2F2`)
- Description column has wrap-text enabled
- `Last Updated` cells are real datetimes formatted `yyyy-mm-dd hh:mm`
- Header pane is frozen and an autofilter is applied to the table

## Page setup

- Orientation: **landscape**
- Fit-to-width: 1 page wide, unlimited pages tall
- Gridlines off, repeating header row when printed
- 0.4″ left/right and 0.5″ top/bottom margins

## Programmatic use

```python
from github_repo_manager import GitHubClient, write_excel

client = GitHubClient()  # reads GITHUB_TOKEN
write_excel(client.list_repos(), "repos.xlsx")
```
