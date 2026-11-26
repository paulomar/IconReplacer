import json
import re

import pytest

from external_helpers import FakeTransport, fixture_json, home  # noqa: F401
from iconreplacer.catalog.github_source import (
    NO_LICENSE,
    GitHubRepoSource,
    parse_repo,
    pick_files,
    raw_url,
    source_id_for,
)
from iconreplacer.core.contracts import DynamicIconSource, IconBytesProvider, IconSource
from iconreplacer.core.models import CATEGORIES, IconKind, RefKind, SourceState

API = "https://api.github.com/repos"


def route(t, owner, repo, repo_json, tree_json, branch="main"):
    t.add(f"{API}/{owner}/{repo}/git/trees/{branch}?recursive=1", tree_json)
    t.add(f"{API}/{owner}/{repo}", repo_json)


def lavi_transport():
    t = FakeTransport()
    route(
        t,
        "LaviMahal",
        "WindowsIcons",
        fixture_json("github_repo_lavi.json"),
        fixture_json("github_tree_lavi.json"),
    )
    return t


def make(t, **kw):
    return GitHubRepoSource("LaviMahal", "WindowsIcons", transport=t, **kw)


def wait_ready(qtbot, src, state=SourceState.READY):
    src.entries()
    qtbot.waitUntil(lambda: src.state() is state)


def test_protocols_and_id(home):  # noqa: F811
    s = make(FakeTransport())
    for proto in (IconSource, DynamicIconSource, IconBytesProvider):
        assert isinstance(s, proto)
    assert s.info.id == "gh-lavimahal-windowsicons" == source_id_for("LaviMahal", "WindowsIcons")
    assert s.info.requires_network


def test_index_parsing(qtbot, home):  # noqa: F811
    t = lavi_transport()
    src = make(t)
    wait_ready(qtbot, src)
    tree = fixture_json("github_tree_lavi.json")["tree"]
    icos = [x["path"] for x in tree if x["path"].endswith(".ico")]
    entries = src.entries()
    assert len(entries) == len(icos) > 0
    assert not any(e.ref.location.endswith(".md") for e in entries)
    assert t.calls_matching("/git/trees/main?recursive=1") and t.calls[0].endswith("/WindowsIcons")
    for e in entries:
        assert e.kind is IconKind.FULL and e.ref.kind is RefKind.REMOTE
        assert e.license == NO_LICENSE == src.info.license
        assert e.categories and e.categories <= set(CATEGORIES)
        assert e.ref.location.startswith(
            "https://raw.githubusercontent.com/LaviMahal/WindowsIcons/main/"
        )
        assert re.fullmatch(r"gh-lavimahal-windowsicons:[0-9a-f]{16}", e.id)
    folders = [e for e in entries if "/folders/" in e.ref.location]
    assert folders and all("Folders" in e.categories for e in folders)
    assert NO_LICENSE == "No license declared - personal use at your own discretion"


def test_license_reported_by_api_is_used(qtbot, home):  # noqa: F811
    t = FakeTransport()
    repo = {"default_branch": "main", "license": {"spdx_id": "MIT", "name": "MIT License"}}
    route(t, "LaviMahal", "WindowsIcons", repo, fixture_json("github_tree_lavi.json"))
    src = make(t)
    wait_ready(qtbot, src)
    assert src.entries()[0].license == "MIT" and src.info.license == "MIT"


def test_non_default_branch_is_resolved(qtbot, home):  # noqa: F811
    t = FakeTransport()
    tree = {"tree": [{"path": "a/b.svg", "type": "blob", "size": 10}]}
    route(t, "o", "r", {"default_branch": "dev/x", "license": None}, tree, branch="dev%2Fx")
    src = GitHubRepoSource("o", "r", transport=t)
    wait_ready(qtbot, src)
    assert src.entries()[0].ref.location == "https://raw.githubusercontent.com/o/r/dev/x/a/b.svg"


def test_dedupe_prefers_ico_svg_png_icns():
    files = [
        ("ICO/Archive/Archive 1.ico", 100),
        ("PNGs/Archive/Archive 1.png", 100),
        ("ICO/1.ico", 100),
        ("PNGs/1.png", 100),
        ("PNGs/only-png.png", 100),
        ("svg/both.svg", 100),
        ("png/both.png", 100),
        ("misc/x.icns", 100),
        ("misc/x.png", 100),
        ("Other/Archive 1.png", 100),  # different folder: a different icon
        ("ICO/_Template.psd", 100),
        ("ICO/huge.ico", 50 * 1024 * 1024),
        ("README.md", 5),
        (".gitignore", 5),
    ]
    got = [p for p, _ in pick_files(files)]
    assert sorted(got, key=str.casefold) == sorted(
        [
            "ICO/Archive/Archive 1.ico",
            "ICO/1.ico",
            "PNGs/only-png.png",
            "svg/both.svg",
            "misc/x.png",
            "Other/Archive 1.png",
        ],
        key=str.casefold,
    )


def test_same_dir_extensions_dedupe_by_stem():
    got = [p for p, _ in pick_files([("a/x.png", 1), ("a/x.ico", 1), ("a/X.svg", 1)])]
    assert got == ["a/x.ico"]


def test_raw_url_is_percent_encoded():
    url = raw_url("o", "r", "main", "ICO/Archive/Archive 1 #2?.ico")
    assert url == "https://raw.githubusercontent.com/o/r/main/ICO/Archive/Archive%201%20%232%3F.ico"
    assert "%C3%A9" in raw_url("o", "r", "main", "é.ico")
    assert ".." not in raw_url("o", "r", "main", "a/b.ico")


