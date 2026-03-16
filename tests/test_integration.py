"""Integration tests for github-scrape."""

from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from github_scrape import config
from github_scrape.api import AuthError, GitHubClient, NotFoundError
from github_scrape.cli import app
from github_scrape.downloader import Downloader

runner = CliRunner()


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    return tmp_path


@pytest.fixture
def mock_github_api() -> None:
    with respx.mock:
        respx.get("https://api.github.com/repos/testowner/testrepo").mock(
            return_value=httpx.Response(200, json={"default_branch": "main"})
        )
        respx.get("https://api.github.com/rate_limit").mock(
            return_value=httpx.Response(
                200,
                json={
                    "resources": {"core": {"limit": 5000, "remaining": 4999, "reset": 1700000000}}
                },
            )
        )
        respx.get(
            "https://api.github.com/repos/testowner/testrepo/git/trees/main?recursive=1"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "tree": [
                        {
                            "path": "README.md",
                            "type": "blob",
                            "size": 100,
                            "sha": "abc123",
                        },
                        {
                            "path": "src/main.py",
                            "type": "blob",
                            "size": 500,
                            "sha": "def456",
                        },
                        {
                            "path": "src/utils/helpers.py",
                            "type": "blob",
                            "size": 300,
                            "sha": "ghi789",
                        },
                        {"path": "tests", "type": "tree", "size": 0, "sha": "jkl012"},
                        {
                            "path": "tests/test_main.py",
                            "type": "blob",
                            "size": 200,
                            "sha": "mno345",
                        },
                    ],
                    "truncated": False,
                },
            )
        )
        respx.get("https://raw.githubusercontent.com/testowner/testrepo/main/README.md").mock(
            return_value=httpx.Response(200, content=b"# Test Repo\n\nThis is a test.")
        )
        respx.get("https://raw.githubusercontent.com/testowner/testrepo/main/src/main.py").mock(
            return_value=httpx.Response(200, content=b"print('hello')")
        )
        respx.get(
            "https://raw.githubusercontent.com/testowner/testrepo/main/src/utils/helpers.py"
        ).mock(return_value=httpx.Response(200, content=b"def help(): pass"))
        respx.get(
            "https://raw.githubusercontent.com/testowner/testrepo/main/tests/test_main.py"
        ).mock(return_value=httpx.Response(200, content=b"def test_x(): pass"))
        yield


