import os
from pathlib import Path

import pytest

from external_helpers import FakeTransport, fixture_json, home  # noqa: F401
from iconreplacer.catalog.external import (
    DEFAULT_GITHUB_REPOS,
    add_local_folder,
    build_external_sources,
    github_source_id,
    parse_github_repo,
    remove_local_folder,
)
from iconreplacer.catalog.github_source import GitHubRepoSource
from iconreplacer.catalog.iconify_source import IconifySource
from iconreplacer.catalog.local_source import LocalFolderSource, local_source_id
from iconreplacer.catalog.registry import SourceRegistry
from iconreplacer.core.contracts import (
    DynamicIconSource,
    IconBytesProvider,
    IconSource,
    SearchableIconSource,
)
from iconreplacer.core.models import Section, SourceState


def test_defaults(home):  # noqa: F811
    sources = build_external_sources(network_allowed=True, transport=FakeTransport())
    ids = [s.info.id for s in sources]
    assert ids == [
        "iconify",
        "phosphor",
        "gh-lavimahal-windowsicons",
        "gh-sameerasw-folder-icons",
    ]
    assert DEFAULT_GITHUB_REPOS == ("LaviMahal/WindowsIcons", "sameerasw/folder-icons")
    for s in sources:
        assert isinstance(s, IconSource | DynamicIconSource | IconBytesProvider)
        assert s.info.section is Section.ONLINE and s.info.requires_network
    assert sum(isinstance(s, SearchableIconSource) for s in sources) == 2
    registry = SourceRegistry(sources)  # ids are unique
    assert len(registry.sources(Section.ONLINE)) == 4


def test_custom_repos_and_local_folders(tmp_path, home):  # noqa: F811
    sources = build_external_sources(
        network_allowed=False,
        github_repos=[
            "https://github.com/Foo/Bar.git",
            "foo/bar",  # duplicate id (case-insensitive)
            "not a repo",
            "../x",
        ],
        local_folders=[tmp_path / "icons"],
        transport=FakeTransport(),
    )
    ids = [s.info.id for s in sources]
    assert ids == ["iconify", "phosphor", "gh-foo-bar", local_source_id(tmp_path / "icons")]
    assert isinstance(sources[2], GitHubRepoSource) and isinstance(sources[3], LocalFolderSource)
    assert sources[3].info.section is Section.LOCAL
    assert len(build_external_sources(network_allowed=True, github_repos=[])) == 2


def test_network_flag_is_applied(home):  # noqa: F811
    sources = build_external_sources(network_allowed=False, transport=FakeTransport())
    assert all(s.state() is SourceState.OFFLINE for s in sources)
    assert all(isinstance(s, IconifySource | GitHubRepoSource) for s in sources)


def test_add_and_remove_local_folder(tmp_path):
    sources: list = []
    first = add_local_folder(sources, tmp_path)
    again = add_local_folder(sources, str(tmp_path))
    assert first is again and len(sources) == 1
    assert not remove_local_folder(sources, tmp_path / "other")
    assert remove_local_folder(sources, tmp_path) and sources == []
    added = add_local_folder(sources, tmp_path)
    assert remove_local_folder(sources, added.info.id) and sources == []


def test_remove_only_touches_local_sources(home):  # noqa: F811
    sources = build_external_sources(network_allowed=True, transport=FakeTransport())
    assert not remove_local_folder(sources, "iconify")
    assert len(sources) == 4


def test_parse_and_ids():
    assert parse_github_repo("https://github.com/sameerasw/folder-icons") == (
        "sameerasw",
        "folder-icons",
    )
    assert github_source_id("A.B", "c_d") == "gh-a-b-c-d"
    with pytest.raises(ValueError):
        parse_github_repo("https://github.com/a/b/c")


def test_offline_default_sources_serve_cache_without_any_call(qtbot, home):  # noqa: F811
    t = FakeTransport()
    t.add(
        "https://api.iconify.design/search?query=folder", fixture_json("iconify_search_folder.json")
    )
    online = build_external_sources(network_allowed=True, github_repos=[], transport=t)
    online[0].entries()
    qtbot.waitUntil(lambda: bool(online[0].entries()))

    t2 = FakeTransport()
    offline = build_external_sources(network_allowed=False, github_repos=[], transport=t2)
    offline[0].entries()
    qtbot.waitUntil(lambda: bool(offline[0].entries()))
    assert offline[0].state() is SourceState.OFFLINE
    assert [e.id for e in offline[0].entries()] == [e.id for e in online[0].entries()]
    assert t2.calls == []


LIVE = os.environ.get("ICONREPLACER_NETWORK_TESTS") == "1"


@pytest.mark.network
@pytest.mark.skipif(not LIVE, reason="live smoke test: set ICONREPLACER_NETWORK_TESTS=1")
def test_live_smoke(qtbot, home):  # noqa: F811
    sources = build_external_sources(network_allowed=True, github_repos=["sameerasw/folder-icons"])
    iconify, phosphor, github = sources
    for s in (iconify, phosphor, github):
        s.entries()
    for s in (iconify, phosphor, github):
        qtbot.waitUntil(lambda s=s: s.state() is SourceState.READY, timeout=60000)
        assert s.entries(), s.info.id
    assert all(not e.ref.location.endswith(("-bold", "-fill")) for e in phosphor.entries())
    data = phosphor.fetch_bytes(phosphor.entries()[0])
    assert data.startswith(b"<svg")
    assert Path(home).exists()
