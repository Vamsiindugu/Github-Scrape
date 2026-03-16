from pathlib import Path

import pytest

from github_scrape import config


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.toml")
    return tmp_path


class TestLoadConfig:
    def test_load_config_missing_file(self, isolated_config: Path) -> None:
        result = config.load_config()
        assert result == {}

    def test_load_config_corrupt_file(self, isolated_config: Path) -> None:
        isolated_config.joinpath("config.toml").write_text("not valid toml [[[")
        result = config.load_config()
        assert result == {}

    def test_save_and_load_roundtrip(self, isolated_config: Path) -> None:
        cfg = {"github": {"token": "test_token"}, "download": {"default_path": "/tmp"}}
        config.save_config(cfg)
        loaded = config.load_config()
        assert loaded["github"]["token"] == "test_token"
        assert loaded["download"]["default_path"] == "/tmp"


class TestToken:
    def test_set_token_and_get_token(self, isolated_config: Path) -> None:
        config.set_token("ghp_test12345678")
        assert config.get_token() == "ghp_test12345678"

    def test_get_token_when_unset(self, isolated_config: Path) -> None:
        assert config.get_token() is None


class TestDownloadPath:
    def test_set_download_path_valid(self, isolated_config: Path, tmp_path: Path) -> None:
        test_dir = tmp_path / "downloads"
        test_dir.mkdir()
        config.set_download_path(str(test_dir))
        assert config.get_download_path() == test_dir

    def test_set_download_path_invalid(self, isolated_config: Path) -> None:
        import pytest

        with pytest.raises(ValueError, match="does not exist"):
            config.set_download_path("/nonexistent/path/12345")

    def test_get_download_path_default(self, isolated_config: Path) -> None:
        from pathlib import Path

        result = config.get_download_path()
        assert result == Path.cwd()


class TestUnsetKey:
    def test_unset_existing_key(self, isolated_config: Path) -> None:
        config.set_token("test_token")
        assert config.unset_key("github", "token") is True
        assert config.get_token() is None

    def test_unset_nonexistent_key(self, isolated_config: Path) -> None:
        assert config.unset_key("github", "token") is False


class TestMaskToken:
    def test_mask_token_long(self) -> None:
        result = config.mask_token("ghp_abc123wxyz")
        assert result == "ghp_****wxyz"

    def test_mask_token_short(self) -> None:
        result = config.mask_token("abc")
        assert result == "********"

    def test_mask_token_exact_8(self) -> None:
        result = config.mask_token("12345678")
        assert result == "1234****5678"


class TestConfigAsDisplayDict:
    def test_config_as_display_dict_empty(self, isolated_config: Path) -> None:
        result = config.config_as_display_dict()
        assert result["token"] == "(not set)"
        assert result["path"] == "(not set)"

    def test_config_as_display_dict_masked(self, isolated_config: Path, tmp_path: Path) -> None:
        config.set_token("ghp_test12345678")
        test_dir = tmp_path / "downloads"
        test_dir.mkdir()
        config.set_download_path(str(test_dir))
        result = config.config_as_display_dict()
        assert result["token"] == "ghp_****5678"
        assert test_dir.name in result["path"]
