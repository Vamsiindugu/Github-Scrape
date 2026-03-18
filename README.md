<div align="center">

# github-scrape

[![PyPI](https://img.shields.io/pypi/v/github-scrape?color=blue)](https://pypi.org/project/github-scrape/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://pypi.org/project/github-scrape/)
[![Tests](https://github.com/Vamsiindugu/Github-Scrape/workflows/CI/badge.svg)](https://github.com/Vamsiindugu/Github-Scrape/actions)
[![Coverage](https://img.shields.io/badge/coverage-85%25-green)](https://github.com/Vamsiindugu/Github-Scrape/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Browse, search & download files from GitHub repos — without cloning**

*A fast terminal UI for cherry-picking exactly what you need*

[Installation](#installation) • [Usage](#usage) • [Features](#features) • [Contributing](#contributing)

</div>

![Demo](Demo.png)

---

## Quick Start

```bash
# Install
pipx install github-scrape

# Run — that's it
github-scrape

# Or go directly to a repo
github-scrape python/cpython
```

---

## Why github-scrape?

| You want to... | With git | With github-scrape |
|---------------|----------|-------------------|
| Grab one file from a repo | `git clone` → find file → `rm -rf` | Select → Download ✓ |
| Browse a large repo | Clone 500MB | Browse instantly |
| Search files | `find . -name "*.py"` | Type `/query` |
| View before downloading | Open browser | Built-in preview |

---

## Installation

```bash
# Recommended: pipx (isolated environment)
pipx install github-scrape

# Or with pip
pip install github-scrape
```

Requires Python 3.12+

---

## Usage

### Launch TUI
```bash
github-scrape
```

Then: Enter repo URL → Browse → Press `d` to download

### Direct to repo
```bash
# Full URL or shorthand
github-scrape facebook/react
github-scrape https://github.com/torvalds/linux

# Private repos
github-scrape owner/private-repo --token YOUR_GITHUB_TOKEN
```

### Configuration
```bash
# Save your GitHub token
github-scrape config set token ghp_xxxxxxxxxxx

# Set default download path
github-scrape config set path ~/Downloads/repos
```

---

## Features

- ⚡ **Fuzzy search** — Find files instantly
- 📊 **Preview pane** — View content before downloading
- 📦 **Batch select** — Download multiple files/folders
- 🔐 **Private repos** — GitHub token support
- 💾 **Smart paths** — Preserves repo structure
- 🎨 **Dual themes** — Emoji 📁 or ASCII `[D]` icons
- ⚡ **Async I/O** — Parallel downloads

---

## Keyboard Shortcuts

| Navigation | Selection | Actions |
|-----------|-----------|---------|
| `↑/↓` or `j/k` — Move | `Space` — Toggle select | `d` — Download |
| `Enter`/`l` — Open | `a` — Select all | `i` — Toggle theme |
| `h`/`Backspace` — Up | `u` — Unselect all | `o` — Open folder |
| `g`/`G` — First/last | | `q` — Quit |
| `/` — Search | | `Ctrl+C` — Force quit |

---

## Development

```bash
git clone https://github.com/Vamsiindugu/Github-Scrape.git
cd Github-Scrape

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run checks
ruff check src/ && mypy src/
```

---

## Troubleshooting

**"No module named github_scrape"**
→ Use `pipx` instead of `pip`

**"Rate limit exceeded"**
→ Set a GitHub token: `github-scrape config set token TOKEN`

**"Permission denied" on download**
→ Check write permissions on download path

---

## Tech Stack

| Component | Library |
|-----------|---------|
| CLI | [Typer](https://github.com/tiangolo/typer) |
| TUI | [Textual](https://github.com/Textualize/textual) |
| HTTP | [httpx](https://github.com/encode/httpx) |
| Search | [rapidfuzz](https://github.com/maxbachmann/rapidfuzz) |

---

## License

MIT © [Vamsi Indugu](https://github.com/Vamsiindugu)
