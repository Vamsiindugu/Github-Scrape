import re
from urllib.parse import urlparse


def parse_github_url(url: str) -> tuple[str, str, str, str]:
    url = url.strip()
    if not url:
        raise ValueError("URL cannot be empty")

    if url.startswith("https://github.com/"):
        parsed = urlparse(url)
        if not parsed.netloc == "github.com":
            raise ValueError(f"Invalid GitHub URL: {url}")

        path_parts = [p for p in parsed.path.split("/") if p]
        if len(path_parts) < 2:
            raise ValueError(f"Invalid GitHub URL (missing owner/repo): {url}")

        owner = path_parts[0]
        repo = path_parts[1]

        if len(path_parts) >= 4 and path_parts[2] == "tree":
            branch = path_parts[3]
            subpath = "/".join(path_parts[4:]) if len(path_parts) > 4 else ""
        else:
            branch = ""
            subpath = ""

        return owner, repo, branch, subpath

    if "/" in url and not url.startswith("http"):
        parts = url.split("/", 1)
        if len(parts) == 2:
            owner, repo = parts
            return owner, repo, "", ""
        raise ValueError(f"Invalid shorthand (expected owner/repo): {url}")

    raise ValueError(f"Invalid GitHub URL: {url}")


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    windows_reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
    base = name.upper().split(".")[0] if "." in name else name.upper()
    if base in windows_reserved:
        name = f"_{name}"
    return name
