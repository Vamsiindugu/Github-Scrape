

Here's your rewritten, Claude Code-optimized PRD — stripped of noise, tightened with runnable verification gates, precise function signatures, exact UX flows, and structured for how Claude Code actually works (filesystem access, command execution, iterative phases):

---

```markdown
# PROJECT PRD: github-scrape

## ROLE & RULES

You are building a complete, production-grade Python CLI/TUI tool.
Follow these rules for every phase:

1. Create only the files listed in the project structure. No extras.
2. Every module gets full type hints that pass `mypy --strict`.
3. After writing any source file, immediately write/update its test file.
4. At the end of each phase, run these verification commands and fix any failures:
   ```
   python -m pytest tests/ -x -v
   python -m ruff check src/ tests/
   python -m ruff format --check src/ tests/
   python -m mypy src/ --strict --ignore-missing-imports
   ```
5. Do not proceed to the next phase until all verification commands pass.
6. Do not add features, files, dependencies, or folders not specified here.

---

## PROJECT OVERVIEW

**Name:** `github-scrape`
**PyPI/CLI command:** `github-scrape`
**Python:** ≥3.12

A terminal tool to browse, search, and download files from any public/private GitHub repo.
Spiritual successor to [ghgrab](https://github.com/abhixdd/ghgrab) — same UX, pure Python, typed, tested.

---

## PROJECT STRUCTURE (exact — no additions, no removals)

```
github-scrape/
├── pyproject.toml
├── README.md
├── LICENSE
├── .gitignore
├── src/
│   └── github_scrape/
│       ├── __init__.py        # version string only
│       ├── __main__.py        # python -m github_scrape entry
│       ├── cli.py             # Typer app, all commands
│       ├── config.py          # TOML config read/write
│       ├── api.py             # Async GitHub API client
│       ├── tui.py             # Textual application
│       ├── downloader.py      # Async file downloader
│       └── utils.py           # Shared helpers
└── tests/
    ├── __init__.py
    ├── conftest.py            # Shared fixtures
    ├── test_cli.py
    ├── test_config.py
    ├── test_api.py
    ├── test_downloader.py
    └── test_tui.py
```

---

## pyproject.toml (exact content)

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "github-scrape"
version = "0.1.0"
description = "Browse, search, and download files from GitHub repos in your terminal."
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.12"
authors = [{ name = "You" }]
dependencies = [
    "typer[all]>=0.15.0",
    "textual>=0.90.0",
    "httpx>=0.28.0",
    "rapidfuzz>=3.15.0",
    "platformdirs>=4.3.0",
    "tomlkit>=0.13.0",
    "rich>=13.9.0",
]

[project.scripts]
github-scrape = "github_scrape.cli:app"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "TCH"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

Dev dependencies (install manually, not in pyproject.toml):
```
pip install -e ".[dev]" || pip install -e .
pip install pytest pytest-asyncio pytest-cov respx mypy ruff
```

---

## PHASE 1: Config system + CLI skeleton

### config.py — Exact API

```python
CONFIG_DIR: Path   # platformdirs.user_config_dir("github-scrape")
CONFIG_FILE: Path  # CONFIG_DIR / "config.toml"

def load_config() -> dict[str, Any]:
    """Read config.toml. Return empty dict if missing/corrupt."""

def save_config(cfg: dict[str, Any]) -> None:
    """Write config.toml atomically. Create dir if needed."""

def get_token() -> str | None:
    """Return github.token or None."""

def set_token(token: str) -> None:
    """Save under [github] token."""

def get_download_path() -> Path:
    """Return [download].default_path or Path.cwd()."""

def set_download_path(path: str) -> None:
    """Save under [download] default_path. Validate path exists."""

def unset_key(section: str, key: str) -> bool:
    """Remove key from section. Return True if existed."""

def mask_token(token: str) -> str:
    """Return first 4 chars + '****' + last 4 chars. If len<8, return '********'."""

