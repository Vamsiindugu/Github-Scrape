# github-scrape

[![PyPI version](https://img.shields.io/pypi/v/github-scrape.svg)](https://pypi.org/project/github-scrape/)
[![Python version](https://img.shields.io/pypi/pyversions/github-scrape.svg)](https://pypi.org/project/github-scrape/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-green.svg)](https://github.com/vamsi/github-scrape/actions)

A terminal tool to browse, search, and download files from any public/private GitHub repo. Spiritual successor to [ghgrab](https://github.com/abhixdd/ghgrab).

![demo](docs/demo.gif)

## Features

- Browse GitHub repositories in an interactive TUI
- Fuzzy search files with rapidfuzz
- Download selected files with progress tracking
- LFS pointer detection
- Private repo support via GitHub token
- Cross-platform path handling

## Installation

```bash
pip install github-scrape
# or
pipx install github-scrape
```

## Quick Start

```bash
# Launch interactive TUI
github-scrape

# Browse specific repo
github-scrape owner/repo

# Browse with full URL
github-scrape https://github.com/owner/repo
```

## CLI Usage

| Command | Description |
| --- | --- |
| `github-scrape` | Launch interactive TUI |
| `github-scrape owner/repo` | Browse repo (shorthand) |
| `github-scrape https://github.com/owner/repo` | Browse repo (full URL) |
| `github-scrape URL --token TOKEN` | Use token for this session |
| `github-scrape URL --cwd` | Download to current directory |
| `github-scrape URL --no-folder` | Don't create repo subfolder |
| `github-scrape config set token TOKEN` | Save GitHub token |
| `github-scrape config set path PATH` | Set default download path |
| `github-scrape config list` | Show current configuration |
| `github-scrape config unset token` | Remove saved token |

## Keyboard Shortcuts

| Key | Action |
| --- | --- |
| `Enter` | Enter folder / submit URL |
| `Backspace`, `h` | Go to parent folder |
| `/` | Focus search bar |
| `Escape` | Close search / go back |
| `Space` | Toggle file selection |
| `a` | Select all visible files |
| `u` | Unselect all |
| `d` | Download selected files |
| `i` | Toggle emoji/ASCII icons |
| `g` | Jump to first file |
| `G` | Jump to last file |
| `q` | Quit |

## Configuration

Config file location:

- Linux/macOS: `~/.config/github-scrape/config.toml`
- Windows: `%APPDATA%\github-scrape\config.toml`

Configuration keys:

- `github.token` - GitHub personal access token
- `download.default_path` - Default download directory

## Contributing

Contributions welcome! Please run tests before submitting:

```bash
pip install -e ".[dev]"
pip install pytest pytest-asyncio respx mypy ruff
python -m pytest tests/ -v
```

## License

MIT License - see [LICENSE](LICENSE) for details.
