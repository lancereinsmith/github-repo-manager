# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `info` command and TUI detail panel (`i`/Enter): languages, latest release,
  CI status, Pages URL, 14-day traffic, open issue/PR split — each field
  degrades gracefully when the token lacks its permission.
- `auth` command showing token type, classic scopes, and per-feature
  availability (`--probe` resolves unknowns for fine-grained tokens).
- Deletion safety net: warnings for forks/stars/public/pinned repos, README
  viewer in the TUI, and `delete --backup` / a backup checkbox that downloads
  a tarball first and aborts deletion if the download fails.
- Capability model: classic-token scope introspection and fine-grained-token
  403 learning power graceful degradation everywhere.
- `Open` column (open issues + PRs) and 📌 pinned badges in the TUI table.
- New docs page: *Choosing a token* with least-privilege PAT recipes.
- `edit` command: homepage, rename, visibility, feature toggles,
  delete-branch-on-merge, merge-strategy defaults, and topics
  (`--topics` / `--add-topic` / `--remove-topic`) in one call.
- `bulk` command and TUI multi-select (`space`, `ctrl+a`, `b` menu): apply
  settings, archive/unarchive, topics, and Dependabot toggles to many repos
  sequentially, with dry-run and confirmation.
- TUI `t` (topics) and `h` (homepage) editors.

## [0.1.0] - 2026-07-14

Initial release.

### Added

- `list` command with a Rich-formatted table and `--json` for machine-readable
  output.
- `excel` command exporting every repo to a landscape `.xlsx` (banded rows,
  frozen header, autofilter, sorted by Last Updated descending).
- `describe` command to set a repository's description.
- `delete` command to remove a repo by `owner/name` with a confirmation prompt.
- `archive` command (with `--unarchive`) to toggle a repo's archived state.
- `tui` command: an interactive Textual table with filter, open-in-browser,
  archive, edit-description, delete, and Excel export.
- `--affiliation` and `--include-orgs` flags on `list` and `excel` to include
  collaborator and organization repositories.
- `--api-url` flag and `GITHUB_API_URL` environment variable for GitHub
  Enterprise Server support.
- Progress spinner while paginating repositories.
- Automatic retries for transient (5xx / network) failures and a clear
  `RateLimitError` when the API rate limit is exhausted.
- Supports Python 3.10 and newer.

### Security

- Excel export escapes cell values that begin with a formula character
  (`= + - @`), preventing spreadsheet formula injection from repo metadata.
