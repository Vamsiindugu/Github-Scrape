from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from github_scrape.logging_cfg import get_logger

logger = get_logger("api")

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0
RETRY_JITTER_MAX = 0.5


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


@dataclass
class RateLimitInfo:
    limit: int = 0
    remaining: int = 0
    reset_timestamp: int = 0
    last_updated: float = 0.0

    @property
    def is_limited(self) -> bool:
        return self.remaining <= 0

    @property
    def reset_datetime(self) -> str:
        if self.reset_timestamp == 0:
            return "unknown"
        return datetime.fromtimestamp(self.reset_timestamp).strftime("%H:%M:%S")

    @property
    def seconds_until_reset(self) -> int:
        if self.reset_timestamp == 0:
            return 0
        return max(0, int(self.reset_timestamp - time.time()))


class GitHubAPIError(Exception):
    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(GitHubAPIError):
    def __init__(self, message: str, status_code: int = 0, retry_after: int | None = None) -> None:
        super().__init__(message, status_code)
        self.retry_after = retry_after


class NotFoundError(GitHubAPIError):
    pass


class AuthError(GitHubAPIError):
    pass


class TreeCache:
    def __init__(self, ttl: float = 300.0) -> None:
        self._cache: dict[str, tuple[float, RepoTree]] = {}
        self._ttl = ttl

    def _key(self, owner: str, repo: str, branch: str) -> str:
        return f"{owner}/{repo}/{branch}"

    def get(self, owner: str, repo: str, branch: str) -> RepoTree | None:
        key = self._key(owner, repo, branch)
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, tree = entry
        if time.time() - ts > self._ttl:
            del self._cache[key]
            return None
        return tree

    def put(self, owner: str, repo: str, branch: str, tree: RepoTree) -> None:
        key = self._key(owner, repo, branch)
        self._cache[key] = (time.time(), tree)

    def invalidate(self, owner: str | None = None, repo: str | None = None, branch: str | None = None) -> int:
        if owner is None:
            count = len(self._cache)
            self._cache.clear()
            return count
        prefix = f"{owner}/" if repo is None else self._key(owner, repo, branch or "")
        to_remove = [k for k in self._cache if k.startswith(prefix)]
        for k in to_remove:
            del self._cache[k]
        return len(to_remove)

    @property
    def size(self) -> int:
        return len(self._cache)


def _backoff_with_jitter(attempt: int) -> float:
    base_wait: float = RETRY_BACKOFF_BASE * (2 ** attempt)
    jitter: float = random.uniform(0, RETRY_JITTER_MAX)
    return base_wait + jitter


class GitHubClient:
    def __init__(self, token: str | None = None, cache_ttl: float = 300.0) -> None:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "github-scrape/0.2.0",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(connect=30.0, read=60.0, write=60.0, pool=30.0),
        )
        self._token = token
        self._rate_limit = RateLimitInfo()
        self._cache = TreeCache(ttl=cache_ttl)
        self._request_count = 0

    @property
    def rate_limit_info(self) -> RateLimitInfo:
        return self._rate_limit

    @property
    def cache(self) -> TreeCache:
        return self._cache

    def _update_rate_limit_from_headers(self, headers: httpx.Headers) -> None:
        try:
            remaining = headers.get("X-RateLimit-Remaining")
            limit = headers.get("X-RateLimit-Limit")
            reset = headers.get("X-RateLimit-Reset")
            if remaining is not None:
                self._rate_limit.remaining = int(remaining)
            if limit is not None:
                self._rate_limit.limit = int(limit)
            if reset is not None:
                self._rate_limit.reset_timestamp = int(reset)
            self._rate_limit.last_updated = time.time()
        except (ValueError, TypeError):
            pass

    def _validate_response(self, resp: httpx.Response, context: str = "") -> None:
        self._update_rate_limit_from_headers(resp.headers)
        if resp.status_code == 404:
            raise NotFoundError(f"{context} not found or is private.", 404)
        if resp.status_code == 401:
            raise AuthError("Invalid token. Run: github-scrape config set token <TOKEN>", 401)
        if resp.status_code == 403 and self._rate_limit.is_limited:
            raise RateLimitError(
                f"Rate limited. Resets at {self._rate_limit.reset_datetime}. "
                f"Add a token for 5000 req/hr.",
                403,
                retry_after=self._rate_limit.seconds_until_reset,
            )
        if resp.status_code == 429:
            retry_after_str = resp.headers.get("Retry-After", "60")
            try:
                retry_after = int(retry_after_str)
            except ValueError:
                retry_after = 60
            raise RateLimitError(
                f"Rate limited. Retry after {retry_after} seconds.",
                429,
                retry_after=retry_after,
            )
        resp.raise_for_status()

    async def _request_with_retry(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                self._request_count += 1
                resp = await self._client.request(method, url, **kwargs)
                self._validate_response(resp, url)
                return resp
            except RateLimitError as e:
                if e.retry_after and e.retry_after > 0 and attempt == 0:
                    logger.warning(f"Rate limited on {url}. Waiting {e.retry_after}s before retry.")
                    await asyncio.sleep(e.retry_after)
                    continue
                raise
            except (httpx.ConnectError, httpx.ReadError, httpx.WriteError) as e:
                last_error = e
                wait = _backoff_with_jitter(attempt)
                logger.warning(f"Network error on {url}, retry {attempt+1}/{MAX_RETRIES} in {wait:.1f}s: {e}")
                await asyncio.sleep(wait)
            except GitHubAPIError:
                raise
            except httpx.HTTPStatusError as e:
                if 500 <= e.response.status_code < 600:
                    last_error = e
                    wait = _backoff_with_jitter(attempt)
                    logger.warning(f"Server error {e.response.status_code} on {url}, retry {attempt+1}/{MAX_RETRIES} in {wait:.1f}s")
                    await asyncio.sleep(wait)
                else:
                    raise
        raise last_error or GitHubAPIError(f"Failed to fetch {url} after {MAX_RETRIES} retries")

    async def get_default_branch(self, owner: str, repo: str) -> str:
        url = f"https://api.github.com/repos/{owner}/{repo}"
        resp = await self._request_with_retry("GET", url)
        data = resp.json()
        return str(data.get("default_branch", "main"))

    async def get_tree(self, owner: str, repo: str, branch: str) -> RepoTree:
        cached = self._cache.get(owner, repo, branch)
        if cached is not None:
            logger.info(f"Cache hit for {owner}/{repo}/{branch}")
            return cached

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
        tree = RepoTree(
            owner=owner,
            repo=repo,
            branch=branch,
            files=files,
            truncated=bool(data.get("truncated", False)),
        )
        self._cache.put(owner, repo, branch, tree)
        return tree

    @staticmethod
    def get_raw_url(owner: str, repo: str, branch: str, path: str) -> str:
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"

    async def fetch_raw(self, url: str) -> bytes:
        resp = await self._request_with_retry("GET", url)
        return resp.content

    async def stream_raw(self, url: str) -> Any:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                async with self._client.stream("GET", url) as resp:
                    self._validate_response(resp, url)
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                return
            except RateLimitError:
                raise
            except GitHubAPIError:
                raise
            except (httpx.ConnectError, httpx.ReadError, httpx.WriteError) as e:
                last_error = e
                wait = _backoff_with_jitter(attempt)
                logger.warning(f"Stream error on {url}, retry {attempt+1}/{MAX_RETRIES} in {wait:.1f}s: {e}")
                await asyncio.sleep(wait)
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
