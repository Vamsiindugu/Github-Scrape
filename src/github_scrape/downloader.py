import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from github_scrape.api import GitHubClient, RepoFile

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
    create_repo_folder: bool
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
    ) -> None:
        self._client = client
        self._owner = owner
        self._repo = repo
        self._branch = branch
        self._dest = dest
        self._create_repo_folder = create_repo_folder
        self._max_concurrent = max_concurrent

    async def download_files(
        self,
        files: list[RepoFile],
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> list[DownloadResult]:
        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def download_with_progress(f: RepoFile) -> DownloadResult:
            async with semaphore:
                result = await self._download_single(f)
                if progress_callback:
                    progress_callback(f.path, result.size, result.size)
                return result

        tasks = [download_with_progress(f) for f in files]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def _download_single(self, file: RepoFile) -> DownloadResult:
        if file.type != "blob":
            return DownloadResult(path=file.path, success=True, size=0, is_lfs=False)

        local_path = self.resolve_dest_path(file.path)

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

            raw_url = await self._client.get_raw_url(
                self._owner, self._repo, self._branch, file.path
            )
            resp = await self._client._client.get(raw_url)
            resp.raise_for_status()

            content = resp.content
            is_lfs = content.startswith(LFS_SIGNATURE.encode())

            local_path.write_bytes(content)

            return DownloadResult(
                path=file.path,
                success=True,
                size=len(content),
                is_lfs=is_lfs,
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
