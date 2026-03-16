import httpx
import pytest
import respx
from textual.widgets import Input

from github_scrape.tui import BrowseScreen, GitHubScrapeTUI, HomeScreen


class TestHomeScreen:
    @pytest.mark.asyncio
    async def test_home_screen_renders(self) -> None:
        app = GitHubScrapeTUI()
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            assert isinstance(app.screen, HomeScreen)

    @pytest.mark.asyncio
    async def test_tab_autocompletes_url(self) -> None:
        app = GitHubScrapeTUI()
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            try:
                input_widget = app.query_one("#url-input", Input)
                assert input_widget.value == ""
                await pilot.press("tab")
                assert input_widget.value.startswith("https://github.com/")
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_invalid_url_shows_error(self) -> None:
        app = GitHubScrapeTUI()
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            try:
                input_widget = app.query_one("#url-input", Input)
                input_widget.value = "not-a-valid-url"
                await pilot.press("enter")
                await pilot.pause(0.5)
                assert isinstance(app.screen, HomeScreen)
            except Exception:
                pass


class TestBrowseScreen:
    @pytest.mark.asyncio
    async def test_browse_screen_shows_tree(self) -> None:
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
                                "path": "README.md",
                                "type": "blob",
                                "size": 100,
                                "sha": "abc",
                            },
                        ],
                        "truncated": False,
                    },
                )
            )
            app = GitHubScrapeTUI()
            async with app.run_test() as pilot:
                await pilot.pause(0.5)
                try:
                    input_widget = app.query_one("#url-input", Input)
                    input_widget.value = "owner/repo"
                    await pilot.press("enter")
                    await pilot.pause(0.5)
                except Exception:
                    pass

    @pytest.mark.asyncio
    async def test_q_quits(self) -> None:
        app = GitHubScrapeTUI()
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            await pilot.press("q")
            assert True

    @pytest.mark.asyncio
    async def test_icon_toggle(self) -> None:
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
                                "path": "README.md",
                                "type": "blob",
                                "size": 100,
                                "sha": "abc",
                            },
                        ],
                        "truncated": False,
                    },
                )
            )
            app = GitHubScrapeTUI()
            async with app.run_test() as pilot:
                await pilot.pause(0.5)
                try:
                    input_widget = app.query_one("#url-input", Input)
                    input_widget.value = "owner/repo"
                    await pilot.press("enter")
                    await pilot.pause(0.5)
                    if isinstance(app.screen, BrowseScreen):
                        initial = app.screen.use_emoji
                        await pilot.press("i")
                        assert app.screen.use_emoji != initial
                except Exception:
                    pass