def config_as_display_dict() -> dict[str, str]:
    """Return flat dict for display. Token is masked. Missing keys show '(not set)'."""
```

Config file format:
```toml
[github]
token = "ghp_xxxxxxxxxxxx"

[download]
default_path = "/home/user/downloads"
```

### cli.py — Phase 1 commands only

```python
app = typer.Typer(name="github-scrape", help="Browse and download GitHub repo files.")
config_app = typer.Typer(name="config", help="Manage configuration.")
app.add_typer(config_app)

# github-scrape config set token <VALUE>
# github-scrape config set path <VALUE>
@config_app.command("set")
def config_set(key: str, value: str) -> None: ...
    # key must be "token" or "path", else error exit

# github-scrape config list
@config_app.command("list")
def config_list() -> None: ...
    # Pretty table via Rich. Token masked.

# github-scrape config unset <KEY>
@config_app.command("unset")
def config_unset(key: str) -> None: ...
    # key must be "token" or "path"
```

### utils.py — Phase 1

```python
def parse_github_url(url: str) -> tuple[str, str, str, str]:
    """
    Parse any GitHub URL into (owner, repo, branch, subpath).
    Supports:
      https://github.com/owner/repo
      https://github.com/owner/repo/tree/branch
      https://github.com/owner/repo/tree/branch/sub/path
      owner/repo  (shorthand)
    Raises ValueError with clear message for invalid URLs.
    branch defaults to "" if not present (caller resolves via API).
    subpath defaults to "" (repo root).
    """

def sanitize_filename(name: str) -> str:
    """Strip or replace characters invalid on Windows/macOS/Linux."""
