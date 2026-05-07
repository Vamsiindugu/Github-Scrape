from pathlib import Path

from github_scrape.downloader import DownloadManifest


class TestDownloadManifest:
    def test_load_missing_returns_none(self, tmp_path: Path) -> None:
        result = DownloadManifest.load(tmp_path)
        assert result is None

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        manifest = DownloadManifest(files={"README.md": "abc123", "src/main.py": "def456"})
        manifest.save(tmp_path)
        loaded = DownloadManifest.load(tmp_path)
        assert loaded is not None
        assert loaded.files == {"README.md": "abc123", "src/main.py": "def456"}

    def test_is_downloaded_true(self) -> None:
        manifest = DownloadManifest(files={"README.md": "abc123"})
        assert manifest.is_downloaded("README.md", "abc123") is True

    def test_is_downloaded_wrong_sha(self) -> None:
        manifest = DownloadManifest(files={"README.md": "abc123"})
        assert manifest.is_downloaded("README.md", "wrong") is False

    def test_is_downloaded_missing_path(self) -> None:
        manifest = DownloadManifest(files={})
        assert manifest.is_downloaded("missing.txt", "abc") is False

    def test_mark_downloaded(self) -> None:
        manifest = DownloadManifest(files={})
        manifest.mark_downloaded("file.txt", "sha1")
        assert manifest.is_downloaded("file.txt", "sha1") is True

    def test_mark_downloaded_overwrites(self) -> None:
        manifest = DownloadManifest(files={"file.txt": "old_sha"})
        manifest.mark_downloaded("file.txt", "new_sha")
        assert manifest.is_downloaded("file.txt", "new_sha") is True
        assert manifest.is_downloaded("file.txt", "old_sha") is False

    def test_load_corrupt_file(self, tmp_path: Path) -> None:
        (tmp_path / ".github-scrape-manifest.json").write_text("not json{{{")
        result = DownloadManifest.load(tmp_path)
        assert result is None
