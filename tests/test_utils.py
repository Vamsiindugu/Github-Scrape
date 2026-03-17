"""Tests for utils.py."""
import pytest

from github_scrape.utils import parse_github_url, sanitize_filename


class TestParseGitHubURL:
    def test_full_url(self) -> None:
        assert parse_github_url("https://github.com/psf/requests") == (
            "psf",
            "requests",
            "",
            "",
        )

    def test_url_with_trailing_slash(self) -> None:
        assert parse_github_url("https://github.com/psf/requests/") == (
            "psf",
            "requests",
            "",
            "",
        )

    def test_url_with_branch(self) -> None:
        owner, repo, branch, sub = parse_github_url(
            "https://github.com/psf/requests/tree/main"
        )
        assert (owner, repo, branch) == ("psf", "requests", "main")
        assert sub == ""

    def test_url_with_branch_and_subpath(self) -> None:
        owner, repo, branch, sub = parse_github_url(
            "https://github.com/psf/requests/tree/main/src/requests"
        )
        assert (owner, repo, branch, sub) == (
            "psf",
            "requests",
            "main",
            "src/requests",
        )

    def test_url_with_nested_subpath(self) -> None:
        owner, repo, branch, sub = parse_github_url(
            "https://github.com/owner/repo/tree/develop/docs/api/v2"
        )
        assert sub == "docs/api/v2"

    def test_shorthand(self) -> None:
        owner, repo, _, _ = parse_github_url("psf/requests")
        assert (owner, repo) == ("psf", "requests")

    def test_url_with_whitespace(self) -> None:
        owner, repo, _, _ = parse_github_url("  psf/requests  ")
        assert (owner, repo) == ("psf", "requests")

    def test_url_with_www(self) -> None:
        with pytest.raises(ValueError):
            parse_github_url("https://www.github.com/a/b")

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            parse_github_url("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            parse_github_url("   ")

    def test_non_github_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            parse_github_url("https://gitlab.com/a/b")

    def test_no_repo_raises(self) -> None:
        with pytest.raises(ValueError, match="missing owner/repo"):
            parse_github_url("https://github.com/onlyowner")

    def test_invalid_shorthand_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            parse_github_url("just-a-name")

    def test_http_url_accepted(self) -> None:
        owner, repo, branch, subpath = parse_github_url("http://github.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"


class TestSanitizeFilename:
    def test_normal_name(self) -> None:
        assert sanitize_filename("README.md") == "README.md"

    def test_slashes_removed(self) -> None:
        result = sanitize_filename("path/to/file.txt")
        assert "/" not in result
        assert "\\" not in result

    def test_backslashes_removed(self) -> None:
        result = sanitize_filename("path\\to\\file.txt")
        assert "\\" not in result

    def test_windows_reserved_con(self) -> None:
        result = sanitize_filename("CON")
        assert result == "_CON"

    def test_windows_reserved_prn(self) -> None:
        result = sanitize_filename("PRN")
        assert result == "_PRN"

    def test_windows_reserved_aux(self) -> None:
        result = sanitize_filename("AUX")
        assert result == "_AUX"

    def test_windows_reserved_nul(self) -> None:
        result = sanitize_filename("NUL")
        assert result == "_NUL"

    def test_windows_reserved_com1(self) -> None:
        result = sanitize_filename("COM1")
        assert result == "_COM1"

    def test_windows_reserved_lpt1(self) -> None:
        result = sanitize_filename("LPT1")
        assert result == "_LPT1"

    def test_windows_reserved_with_extension(self) -> None:
        result = sanitize_filename("CON.txt")
        assert result == "_CON.txt"

    def test_special_chars_removed(self) -> None:
        result = sanitize_filename('file<>:"|?*name.txt')
        for char in '<>:"/\\|?*':
            assert char not in result

    def test_unicode_preserved(self) -> None:
        assert sanitize_filename("日本語.txt") == "日本語.txt"

    def test_spaces_preserved(self) -> None:
        assert sanitize_filename("my file.txt") == "my file.txt"

    def test_dots_preserved(self) -> None:
        assert sanitize_filename("file.name.txt") == "file.name.txt"

    def test_empty_string(self) -> None:
        assert sanitize_filename("") == ""

    def test_case_insensitive_reserved(self) -> None:
        result = sanitize_filename("con")
        assert result == "_con"