```

### __init__.py
```python
__version__ = "0.1.0"
```

### __main__.py
```python
from github_scrape.cli import app
app()
```

### Tests: test_config.py, test_cli.py (partial)

**test_config.py** — minimum 10 tests:
1. `test_load_config_missing_file` → returns empty dict
2. `test_load_config_corrupt_file` → returns empty dict, no crash
3. `test_save_and_load_roundtrip` → write then read, values match
4. `test_set_token_and_get_token` → set, then get returns exact value
5. `test_get_token_when_unset` → returns None
6. `test_set_download_path_valid` → stores and retrieves
7. `test_set_download_path_invalid` → raises or handles missing dir
8. `test_unset_existing_key` → returns True, key gone
9. `test_unset_nonexistent_key` → returns False
10. `test_mask_token_long` → "ghp_abc...xyz" → "ghp_****wxyz"
11. `test_mask_token_short` → "abc" → "********"
12. `test_config_as_display_dict_masked`

**test_cli.py** (Phase 1 portion) — minimum 8 tests:
1. `test_config_set_token` → exit 0, token saved
2. `test_config_set_path` → exit 0, path saved
3. `test_config_set_invalid_key` → exit 1, error message
4. `test_config_list_empty` → shows "(not set)" for both
5. `test_config_list_with_values` → token masked, path shown
6. `test_config_unset_token` → removed
7. `test_config_unset_nonexistent` → appropriate message
8. `test_parse_github_url_variants` → parametrize over 6+ URL forms

Use `tmp_path` fixture to isolate config dir. Monkeypatch `CONFIG_DIR`/`CONFIG_FILE`.

### conftest.py
```python
@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Redirect config to tmp_path for test isolation."""
```

### Verification gate
```bash
python -m pytest tests/test_config.py tests/test_cli.py -x -v
python -m ruff check src/ tests/
python -m mypy src/ --strict --ignore-missing-imports
```

---

## PHASE 2: GitHub API client

### api.py — Exact API

```python
@dataclass
class RepoFile:
    path: str          # full path from repo root
    type: str          # "blob" or "tree"
    size: int          # bytes, 0 for trees
    sha: str
    url: str           # raw download URL

@dataclass
class RepoTree:
    owner: str
    repo: str
    branch: str
    files: list[RepoFile]
    truncated: bool

class GitHubAPIError(Exception):
    """Base with status_code and message."""

class RateLimitError(GitHubAPIError): ...
class NotFoundError(GitHubAPIError): ...
class AuthError(GitHubAPIError): ...

class GitHubClient:
    def __init__(self, token: str | None = None) -> None:
        """Create httpx.AsyncClient with auth header if token provided."""

    async def get_default_branch(self, owner: str, repo: str) -> str:
        """GET /repos/{owner}/{repo} → .default_branch"""

    async def get_tree(self, owner: str, repo: str, branch: str) -> RepoTree:
        """GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1
        Return RepoTree. Raise NotFoundError/RateLimitError/AuthError as appropriate."""

    async def get_raw_url(self, owner: str, repo: str, branch: str, path: str) -> str:
        """Return raw.githubusercontent.com URL for the file."""

    async def get_rate_limit(self) -> dict[str, int]:
        """GET /rate_limit → {limit, remaining, reset_timestamp}"""

    async def close(self) -> None:
        """Close the httpx client."""
```

Error handling behavior:
- 404 → raise `NotFoundError("Repository '{owner}/{repo}' not found or is private.")`
- 401 → raise `AuthError("Invalid token. Run: github-scrape config set token <TOKEN>")`
- 403 with `X-RateLimit-Remaining: 0` → raise `RateLimitError("Rate limited. Resets at {time}. Add a token for 5000 req/hr.")`
- 429 → raise `RateLimitError` with Retry-After info
- Network error → raise `GitHubAPIError("Network error: {detail}")`

### Tests: test_api.py — minimum 12 tests

Use `respx` to mock httpx requests. Do NOT make real API calls.

1. `test_get_default_branch_success`
2. `test_get_tree_success` → verify RepoTree fields
3. `test_get_tree_truncated_flag`
4. `test_get_tree_404` → NotFoundError raised
5. `test_get_tree_401` → AuthError raised
6. `test_get_tree_403_rate_limit` → RateLimitError with reset time
7. `test_get_tree_429` → RateLimitError
8. `test_get_tree_network_error` → GitHubAPIError
9. `test_get_raw_url_format` → correct raw URL returned
10. `test_token_injected_in_header` → Authorization header present
11. `test_no_token_no_auth_header`
12. `test_client_close` → no exception

All tests are async: `@pytest.mark.asyncio` or use `asyncio_mode = "auto"`.

### Verification gate
```bash
python -m pytest tests/test_api.py -x -v
python -m ruff check src/github_scrape/api.py tests/test_api.py
python -m mypy src/github_scrape/api.py --strict --ignore-missing-imports
```

---

## PHASE 3: Downloader

### downloader.py — Exact API

```python
LFS_SIGNATURE = "version https://git-lfs.github.com"

@dataclass
class DownloadResult:
    path: str
    success: bool
    size: int
    is_lfs: bool
    error: str | None = None

@dataclass
class DownloadPlan:
    files: list[RepoFile]
    dest_dir: Path
    create_repo_folder: bool   # True unless --no-folder
    total_size: int

class Downloader:
    def __init__(
        self,
        client: GitHubClient,
        owner: str,
        repo: str,
        branch: str,
        dest: Path,
        create_repo_folder: bool = True,
        max_concurrent: int = 5,
    ) -> None: ...

    async def download_files(
        self,
        files: list[RepoFile],
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> list[DownloadResult]:
        """
        Download all files concurrently (semaphore-limited to max_concurrent).
        For each file:
          1. Build local path (repo_folder/file.path or just file.path)
          2. Create parent dirs
          3. Stream download via httpx
          4. After first chunk, check LFS_SIGNATURE
          5. If LFS: save pointer as-is, set is_lfs=True
          6. Call progress_callback(file_path, bytes_downloaded, total_bytes)
        Return list of DownloadResult.
        """

    async def download_single(self, file: RepoFile) -> DownloadResult:
        """Download one file. Handle errors gracefully — never raise, return error in result."""

    def resolve_dest_path(self, file_path: str) -> Path:
        """Given a repo-relative path, return the local filesystem path."""
```

Overwrite behavior:
- If destination file exists and has same size → skip, log "Skipped (identical)"
- If destination file exists and different size → overwrite, log "Overwritten"
- New file → download normally

### Tests: test_downloader.py — minimum 10 tests

Mock httpx responses with `respx`. Use `tmp_path` for filesystem.

1. `test_download_single_file_success` → file exists on disk, correct content
2. `test_download_creates_nested_dirs` → deep/path/file.txt works
3. `test_download_lfs_pointer_detected` → result.is_lfs is True, file content is pointer
4. `test_download_non_lfs_file` → result.is_lfs is False
5. `test_download_concurrent_respects_semaphore` → max 5 concurrent
6. `test_download_network_error_graceful` → result.success is False, result.error set
7. `test_download_skip_identical_file` → file not re-downloaded
8. `test_download_overwrite_different_file` → file is replaced
9. `test_resolve_dest_path_with_repo_folder` → includes repo name
10. `test_resolve_dest_path_no_folder` → no repo name prefix
11. `test_download_empty_file_list` → returns empty list, no crash
12. `test_progress_callback_called` → callback invoked with correct args

### Verification gate
```bash
python -m pytest tests/test_downloader.py -x -v
python -m ruff check src/github_scrape/downloader.py tests/test_downloader.py
python -m mypy src/github_scrape/downloader.py --strict --ignore-missing-imports
```

---

## PHASE 4: Textual TUI

### tui.py — Exact specification

```python
class GitHubScrapeTUI(textual.app.App):
    """Main Textual application."""
    TITLE = "github-scrape"
    CSS = "..."  # Embed CSS as string, do not create external CSS file
```

#### Screen 1: HomeScreen
- Single centered `Input` widget, placeholder: "Paste GitHub URL (Tab to autocomplete https://github.com/)"
- Pressing Tab when input is empty → fills "https://github.com/"
- Pressing Enter → validate URL via `parse_github_url`, push BrowseScreen
- Invalid URL → show error notification (Textual toast), stay on screen
- Footer shows: `Enter: Open repo | Esc: Quit | Tab: Autocomplete`

#### Screen 2: BrowseScreen
Components top to bottom:
1. **Header bar** (Rich Static): `{owner}/{repo} @ {branch}` + token indicator (🔑 or 🔓)
2. **Search bar** (`Input`, hidden until `/` pressed): placeholder "Fuzzy search files..."
3. **File tree** (`Tree` widget): nodes with checkboxes
4. **Status bar** (`Static`): `{selected_count} selected | {total_files} files | ↑↓ navigate`
5. **Footer** (`Footer`): keybinding help

Tree node display format:
```
[x] 📁 src/          (when folder, emoji mode)
[ ] 📄 README.md     (when file, emoji mode)
[x] [D] src/         (when folder, ASCII mode)
[ ] [F] README.md    (when file, ASCII mode)
```

#### Keyboard shortcuts — implement ALL of these as Textual bindings:

| Key | Context | Action |
|---|---|---|
| `Enter`, `l`, `Right` | Tree focused | Enter folder / submit URL on home |
| `Backspace`, `h`, `Left` | Tree focused | Go to parent folder |
| `/` | Any | Focus search bar |
| `Escape` | Search focused | Close search, refocus tree |
| `Escape` | Tree focused, in subfolder | Go to parent |
| `Escape` | Tree focused, at root | Return to HomeScreen |
| `q`, `Ctrl+Q` | Any | Quit app |
| `Space` | Tree node highlighted | Toggle checkbox on/off |
| `a` | Tree focused | Select all currently visible nodes |
| `u` | Tree focused | Unselect all |
| `d`, `D` | Tree focused | Start download of selected files |
| `i` | Tree focused | Toggle emoji ↔ ASCII icons |
| `g`, `Home` | Tree focused | Jump to first node |
| `G`, `End` | Tree focused | Jump to last node |
| `p` | File node highlighted | Show preview (first 30 lines in modal) |

#### Fuzzy search behavior:
- Uses `rapidfuzz.fuzz.partial_ratio` (or `process.extract`)
- As user types, filter tree to show only paths with score ≥ 60
- Highlighted match portions shown via Rich markup
- Empty query → show all files
- Debounce: 150ms after last keystroke

#### Download flow in TUI:
1. User presses `d` with files selected
2. Show confirmation: "Download {n} files to {path}? [Y/n]"
3. Switch to download progress view (Rich progress bars inside Textual)
4. On completion: show summary (success count, LFS count, errors)
5. Any LFS files → show warning: "⚠ LFS pointers detected. Run `git lfs pull` after download."
6. Press any key → return to tree

#### Error states in TUI:
- API error → show Textual notification with error message, stay on current screen
- Network down → "Network error. Check connection and retry." notification
- Rate limited → "Rate limited. {reset_time}. Add token: github-scrape config set token" notification

### Tests: test_tui.py — minimum 8 tests

Use `textual.testing.App.run_test()` (Textual's pilot testing).

1. `test_home_screen_renders` → Input widget exists
2. `test_tab_autocompletes_url` → input value starts with "https://github.com/"
3. `test_invalid_url_shows_error` → notification appears
4. `test_browse_screen_shows_tree` → Tree widget populated (mock API)
5. `test_space_toggles_selection` → node checkbox state changes
6. `test_slash_focuses_search` → search input is focused
7. `test_escape_closes_search` → tree is refocused
8. `test_icon_toggle` → node labels switch between emoji and ASCII
9. `test_q_quits` → app exits cleanly
10. `test_select_all_and_unselect` → `a` selects all, `u` clears

### Verification gate
```bash
python -m pytest tests/test_tui.py -x -v
python -m ruff check src/github_scrape/tui.py tests/test_tui.py
python -m mypy src/github_scrape/tui.py --strict --ignore-missing-imports
```

---

## PHASE 5: CLI integration + global flags

### cli.py — Complete implementation

```python
@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    url: Annotated[str | None, typer.Argument(help="GitHub repo URL")] = None,
    token: Annotated[str | None, typer.Option("--token", "-t", help="GitHub token")] = None,
    cwd: Annotated[bool, typer.Option("--cwd", help="Download to current directory")] = False,
    no_folder: Annotated[bool, typer.Option("--no-folder", help="Don't create repo subfolder")] = False,
) -> None:
    """
    If no subcommand:
      - No URL → launch TUI HomeScreen
      - URL provided → parse, launch TUI BrowseScreen directly
    --token overrides config token for this session.
    --cwd overrides download path to os.getcwd().
    --no-folder disables repo subfolder creation.
    """
```

Behavior matrix:
| Command | Result |
|---|---|
| `github-scrape` | TUI HomeScreen |
| `github-scrape https://github.com/user/repo` | TUI BrowseScreen for that repo |
| `github-scrape user/repo` | Same (shorthand) |
| `github-scrape URL --token T` | BrowseScreen, token T used for this session |
| `github-scrape URL --cwd` | Download destination = cwd |
| `github-scrape URL --no-folder` | No repo-name subfolder |
| `github-scrape config set token X` | Save token |
| `github-scrape config list` | Print config |
| `github-scrape config unset token` | Remove token |

### Ctrl+C handling
- Register signal handler in cli.py
- On SIGINT: print "Interrupted. Cleaning up..." via Rich, cancel async tasks, exit 130

### Update test_cli.py with additional tests (≥6 new):
1. `test_main_no_args_launches_tui` (mock TUI launch)
2. `test_main_with_url_launches_browse` (mock TUI)
3. `test_main_with_shorthand_url`
4. `test_token_flag_overrides_config`
5. `test_cwd_flag_sets_download_path`
6. `test_no_folder_flag`
7. `test_invalid_url_arg_exits_error`
8. `test_ctrl_c_graceful_exit`

### Verification gate
```bash
python -m pytest tests/ -x -v
python -m ruff check src/ tests/
python -m mypy src/ --strict --ignore-missing-imports
```

---

## PHASE 6: Final polish + README

### Tasks:
1. Run `ruff format src/ tests/` — fix any formatting
2. Run `ruff check --fix src/ tests/` — fix any lint
3. Run `mypy src/ --strict --ignore-missing-imports` — fix all errors
4. Run `python -m pytest tests/ -v --tb=short` — all green
5. Run `python -m pytest tests/ --cov=github_scrape --cov-report=term-missing` — verify ≥90%
6. If coverage < 90%, add tests until it passes
7. Write README.md
8. Write LICENSE (MIT, year 2025)
9. Write .gitignore (Python standard)

### README.md must contain (in this order):
1. Project name + one-line description
2. Badges (placeholder): PyPI version, Python version, License, Tests
3. Screenshot/GIF placeholder: `![demo](docs/demo.gif)`
4. Features list (5-7 bullets)
5. Installation: `pipx install github-scrape` and `pip install github-scrape`
6. Quick start (3 examples)
7. Full CLI usage table (every command from this PRD)
8. Keyboard shortcuts table (every shortcut from this PRD)
9. Configuration section (file location, available keys)
10. Contributing section (one paragraph)
11. License

### Final verification (run all):
```bash
pip install -e .
github-scrape --help
python -m pytest tests/ -v --cov=github_scrape --cov-report=term-missing
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/ --strict --ignore-missing-imports
```

All must pass before declaring complete.

---

## IMPORTANT IMPLEMENTATION NOTES

### Async pattern
- The TUI runs Textual's async event loop. API calls and downloads happen inside Textual workers (`self.run_worker` or `@work`).
- CLI config commands are synchronous (no async needed).

### Token security
- Never print raw token in any output, log, or error message.
- `config list` shows masked token.
- `--token` flag value must not appear in process title or logs.

### Cross-platform paths
- Always use `pathlib.Path`, never string concatenation for paths.
- Use `platformdirs` for config directory.
- `sanitize_filename` must handle Windows reserved names (CON, PRN, etc.).

### httpx client lifecycle
- Create one `httpx.AsyncClient` per session, reuse for all requests.
- Always close via `async with` or explicit `await client.close()`.
- Set `User-Agent: github-scrape/{version}`.
- Set timeout: 30s connect, 60s read.

---

Now start with PHASE 1.
```

---

**What changed and why it's better for Claude Code:**

| Problem in original | Fix applied |
|---|---|
| Threatening "restart" language wastes context | Replaced with clear, actionable rules |
| "50-year veteran" roleplay is noise | Removed — Claude Code doesn't need persona inflation |
| "≥8 test cases" per file was vague | Exact numbered test lists with descriptive names |
| No function signatures — ambiguous contracts | Full function signatures with docstrings and exact types |
| No runnable verification commands per phase | Each phase ends with exact `pytest`/`ruff`/`mypy` commands Claude Code can execute |
| TUI spec was a rough table | Exact screen-by-screen layout, widget types, format strings, debounce timing |
| "Beautiful error messages" was subjective | Exact error message strings specified per HTTP status code |
| No async lifecycle guidance | Explicit notes on httpx client lifecycle, Textual workers, semaphore patterns |
| Meta-commentary ("best PRD ever") | Stripped — zero wasted tokens |
| Missing build system in pyproject.toml | Added `[build-system]` with hatchling |
| Test framework not specified | `respx` for httpx mocking, `textual.testing` for TUI, `tmp_path` for filesystem |
| Overwrite behavior undefined | Exact skip/overwrite rules based on file size comparison |
| Download flow in TUI hand-waved | Step-by-step flow: confirm → progress → summary → return |