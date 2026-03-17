"""Textual TUI for github-scrape."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Container, Horizontal, Middle, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    LoadingIndicator,
    Static,
    Tree,
)
from textual.widgets.tree import TreeNode

from github_scrape.api import (
    AuthError,
    GitHubAPIError,
    GitHubClient,
    NotFoundError,
    RateLimitError,
    RepoFile,
    RepoTree,
)
from github_scrape.config import get_download_path, get_token, mask_token
from github_scrape.downloader import DownloadResult, Downloader
from github_scrape.utils import parse_github_url

# ASCII art for the title
TITLE_ART = """[bold #58a6ff]

 ██████╗ ██╗████████╗██╗  ██╗██╗   ██╗██████╗     ███████╗ ██████╗██████╗  █████╗ ██████╗ ███████╗
██╔════╝ ██║╚══██╔══╝██║  ██║██║   ██║██╔══██╗    ██╔════╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██╔════╝
██║  ███╗██║   ██║   ███████║██║   ██║██████╔╝    ███████╗██║     ██████╔╝███████║██████╔╝█████╗  
██║   ██║██║   ██║   ██╔══██║██║   ██║██╔══██╗    ╚════██║██║     ██╔══██╗██╔══██║██╔═══╝ ██╔══╝  
╚██████╔╝██║   ██║   ██║  ██║╚██████╔╝██████╔╝    ███████║╚██████╗██║  ██║██║  ██║██║     ███████╗
 ╚═════╝ ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝     ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝
[/bold #58a6ff]"""


# ─── Data attached to tree nodes ─────────────────────────────
@dataclass
class FileNodeData:
    """Data stored in each tree node."""

    repo_file: RepoFile
    selected: bool = False


# ─── Home Screen ─────────────────────────────────────────────
class HomeScreen(Screen[str]):
    """Landing screen — centered ASCII art + URL input."""

    BINDINGS = [
        Binding("escape", "quit_app", "Quit", show=True),
        Binding("q", "quit_app", "Quit", show=False),
        Binding("ctrl+q", "quit_app", "Quit", show=False),
    ]

    CSS = """
    HomeScreen {
        align: center middle;
        background: $surface;
    }

    #home-wrapper {
        width: 100%;
        height: 100%;
        align: center middle;
    }

    #home-content {
        width: auto;
        height: auto;
        align: center middle;
        content-align: center middle;
    }

    #ascii-art {
        width: auto;
        height: auto;
        text-align: center;
        content-align: center middle;
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }

    #tagline {
        width: auto;
        text-align: center;
        content-align: center middle;
        color: $text-muted;
        margin-bottom: 1;
    }

    #input-section {
        width: auto;
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    #url-prompt {
        text-align: center;
        content-align: center middle;
        color: $text;
        text-style: bold;
        margin-bottom: 1;
    }

    #url-input {
        width: 76;
    }

    #examples {
        width: auto;
        text-align: center;
        content-align: center middle;
        color: $text-muted;
        margin-top: 1;
    }

    #hint-text {
        width: auto;
        text-align: center;
        content-align: center middle;
        color: $text-disabled;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Middle():
            with Center():
                with Vertical(id="home-content"):
                    yield Static(TITLE_ART, id="ascii-art")
                    yield Static(
                        "Browse, search & download files from GitHub repos",
                        id="tagline",
                    )
                    with Vertical(id="input-section"):
                        yield Static("GitHub Repository URL", id="url-prompt")
                        yield Input(
                            placeholder="owner/repo or https://github.com/user/repo",
                            id="url-input",
                        )
                        yield Static(
                            "Examples: facebook/react  •  https://github.com/python/cpython",
                            id="examples",
                        )
                    yield Static(
                        "Enter: Browse  •  Tab: Autocomplete  •  Esc: Quit",
                        id="hint-text",
                    )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#url-input", Input).focus()

    @on(Input.Submitted, "#url-input")
    def on_url_submitted(self, event: Input.Submitted) -> None:
        url = event.value.strip()
        if not url:
            self.notify("Please enter a GitHub URL", severity="error")
            return
        try:
            owner, repo, branch, subpath = parse_github_url(url)
        except ValueError as e:
            self.notify(str(e), severity="error")
            return
        self.dismiss(url)

    def on_key(self, event: Any) -> None:
        if event.key == "tab":
            inp = self.query_one("#url-input", Input)
            if not inp.value or inp.value.strip() == "":
                inp.value = "https://github.com/"
                inp.cursor_position = len(inp.value)
                event.prevent_default()
                event.stop()

    def action_quit_app(self) -> None:
        self.app.exit()


# ─── Browse Screen ───────────────────────────────────────────
class BrowseScreen(Screen[None]):
    """Repository file browser with tree, search, selection, download."""

    BINDINGS = [
        Binding("q", "quit_app", "Quit", show=True),
        Binding("ctrl+q", "quit_app", "Quit", show=False),
        Binding("escape", "handle_escape", "Back / Close", show=True),
        Binding("slash", "focus_search", "Search", key_display="/", show=True),
        Binding("space", "toggle_select", "Select", show=True),
        Binding("a", "select_all", "Select All", show=True),
        Binding("u", "unselect_all", "Unselect All", show=True),
        Binding("d", "download", "Download", show=True),
        Binding("D", "download", "Download", show=False),
        Binding("i", "toggle_icons", "Toggle Icons", show=True),
        Binding("g", "jump_top", "Top", show=False),
        Binding("home", "jump_top", "Top", show=False),
        Binding("G", "jump_bottom", "Bottom", show=False),
        Binding("end", "jump_bottom", "Bottom", show=False),
        Binding("p", "preview_file", "Preview", show=True),
        Binding("enter", "enter_node", "Open", show=False),
        Binding("l", "enter_node", "Open", show=False),
        Binding("right", "enter_node", "Open", show=False),
        Binding("backspace", "go_back", "Back", show=False),
        Binding("h", "go_back", "Back", show=False),
        Binding("left", "go_back", "Back", show=False),
    ]

    CSS = """
    BrowseScreen {
        background: $surface;
    }

    #browse-wrapper {
        width: 100%;
        height: 100%;
        align: center middle;
    }

    #browse-content {
        width: 90;
        height: 100%;
        align: center middle;
    }

    #repo-header {
        width: 100%;
        height: 3;
        background: $accent;
        color: $text;
        content-align: center middle;
        text-align: center;
        text-style: bold;
        padding: 0 2;
    }

    #search-container {
        width: 100%;
        height: auto;
        display: none;
        padding: 0 1;
    }

    #search-container.visible {
        display: block;
    }

    #search-input {
        width: 100%;
    }

    #file-tree {
        width: 100%;
        height: 1fr;
        padding: 0 1;
        border: solid $surface-lighten-3;
    }

    #status-bar {
        width: 100%;
        height: 1;
        background: $panel;
        color: $text-muted;
        content-align: center middle;
        text-align: center;
        padding: 0 2;
    }
    """

    def __init__(
        self,
        url: str,
        token_override: str | None = None,
        cwd: bool = False,
        no_folder: bool = False,
    ) -> None:
        super().__init__()
        self.url = url
        self.token_override = token_override
        self.cwd_mode = cwd
        self.no_folder = no_folder
        self.emoji_icons = True
        self.selected_files: set[str] = set()
        self.all_files: list[RepoFile] = []
        self.repo_tree: RepoTree | None = None
        self.owner = ""
        self.repo = ""
        self.branch = ""
        self.subpath = ""
        self.current_path: list[str] = []

    def compose(self) -> ComposeResult:
        yield Static("Loading...", id="repo-header")
        with Container(id="search-container"):
            yield Input(placeholder="Fuzzy search files...", id="search-input")
        with Middle():
            with Center():
                with Vertical(id="browse-content"):
                    yield Tree("Repository", id="file-tree")
        yield Static("Loading repository...", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._parse_and_load()

    def _parse_and_load(self) -> None:
        try:
            self.owner, self.repo, self.branch, self.subpath = parse_github_url(self.url)
        except ValueError as e:
            self.notify(str(e), severity="error")
            return
        self._load_tree()

    @work(exclusive=True)
    async def _load_tree(self) -> None:
        token = self.token_override or get_token()
        client = GitHubClient(token=token)
        try:
            if not self.branch:
                self.branch = await client.get_default_branch(self.owner, self.repo)

            self.repo_tree = await client.get_tree(self.owner, self.repo, self.branch)
            self.all_files = self.repo_tree.files

            # Update header
            token_icon = "🔑" if token else "🔓"
            header = self.query_one("#repo-header", Static)
            header.update(
                f" {self.owner}/{self.repo} @ {self.branch} {token_icon}"
            )

            # Build tree
            self._build_tree()
            self._update_status()

        except NotFoundError as e:
            self.notify(str(e), severity="error")
        except AuthError as e:
            self.notify(str(e), severity="error")
        except RateLimitError as e:
            self.notify(str(e), severity="error")
        except GitHubAPIError as e:
            self.notify(str(e), severity="error")
        finally:
            await client.close()

    def _build_tree(self, filter_query: str = "") -> None:
        """Build or rebuild the file tree, optionally filtered."""
        tree_widget = self.query_one("#file-tree", Tree)
        tree_widget.clear()
        tree_widget.root.expand()

        if not self.all_files:
            return

        # Filter files if query present
        if filter_query:
            from rapidfuzz import fuzz

            visible = [
                f
                for f in self.all_files
                if fuzz.partial_ratio(filter_query.lower(), f.path.lower()) >= 60
            ]
        else:
            visible = list(self.all_files)

        # Determine current view path
        prefix = "/".join(self.current_path)

        # Build directory structure
        dirs_added: set[str] = set()

        for repo_file in sorted(visible, key=lambda f: (f.type != "tree", f.path)):
            path = repo_file.path

            # If we're in a subfolder, only show contents of that folder
            if prefix:
                if not path.startswith(prefix + "/"):
                    continue
                relative = path[len(prefix) + 1 :]
            else:
                relative = path

            # Only show immediate children
            parts = relative.split("/")
            if len(parts) > 1 and repo_file.type == "blob":
                # This file is nested — show its parent dir instead
                dir_name = parts[0]
                dir_path = f"{prefix}/{dir_name}" if prefix else dir_name
                if dir_path not in dirs_added:
                    dirs_added.add(dir_path)
                    dir_file = RepoFile(
                        path=dir_path, type="tree", size=0, sha="", url=""
                    )
                    node_data = FileNodeData(repo_file=dir_file, selected=dir_path in self.selected_files)
                    label = self._format_node_label(dir_file, dir_path in self.selected_files)
                    tree_widget.root.add(label, data=node_data, allow_expand=False)
                continue

            if repo_file.type == "tree":
                if path not in dirs_added:
                    dirs_added.add(path)
                    node_data = FileNodeData(repo_file=repo_file, selected=path in self.selected_files)
                    label = self._format_node_label(repo_file, path in self.selected_files)
                    tree_widget.root.add(label, data=node_data, allow_expand=False)
                continue

            if len(parts) == 1:
                node_data = FileNodeData(repo_file=repo_file, selected=path in self.selected_files)
                label = self._format_node_label(repo_file, path in self.selected_files)
                tree_widget.root.add(label, data=node_data, allow_expand=False)

        tree_widget.root.expand()
        tree_widget.focus()

    def _format_node_label(self, repo_file: RepoFile, selected: bool) -> Text:
        """Format a tree node label with selection indicator and icon."""
        # Selection indicator
        check = "[*]" if selected else "[ ]"

        # Icon
        if repo_file.type == "tree":
            icon = "📁 " if self.emoji_icons else "[D] "
        else:
            icon = "📄 " if self.emoji_icons else "[F] "

        # Name (just the last part of the path)
        name = repo_file.path.split("/")[-1]
        if repo_file.type == "tree":
            name += "/"

        # Size for files
        size_str = ""
        if repo_file.type == "blob" and repo_file.size > 0:
            size_str = f" ({_format_size(repo_file.size)})"

        label_str = f"{check} {icon}{name}{size_str}"

        text = Text(label_str)
        if selected:
            text.stylize("bold green", 0, 3)  # [*] in green
        else:
            text.stylize("dim", 0, 3)  # [ ] dimmed

        if repo_file.type == "tree":
            text.stylize("bold cyan", 4, 4 + len(icon) + len(name))

        return text

    def _update_status(self) -> None:
        """Update the status bar with selection count."""
        total = len([f for f in self.all_files if f.type == "blob"])
        selected = len(self.selected_files)
        path_display = "/" + "/".join(self.current_path) if self.current_path else "/"

        status = self.query_one("#status-bar", Static)
        status.update(
            f" {selected} selected │ {total} files │ {path_display} │ ↑↓ navigate Space: select"
        )

    def _refresh_node_label(self, node: TreeNode[FileNodeData]) -> None:
        """Update a single node's label to reflect selection state."""
        if node.data is None:
            return
        node.set_label(
            self._format_node_label(node.data.repo_file, node.data.selected)
        )

    # ── Actions ──────────────────────────────────────────

    def action_toggle_select(self) -> None:
        """Toggle selection on the highlighted node."""
        tree = self.query_one("#file-tree", Tree)
        node = tree.cursor_node
        if node is None or node.data is None:
            return

        data: FileNodeData = node.data
        path = data.repo_file.path

        if data.selected:
            # Deselect
            data.selected = False
            self.selected_files.discard(path)
            # If it's a folder, deselect all children
            if data.repo_file.type == "tree":
                self._set_children_selection(path, False)
        else:
            # Select
            data.selected = True
            self.selected_files.add(path)
            # If it's a folder, select all children
            if data.repo_file.type == "tree":
                self._set_children_selection(path, True)

        self._refresh_node_label(node)
        self._update_status()

        # Also refresh any child nodes visible in tree
        self._refresh_all_visible_nodes()

    def _set_children_selection(self, folder_path: str, selected: bool) -> None:
        """Select/deselect all files under a folder path."""
        for f in self.all_files:
            if f.path.startswith(folder_path + "/") and f.type == "blob":
                if selected:
                    self.selected_files.add(f.path)
                else:
                    self.selected_files.discard(f.path)

    def _refresh_all_visible_nodes(self) -> None:
        """Refresh labels of all visible tree nodes."""
        tree = self.query_one("#file-tree", Tree)
        for node in tree.root.children:
            if node.data is not None:
                path = node.data.repo_file.path
                node.data.selected = path in self.selected_files
                self._refresh_node_label(node)

    def action_select_all(self) -> None:
        """Select all visible nodes."""
        tree = self.query_one("#file-tree", Tree)
        for node in tree.root.children:
            if node.data is not None:
                node.data.selected = True
                path = node.data.repo_file.path
                self.selected_files.add(path)
                if node.data.repo_file.type == "tree":
                    self._set_children_selection(path, True)
        self._refresh_all_visible_nodes()
        self._update_status()

    def action_unselect_all(self) -> None:
        """Unselect all nodes."""
        self.selected_files.clear()
        tree = self.query_one("#file-tree", Tree)
        for node in tree.root.children:
            if node.data is not None:
                node.data.selected = False
        self._refresh_all_visible_nodes()
        self._update_status()

    def action_toggle_icons(self) -> None:
        """Toggle between emoji and ASCII icons."""
        self.emoji_icons = not self.emoji_icons
        self._build_tree()
        self._update_status()

    def action_enter_node(self) -> None:
        """Enter a folder."""
        tree = self.query_one("#file-tree", Tree)
        node = tree.cursor_node
        if node is None or node.data is None:
            return

        if node.data.repo_file.type == "tree":
            folder_name = node.data.repo_file.path.split("/")[-1]
            self.current_path.append(folder_name)
            self._build_tree()
            self._update_status()

    def action_go_back(self) -> None:
        """Go to parent folder."""
        if self.current_path:
            self.current_path.pop()
            self._build_tree()
            self._update_status()

    def action_handle_escape(self) -> None:
        """Escape context-dependent behavior."""
        # If search is visible, close it
        search_container = self.query_one("#search-container")
        if "visible" in search_container.classes:
            search_container.remove_class("visible")
            self.query_one("#file-tree", Tree).focus()
            self._build_tree()  # Reset filter
            return

        # If in subfolder, go back
        if self.current_path:
            self.current_path.pop()
            self._build_tree()
            self._update_status()
            return

        # At root, go home
        self.app.pop_screen()

    def action_focus_search(self) -> None:
        """Show and focus the search bar."""
        search_container = self.query_one("#search-container")
        search_container.add_class("visible")
        search_input = self.query_one("#search-input", Input)
        search_input.value = ""
        search_input.focus()

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Filter tree as user types."""
        self._build_tree(filter_query=event.value)

    def action_jump_top(self) -> None:
        tree = self.query_one("#file-tree", Tree)
        if tree.root.children:
            tree.cursor_line = 0
            tree.scroll_home()

    def action_jump_bottom(self) -> None:
        tree = self.query_one("#file-tree", Tree)
        if tree.root.children:
            tree.cursor_line = len(tree.root.children) - 1
            tree.scroll_end()

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_download(self) -> None:
        """Download selected files."""
        if not self.selected_files:
            self.notify("No files selected. Use Space to select files.", severity="warning")
            return
        self._start_download()

    @work(exclusive=True)
    async def _start_download(self) -> None:
        """Run the download process."""
        # Determine destination
        if self.cwd_mode:
            dest = Path.cwd()
        else:
            dest = get_download_path()

        token = self.token_override or get_token()
        client = GitHubClient(token=token)

        try:
            selected_repo_files = [
                f
                for f in self.all_files
                if f.path in self.selected_files and f.type == "blob"
            ]

            if not selected_repo_files:
                self.notify("No files to download.", severity="warning")
                return

            count = len(selected_repo_files)
            self.notify(f"Downloading {count} file(s) to {dest}...")

            downloader = Downloader(
                client=client,
                owner=self.owner,
                repo=self.repo,
                branch=self.branch,
                dest=dest,
                create_repo_folder=not self.no_folder,
            )

            results = await downloader.download_files(selected_repo_files)

            # Summary
            success = sum(1 for r in results if r.success)
            failed = sum(1 for r in results if not r.success)
            lfs = sum(1 for r in results if r.is_lfs)

            summary = f"✓ {success} downloaded"
            if failed:
                summary += f" │ ✗ {failed} failed"
            if lfs:
                summary += f" │ ⚠ {lfs} LFS pointers"

            self.notify(summary, severity="information" if failed == 0 else "warning")

            if lfs:
                self.notify(
                    "⚠ LFS pointers detected. Run `git lfs pull` after download.",
                    severity="warning",
                )

        except GitHubAPIError as e:
            self.notify(str(e), severity="error")
        finally:
            await client.close()

    def action_preview_file(self) -> None:
        """Preview the highlighted file."""
        tree = self.query_one("#file-tree", Tree)
        node = tree.cursor_node
        if node is None or node.data is None:
            return
        if node.data.repo_file.type != "blob":
            self.notify("Can only preview files, not folders.", severity="warning")
            return
        self._fetch_preview(node.data.repo_file)

    @work(exclusive=True)
    async def _fetch_preview(self, repo_file: RepoFile) -> None:
        """Fetch and show file preview."""
        token = self.token_override or get_token()
        client = GitHubClient(token=token)
        try:
            url = await client.get_raw_url(self.owner, self.repo, self.branch, repo_file.path)
            async with client._client as c:
                response = await c.get(url)
                content = response.text
                lines = content.splitlines()[:30]
                preview_text = "\n".join(lines)
                if len(content.splitlines()) > 30:
                    preview_text += "\n\n... (truncated at 30 lines)"

                self.app.push_screen(PreviewScreen(repo_file.path, preview_text))
        except Exception as e:
            self.notify(f"Preview failed: {e}", severity="error")
        finally:
            await client.close()


class PreviewScreen(Screen[None]):
    """Modal screen showing file preview."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
    ]

    CSS = """
    PreviewScreen {
        align: center middle;
    }

    #preview-container {
        width: 80%;
        height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    #preview-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #preview-content {
        width: 100%;
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self, filename: str, content: str) -> None:
        super().__init__()
        self.filename = filename
        self.content = content

    def compose(self) -> ComposeResult:
        with Container(id="preview-container"):
            yield Static(f"── {self.filename} ──", id="preview-title")
            yield VerticalScroll(
                Static(self.content, id="preview-text"),
                id="preview-content",
            )

    def action_close(self) -> None:
        self.app.pop_screen()


# ─── Helper ──────────────────────────────────────────────────
def _format_size(size: int) -> str:
    """Format bytes to human readable."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"


