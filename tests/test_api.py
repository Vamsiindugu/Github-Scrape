import httpx
import pytest
import respx

from github_scrape.api import (
    AuthError,
    GitHubClient,
    NotFoundError,
    RateLimitError,
)


class TestGitHubClient:
    @pytest.mark.asyncio
    async def test_get_default_branch_success(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/repos/owner/repo").mock(
                return_value=httpx.Response(200, json={"default_branch": "main"})
            )
            async with GitHubClient() as client:
                branch = await client.get_default_branch("owner", "repo")
                assert branch == "main"

    @pytest.mark.asyncio
    async def test_get_tree_success(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/repos/owner/repo/git/trees/main?recursive=1").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "tree": [
                            {"path": "README.md", "type": "blob", "size": 100, "sha": "abc123"},
                            {"path": "src", "type": "tree", "size": 0, "sha": "def456"},
                        ],
                        "truncated": False,
                    },
                )
            )
            async with GitHubClient() as client:
                tree = await client.get_tree("owner", "repo", "main")
                assert tree.owner == "owner"
                assert tree.repo == "repo"
                assert tree.branch == "main"
                assert len(tree.files) == 2
                assert tree.files[0].path == "README.md"
                assert tree.files[0].type == "blob"
                assert tree.truncated is False

    @pytest.mark.asyncio
    async def test_get_tree_truncated_flag(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/repos/owner/repo/git/trees/main?recursive=1").mock(
                return_value=httpx.Response(
                    200,
                    json={"tree": [], "truncated": True},
                )
            )
            async with GitHubClient() as client:
                tree = await client.get_tree("owner", "repo", "main")
                assert tree.truncated is True

    @pytest.mark.asyncio
    async def test_get_tree_404(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/repos/owner/repo/git/trees/main?recursive=1").mock(
                return_value=httpx.Response(404)
            )
            async with GitHubClient() as client:
                with pytest.raises(NotFoundError, match="not found"):
                    await client.get_tree("owner", "repo", "main")

    @pytest.mark.asyncio
    async def test_get_tree_401(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/repos/owner/repo/git/trees/main?recursive=1").mock(
                return_value=httpx.Response(401)
            )
            async with GitHubClient() as client:
                with pytest.raises(AuthError, match="Invalid token"):
                    await client.get_tree("owner", "repo", "main")

    @pytest.mark.asyncio
    async def test_get_tree_403_rate_limit(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/repos/owner/repo/git/trees/main?recursive=1").mock(
                return_value=httpx.Response(
                    403,
                    headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"},
                )
            )
            async with GitHubClient() as client:
                with pytest.raises(RateLimitError, match="Rate limited"):
                    await client.get_tree("owner", "repo", "main")

    @pytest.mark.asyncio
    async def test_get_tree_429(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/repos/owner/repo/git/trees/main?recursive=1").mock(
                return_value=httpx.Response(429, headers={"Retry-After": "60"})
            )
            async with GitHubClient() as client:
                with pytest.raises(RateLimitError, match="Retry after"):
                    await client.get_tree("owner", "repo", "main")

    @pytest.mark.asyncio
    async def test_get_tree_network_error(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/repos/owner/repo/git/trees/main?recursive=1").mock(
                side_effect=httpx.ConnectError("Network error")
            )
            async with GitHubClient() as client:
                with pytest.raises(httpx.ConnectError):
                    await client.get_tree("owner", "repo", "main")

    @pytest.mark.asyncio
    async def test_get_raw_url_format(self) -> None:
        url = GitHubClient.get_raw_url("owner", "repo", "main", "src/file.py")
        assert url == "https://raw.githubusercontent.com/owner/repo/main/src/file.py"

    @pytest.mark.asyncio
    async def test_token_injected_in_header(self) -> None:
        with respx.mock:
            request_made = False

            def check_headers(request: httpx.Request) -> httpx.Response:
                nonlocal request_made
                request_made = True
                assert "Authorization" in request.headers
                assert request.headers["Authorization"] == "Bearer test_token"
                return httpx.Response(200, json={"default_branch": "main"})

            respx.get("https://api.github.com/repos/owner/repo").mock(side_effect=check_headers)
            async with GitHubClient(token="test_token") as client:
                await client.get_default_branch("owner", "repo")
            assert request_made

    @pytest.mark.asyncio
    async def test_no_token_no_auth_header(self) -> None:
        with respx.mock:
            request_made = False

            def check_headers(request: httpx.Request) -> httpx.Response:
                nonlocal request_made
                request_made = True
                assert "Authorization" not in request.headers
                return httpx.Response(200, json={"default_branch": "main"})

            respx.get("https://api.github.com/repos/owner/repo").mock(side_effect=check_headers)
            async with GitHubClient() as client:
                await client.get_default_branch("owner", "repo")
            assert request_made

    @pytest.mark.asyncio
    async def test_client_close(self) -> None:
        client = GitHubClient()
        await client.close()

    @pytest.mark.asyncio
    async def test_get_rate_limit(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/rate_limit").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "resources": {
                            "core": {"limit": 5000, "remaining": 4999, "reset": 1700000000}
                        }
                    },
                )
            )
            async with GitHubClient() as client:
                limits = await client.get_rate_limit()
                assert limits["limit"] == 5000
                assert limits["remaining"] == 4999

    @pytest.mark.asyncio
    async def test_rate_limit_info_updated_from_headers(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/repos/owner/repo").mock(
                return_value=httpx.Response(
                    200,
                    json={"default_branch": "main"},
                    headers={
                        "X-RateLimit-Limit": "5000",
                        "X-RateLimit-Remaining": "4998",
                        "X-RateLimit-Reset": "1700000000",
                    },
                )
            )
            async with GitHubClient() as client:
                await client.get_default_branch("owner", "repo")
                info = client.rate_limit_info
                assert info.limit == 5000
                assert info.remaining == 4998
                assert info.reset_timestamp == 1700000000

    @pytest.mark.asyncio
    async def test_tree_cache_avoids_duplicate_requests(self) -> None:
        with respx.mock:
            call_count = 0

            def track(request: httpx.Request) -> httpx.Response:
                nonlocal call_count
                call_count += 1
                return httpx.Response(
                    200,
                    json={"tree": [{"path": "a.txt", "type": "blob", "size": 5, "sha": "x"}], "truncated": False},
                )

            respx.get("https://api.github.com/repos/owner/repo/git/trees/main?recursive=1").mock(
                side_effect=track
            )
            async with GitHubClient() as client:
                tree1 = await client.get_tree("owner", "repo", "main")
                tree2 = await client.get_tree("owner", "repo", "main")
                assert tree1 is tree2
                assert call_count == 1
                assert client.cache.size == 1

    @pytest.mark.asyncio
    async def test_rate_limit_error_has_retry_after(self) -> None:
        with respx.mock:
            respx.get("https://api.github.com/repos/owner/repo/git/trees/main?recursive=1").mock(
                return_value=httpx.Response(429, headers={"Retry-After": "30"})
            )
            async with GitHubClient() as client:
                with pytest.raises(RateLimitError) as exc_info:
                    await client.get_tree("owner", "repo", "main")
                assert exc_info.value.retry_after == 30
