from pathlib import Path

import pytest
from typer.testing import CliRunner

from github_scrape import cli, config

runner = CliRunner()


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    config.invalidate_cache()
    return tmp_path


class TestConfigCommands:
    def test_config_set_token(self, isolated_config: Path) -> None:
        result = runner.invoke(cli.app, ["config", "set", "token", "ghp_test123"])
        assert result.exit_code == 0
        assert "Token saved" in result.stdout

    def test_config_set_path(self, isolated_config: Path, tmp_path: Path) -> None:
        test_dir = tmp_path / "downloads"
        test_dir.mkdir()
        result = runner.invoke(cli.app, ["config", "set", "path", str(test_dir)])
        assert result.exit_code == 0
        assert "Download path saved" in result.stdout

    def test_config_set_invalid_key(self, isolated_config: Path) -> None:
        result = runner.invoke(cli.app, ["config", "set", "invalid", "value"])
        assert result.exit_code == 1
        assert "Invalid key" in result.stdout

    def test_config_list_empty(self, isolated_config: Path) -> None:
        result = runner.invoke(cli.app, ["config", "list"])
        assert result.exit_code == 0
        assert "(not set)" in result.stdout

    def test_config_list_with_values(self, isolated_config: Path, tmp_path: Path) -> None:
        config.set_token("ghp_test12345678")
        test_dir = tmp_path / "downloads"
        test_dir.mkdir()
        config.set_download_path(str(test_dir))
        result = runner.invoke(cli.app, ["config", "list"])
        assert result.exit_code == 0
        assert "ghp_****5678" in result.stdout

    def test_config_unset_token(self, isolated_config: Path) -> None:
        config.set_token("test_token")
        result = runner.invoke(cli.app, ["config", "unset", "token"])
        assert result.exit_code == 0
        assert "Token removed" in result.stdout

    def test_config_unset_nonexistent(self, isolated_config: Path) -> None:
        result = runner.invoke(cli.app, ["config", "unset", "token"])
        assert result.exit_code == 0
        assert "was not set" in result.stdout


class TestParseGitHubUrl:
    def test_parse_full_url(self) -> None:
        from github_scrape.utils import parse_github_url

        owner, repo, branch, subpath = parse_github_url("https://github.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"
        assert branch == ""
        assert subpath == ""

    def test_parse_url_with_branch(self) -> None:
        from github_scrape.utils import parse_github_url

        owner, repo, branch, subpath = parse_github_url("https://github.com/owner/repo/tree/main")
        assert owner == "owner"
        assert repo == "repo"
        assert branch == "main"
        assert subpath == ""

    def test_parse_url_with_branch_and_subpath(self) -> None:
        from github_scrape.utils import parse_github_url

        owner, repo, branch, subpath = parse_github_url(
            "https://github.com/owner/repo/tree/main/src/lib"
        )
        assert owner == "owner"
        assert repo == "repo"
        assert branch == "main"
        assert subpath == "src/lib"

    def test_parse_shorthand(self) -> None:
        from github_scrape.utils import parse_github_url

        owner, repo, branch, subpath = parse_github_url("owner/repo")
        assert owner == "owner"
        assert repo == "repo"
        assert branch == ""
        assert subpath == ""

    def test_parse_invalid_url(self) -> None:
        from github_scrape.utils import parse_github_url

        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            parse_github_url("https://gitlab.com/owner/repo")

    def test_parse_empty_url(self) -> None:
        from github_scrape.utils import parse_github_url

        with pytest.raises(ValueError, match="URL cannot be empty"):
            parse_github_url("")


class TestConfigUnsetPath:
    def test_config_unset_path(self, isolated_config: Path, tmp_path: Path) -> None:
        test_dir = tmp_path / "downloads"
        test_dir.mkdir()
        config.set_download_path(str(test_dir))
        result = runner.invoke(cli.app, ["config", "unset", "path"])
        assert result.exit_code == 0
        assert "Download path removed" in result.stdout

    def test_config_unset_path_not_set(self, isolated_config: Path) -> None:
        result = runner.invoke(cli.app, ["config", "unset", "path"])
        assert result.exit_code == 0
        assert "was not set" in result.stdout

    def test_config_unset_invalid_key(self, isolated_config: Path) -> None:
        result = runner.invoke(cli.app, ["config", "unset", "invalid"])
        assert result.exit_code == 1
        assert "Invalid key" in result.stdout


class TestConfigSetInvalidPath:
    def test_config_set_invalid_path(self, isolated_config: Path) -> None:
        result = runner.invoke(cli.app, ["config", "set", "path", "/nonexistent/path/xyz"])
        assert result.exit_code == 1
        assert "Error" in result.stdout


class TestMainIntegration:
    def test_main_no_args_launches_tui(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pytest.skip("TUI requires interactive terminal - tested via run_test()")

    def test_main_with_url_launches_browse(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pytest.skip("TUI requires interactive terminal")

    def test_main_with_shorthand_url(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pytest.skip("TUI requires interactive terminal")

    def test_invalid_url_arg_exits_error(self, isolated_config: Path) -> None:
        pytest.skip("TUI requires interactive terminal")

    def test_main_with_token_option(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pytest.skip("TUI requires interactive terminal - token passed via TUI constructor")

    def test_main_with_cwd_flag(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pytest.skip("TUI requires interactive terminal - cwd passed via TUI constructor")

    def test_main_with_no_folder_flag(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pytest.skip("TUI requires interactive terminal - no_folder passed via TUI constructor")

    def test_main_invalid_url_exits_with_error(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pytest.skip("TUI error handling requires interactive terminal")
