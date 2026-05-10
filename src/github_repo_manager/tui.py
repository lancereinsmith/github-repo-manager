"""Textual TUI for browsing and managing repos."""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any, ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Label

from github_repo_manager.client import GitHubClient
from github_repo_manager.excel import DEFAULT_EXCEL_FILE, write_excel


class ConfirmDeleteScreen(ModalScreen[bool]):
    """Modal that requires the user to retype the full name to confirm."""

    DEFAULT_CSS = """
    ConfirmDeleteScreen { align: center middle; }
    #dialog {
        width: 70; height: auto;
        border: thick $error;
        background: $surface;
        padding: 1 2;
    }
    #title { color: $error; text-style: bold; }
    #hint  { color: $text-muted; margin-bottom: 1; }
    """

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, full_name: str) -> None:
        super().__init__()
        self.full_name = full_name

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(f"Delete {self.full_name}?", id="title")
            yield Label("Type the full name to confirm (esc to cancel):", id="hint")
            yield Input(placeholder=self.full_name, id="confirm")

    @on(Input.Submitted)
    def _submit(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() == self.full_name)

    def action_cancel(self) -> None:
        self.dismiss(False)


class FilterScreen(ModalScreen[str]):
    """Modal for entering a substring filter applied to name + description."""

    DEFAULT_CSS = """
    FilterScreen { align: center middle; }
    #fdialog {
        width: 60; height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, current: str = "") -> None:
        super().__init__()
        self.current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="fdialog"):
            yield Label("Filter (substring of name/description; empty to clear):")
            yield Input(value=self.current, id="filt")

    @on(Input.Submitted)
    def _submit(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def action_cancel(self) -> None:
        self.dismiss(self.current)


class EditDescriptionScreen(ModalScreen[str | None]):
    """Modal for editing the description of a repo. Returns `None` if cancelled."""

    DEFAULT_CSS = """
    EditDescriptionScreen { align: center middle; }
    #edialog {
        width: 80; height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, full_name: str, current: str = "") -> None:
        super().__init__()
        self.full_name = full_name
        self.current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="edialog"):
            yield Label(f"Edit description for {self.full_name} (esc to cancel):")
            yield Input(value=self.current, id="desc")

    @on(Input.Submitted)
    def _submit(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class GitHubRepoApp(App[None]):
    """Interactive table of the user's repos with delete/export actions."""

    CSS = "DataTable { height: 1fr; }"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("e", "export_excel", "Excel"),
        Binding("x", "open_excel", "Open xlsx"),
        Binding("o", "open_browser", "Open"),
        Binding("a", "toggle_archive", "Archive/Unarchive"),
        Binding("c", "edit_description", "Change desc"),
        Binding("d", "delete_repo", "Delete"),
        Binding("slash", "filter", "Filter"),
    ]

    def __init__(self, client: GitHubClient) -> None:
        super().__init__()
        self.client = client
        self.all_repos: list[dict[str, Any]] = []
        self.filter_text: str = ""
        self.username: str = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield DataTable(zebra_stripes=True, cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "GitHub Repos"
        self.sub_title = "loading…"
        table = self.query_one(DataTable)
        table.add_columns("Name", "Vis.", "Description", "Lang", "Stars", "Updated")
        self.load_repos()

    @work(thread=True, exclusive=True)
    def load_repos(self) -> None:
        try:
            username = self.client.whoami() or ""
            repos = self.client.list_repos()
        except Exception as e:
            self.call_from_thread(self.notify, f"Failed to load: {e}", severity="error")
            return
        self.call_from_thread(self._on_loaded, username, repos)

    def _on_loaded(self, username: str, repos: list[dict[str, Any]]) -> None:
        self.username = username
        self.all_repos = repos
        self.refresh_table()

    def refresh_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        ft = self.filter_text.lower()
        visible = [
            r
            for r in self.all_repos
            if not ft
            or ft in (r.get("name") or "").lower()
            or ft in (r.get("description") or "").lower()
        ]
        for repo in visible:
            desc = (repo.get("description") or "").replace("\n", " ")
            if len(desc) > 80:
                desc = desc[:77] + "…"
            vis = "🔒" if repo["private"] else "🌐"
            if repo.get("archived"):
                vis += "❌"
            table.add_row(
                repo["name"],
                vis,
                desc,
                repo.get("language") or "",
                str(repo.get("stargazers_count", 0)),
                (repo.get("updated_at") or "")[:10],
                key=repo["full_name"],
            )
        suffix = f" — filter: {self.filter_text!r}" if self.filter_text else ""
        self.sub_title = f"{self.username} — {len(visible)}/{len(self.all_repos)}{suffix}"

    def _selected_repo(self) -> dict[str, Any] | None:
        table = self.query_one(DataTable)
        if table.row_count == 0:
            return None
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        except Exception:
            return None
        for r in self.all_repos:
            if r["full_name"] == row_key:
                return r
        return None

    def action_refresh(self) -> None:
        self.sub_title = "loading…"
        self.load_repos()

    def action_export_excel(self) -> None:
        try:
            write_excel(self.all_repos, DEFAULT_EXCEL_FILE)
            self.notify(f"Wrote {len(self.all_repos)} repos to {DEFAULT_EXCEL_FILE}")
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")

    def action_open_browser(self) -> None:
        repo = self._selected_repo()
        if repo and repo.get("html_url"):
            webbrowser.open(repo["html_url"])
            self.notify(f"Opened {repo['full_name']}")

    def action_open_excel(self) -> None:
        path = Path(DEFAULT_EXCEL_FILE).resolve()
        if not path.is_file():
            self.notify(f"No spreadsheet at {path} — press 'e' to export first.", severity="warning")
            return
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=True)
            elif sys.platform == "win32":
                os.startfile(str(path))
            else:
                subprocess.run(["xdg-open", str(path)], check=True)
        except (OSError, subprocess.CalledProcessError) as e:
            self.notify(f"Open failed: {e}", severity="error")
            return
        self.notify(f"Opened {path.name}")

    def action_delete_repo(self) -> None:
        repo = self._selected_repo()
        if not repo:
            return
        full = repo["full_name"]

        def after(confirmed: bool | None) -> None:
            if not confirmed:
                self.notify("Cancelled")
                return
            ok, msg = self.client.delete_repo(full)
            if ok:
                self.all_repos = [r for r in self.all_repos if r["full_name"] != full]
                self.refresh_table()
                self.notify(msg, severity="warning")
            else:
                self.notify(f"Delete failed: {msg}", severity="error")

        self.push_screen(ConfirmDeleteScreen(full), after)

    def action_toggle_archive(self) -> None:
        repo = self._selected_repo()
        if not repo:
            return
        archived = bool(repo.get("archived"))
        target = not archived
        ok, msg = self.client.set_archived(repo["full_name"], archived=target)
        if not ok:
            self.notify(f"Archive failed: {msg}", severity="error")
            return
        repo["archived"] = target
        self.all_repos.sort(key=lambda r: bool(r.get("archived")))
        self.refresh_table()
        self.notify(msg, severity="warning")

    def action_filter(self) -> None:
        def after(text: str | None) -> None:
            self.filter_text = text or ""
            self.refresh_table()

        self.push_screen(FilterScreen(self.filter_text), after)

    def action_edit_description(self) -> None:
        repo = self._selected_repo()
        if not repo:
            return
        full = repo["full_name"]
        current = repo.get("description") or ""

        def after(new_desc: str | None) -> None:
            if new_desc is None:
                self.notify("Cancelled")
                return
            ok, msg = self.client.set_description(full, new_desc)
            if not ok:
                self.notify(f"Update failed: {msg}", severity="error")
                return
            repo["description"] = new_desc
            self.refresh_table()
            self.notify(msg)

        self.push_screen(EditDescriptionScreen(full, current), after)