def test_fetch_bytes_uses_raw_host_and_disk_cache(qtbot, home):  # noqa: F811
    t = lavi_transport()
    t.add("https://raw.githubusercontent.com/LaviMahal/WindowsIcons/main/", b"\x00\x00\x01\x00icon")
    src = make(t)
    wait_ready(qtbot, src)
    entry = src.entries()[0]
    assert src.fetch_bytes(entry).startswith(b"\x00\x00\x01\x00")
    raw_calls = t.calls_matching("raw.githubusercontent.com")
    assert len(raw_calls) == 1 and " " not in raw_calls[0]
    src.fetch_bytes(entry)
    assert len(t.calls_matching("raw.githubusercontent.com")) == 1
    files = [f for f in (home / "cache").rglob("*") if f.is_file()]
    assert all(re.fullmatch(r"[0-9a-f]{40}\.(bin|json)", f.name) for f in files)


def test_forged_entry_cannot_fetch_arbitrary_urls(qtbot, home):  # noqa: F811
    import copy

    t = lavi_transport()
    src = make(t)
    wait_ready(qtbot, src)
    from iconreplacer.core.models import IconRef

    forged = copy.replace(src.entries()[0], ref=IconRef(RefKind.REMOTE, "https://evil.test/a.ico"))
    forged = copy.replace(forged, id="gh-lavimahal-windowsicons:ffffffffffffffff")
    with pytest.raises(ValueError):
        src.fetch_bytes(forged)
    assert not t.calls_matching("evil")


def test_rate_limit_sets_error_and_cache_is_served(qtbot, home):  # noqa: F811
    t = lavi_transport()
    first = make(t)
    wait_ready(qtbot, first)
    expected = [e.id for e in first.entries()]
    # age the cached index beyond the 24 h TTL
    for f in (home / "cache").rglob("*.json"):
        data = json.loads(f.read_text("utf-8"))
        data["fetched_at"] = 0
        f.write_text(json.dumps(data), "utf-8")

    t2 = FakeTransport()
    t2.add(f"{API}/LaviMahal/WindowsIcons", b"{}", 403, {"x-ratelimit-remaining": "0"})
    second = make(t2)
    wait_ready(qtbot, second, SourceState.ERROR)
    assert "rate limit" in (second.last_error() or "").lower()
    assert [e.id for e in second.entries()] == expected


def test_rate_limit_without_cache(qtbot, home):  # noqa: F811
    t = FakeTransport()
    t.add(f"{API}/LaviMahal/WindowsIcons", b"{}", 429)
    src = make(t)
    wait_ready(qtbot, src, SourceState.ERROR)
    assert "rate limit" in src.last_error().lower() and not src.entries()


def test_not_found_message(qtbot, home):  # noqa: F811
    t = FakeTransport()
    t.add(f"{API}/LaviMahal/WindowsIcons", b"{}", 404)
    src = make(t)
    wait_ready(qtbot, src, SourceState.ERROR)
    assert "not found" in src.last_error()


def test_fresh_cache_skips_network_and_stale_is_revalidated(qtbot, home):  # noqa: F811
    t = lavi_transport()
    wait_ready(qtbot, make(t))
    t.calls.clear()
    fresh = make(t)
    wait_ready(qtbot, fresh)
    assert fresh.entries() and t.calls == []  # fresh within 24 h

    for f in (home / "cache").rglob("*.json"):
        data = json.loads(f.read_text("utf-8"))
        data["fetched_at"] = 0
        f.write_text(json.dumps(data), "utf-8")
    stale = make(t)
    stale.entries()
    qtbot.waitUntil(lambda: bool(stale.entries()))  # served from the stale cache
    qtbot.waitUntil(lambda: bool(t.calls) and stale.state() is SourceState.READY)
    assert t.calls  # revalidated in the background


def test_offline_serves_cache_without_transport_calls(qtbot, home):  # noqa: F811
    t = lavi_transport()
    first = make(t)
    wait_ready(qtbot, first)
    t2 = FakeTransport()
    off = make(t2, network_allowed=False)
    wait_ready(qtbot, off, SourceState.OFFLINE)
    qtbot.waitUntil(lambda: bool(off.entries()))
    assert len(off.entries()) == len(first.entries())
    assert t2.calls == []
    with pytest.raises(OSError):
        off.fetch_bytes(off.entries()[0])  # not cached and offline
    assert t2.calls == []


def test_truncated_or_bad_json_is_error(qtbot, home):  # noqa: F811
    t = FakeTransport()
    t.add(f"{API}/LaviMahal/WindowsIcons", b"not json")
    src = make(t)
    wait_ready(qtbot, src, SourceState.ERROR)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("LaviMahal/WindowsIcons", ("LaviMahal", "WindowsIcons")),
        ("https://github.com/sameerasw/folder-icons", ("sameerasw", "folder-icons")),
        ("https://github.com/LaviMahal/WindowsIcons.git", ("LaviMahal", "WindowsIcons")),
        ("  https://github.com/a/b.c/  ", ("a", "b.c")),
    ],
)
def test_parse_repo_accepts(text, expected):
    assert parse_repo(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "a/b/c",
        "../x",
        "a/..",
        "http://github.com/a/b",
        "https://evil.test/a/b",
        "https://github.com/a/b/tree/main",
        "https://github.com.evil.test/a/b",
        "-bad/repo",
        "a b/c",
        "a/b;rm",
        "",
        "owner",
    ],
)
def test_parse_repo_rejects(text):
    with pytest.raises(ValueError):
        parse_repo(text)