class TestConfigIntegration:
    def test_full_config_workflow(self, isolated_config: Path, tmp_path: Path) -> None:
        result = runner.invoke(app, ["config", "list"])
        assert result.exit_code == 0
        assert "(not set)" in result.stdout

        result = runner.invoke(app, ["config", "set", "token", "ghp_test12345678"])
        assert result.exit_code == 0
        assert "Token saved" in result.stdout

        result = runner.invoke(app, ["config", "list"])
        assert result.exit_code == 0
        assert "ghp_****" in result.stdout

        download_dir = tmp_path / "downloads"
        download_dir.mkdir()
        result = runner.invoke(app, ["config", "set", "path", str(download_dir)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["config", "list"])
        assert result.exit_code == 0
        assert "path" in result.stdout

        result = runner.invoke(app, ["config", "unset", "token"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["config", "list"])
        assert "(not set)" in result.stdout


class TestAPIIntegration:
    @pytest.mark.asyncio
    async def test_full_api_workflow(self, isolated_config: Path, mock_github_api: None) -> None:
        async with GitHubClient() as client:
            branch = await client.get_default_branch("testowner", "testrepo")
            assert branch == "main"

            tree = await client.get_tree("testowner", "testrepo", branch)
            assert tree.owner == "testowner"
            assert tree.repo == "testrepo"
            assert len(tree.files) == 5

            blob_files = [f for f in tree.files if f.type == "blob"]
            assert len(blob_files) == 4

            rate_limit = await client.get_rate_limit()
            assert "limit" in rate_limit
            assert "remaining" in rate_limit


class TestDownloaderIntegration:
    @pytest.mark.asyncio
    async def test_full_download_workflow(
        self, isolated_config: Path, tmp_path: Path, mock_github_api: None
    ) -> None:
        dest = tmp_path / "output"
        dest.mkdir()

        async with GitHubClient() as client:
            tree = await client.get_tree("testowner", "testrepo", "main")
            blob_files = [f for f in tree.files if f.type == "blob"]

            downloader = Downloader(
                client,
                "testowner",
                "testrepo",
                "main",
                dest,
                create_repo_folder=True,
            )

            results = await downloader.download_files(blob_files[:2])

            assert len(results) == 2
            assert all(r.success for r in results)

            readme_path = dest / "testrepo" / "README.md"
            assert readme_path.exists()
            content = readme_path.read_text()
            assert "Test Repo" in content

            main_path = dest / "testrepo" / "src" / "main.py"
            assert main_path.exists()

    @pytest.mark.asyncio
    async def test_download_no_folder_flag(
        self, isolated_config: Path, tmp_path: Path, mock_github_api: None
    ) -> None:
        dest = tmp_path / "output_no_folder"
        dest.mkdir()

        async with GitHubClient() as client:
            tree = await client.get_tree("testowner", "testrepo", "main")
            blob_files = [f for f in tree.files if f.type == "blob"]

            downloader = Downloader(
                client,
                "testowner",
                "testrepo",
                "main",
                dest,
                create_repo_folder=False,
            )

            await downloader.download_files([blob_files[0]])

            readme_path = dest / "README.md"
            assert readme_path.exists()
            assert "testrepo" not in str(readme_path)


class TestURLParsingIntegration:
    def test_various_url_formats(self) -> None:
        from github_scrape.utils import parse_github_url

        test_cases = [
            ("owner/repo", ("owner", "repo", "", "")),
            ("https://github.com/owner/repo", ("owner", "repo", "", "")),
            (
                "https://github.com/owner/repo/tree/main",
                ("owner", "repo", "main", ""),
            ),
            (
                "https://github.com/owner/repo/tree/main/src/lib",
                ("owner", "repo", "main", "src/lib"),
            ),
            (
                "https://github.com/owner/repo/tree/develop/docs/api/v2",
                ("owner", "repo", "develop", "docs/api/v2"),
            ),
        ]

        for url, expected in test_cases:
            result = parse_github_url(url)
            assert result == expected, f"Failed for {url}"


class TestErrorHandlingIntegration:
    @pytest.mark.asyncio
    async def test_api_error_404(self, isolated_config: Path) -> None:
        with respx.mock:
            respx.get("https://api.github.com/repos/nonexistent/repo").mock(
                return_value=httpx.Response(404)
            )
            async with GitHubClient() as client:
                with pytest.raises(NotFoundError):
                    await client.get_default_branch("nonexistent", "repo")

    @pytest.mark.asyncio
    async def test_api_error_401(self, isolated_config: Path) -> None:
        with respx.mock:
            respx.get("https://api.github.com/repos/private/repo").mock(
                return_value=httpx.Response(401)
            )
            async with GitHubClient() as client:
                with pytest.raises(AuthError):
                    await client.get_default_branch("private", "repo")

    @pytest.mark.asyncio
    async def test_download_handles_network_error(
        self, isolated_config: Path, tmp_path: Path
    ) -> None:
        with respx.mock:
            respx.get("https://api.github.com/repos/owner/repo").mock(
                return_value=httpx.Response(200, json={"default_branch": "main"})
            )
            respx.get("https://api.github.com/repos/owner/repo/git/trees/main?recursive=1").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "tree": [
                            {
                                "path": "file.txt",
                                "type": "blob",
                                "size": 10,
                                "sha": "abc",
                            }
                        ],
                        "truncated": False,
                    },
                )
            )
            respx.get("https://raw.githubusercontent.com/owner/repo/main/file.txt").mock(
                side_effect=httpx.ConnectError("Network error")
            )

            dest = tmp_path / "output"
            dest.mkdir()

            async with GitHubClient() as client:
                tree = await client.get_tree("owner", "repo", "main")
                downloader = Downloader(client, "owner", "repo", "main", dest)
                results = await downloader.download_files(tree.files)

                assert len(results) == 1
                assert results[0].success is False
                assert results[0].error is not None


class TestEndToEnd:
    def test_config_persistence(self, isolated_config: Path, tmp_path: Path) -> None:
        result = runner.invoke(app, ["config", "set", "token", "ghp_persistent123"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["config", "list"])
        assert "ghp_****" in result.stdout

        loaded = config.load_config()
        assert loaded["github"]["token"] == "ghp_persistent123"

    def test_config_invalid_path(self, isolated_config: Path) -> None:
        result = runner.invoke(app, ["config", "set", "path", "/nonexistent/path/xyz"])
        assert result.exit_code == 1
        assert "Error" in result.stdout

    def test_config_invalid_key(self, isolated_config: Path) -> None:
        result = runner.invoke(app, ["config", "set", "invalid_key", "value"])
        assert result.exit_code == 1
        assert "Invalid key" in result.stdout

    def test_full_cli_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "github-scrape" in result.stdout
        assert "config" in result.stdout

        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "set" in result.stdout
        assert "list" in result.stdout
        assert "unset" in result.stdout
