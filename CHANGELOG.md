# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `describe` CLI subcommand to set a repository's description.
- `list --json` for machine-readable output.
- `--affiliation` and `--include-orgs` flags on `list` and `excel` to include
  collaborator and organization repositories.
- `--api-url` flag and `GITHUB_API_URL` environment variable for GitHub
  Enterprise Server support.
- Progress spinner while paginating repositories.
- Automatic retries for transient (5xx / network) failures and a clear
  `RateLimitError` when the API rate limit is exhausted.

### Changed

- Renamed the distribution and import package to `gman`.
- Lowered the supported Python floor to 3.10.

### Security

- Excel export now escapes cell values that begin with a formula character
  (`= + - @`), preventing spreadsheet formula injection from repo metadata.

## [0.1.0]

- Initial release: `list`, `delete`, `archive`, `excel`, and `tui` commands.
