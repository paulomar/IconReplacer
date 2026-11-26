import gzip

import pytest

from external_helpers import FakeTransport
from iconreplacer.catalog import net
from iconreplacer.catalog.net import (
    BlockedError,
    HttpClient,
    HttpError,
    OfflineError,
    Response,
    TooLargeError,
    TransportError,
)

HOST = "api.example.test"


def client(transport, **kw):
    return HttpClient([HOST], transport, **kw)


def test_get_ok_sends_generic_user_agent():
    t = FakeTransport()
    t.add(f"https://{HOST}/a", b"hello")
    resp = client(t).get(f"https://{HOST}/a")
    assert resp.body == b"hello"
    ua = t.headers[0]["User-Agent"]
    assert ua == net.USER_AGENT and ua.startswith("IconReplacer/")
    assert "gzip" in t.headers[0]["Accept-Encoding"]


@pytest.mark.parametrize(
    "url",
    [
        f"http://{HOST}/a",
        "ftp://api.example.test/a",
        "file:///c:/windows/win.ini",
        f"https://user:pw@{HOST}/a",
        f"https://{HOST}:8443/a",
        "https://evil.test/a",
        f"https://{HOST}.evil.test/a",
    ],
)
def test_rejects_scheme_host_credentials_port_without_connecting(url):
    t = FakeTransport()
    with pytest.raises(BlockedError):
        client(t).get(url)
    assert t.calls == []


def test_redirect_to_allowed_https_is_followed():
    t = FakeTransport()
    t.add(f"https://{HOST}/old", b"", 302, {"location": "/new"})
    t.add(f"https://{HOST}/new", b"moved")
    assert client(t).get(f"https://{HOST}/old").body == b"moved"


@pytest.mark.parametrize("target", [f"http://{HOST}/x", "https://evil.test/x"])
def test_redirect_to_non_https_or_foreign_host_is_rejected(target):
    t = FakeTransport()
    t.add(f"https://{HOST}/old", b"", 301, {"location": target})
    with pytest.raises(BlockedError):
        client(t).get(f"https://{HOST}/old")
    assert t.calls == [f"https://{HOST}/old"]


def test_redirect_loop_is_bounded():
    t = FakeTransport()
    t.add(f"https://{HOST}/loop", b"", 302, {"location": f"https://{HOST}/loop"})
    with pytest.raises(TransportError):
        client(t).get(f"https://{HOST}/loop")
    assert len(t.calls) == net.MAX_REDIRECTS + 1


def test_size_limit():
    t = FakeTransport()
    t.add(f"https://{HOST}/big", b"x" * 101)
    with pytest.raises(TooLargeError):
        client(t).get(f"https://{HOST}/big", max_bytes=100)


def test_http_errors_are_typed_and_rate_limit_detected():
    t = FakeTransport()
    t.add(f"https://{HOST}/missing", b"", 404)
    t.add(f"https://{HOST}/limit", b"", 403, {"x-ratelimit-remaining": "0"})
    t.add(f"https://{HOST}/forbidden", b"", 403)
    t.add(f"https://{HOST}/slow", b"", 429)
    c = client(t)
    with pytest.raises(HttpError) as e404:
        c.get(f"https://{HOST}/missing")
    assert e404.value.status == 404 and not e404.value.rate_limited
    for path in ("limit", "slow"):
        with pytest.raises(HttpError) as e:
            c.get(f"https://{HOST}/{path}")
        assert e.value.rate_limited
    with pytest.raises(HttpError) as e403:
        c.get(f"https://{HOST}/forbidden")
    assert not e403.value.rate_limited


def test_offline_fails_fast_without_transport_call():
    t = FakeTransport()
    c = client(t, network_allowed=False)
    with pytest.raises(OfflineError):
        c.get(f"https://{HOST}/a")
    assert t.calls == []
    c.network_allowed = True
    t.add(f"https://{HOST}/a", b"ok")
    assert c.get(f"https://{HOST}/a").body == b"ok"


def test_all_errors_are_oserror():
    for cls in (BlockedError, OfflineError, TooLargeError, TransportError):
        assert issubclass(cls, OSError)


def test_gzip_inflate_is_size_bounded():
    data = gzip.compress(b"a" * 1000)
    assert net._inflate(data, 2000) == b"a" * 1000
    with pytest.raises(TooLargeError):
        net._inflate(data, 500)


def test_response_dataclass_defaults():
    assert Response(200, b"").headers == {}
