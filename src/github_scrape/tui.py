from typing import Any

from rich.text import Text
from rich.panel import Panel
from rich.box import MINIMAL
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Input, Label, Static, Tree

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
    CSS = """
    Screen {
        background: $panel;
    }
    #title-container {
        width: 100%;
        height: 12;
        align: center middle;
        margin: 1 0;
    }
    #title-text {
        width: 100%;
        content-align: center middle;
        text-style: bold;
    }
    .input-container {
        width: 70;
        height: auto;
        align: center middle;
        padding: 1 2;
        border: tall $primary;
        background: $surface;
        margin: 1 0;
    }
    #url-input {
        width: 100%;
        height: 1;
        margin: 1 0;
    }
    #instructions {
        width: 70;
        align: center middle;
        text-style: italic;
        color: $text-muted;
        margin: 1 0;
    }
    #examples {
        width: 70;
        align: center middle;
        text-style: dim;
        color: $text-muted;
        margin: 1 0;
    }
    #footer-info {
        width: 100%;
        height: 1;
        dock: bottom;
        content-align: center middle;
        text-style: italic;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        # Enhanced ASCII Art Title with gradient-like styling using Textual Rich markup
        # Using bold cyan/blue colors to mimic the Gemini CLI blue/violet gradient effect
        ascii_art = """[bold #58a6ff]
  ██████╗ ██╗   ██╗ ██████╗ ██████╗  █████╗ ██████╗
 ██╔════╝ ██║   ██║██╔════╝ ██╔══██╗██╔══██╗██╔══██╗
 ██║  ███╗██║   ██║██║  ███╗██████╔╝███████║██████╔╝
 ██║   ██║██║   ██║██║   ██║██╔══██╗██╔══██║██╔══██╗
 ╚██████╔╝╚██████╔╝╚██████╔╝██║  ██║██║  ██║██████╔╝
  ╚═════╝  ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝[/bold #58a6ff]

[bold #79c0ff]github-scrape[/bold #79c0ff] [dim]—[/dim] [italic]Download any file or folder from GitHub. No full clones. Just what you need.[/italic]
"""

        yield Container(
            Static(
                ascii_art,
                id="title-text",
                classes="title-text"
            ),
            classes="title-container",
            id="title-container"
        )

        yield Container(
            Label("[bold]Enter GitHub URL[/bold] [dim](Press Tab to autocomplete https://github.com/)[/dim]"),
            Input(placeholder="owner/repo or full URL", id="url-input"),
            Label("[dim]Press Enter to browse, ESC to quit[/dim]", classes="instructions", id="instructions"),
            classes="input-container",
        )

        # Examples with better styling
        yield Static(
            "[dim]Examples: https://github.com/user/repo | user/repo | https://github.com/user/repo/tree/main/path[/dim]",
            id="examples"
        )

        # Footer with additional info
        yield Static("[dim]github-scrape v0.1.0 | Press Ctrl+C to quit[/dim]", id="footer-info")
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "url-input":
            self._handle_url(event.value)

    def on_key(self, event: Any) -> None:
        if event.key == "tab":
            input_widget = self.query_one("#url-input", Input)
            if not input_widget.value:
                input_widget.value = "https://github.com/"
            else:
                input_widget.value = "https://github.com/" + input_widget.value
            input_widget.cursor_position = len(input_widget.value)
            event.stop()

    def _handle_url(self, url: str) -> None:
        try:
            owner, repo, branch, subpath = parse_github_url(url)
            self.app.push_screen(
                BrowseScreen(owner=owner, repo=repo, branch=branch, subpath=subpath)
            )
        except ValueError as e:
            self.notify(str(e), title="Invalid URL", severity="error")


class BrowseScreen(Screen[object]):
    CSS = """
    .header-bar {
        height: 3;
        background: $primary;
        padding: 1 2;
        border-bottom: solid $primary-lighten-1;
        content-align: center middle;
    }
    .header-title {
        text-style: bold;
        color: $text;
    }
    .header-subtitle {
        text-style: italic;
        color: $text-muted;
    }
    .search-container {
        height: auto;
        dock: top;
        display: none;
        padding: 1 2;
        background: $surface;
        border-bottom: solid $primary;
    }
    .search-visible {
        display: block;
    }
    #file-tree {
        height: 1fr;
        border: none;
        margin: 1 0;
        background: $surface-lighten-1;
    }
    .status-bar {
        height: 3;
        background: $surface-darken-1;
        padding: 1 2;
        border-top: solid $primary;
        content-align: center middle;
    }
    .status-text {
        text-style: bold;
    }
    .tree-node {
        padding: 0 1;
    }
    .tree-node:focus {
        background: $accent;
        color: $text;
    }
    .tree-file {
        color: $text;
    }
    .tree-folder {
        color: $primary-lighten-1;
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
        token = config.get_token()
        token_indicator = "🔑" if token else "🔓"

        # Create header with better formatting
        header_container = Container(
            Static(
                f"{self._owner}/{self._repo}",
                classes="header-title",
                id="header-title",
            ),
            Static(
                f"@ {self._branch or 'default'} {token_indicator}",
                classes="header-subtitle",
                id="header-subtitle",
            ),
            classes="header-bar",
            id="header-bar",
        )

        search_container = Container(
            Input(placeholder="🔍 Fuzzy search files (press '/' to focus)...", id="search-input"),
            classes="search-container",
            id="search-container",
        )

        tree_widget = Tree(label="📁 Files & Folders", id="file-tree")
        tree_widget.styles.border = ("solid", "$primary")
        tree_widget.styles.background = "$surface-lighten-1"

        status_container = Container(
            Static(
                "0 selected | 0 files | Use arrows/enter/backspace for navigation",
                classes="status-text",
                id="status-text",
            ),
            classes="status-bar",
            id="status-bar",
        )

        yield Container(
            header_container,
            search_container,
            tree_widget,
            status_container,
        )
        yield Footer()

    async def on_mount(self) -> None:
        await self._load_tree()

    async def _load_tree(self) -> None:
        token = config.get_token()
        try:
            async with GitHubClient(token) as client:
                if not self._branch:
                    self._branch = await client.get_default_branch(self._owner, self._repo)
                tree = await client.get_tree(self._owner, self._repo, self._branch)
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

                # Different styling for selected vs unselected
                if f.path in self.selected_files:
                    label = f"[bold green]✓[/bold green] {icon} [bold]{part}[/bold]"
                else:
                    label = f"[ ] {icon} {part}"

                child_node = None
                for child in node.children:
                    if child.label:
                        label_str = (
                            child.label.plain if isinstance(child.label, Text) else str(child.label)
                        )
                        if label_str.endswith(part):
                            child_node = child
                            break
                if child_node:
                    node = child_node
                else:
                    node = node.add(part, data=f if is_file else None)
                    node.set_label(Text.from_markup(label))

                    # Apply different styling based on file type
                    if is_file:
                        node.set_classes("tree-node tree-file")
                    else:
                        node.set_classes("tree-node tree-folder")

    def _get_icon(self, is_file: bool) -> str:
        if self.use_emoji:
            return "📄" if is_file else "📁"
        return "[F]" if is_file else "[D]"

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[object]) -> None:
        pass

    def action_toggle_selection(self) -> None:
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
        if self.tree_data:
            for f in self.tree_data.files:
                if f.type == "blob":
                    self.selected_files.add(f.path)
            self._update_status()
            self._populate_tree()

    def action_unselect_all(self) -> None:
        self.selected_files.clear()
        self._update_status()
        self._populate_tree()

    def action_focus_search(self) -> None:
        container = self.query_one("#search-container", Container)
        search_input = self.query_one("#search-input", Input)
        container.add_class("search-visible")
        self._search_visible = True
        search_input.focus()

    def action_go_back(self) -> None:
        if self._search_visible:
            container = self.query_one("#search-container", Container)
            container.remove_class("search-visible")
            self._search_visible = False
            self.query_one("#file-tree", Tree).focus()
        else:
            self.app.pop_screen()

    def action_toggle_icons(self) -> None:
        self.use_emoji = not self.use_emoji
        self._populate_tree()

    def action_scroll_home(self) -> None:
        tree = self.query_one("#file-tree", Tree)
        tree.action_scroll_home()

    def action_scroll_end(self) -> None:
        tree = self.query_one("#file-tree", Tree)
        tree.action_scroll_end()

    def action_preview(self) -> None:
        tree = self.query_one("#file-tree", Tree)
        node = tree.cursor_node
        if node and node.data:
            self.notify("Preview not yet implemented", title="Info", severity="information")

    def action_enter_node(self) -> None:
        tree = self.query_one("#file-tree", Tree)
        node = tree.cursor_node
        if node:
            if node.children:
                node.toggle()
            elif node.data:
                self.notify("Use Space to select files", title="Info", severity="information")

    def action_go_up(self) -> None:
        tree = self.query_one("#file-tree", Tree)
        node = tree.cursor_node
        if node and node.parent:
            tree.select_node(node.parent)

    async def action_download(self) -> None:
        if not self.selected_files:
            self.notify("No files selected", title="Info", severity="information")
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
        status = self.query_one("#status-bar", Static)
        total = len(self.tree_data.files) if self.tree_data else 0
        selected = len(self.selected_files)
        status.update(f"{selected} selected | {total} files | nav: arrows/enter")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self._current_filter = event.value
            self._filter_tree(event.value)

    def _filter_tree(self, query: str) -> None:
        if not query:
            self._populate_tree()
            return

        try:
            from rapidfuzz import fuzz

            if self.tree_data:
                for f in self.tree_data.files:
                    score = fuzz.partial_ratio(query.lower(), f.path.lower())
                    if score >= 60:
                        pass
        except ImportError:
            pass


class GitHubScrapeTUI(App[object]):
    CSS = """
    Screen {
        background: $surface;
    }

    /* Enhanced color scheme - GitHub Dark Theme inspired */
    $primary: #58a6ff;
    $primary-lighten-1: #79c0ff;
    $primary-darken-1: #388bfd;
    $secondary: #6e7681;
    $surface: #0d1117;
    $surface-darken-1: #010409;
    $surface-lighten-1: #161b22;
    $surface-lighten-2: #21262d;
    $panel: #161b22;
    $accent: #238636;
    $accent-lighten-1: #2ea043;
    $accent-warning: #d29922;
    $accent-danger: #f85149;
    $text: #c9d1d9;
    $text-muted: #8b949e;

    /* Scrollbar styling */
    Tree > .scrollbar-corner {
        background: $surface;
    }
    Tree > .scrollbar-horizontal,
    Tree > .scrollbar-vertical {
        tint: $primary 30%;
    }

    /* Input styling */
    Input {
        border: tall $surface-lighten-2;
        background: $surface-darken-1;
    }
    Input:focus {
        border: tall $primary;
    }
    """

    TITLE = "github-scrape - Advanced GitHub File Browser"
    SUB_TITLE = "Download files from GitHub without cloning entire repositories"
    SCREENS = {"home": HomeScreen}

    def on_mount(self) -> None:
        self.title = self.TITLE
        self.push_screen("home")
