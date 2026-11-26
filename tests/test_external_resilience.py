import threading
import time

from external_helpers import FakeTransport, fixture_json, home  # noqa: F401
from iconreplacer.catalog import external_base
from iconreplacer.catalog.external import build_external_sources, shutdown_all
from iconreplacer.catalog.iconify_source import API, default_iconify_sources
from iconreplacer.core.models import SourceState


def phosphor_with(t):
    t.add(f"{API}/collection?prefix=ph", fixture_json("iconify_ph_collection.json"))
    t.add(f"{API}/collections?prefixes=ph", fixture_json("iconify_collections_ph.json"))
    return default_iconify_sources(transport=t)[1]


def batch_calls(t):
    return t.calls_matching("/ph.json?icons=")


def test_backoff_limits_retries_until_clock_expires(qtbot, home):  # noqa: F811
    t = FakeTransport()
    t.add(f"{API}/ph.json?icons=", b"", 500)
    src = phosphor_with(t)
    src.entries()
    qtbot.waitUntil(lambda: src.state() is SourceState.READY and bool(src.entries()))
    now = [1000.0]
    src._clock = lambda: now[0]
    entry = src.entries()[0]

    def settle(n):
        qtbot.waitUntil(lambda: len(batch_calls(t)) == n and entry.id not in src._inflight)
        qtbot.waitUntil(lambda: src._backing_off(entry.id))

    for _ in range(3):
        src.render(entry, 16)
    settle(1)
    for _ in range(10):  # repeated paints while backing off: placeholder, no request
        assert src.render(entry, 16).pixelColor(8, 8).alpha() == 0
    qtbot.wait(150)
    assert len(batch_calls(t)) == 1

    now[0] += 29
    src.render(entry, 16)
    qtbot.wait(100)
    assert len(batch_calls(t)) == 1  # 30 s not yet elapsed
    now[0] += 2  # 31 s
    src.render(entry, 16)
    settle(2)
    now[0] += 31  # delay doubled to 60 s
    src.render(entry, 16)
    qtbot.wait(100)
    assert len(batch_calls(t)) == 2
    now[0] += 30
    src.render(entry, 16)
    settle(3)
    assert src._backoff[entry.id][1] == 120.0


def test_backoff_is_capped_and_reset_by_refresh_toggle_and_success(qtbot, home):  # noqa: F811
    src = phosphor_with(FakeTransport())
    for _ in range(12):
        src._fail("x")
    assert src._backoff["x"][1] == external_base.BACKOFF_MAX == 600.0
    assert external_base.BACKOFF_START == 30.0
    src.refresh()
    assert not src._backoff
    src._fail("x")
    src.set_network_allowed(False)
    assert not src._backoff
    src._fail("x")
    src.set_network_allowed(True)
    assert not src._backoff
    src._fail("x")
    src._reset_backoff("x")
    assert not src._backing_off("x")


def test_success_after_backoff_clears_it(qtbot, home):  # noqa: F811
    t = FakeTransport()
    t.add(f"{API}/ph.json?icons=", b"", 500)
    src = phosphor_with(t)
    src.entries()
    qtbot.waitUntil(lambda: src.state() is SourceState.READY and bool(src.entries()))
    now = [0.0]
    src._clock = lambda: now[0]
    entry = src.entries()[0]
    src.render(entry, 16)
    qtbot.waitUntil(lambda: src._backing_off(entry.id))
    t.routes.insert(0, (f"{API}/ph.json?icons=", _ok_response()))
    now[0] += 31
    src.render(entry, 16)
    qtbot.waitUntil(lambda: entry.id not in src._backoff)
    qtbot.waitUntil(lambda: src.render(entry, 16).pixelColor(8, 8).alpha() == 255)


def _ok_response():
    import json

    from iconreplacer.catalog.net import Response

    body = {"icons": {"folder": {"body": '<rect width="16" height="16"/>'}}}
    return Response(200, json.dumps(body).encode(), {}, "")


def test_close_and_shutdown_all_do_not_wait_for_inflight_http(qtbot, home):  # noqa: F811
    t = FakeTransport()
    entered = threading.Event()
    release = threading.Event()

    def blocked(url):
        entered.set()
        release.wait(10)
        raise OSError("late")

    t.add_handler(f"{API}/search?query=folder", blocked)
    sources = build_external_sources(network_allowed=True, github_repos=[], transport=t)
    calls = []
    sources[0].subscribe(lambda: calls.append(1))
    sources[0].entries()
    assert entered.wait(5)
    start = time.perf_counter()
    shutdown_all(sources)
    assert time.perf_counter() - start < 0.5
    release.set()
    qtbot.wait(200)
    assert not calls  # nothing is delivered after close
    assert sources[0].state() is SourceState.LOADING  # late result dropped silently
    assert not sources[0].entries()
    sources[0].refresh()  # no-op after close
    qtbot.wait(50)
    assert len(t.calls_matching("search?query=folder")) == 1


def test_pool_is_recreated_after_shutdown_and_threads_are_daemons(home):  # noqa: F811
    shutdown_all()
    pool = external_base.pool()
    done = threading.Event()
    pool.submit(done.set)
    assert done.wait(5)
    assert all(th.daemon for th in threading.enumerate() if th.name.startswith("iconreplacer-src-"))
