from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from github_scrape.api import GitHubAPIError, GitHubClient, RepoFile

if TYPE_CHECKING:
    pass

LFS_SIGNATURES = [
    b"version https://git-lfs.github.com",
    b"version https://git-lfs.github.com/",
]
DEFAULT_CHUNK_SIZE = 64 * 1024


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
    create_repo_folder: bool
    total_size: int


def is_lfs_pointer(content: bytes) -> bool:
    """Check if content is a Git LFS pointer file."""
    for sig in LFS_SIGNATURES:
        if content.startswith(sig):
            return True
    return False


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
    ) -> None:
        self._client = client
        self._owner = owner
        self._repo = repo
        self._branch = branch
        self._dest = dest
        self._create_repo_folder = create_repo_folder
        self._max_concurrent = max_concurrent
        self._shutdown_event = asyncio.Event()

    async def download_files(
        self,
        files: list[RepoFile],
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> list[DownloadResult]:
        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def download_with_progress(f: RepoFile) -> DownloadResult:
            if self._shutdown_event.is_set():
                return DownloadResult(
                    path=f.path, success=False, size=0, is_lfs=False, error="Download cancelled"
                )
            async with semaphore:
                result = await self._download_single(f)
                if progress_callback:
                    progress_callback(f.path, result.size, result.size)
                return result

        tasks = [asyncio.create_task(download_with_progress(f)) for f in files]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return [
                r if isinstance(r, DownloadResult) else
                DownloadResult(path=files[i].path, success=False, size=0, is_lfs=False, error=str(r))
                for i, r in enumerate(results)
            ]
        except asyncio.CancelledError:
            self._shutdown_event.set()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            return [
                DownloadResult(path=f.path, success=False, size=0, is_lfs=False, error="Cancelled")
                for f in files
            ]

    async def _download_single(self, file: RepoFile) -> DownloadResult:
        if file.type != "blob":
            return DownloadResult(path=file.path, success=True, size=0, is_lfs=False)

        local_path = self.resolve_dest_path(file.path)
        temp_path: Path | None = None

        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)

            if local_path.exists() and local_path.stat().st_size == file.size:
                return DownloadResult(
                    path=file.path,
                    success=True,
                    size=file.size,
                    is_lfs=False,
                    error="Skipped (identical)",
                )

            raw_url = GitHubClient.get_raw_url(
                self._owner, self._repo, self._branch, file.path
            )

            content = await self._client.fetch_raw(raw_url)
            is_lfs = is_lfs_pointer(content)

            fd, temp_path_str = tempfile.mkstemp(
                dir=local_path.parent,
                prefix=f".{local_path.name}.",
                suffix=".tmp"
            )
            temp_path = Path(temp_path_str)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(content)
                os.replace(temp_path, local_path)
                temp_path = None
            finally:
                if temp_path and temp_path.exists():
                    temp_path.unlink()

            return DownloadResult(
                path=file.path,
                success=True,
                size=len(content),
                is_lfs=is_lfs,
            )

        except asyncio.CancelledError:
            if temp_path and temp_path.exists():
                temp_path.unlink()
            raise
        except OSError as e:
            return DownloadResult(
                path=file.path,
                success=False,
                size=0,
                is_lfs=False,
                error=f"IO error: {e}",
            )
        except GitHubAPIError as e:
            return DownloadResult(
                path=file.path,
                success=False,
                size=0,
                is_lfs=False,
                error=f"API error: {e}",
            )
        except Exception as e:
            return DownloadResult(
                path=file.path,
                success=False,
                size=0,
                is_lfs=False,
                error=str(e),
            )

    async def download_single(self, file: RepoFile) -> DownloadResult:
        return await self._download_single(file)

    def resolve_dest_path(self, file_path: str) -> Path:
        if self._create_repo_folder:
            return self._dest / self._repo / file_path
        return self._dest / file_path

    def create_plan(self, files: list[RepoFile]) -> DownloadPlan:
        total_size = sum(f.size for f in files if f.type == "blob")
        return DownloadPlan(
            files=files,
            dest_dir=self._dest,
            create_repo_folder=self._create_repo_folder,
            total_size=total_size,
        )
