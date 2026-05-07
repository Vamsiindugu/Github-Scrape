import time

from github_scrape.api import RepoFile, RepoTree, TreeCache


def _make_tree(owner: str = "o", repo: str = "r", branch: str = "b") -> RepoTree:
    return RepoTree(
        owner=owner,
        repo=repo,
        branch=branch,
        files=[RepoFile(path="f.txt", type="blob", size=10, sha="abc", url="")],
        truncated=False,
    )


class TestTreeCache:
    def test_put_and_get(self) -> None:
        cache = TreeCache(ttl=60.0)
        tree = _make_tree()
        cache.put("o", "r", "b", tree)
        result = cache.get("o", "r", "b")
        assert result is not None
        assert result.owner == "o"

    def test_get_missing_returns_none(self) -> None:
        cache = TreeCache(ttl=60.0)
        assert cache.get("x", "y", "z") is None

    def test_expired_entry_returns_none(self) -> None:
        cache = TreeCache(ttl=0.0)
        tree = _make_tree()
        cache.put("o", "r", "b", tree)
        time.sleep(0.01)
        assert cache.get("o", "r", "b") is None

    def test_invalidate_all(self) -> None:
        cache = TreeCache(ttl=60.0)
        cache.put("a", "b", "c", _make_tree())
        cache.put("d", "e", "f", _make_tree())
        assert cache.size == 2
        count = cache.invalidate()
        assert count == 2
        assert cache.size == 0

    def test_invalidate_by_owner(self) -> None:
        cache = TreeCache(ttl=60.0)
        cache.put("keep", "r", "b", _make_tree())
        cache.put("remove", "r", "b", _make_tree())
        count = cache.invalidate(owner="remove")
        assert count == 1
        assert cache.size == 1

    def test_size_property(self) -> None:
        cache = TreeCache(ttl=60.0)
        assert cache.size == 0
        cache.put("o", "r", "b", _make_tree())
        assert cache.size == 1
