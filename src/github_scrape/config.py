from pathlib import Path
from typing import Any

import platformdirs
import tomlkit

CONFIG_DIR: Path = Path(platformdirs.user_config_dir("github-scrape"))
CONFIG_FILE: Path = CONFIG_DIR / "config.toml"


def load_config() -> dict[str, Any]:
    try:
        content = CONFIG_FILE.read_text()
        return dict(tomlkit.parse(content))
    except (OSError, tomlkit.exceptions.ParseError):
        return {}


def save_config(cfg: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    doc = tomlkit.document()
    for section, values in cfg.items():
        doc[section] = values
    CONFIG_FILE.write_text(tomlkit.dumps(doc))


def get_token() -> str | None:
    cfg = load_config()
    github = cfg.get("github", {})
    if isinstance(github, dict):
        token = github.get("token")
        if isinstance(token, str):
            return token
    return None


def set_token(token: str) -> None:
    cfg = load_config()
    if "github" not in cfg:
        cfg["github"] = {}
    if not isinstance(cfg["github"], dict):
        cfg["github"] = {}
    cfg["github"]["token"] = token
    save_config(cfg)


def get_download_path() -> Path:
    cfg = load_config()
    download = cfg.get("download", {})
    if isinstance(download, dict):
        path = download.get("default_path")
        if isinstance(path, str):
            return Path(path)
    return Path.cwd()


def set_download_path(path: str) -> None:
    p = Path(path)
    if not p.exists():
        raise ValueError(f"Path does not exist: {path}")
    cfg = load_config()
    if "download" not in cfg:
        cfg["download"] = {}
    if not isinstance(cfg["download"], dict):
        cfg["download"] = {}
    cfg["download"]["default_path"] = str(p.resolve())
    save_config(cfg)


def unset_key(section: str, key: str) -> bool:
    cfg = load_config()
    if section in cfg and isinstance(cfg[section], dict) and key in cfg[section]:
        del cfg[section][key]
        if not cfg[section]:
            del cfg[section]
        save_config(cfg)
        return True
    return False


def mask_token(token: str) -> str:
    if len(token) < 8:
        return "********"
    return f"{token[:4]}****{token[-4:]}"


def config_as_display_dict() -> dict[str, str]:
    cfg = load_config()
    result: dict[str, str] = {}

    github = cfg.get("github", {})
    if isinstance(github, dict):
        token = github.get("token")
        if isinstance(token, str):
            result["token"] = mask_token(token)
        else:
            result["token"] = "(not set)"
    else:
        result["token"] = "(not set)"

    download = cfg.get("download", {})
    if isinstance(download, dict):
        path = download.get("default_path")
        if isinstance(path, str):
            result["path"] = path
        else:
            result["path"] = "(not set)"
    else:
        result["path"] = "(not set)"

    return result
