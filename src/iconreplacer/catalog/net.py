"""Tiny, hardened HTTP client for the external icon sources.

HTTPS only, per-source host allow-list, redirects re-validated hop by hop,
connect/read timeouts, response size limits, gzip support and typed errors.
The wire is behind an injectable ``Transport`` so tests never touch the network.
"""

from __future__ import annotations

import gzip
import ssl
import urllib.error
import urllib.request
import zlib
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from iconreplacer.version import __version__

USER_AGENT = f"IconReplacer/{__version__}"
TIMEOUT = 10.0
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_INDEX_BYTES = 20 * 1024 * 1024
MAX_REDIRECTS = 3


class NetError(OSError):
    """Base class of every error raised by the client."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


class OfflineError(NetError):
    """The network is not allowed (or unreachable)."""


class BlockedError(NetError):
    """Scheme or host rejected by policy."""


class TooLargeError(NetError):
    """Response exceeds the size limit."""


class TransportError(NetError):
    """Connection, TLS or timeout failure."""


class HttpError(NetError):
    """HTTP status >= 400."""

    def __init__(self, status: int, message: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.headers = headers or {}

    @property
    def rate_limited(self) -> bool:
        if self.status == 429:
            return True
        return self.status == 403 and (
            self.headers.get("x-ratelimit-remaining") == "0" or "retry-after" in self.headers
        )


@dataclass(frozen=True, slots=True)
class Response:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)  # lower-case names
    url: str = ""


# (url, headers, timeout, max_bytes) -> Response. Must NOT follow redirects.
Transport = Callable[[str, dict[str, str], float, int], Response]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


def _inflate(body: bytes, max_bytes: int) -> bytes:
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    out = decoder.decompress(body, max_bytes + 1)
    if len(out) > max_bytes or decoder.unconsumed_tail:
        raise TooLargeError(f"response larger than {max_bytes // 1024} KiB")
    return out


def urllib_transport(url: str, headers: dict[str, str], timeout: float, max_bytes: int) -> Response:
    """Default transport: urllib with TLS verification and no automatic redirects."""
    opener = urllib.request.build_opener(
        _NoRedirect, urllib.request.HTTPSHandler(context=ssl.create_default_context())
    )
    request = urllib.request.Request(url, headers=headers, method="GET")  # noqa: S310
    try:
        resp = opener.open(request, timeout=timeout)
        status = resp.status
    except urllib.error.HTTPError as exc:  # 3xx/4xx/5xx
        resp = exc
        status = exc.code
    except (urllib.error.URLError, TimeoutError, ssl.SSLError, OSError) as exc:
        raise TransportError(f"connection failed: {getattr(exc, 'reason', exc)}") from exc
    try:
        hdrs = {k.lower(): v for k, v in resp.headers.items()}
        raw = resp.read(max_bytes + 1)
    except (TimeoutError, OSError) as exc:
        raise TransportError(f"read failed: {exc}") from exc
    finally:
        resp.close()
    if hdrs.get("content-encoding", "").lower() == "gzip":
        try:
            raw = _inflate(raw, max_bytes)
        except (zlib.error, EOFError, gzip.BadGzipFile) as exc:
            raise TransportError("invalid gzip data") from exc
    if len(raw) > max_bytes:
        raise TooLargeError(f"response larger than {max_bytes // 1024} KiB")
    return Response(status, raw, hdrs, url)


class HttpClient:
    """GET-only client bound to a host allow-list and a network-allowed flag."""

    def __init__(
        self,
        allowed_hosts: Collection[str],
        transport: Transport | None = None,
        network_allowed: bool = True,
        timeout: float = TIMEOUT,
    ) -> None:
        self._hosts = frozenset(h.lower() for h in allowed_hosts)
        self._transport = transport or urllib_transport
        self._allowed = network_allowed
        self._timeout = timeout

    @property
    def network_allowed(self) -> bool:
        return self._allowed

    @network_allowed.setter
    def network_allowed(self, value: bool) -> None:
        self._allowed = bool(value)

    def check_url(self, url: str) -> str:
        """Validate scheme and host; returns the URL or raises ``BlockedError``."""
        parts = urlsplit(url)
        if parts.scheme != "https":
            raise BlockedError(f"only HTTPS is allowed: {parts.scheme or 'no scheme'}")
        if parts.username or parts.password:
            raise BlockedError("credentials in URL are not allowed")
        host = (parts.hostname or "").lower()
        if host not in self._hosts:
            raise BlockedError(f"host not allowed: {host or '?'}")
        try:
            if parts.port not in (None, 443):
                raise BlockedError("only port 443 is allowed")
        except ValueError as exc:
            raise BlockedError("invalid port") from exc
        return url

    def get(self, url: str, *, max_bytes: int = MAX_FILE_BYTES, accept: str = "*/*") -> Response:
        """Fetch ``url``; raises a ``NetError`` subclass on any failure (including HTTP >= 400)."""
        if not self._allowed:
            raise OfflineError("network access is disabled")
        headers = {"User-Agent": USER_AGENT, "Accept": accept, "Accept-Encoding": "gzip"}
        current = self.check_url(url)
        for _ in range(MAX_REDIRECTS + 1):
            resp = self._transport(current, headers, self._timeout, max_bytes)
            if len(resp.body) > max_bytes:
                raise TooLargeError(f"response larger than {max_bytes // 1024} KiB")
            if resp.status in (301, 302, 303, 307, 308):
                location = resp.headers.get("location")
                if not location:
                    raise TransportError("redirect without location")
                current = self.check_url(urljoin(current, location))
                continue
            if resp.status >= 400:
                raise HttpError(resp.status, f"HTTP {resp.status}", resp.headers)
            return resp
        raise TransportError("too many redirects")
