# TUI: Edit Repo Description

## Goal

Add a TUI action that edits the description of the selected repository on GitHub, mirroring the existing patterns for `set_archived` (client) and `FilterScreen` (modal).

## User flow

1. User selects a row in the `DataTable`.
2. User presses `c` ("Change description").
3. A modal opens with an `Input` pre-populated with the current description.
4. On submit, the new value is sent to GitHub via PATCH `/repos/{owner}/{repo}`.
5. On success, the in-memory repo dict is mutated, the table is refreshed, and a notification is shown.
6. Pressing `Esc` cancels with no API call.

Empty submission is allowed — it clears the description on GitHub.

## Components

### `GitHubClient.set_description` (client.py)

```python
def set_description(self, full_name: str, description: str) -> tuple[bool, str]:
    r = self.session.patch(
        f"{GITHUB_API}/repos/{full_name}",
        json={"description": description},
        timeout=30,
    )
    if r.status_code == 200:
        return True, f"Updated description for {full_name}"
    return False, f"HTTP {r.status_code}: {r.text[:160]}"
```

Mirrors `set_archived` exactly.

### `EditDescriptionScreen` (tui.py)

A `ModalScreen[str | None]` mirroring `FilterScreen`:
- Pre-populates `Input` with the current description.
- Submit dismisses with the new string (may be empty).
- `Esc` dismisses with `None` (cancel).

### `action_edit_description` (tui.py)

- Resolves the selected repo (no-op if none).
- Pushes `EditDescriptionScreen`.
- On callback: if `None`, do nothing (cancel); otherwise call `client.set_description`. On success, mutate `repo["description"]` in place and call `refresh_table()`. On failure, show an error notification.

### Binding

Add `Binding("c", "edit_description", "Change desc")` to `BINDINGS`.

## Docs

Add the `c` row to the keybindings table in `docs/tui.md`, and a short "Edit description" subsection under "Modals".

## Out of scope

- No CLI subcommand for description editing in this spec (could be added later if useful).
- No multi-line description editor — single-line `Input` matches the existing `FilterScreen` UX, and GitHub descriptions are single-line strings anyway.
- No optimistic-update rollback on failure — consistent with how `toggle_archive` handles failure (notify only, in-memory state is only updated on success).
