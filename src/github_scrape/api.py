from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0


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
            "User-Agent": "github-scrape-project/0.1.1",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(connect=30.0, read=60.0, write=60.0, pool=30.0),
        )
        self._token = token

    def _validate_response(self, resp: httpx.Response, context: str = "") -> None:
        if resp.status_code == 404:
            raise NotFoundError(f"{context} not found or is private.", 404)
        if resp.status_code == 401:
            raise AuthError("Invalid token. Run: github-scrape config set token <TOKEN> (Github Scrape Project)", 401)
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

    async def _request_with_retry(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.request(method, url, **kwargs)
                self._validate_response(resp, url)
                return resp
            except (httpx.ConnectError, httpx.ReadError, httpx.WriteError) as e:
                last_error = e
                wait_time = RETRY_BACKOFF_BASE * (2**attempt)
                logger.warning(f"Network error on {url}, retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
            except RateLimitError:
                raise
            except GitHubAPIError:
                raise
            except httpx.HTTPStatusError as e:
                if 500 <= e.response.status_code < 600:
                    last_error = e
                    wait_time = RETRY_BACKOFF_BASE * (2**attempt)
                    logger.warning(f"Server error {e.response.status_code}, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    raise
        raise last_error or GitHubAPIError(f"Failed to fetch {url} after {MAX_RETRIES} retries")

    async def get_default_branch(self, owner: str, repo: str) -> str:
        url = f"https://api.github.com/repos/{owner}/{repo}"
        resp = await self._request_with_retry("GET", url)
        data = resp.json()
        return str(data.get("default_branch", "main"))

    async def get_tree(self, owner: str, repo: str, branch: str) -> RepoTree:
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        resp = await self._request_with_retry("GET", url)
        data = resp.json()
        files: list[RepoFile] = []
        for item in data.get("tree", []):
            path = str(item.get("path", ""))
            item_type = str(item.get("type", "blob"))
            size = int(item.get("size", 0))
            sha = str(item.get("sha", ""))
            raw_url = self.get_raw_url(owner, repo, branch, path)
            files.append(RepoFile(path=path, type=item_type, size=size, sha=sha, url=raw_url))
        return RepoTree(
            owner=owner,
            repo=repo,
            branch=branch,
            files=files,
            truncated=bool(data.get("truncated", False)),
        )

    @staticmethod
    def get_raw_url(owner: str, repo: str, branch: str, path: str) -> str:
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"

    async def fetch_raw(self, url: str) -> bytes:
        """Fetch raw content from a URL with retry logic."""
        resp = await self._request_with_retry("GET", url)
        return resp.content

    async def stream_raw(self, url: str) -> AsyncIterator[bytes]:
        """Stream raw content from a URL with retry logic."""
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                async with self._client.stream("GET", url) as resp:
                    self._validate_response(resp, url)
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                return
            except (httpx.ConnectError, httpx.ReadError, httpx.WriteError) as e:
                last_error = e
                wait_time = RETRY_BACKOFF_BASE * (2**attempt)
                logger.warning(f"Stream error on {url}, retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
            except RateLimitError:
                raise
            except GitHubAPIError:
                raise
        raise last_error or GitHubAPIError(f"Failed to stream {url} after {MAX_RETRIES} retries")

    async def get_rate_limit(self) -> dict[str, int]:
        url = "https://api.github.com/rate_limit"
        resp = await self._request_with_retry("GET", url)
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

    async def __aenter__(self) -> GitHubClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
