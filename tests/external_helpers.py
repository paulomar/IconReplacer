"""Shared helpers for the external source tests: fake transport, fixtures, home dir."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from iconreplacer.catalog.external_base import shutdown_pool
from iconreplacer.catalog.net import Response, TransportError
from iconreplacer.core import paths

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text("utf-8"))


def quiesce() -> None:
    """Stop the worker pool and wait for running tasks so none outlive the test's home."""
    shutdown_pool()
    for th in threading.enumerate():
        if th.name.startswith("iconreplacer-src-"):
            th.join(3)


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Isolated ICONREPLACER_HOME so caches never leave tmp_path."""
    monkeypatch.setenv(paths.ENV_HOME, str(tmp_path / "home"))
    paths.reset_cache()
    yield tmp_path / "home"
    quiesce()
    paths.reset_cache()


Handler = Response | Exception | Callable[[str], Response]


class FakeTransport:
    """Routes requests by URL prefix (first registered match wins) and records calls."""

    def __init__(self) -> None:
        self.routes: list[tuple[str, Handler]] = []
        self.calls: list[str] = []
        self.headers: list[dict[str, str]] = []
        self._lock = threading.Lock()

    def add(self, prefix: str, body: Any = b"", status: int = 200, headers: dict | None = None):
        if isinstance(body, bytes):
            raw = body
        elif isinstance(body, str):
            raw = body.encode("utf-8")
        else:
            raw = json.dumps(body).encode("utf-8")
        self.routes.append((prefix, Response(status, raw, headers or {}, prefix)))

    def add_handler(self, prefix: str, handler: Handler) -> None:
        self.routes.append((prefix, handler))

    def clear(self) -> None:
        self.routes.clear()

    def __call__(self, url: str, headers: dict[str, str], timeout: float, max_bytes: int):
        with self._lock:
            self.calls.append(url)
            self.headers.append(headers)
        for prefix, handler in self.routes:
            if url.startswith(prefix):
                if isinstance(handler, Exception):
                    raise handler
                if callable(handler):
                    return handler(url)
                return handler
        raise TransportError(f"no fake route for {url}")

    def calls_matching(self, text: str) -> list[str]:
        return [c for c in self.calls if text in c]
