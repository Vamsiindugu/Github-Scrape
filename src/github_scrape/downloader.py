from __future__ import annotations

import asyncio
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from github_scrape.api import GitHubAPIError, GitHubClient, RepoFile
from github_scrape.logging_cfg import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger("downloader")

LFS_SIGNATURES = [
    b"version https://git-lfs.github.com",
    b"version https://git-lfs.github.com/",
]
DEFAULT_CHUNK_SIZE = 64 * 1024
MANIFEST_FILENAME = ".github-scrape-manifest.json"


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


@dataclass
class DownloadManifest:
    files: dict[str, str]

    @staticmethod
    def load(path: Path) -> DownloadManifest | None:
        manifest_path = path / MANIFEST_FILENAME
        if not manifest_path.exists():
            return None
        try:
            data = json.loads(manifest_path.read_text())
            return DownloadManifest(files=data.get("files", {}))
        except (json.JSONDecodeError, OSError):
            return None

    def save(self, path: Path) -> None:
        manifest_path = path / MANIFEST_FILENAME
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps({"files": self.files}, indent=2))

    def is_downloaded(self, file_path: str, sha: str) -> bool:
        return self.files.get(file_path) == sha

    def mark_downloaded(self, file_path: str, sha: str) -> None:
        self.files[file_path] = sha


def is_lfs_pointer(content: bytes) -> bool:
    return any(content.startswith(sig) for sig in LFS_SIGNATURES)


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
        self._manifest: DownloadManifest | None = None

    def _get_manifest(self) -> DownloadManifest:
        if self._manifest is None:
            dest_dir = self._dest / self._repo if self._create_repo_folder else self._dest
            self._manifest = DownloadManifest.load(dest_dir) or DownloadManifest(files={})
        return self._manifest

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
        finally:
            self._persist_manifest()

    def _persist_manifest(self) -> None:
        if self._manifest and self._manifest.files:
            dest_dir = self._dest / self._repo if self._create_repo_folder else self._dest
            self._manifest.save(dest_dir)
            logger.info(f"Persisted download manifest with {len(self._manifest.files)} entries")

    async def _download_single(self, file: RepoFile) -> DownloadResult:
        if file.type != "blob":
            return DownloadResult(path=file.path, success=True, size=0, is_lfs=False)

        manifest = self._get_manifest()
        if manifest.is_downloaded(file.path, file.sha):
            local_path = self.resolve_dest_path(file.path)
            if local_path.exists():
                logger.debug(f"Skipping {file.path} — already downloaded (sha={file.sha})")
                return DownloadResult(
                    path=file.path,
                    success=True,
                    size=file.size,
                    is_lfs=False,
                    error="Skipped (manifest hit)",
                )

        local_path = self.resolve_dest_path(file.path)
        temp_path: Path | None = None

        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)

            if local_path.exists() and local_path.stat().st_size == file.size:
                manifest.mark_downloaded(file.path, file.sha)
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

            manifest.mark_downloaded(file.path, file.sha)
            logger.info(f"Downloaded {file.path} ({len(content)} bytes)")

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
            logger.error(f"IO error downloading {file.path}: {e}")
            return DownloadResult(
                path=file.path,
                success=False,
                size=0,
                is_lfs=False,
                error=f"IO error: {e}",
            )
        except GitHubAPIError as e:
            logger.error(f"API error downloading {file.path}: {e}")
            return DownloadResult(
                path=file.path,
                success=False,
                size=0,
                is_lfs=False,
                error=f"API error: {e}",
            )
        except Exception as e:
            logger.error(f"Unexpected error downloading {file.path}: {e}")
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
