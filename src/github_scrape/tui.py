from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container
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
        align: center middle;
    }
    .input-container {
        width: 60;
        height: auto;
        padding: 2;
        border: solid green;
    }
    Input {
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        yield Container(
            Label("Paste GitHub URL (Tab to autocomplete https://github.com/)"),
            Input(placeholder="owner/repo or full URL", id="url-input"),
            classes="input-container",
        )
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
        height: 1;
        background: $surface;
        padding: 0 1;
    }
    .search-container {
        height: auto;
        dock: top;
        display: none;
    }
    .search-visible {
        display: block;
    }
    Tree {
        height: 1fr;
    }
    .status-bar {
        height: 1;
        background: $surface;
        padding: 0 1;
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
        yield Container(
            Static(
                f"{self._owner}/{self._repo} @ {self._branch or 'default'} {token_indicator}",
                classes="header-bar",
                id="header-bar",
            ),
            Container(
                Input(placeholder="Fuzzy search files...", id="search-input"),
                classes="search-container",
                id="search-container",
            ),
            Tree(label="Files", id="file-tree"),
            Static(
                "0 selected | 0 files | nav: arrows/enter/backspace",
                classes="status-bar",
                id="status-bar",
            ),
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
        root.set_label(f"{self._owner}/{self._repo}")
        root.expand()

        for f in self.tree_data.files:
            parts = f.path.split("/")
            node = root
            for i, part in enumerate(parts):
                is_file = i == len(parts) - 1 and f.type == "blob"
                icon = self._get_icon(is_file)
                label = f"[{'x' if f.path in self.selected_files else ' '}] {icon} {part}"
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
    """

    TITLE = "github-scrape"
    SCREENS = {"home": HomeScreen}

    def on_mount(self) -> None:
        self.push_screen("home")
