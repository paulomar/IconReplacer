import re

from external_helpers import home  # noqa: F401
from iconreplacer.catalog.online_cache import INDEX_TTL, DiskCache, hash_name

HASHED = re.compile(r"[0-9a-f]{40}\.(bin|json)")


def test_names_are_hashes_inside_source_directory(home):  # noqa: F811
    cache = DiskCache("src-a")
    hostile = ["../../evil.ico", "..\\..\\evil.ico", "C:/Windows/x.ico", "a/b c/%2e%2e/d.png"]
    for key in hostile:
        cache.put_bytes(key, b"data")
        cache.put_json(key, {"k": key})
        assert cache.get_bytes(key) == b"data"
        assert cache.get_json(key)[0] == {"k": key}
    files = list(cache.directory.iterdir())
    assert files and all(HASHED.fullmatch(f.name) for f in files)
    assert all(f.parent == home / "cache" / "src-a" for f in files)
    assert not list(home.rglob("evil*"))


def test_hash_is_stable_and_distinct():
    assert hash_name("a") == hash_name("a") != hash_name("b")


def test_missing_and_corrupt_entries_return_none(home):  # noqa: F811
    cache = DiskCache("src-b")
    assert cache.get_bytes("x") is None and cache.get_json("x") is None
    (cache.directory / f"{hash_name('x')}.json").write_text("{not json", "utf-8")
    assert cache.get_json("x") is None


def test_ttl_freshness_uses_injected_clock(home):  # noqa: F811
    now = [1000.0]
    cache = DiskCache("src-c", clock=lambda: now[0])
    cache.put_json("k", [1])
    _, fetched = cache.get_json("k")
    assert cache.is_fresh(fetched)
    now[0] += INDEX_TTL - 1
    assert cache.is_fresh(fetched)
    now[0] += 2
    assert not cache.is_fresh(fetched)
    assert INDEX_TTL == 24 * 3600


def test_no_partial_files_left(home):  # noqa: F811
    cache = DiskCache("src-d")
    cache.put_bytes("k", b"x")
    assert not list(cache.directory.glob("*.part"))
