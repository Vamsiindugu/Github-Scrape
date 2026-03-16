from dataclasses import dataclass
from datetime import datetime

import httpx


@dataclass
class RepoFile:
    path: str
    type: str
    size: int
    sha: str
    url: str


@dataclass
class RepoTree:
    owner: str
    repo: str
    branch: str
    files: list[RepoFile]
    truncated: bool


class GitHubAPIError(Exception):
    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(GitHubAPIError):
    pass


class NotFoundError(GitHubAPIError):
    pass


class AuthError(GitHubAPIError):
    pass


class GitHubClient:
    def __init__(self, token: str | None = None) -> None:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "github-scrape/0.1.0",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(connect=30.0, read=60.0, write=60.0, pool=30.0),
        )
        self._token = token

    async def get_default_branch(self, owner: str, repo: str) -> str:
        url = f"https://api.github.com/repos/{owner}/{repo}"
        resp = await self._client.get(url)
        if resp.status_code == 404:
            raise NotFoundError(f"Repository '{owner}/{repo}' not found or is private.", 404)
        if resp.status_code == 401:
            raise AuthError("Invalid token. Run: github-scrape config set token <TOKEN>", 401)
        if resp.status_code == 403:
            remaining = resp.headers.get("X-RateLimit-Remaining", "unknown")
            if remaining == "0":
                reset_ts = int(resp.headers.get("X-RateLimit-Reset", "0"))
                reset_time = datetime.fromtimestamp(reset_ts).strftime("%H:%M:%S")
                raise RateLimitError(
                    f"Rate limited. Resets at {reset_time}. Add a token for 5000 req/hr.",
                    403,
                )
        resp.raise_for_status()
        data = resp.json()
        return str(data.get("default_branch", "main"))

    async def get_tree(self, owner: str, repo: str, branch: str) -> RepoTree:
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        resp = await self._client.get(url)
        if resp.status_code == 404:
            raise NotFoundError(f"Repository '{owner}/{repo}' or branch '{branch}' not found.", 404)
        if resp.status_code == 401:
            raise AuthError("Invalid token. Run: github-scrape config set token <TOKEN>", 401)
        if resp.status_code == 403:
            remaining = resp.headers.get("X-RateLimit-Remaining", "unknown")
            if remaining == "0":
                reset_ts = int(resp.headers.get("X-RateLimit-Reset", "0"))
                reset_time = datetime.fromtimestamp(reset_ts).strftime("%H:%M:%S")
                raise RateLimitError(
                    f"Rate limited. Resets at {reset_time}. Add a token for 5000 req/hr.",
                    403,
                )
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "unknown")
            raise RateLimitError(
                f"Rate limited. Retry after {retry_after} seconds.",
                429,
            )
        resp.raise_for_status()
        data = resp.json()
        files: list[RepoFile] = []
        for item in data.get("tree", []):
            path = str(item.get("path", ""))
            item_type = str(item.get("type", "blob"))
            size = int(item.get("size", 0))
            sha = str(item.get("sha", ""))
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
            files.append(RepoFile(path=path, type=item_type, size=size, sha=sha, url=raw_url))
        return RepoTree(
            owner=owner,
            repo=repo,
            branch=branch,
            files=files,
            truncated=bool(data.get("truncated", False)),
        )

    async def get_raw_url(self, owner: str, repo: str, branch: str, path: str) -> str:
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"

    async def get_rate_limit(self) -> dict[str, int]:
        url = "https://api.github.com/rate_limit"
        resp = await self._client.get(url)
        resp.raise_for_status()
        data = resp.json()
        resources = data.get("resources", {})
        core = resources.get("core", {})
        return {
            "limit": int(core.get("limit", 0)),
            "remaining": int(core.get("remaining", 0)),
            "reset_timestamp": int(core.get("reset", 0)),
        }

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
