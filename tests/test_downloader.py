from pathlib import Path

import httpx
import pytest
import respx

from github_scrape.api import GitHubClient, RepoFile
from github_scrape.downloader import LFS_SIGNATURES, MANIFEST_FILENAME, Downloader, DownloadManifest


@pytest.fixture
async def client() -> GitHubClient:
    c = GitHubClient()
    yield c
    await c.close()


@pytest.fixture
def tmp_dest(tmp_path: Path) -> Path:
    dest = tmp_path / "downloads"
    dest.mkdir()
    return dest


class TestDownloader:
    @pytest.mark.asyncio
    async def test_download_single_file_success(self, client: GitHubClient, tmp_dest: Path) -> None:
        with respx.mock:
            respx.get("https://raw.githubusercontent.com/owner/repo/main/README.md").mock(
                return_value=httpx.Response(200, content=b"Hello World")
            )
            downloader = Downloader(client, "owner", "repo", "main", tmp_dest)
            file = RepoFile(path="README.md", type="blob", size=11, sha="abc", url="")
            result = await downloader.download_single(file)
            assert result.success is True
            assert result.size == 11
            assert result.is_lfs is False
            local_file = tmp_dest / "repo" / "README.md"
            assert local_file.exists()
            assert local_file.read_text() == "Hello World"

    @pytest.mark.asyncio
    async def test_download_creates_nested_dirs(self, client: GitHubClient, tmp_dest: Path) -> None:
        with respx.mock:
            respx.get("https://raw.githubusercontent.com/owner/repo/main/deep/path/file.txt").mock(
                return_value=httpx.Response(200, content=b"nested")
            )
            downloader = Downloader(client, "owner", "repo", "main", tmp_dest)
            file = RepoFile(path="deep/path/file.txt", type="blob", size=6, sha="abc", url="")
            result = await downloader.download_single(file)
            assert result.success is True
            assert (tmp_dest / "repo" / "deep" / "path" / "file.txt").exists()

    @pytest.mark.asyncio
    async def test_download_lfs_pointer_detected(
        self, client: GitHubClient, tmp_dest: Path
    ) -> None:
        lfs_content = LFS_SIGNATURES[0] + b"\noid sha256:abc123\nsize 12345"
        with respx.mock:
            respx.get("https://raw.githubusercontent.com/owner/repo/main/large.bin").mock(
                return_value=httpx.Response(200, content=lfs_content)
            )
            downloader = Downloader(client, "owner", "repo", "main", tmp_dest)
            file = RepoFile(path="large.bin", type="blob", size=len(lfs_content), sha="abc", url="")
            result = await downloader.download_single(file)
            assert result.is_lfs is True

    @pytest.mark.asyncio
    async def test_download_non_lfs_file(self, client: GitHubClient, tmp_dest: Path) -> None:
        with respx.mock:
            respx.get("https://raw.githubusercontent.com/owner/repo/main/normal.txt").mock(
                return_value=httpx.Response(200, content=b"normal content")
            )
            downloader = Downloader(client, "owner", "repo", "main", tmp_dest)
            file = RepoFile(path="normal.txt", type="blob", size=14, sha="abc", url="")
            result = await downloader.download_single(file)
            assert result.is_lfs is False

    @pytest.mark.asyncio
    async def test_download_concurrent_respects_semaphore(
        self, client: GitHubClient, tmp_dest: Path
    ) -> None:
        call_count = 0

        def track_calls(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, content=b"x")

        with respx.mock:
            for i in range(10):
                respx.get(f"https://raw.githubusercontent.com/owner/repo/main/file{i}.txt").mock(
                    side_effect=track_calls
                )
            downloader = Downloader(client, "owner", "repo", "main", tmp_dest, max_concurrent=5)
            files = [
                RepoFile(path=f"file{i}.txt", type="blob", size=1, sha=f"sha{i}", url="")
                for i in range(10)
            ]
            results = await downloader.download_files(files)
            assert len(results) == 10
            assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_download_network_error_graceful(
        self, client: GitHubClient, tmp_dest: Path
    ) -> None:
        with respx.mock:
            respx.get("https://raw.githubusercontent.com/owner/repo/main/error.txt").mock(
                side_effect=httpx.ConnectError("Network error")
            )
            downloader = Downloader(client, "owner", "repo", "main", tmp_dest)
            file = RepoFile(path="error.txt", type="blob", size=10, sha="abc", url="")
            result = await downloader.download_single(file)
            assert result.success is False
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_download_skip_identical_file(self, client: GitHubClient, tmp_dest: Path) -> None:
        existing_file = tmp_dest / "repo" / "exists.txt"
        existing_file.parent.mkdir(parents=True, exist_ok=True)
        existing_file.write_bytes(b"existing content")

        with respx.mock:
            respx.get("https://raw.githubusercontent.com/owner/repo/main/exists.txt").mock(
                return_value=httpx.Response(200, content=b"new content")
            )
            downloader = Downloader(client, "owner", "repo", "main", tmp_dest)
            file = RepoFile(path="exists.txt", type="blob", size=16, sha="abc", url="")
            result = await downloader.download_single(file)
            assert "Skipped" in (result.error or "")

    @pytest.mark.asyncio
    async def test_download_overwrite_different_file(
        self, client: GitHubClient, tmp_dest: Path
    ) -> None:
        existing_file = tmp_dest / "repo" / "exists.txt"
        existing_file.parent.mkdir(parents=True, exist_ok=True)
        existing_file.write_bytes(b"old")

        with respx.mock:
            respx.get("https://raw.githubusercontent.com/owner/repo/main/exists.txt").mock(
                return_value=httpx.Response(200, content=b"new content longer")
            )
            downloader = Downloader(client, "owner", "repo", "main", tmp_dest)
            file = RepoFile(path="exists.txt", type="blob", size=19, sha="abc", url="")
            result = await downloader.download_single(file)
            assert result.success is True
            assert existing_file.read_text() == "new content longer"

    @pytest.mark.asyncio
    async def test_resolve_dest_path_with_repo_folder(
        self, tmp_dest: Path, client: GitHubClient
    ) -> None:
        downloader = Downloader(client, "owner", "repo", "main", tmp_dest, create_repo_folder=True)
        result = downloader.resolve_dest_path("src/file.py")
        assert "repo" in result.parts
        assert result.name == "file.py"

    @pytest.mark.asyncio
    async def test_resolve_dest_path_no_folder(self, tmp_dest: Path, client: GitHubClient) -> None:
        downloader = Downloader(client, "owner", "repo", "main", tmp_dest, create_repo_folder=False)
        result = downloader.resolve_dest_path("src/file.py")
        assert "repo" not in result.parts
        assert result.name == "file.py"

    @pytest.mark.asyncio
    async def test_download_empty_file_list(self, client: GitHubClient, tmp_dest: Path) -> None:
        downloader = Downloader(client, "owner", "repo", "main", tmp_dest)
        results = await downloader.download_files([])
        assert results == []

    @pytest.mark.asyncio
    async def test_progress_callback_called(self, client: GitHubClient, tmp_dest: Path) -> None:
        callback_calls: list[tuple[str, int, int]] = []

        def callback(path: str, downloaded: int, total: int) -> None:
            callback_calls.append((path, downloaded, total))

        with respx.mock:
            respx.get("https://raw.githubusercontent.com/owner/repo/main/file.txt").mock(
                return_value=httpx.Response(200, content=b"content")
            )
            downloader = Downloader(client, "owner", "repo", "main", tmp_dest)
            file = RepoFile(path="file.txt", type="blob", size=7, sha="abc", url="")
            await downloader.download_files([file], progress_callback=callback)
            assert len(callback_calls) == 1
            assert callback_calls[0][0] == "file.txt"

    @pytest.mark.asyncio
    async def test_download_tree_skipped(self, client: GitHubClient, tmp_dest: Path) -> None:
        downloader = Downloader(client, "owner", "repo", "main", tmp_dest)
        file = RepoFile(path="src", type="tree", size=0, sha="abc", url="")
        result = await downloader.download_single(file)
        assert result.success is True
        assert result.size == 0

    @pytest.mark.asyncio
    async def test_download_persists_manifest(self, client: GitHubClient, tmp_dest: Path) -> None:
        with respx.mock:
            respx.get("https://raw.githubusercontent.com/owner/repo/main/README.md").mock(
                return_value=httpx.Response(200, content=b"Hello World")
            )
            downloader = Downloader(client, "owner", "repo", "main", tmp_dest)
            file = RepoFile(path="README.md", type="blob", size=11, sha="abc123", url="")
            await downloader.download_files([file])
            manifest_path = tmp_dest / "repo" / MANIFEST_FILENAME
            assert manifest_path.exists()
            manifest = DownloadManifest.load(tmp_dest / "repo")
            assert manifest is not None
            assert manifest.is_downloaded("README.md", "abc123")

    @pytest.mark.asyncio
    async def test_download_manifest_hit_skips_file(self, client: GitHubClient, tmp_dest: Path) -> None:
        dest_dir = tmp_dest / "repo"
        dest_dir.mkdir(parents=True)
        (dest_dir / "README.md").write_bytes(b"cached")
        manifest = DownloadManifest(files={"README.md": "abc123"})
        manifest.save(dest_dir)

        downloader = Downloader(client, "owner", "repo", "main", tmp_dest)
        file = RepoFile(path="README.md", type="blob", size=6, sha="abc123", url="")
        result = await downloader.download_single(file)
        assert "Skipped" in (result.error or "")
        assert "manifest" in (result.error or "")
