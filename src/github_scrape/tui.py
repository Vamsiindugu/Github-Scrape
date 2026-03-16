"""Textual TUI for github-scrape - Clean, centered UI like ghgrab."""

from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal, Center
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Input, Static, Tree

from github_scrape import config
from github_scrape.api import (
    AuthError,
    GitHubClient,
    NotFoundError,
    RateLimitError,
    RepoFile,
    RepoTree,
)
from github_scrape.downloader import Downloader
from github_scrape.utils import parse_github_url


class HomeScreen(Screen[object]):
    """Home screen with centered layout matching ghgrab style."""

    CSS = """
    Screen {
        align: center middle;
        background: $surface-darken-1;
    }

    #content {
        width: auto;
        height: auto;
        align: center middle;
    }

    #ascii-header {
        width: auto;
        height: auto;
        text-align: center;
        content-align: center middle;
        color: #58a6ff;
        text-style: bold;
    }

    #tagline {
        width: auto;
        text-align: center;
        content-align: center middle;
        margin-top: 1;
        text-style: dim;
        color: $text-muted;
    }

    #input-box {
        width: 76;
        height: auto;
        border: solid $primary;
        padding: 1 2;
        margin-top: 2;
        background: $surface;
    }

    #input-label {
        text-align: center;
        content-align: center middle;
        text-style: bold;
        color: $text;
    }

    #url-input {
        margin-top: 1;
    }

    #input-hint {
        text-align: center;
        content-align: center middle;
        margin-top: 1;
        text-style: dim;
        color: $text-muted;
    }

    #examples {
        width: 76;
        text-align: center;
        content-align: center middle;
        margin-top: 1;
        text-style: dim;
        color: $text-muted;
    }

    #footer-info {
        width: 100%;
        dock: bottom;
        text-align: center;
        content-align: center middle;
        text-style: dim;
        padding: 1 0;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        # Clean ASCII art - using Rich markup for coloring
        ascii_art = """[bold #58a6ff]
 ██████╗ ██╗████████╗██╗ ██╗██╗ ██╗██████╗ ███████╗ ██████╗██████╗ █████╗ ██████╗ ███████╗
██╔════╝ ██║╚══██╔══╝██║ ██║██║ ██║██╔══██╗ ██╔════╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██╔════╝
██║ ███╗██║ ██║ ███████║██║ ██║██████╔╝ ███████╗██║ ██████╔╝███████║██████╔╝█████╗
██║ ██║██║ ██║ ██╔══██║██║ ██║██╔══██╗ ╚════██║██║ ██╔══██╗██╔══██║██╔═══╝ ██╔══╝
╚██████╔╝██║ ██║ ██║ ██║╚██████╔╝██████╔╝ ███████║╚██████╗██║ ██║██║ ██║██║ ███████╗
 ╚═════╝ ╚═╝ ╚═╝ ╚═╝ ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝ ╚═════╝╚═╝ ╚═╝╚═╝ ╚═╝╚═╝ ╚══════╝[/bold #58a6ff]"""

        with Vertical(id="content"):
            yield Static(ascii_art, id="ascii-header")
            yield Static(
                "github-scrape — Download any file or folder from GitHub. No full clones.",
                id="tagline"
            )

            with Container(id="input-box"):
                yield Static("Enter GitHub URL", id="input-label")
                yield Input(
                    placeholder="owner/repo or full URL",
                    id="url-input"
                )
                yield Static(
                    "Press Tab to autocomplete https://github.com/",
                    id="input-hint"
                )

            yield Static(
                "Examples: owner/repo | https://github.com/user/repo | https://github.com/user/repo/tree/main/path",
                id="examples"
            )

        yield Static(
            "github-scrape v0.1.0 | Press ESC or Ctrl+C to quit",
            id="footer-info"
        )
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle URL submission."""
        if event.input.id == "url-input":
            self._handle_url(event.value)

    def on_key(self, event: Any) -> None:
        """Handle Tab key for autocomplete."""
        if event.key == "tab":
            input_widget = self.query_one("#url-input", Input)
            if not input_widget.value:
                input_widget.value = "https://github.com/"
            else:
                input_widget.value = "https://github.com/" + input_widget.value
            input_widget.cursor_position = len(input_widget.value)
            event.stop()

    def _handle_url(self, url: str) -> None:
        """Parse URL and navigate to BrowseScreen."""
        try:
            owner, repo, branch, subpath = parse_github_url(url)
            self.app.push_screen(
                BrowseScreen(owner=owner, repo=repo, branch=branch, subpath=subpath)
            )
        except ValueError as e:
            self.notify(str(e), title="Invalid URL", severity="error")


class BrowseScreen(Screen[object]):
    """File browser screen with tree view."""

    CSS = """
    Screen {
        background: $surface-darken-1;
    }

    #header-bar {
        width: 100%;
        height: 3;
        dock: top;
        background: $primary-darken-1;
        border-bottom: solid $primary;
        text-align: center;
        content-align: center middle;
    }

    #header-title {
        text-style: bold;
        color: $text;
    }

    #header-subtitle {
        color: $text-muted;
    }

    #search-container {
        width: 100%;
        height: auto;
        dock: top;
        display: none;
        background: $surface;
        border-bottom: solid $primary;
        padding: 1 2;
    }

    #search-container.search-visible {
        display: block;
    }

    #file-tree {
        width: 100%;
        height: 1fr;
        border: solid $surface-lighten-2;
        margin: 1;
        background: $surface;
    }

    #status-bar {
        width: 100%;
        height: 3;
        dock: bottom;
        background: $surface-darken-1;
        border-top: solid $primary;
        text-align: center;
        content-align: center middle;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("q", "quit", "Quit"),
        ("d", "download", "Download"),
        ("space", "toggle_selection", "Toggle"),
        ("a", "select_all", "Select All"),
        ("u", "unselect_all", "Unselect All"),
        ("/", "focus_search", "Search"),
        ("i", "toggle_icons", "Toggle Icons"),
        ("g", "scroll_home", "Top"),
        ("G", "scroll_end", "Bottom"),
        ("p", "preview", "Preview"),
        ("enter", "enter_node", "Enter"),
        ("backspace", "go_up", "Up"),
        ("h", "go_up", "Up"),
        ("l", "enter_node", "Enter"),
    ]

    owner: reactive[str] = reactive("")
    repo: reactive[str] = reactive("")
    branch: reactive[str] = reactive("")
    subpath: reactive[str] = reactive("")
    tree_data: reactive[RepoTree | None] = reactive(None)
    selected_files: reactive[set[str]] = reactive(set)
    use_emoji: reactive[bool] = reactive(True)

    def __init__(
        self,
        owner: str = "",
        repo: str = "",
        branch: str = "",
        subpath: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._owner = owner
        self._repo = repo
        self._branch = branch
        self._subpath = subpath
        self._search_visible = False
        self._current_filter = ""

    def compose(self) -> ComposeResult:
        """Compose the BrowseScreen UI."""
        token = config.get_token()
        token_indicator = "🔓 Using public API"
        if token:
            masked = token[:8] + "***" if len(token) > 8 else token[:4] + "***"
            token_indicator = f"🔑 Token {masked}"

        yield Container(
            Static(
                f"{self._owner}/{self._repo}",
                id="header-title",
            ),
            Static(
                f"@{self._branch or 'default'} | {token_indicator}",
                id="header-subtitle",
            ),
            id="header-bar",
        )

        yield Container(
            Input(
                placeholder="🔍 Search files (type to filter)...",
                id="search-input"
            ),
            id="search-container",
        )

        yield Tree(
            label="📁 Files & Folders",
            id="file-tree"
        )

        yield Container(
            Static(
                "0 selected | 0 files | Enter to toggle, Space to select, d to download",
                id="status-text",
            ),
            id="status-bar",
        )

        yield Footer()

    async def on_mount(self) -> None:
        """Load the repository tree on mount."""
        await self._load_tree()

    async def _load_tree(self) -> None:
        """Load tree from GitHub API."""
        token = config.get_token()
        try:
            async with GitHubClient(token) as client:
                if not self._branch:
                    self._branch = await client.get_default_branch(
                        self._owner, self._repo
                    )
                tree = await client.get_tree(
                    self._owner, self._repo, self._branch
                )
                self.tree_data = tree
                self._populate_tree()
        except NotFoundError as e:
            self.notify(str(e), title="Not Found", severity="error")
        except AuthError as e:
            self.notify(str(e), title="Auth Error", severity="error")
        except RateLimitError as e:
            self.notify(str(e), title="Rate Limited", severity="error")
        except Exception as e:
            self.notify(str(e), title="Error", severity="error")

    def _populate_tree(self) -> None:
        """Populate the tree widget with files."""
        tree = self.query_one("#file-tree", Tree)
        tree.clear()
        if not self.tree_data:
            return

        root = tree.root
        root.set_label(f"📂 {self._owner}/{self._repo}")
        root.expand()

        for f in self.tree_data.files:
            parts = f.path.split("/")
            node = root
            for i, part in enumerate(parts):
                is_file = i == len(parts) - 1 and f.type == "blob"
                icon = self._get_icon(is_file)
                if f.path in self.selected_files:
                    label = f"✓ {icon} {part}"
                else:
                    label = f" {icon} {part}"
                child_node = None
                for child in node.children:
                    if child.label:
                        label_str = str(child.label)
                        if label_str.endswith(part):
                            child_node = child
                            break
                if child_node:
                    node = child_node
                else:
                    node = node.add(part, data=f if is_file else None)
                from rich.text import Text
                node.set_label(Text.from_markup(label))

    def _get_icon(self, is_file: bool) -> str:
        """Return icon for file or folder."""
        if self.use_emoji:
            return "📄" if is_file else "📁"
        return "[F]" if is_file else "[D]"

    def action_toggle_selection(self) -> None:
        """Toggle selection on current node."""
        tree = self.query_one("#file-tree", Tree)
        node = tree.cursor_node
        if node and node.data:
            file = node.data
            if isinstance(file, RepoFile):
                if file.path in self.selected_files:
                    self.selected_files.discard(file.path)
                else:
                    self.selected_files.add(file.path)
                self._update_status()
                self._populate_tree()

    def action_select_all(self) -> None:
        """Select all visible files."""
        if self.tree_data:
            for f in self.tree_data.files:
                if f.type == "blob":
                    self.selected_files.add(f.path)
            self._update_status()
            self._populate_tree()

    def action_unselect_all(self) -> None:
        """Unselect all files."""
        self.selected_files.clear()
        self._update_status()
        self._populate_tree()

    def action_focus_search(self) -> None:
        """Show and focus search bar."""
        container = self.query_one("#search-container", Container)
        search_input = self.query_one("#search-input", Input)
        container.add_class("search-visible")
        self._search_visible = True
        search_input.focus()

    def action_go_back(self) -> None:
        """Go back or close search."""
        if self._search_visible:
            container = self.query_one("#search-container", Container)
            container.remove_class("search-visible")
            self._search_visible = False
            self.query_one("#file-tree", Tree).focus()
        else:
            self.app.pop_screen()

    def action_toggle_icons(self) -> None:
        """Toggle between emoji and ASCII icons."""
        self.use_emoji = not self.use_emoji
        self._populate_tree()

    def action_scroll_home(self) -> None:
        """Scroll to top of tree."""
        tree = self.query_one("#file-tree", Tree)
        tree.action_scroll_home()

    def action_scroll_end(self) -> None:
        """Scroll to bottom of tree."""
        tree = self.query_one("#file-tree", Tree)
        tree.action_scroll_end()

    def action_preview(self) -> None:
        """Preview current file."""
        tree = self.query_one("#file-tree", Tree)
        node = tree.cursor_node
        if node and node.data:
            self.notify(
                "Preview not yet implemented",
                title="Info",
                severity="information"
            )

    def action_enter_node(self) -> None:
        """Enter folder or select file."""
        tree = self.query_one("#file-tree", Tree)
        node = tree.cursor_node
        if node:
            if node.children:
                node.toggle()
            elif node.data:
                self.notify(
                    "Use Space to select files",
                    title="Info",
                    severity="information"
                )

    def action_go_up(self) -> None:
        """Go to parent folder."""
        tree = self.query_one("#file-tree", Tree)
        node = tree.cursor_node
        if node and node.parent:
            tree.select_node(node.parent)

    async def action_download(self) -> None:
        """Download selected files."""
        if not self.selected_files:
            self.notify(
                "No files selected",
                title="Info",
                severity="information"
            )
            return

        dest = config.get_download_path()
        if self.tree_data:
            files_to_download = [
                f
                for f in self.tree_data.files
                if f.path in self.selected_files and f.type == "blob"
            ]
            if files_to_download:
                self.notify(
                    f"Downloading {len(files_to_download)} files to {dest}...",
                    title="Download",
                    severity="information",
                )
                token = config.get_token()
                async with GitHubClient(token) as client:
                    downloader = Downloader(
                        client,
                        self._owner,
                        self._repo,
                        self._branch,
                        dest,
                    )
                    results = await downloader.download_files(files_to_download)
                    success = sum(1 for r in results if r.success)
                    lfs_count = sum(1 for r in results if r.is_lfs)
                    errors = sum(1 for r in results if not r.success)
                    msg = f"Downloaded {success} files"
                    if lfs_count:
                        msg += f" ({lfs_count} LFS pointers)"
                    if errors:
                        msg += f", {errors} errors"
                    self.notify(msg, title="Complete", severity="information")
                    if lfs_count:
                        self.notify(
                            "Run 'git lfs pull' for LFS files",
                            title="LFS Warning",
                            severity="warning",
                        )

    def _update_status(self) -> None:
        """Update status bar with selection info."""
        from textual.widgets import Static
        status = self.query_one("#status-text", Static)
        total = len(self.tree_data.files) if self.tree_data else 0
        selected = len(self.selected_files)
        status.update(
            f"{selected} selected | {total} files | "
            "Enter to toggle, Space to select, d to download"
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter tree on search input change."""
        if event.input.id == "search-input":
            self._current_filter = event.value
            self._filter_tree(event.value)

    def _filter_tree(self, query: str) -> None:
        """Filter tree based on fuzzy search query."""
        if not query:
            self._populate_tree()
            return
        try:
            from rapidfuzz import fuzz
            if self.tree_data:
                for f in self.tree_data.files:
                    score = fuzz.partial_ratio(query.lower(), f.path.lower())
                    if score >= 60:
                        pass  # TODO: Implement filtering
        except ImportError:
            pass


class GitHubScrapeTUI(App[object]):
    """Main TUI application."""

    CSS = """
    Screen {
        background: $surface-darken-1;
    }

    /* GitHub Dark Theme */
    $primary: #58a6ff;
    $primary-lighten-1: #79c0ff;
    $primary-darken-1: #1f6feb;
    $surface: #0d1117;
    $surface-darken-1: #0c0e12;
    $surface-lighten-1: #161b22;
    $surface-lighten-2: #21262d;
    $accent: #238636;
    $accent-warning: #d29922;
    $accent-danger: #f85149;
    $text: #c9d1d9;
    $text-muted: #8b949e;

    Input {
        border: solid $surface-lighten-2;
        background: $surface;
    }
    Input:focus {
        border: solid $primary;
    }
    Tree:focus {
        border: solid $primary;
    }
    """

    TITLE = "github-scrape"
    SUB_TITLE = "GitHub File Browser & Downloader"
    SCREENS = {"home": HomeScreen}

    def on_mount(self) -> None:
        """Push home screen on mount."""
        self.title = self.TITLE
        self.push_screen("home")