# ─── Main App ────────────────────────────────────────────────
class GitHubScrapeTUI(App[None]):
    """Main Textual application."""

    TITLE = "github-scrape"

    CSS = """
    Screen {
        background: $surface;
    }

    /* GitHub Dark Theme */
    $accent: #58a6ff;
    $accent-light: #79c0ff;
    $accent-dark: #1f6feb;
    $surface: #0d1117;
    $surface-light: #161b22;
    $surface-lighter: #21262d;
    $panel: #0c0e12;
    $text: #c9d1d9;
    $text-muted: #8b949e;
    $text-disabled: #6e7681;
    $success: #238636;
    $warning: #d29922;
    $error: #f85149;
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        cwd: bool = False,
        no_folder: bool = False,
    ) -> None:
        super().__init__()
        self.initial_url = url
        self.token_override = token
        self.cwd_mode = cwd
        self.no_folder = no_folder

    def on_mount(self) -> None:
        if self.initial_url:
            self.push_screen(
                BrowseScreen(
                    url=self.initial_url,
                    token_override=self.token_override,
                    cwd=self.cwd_mode,
                    no_folder=self.no_folder,
                )
            )
        else:
            self.push_screen(HomeScreen(), callback=self._on_home_dismiss)

    def _on_home_dismiss(self, url: str | None) -> None:
        """Called when HomeScreen returns a URL."""
        if url:
            self.push_screen(
                BrowseScreen(
                    url=url,
                    token_override=self.token_override,
                    cwd=self.cwd_mode,
                    no_folder=self.no_folder,
                )
            )
        else:
            self.exit()
