"""On-disk cache for online sources.

File names are hashes of an opaque key, never derived from remote paths, so a
hostile path (``../../x``) cannot escape the cache directory. Writes are atomic.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from iconreplacer.core import paths

INDEX_TTL = 24 * 3600.0


def hash_name(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:40]


class DiskCache:
    def __init__(
        self,
        source_id: str,
        ttl: float = INDEX_TTL,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.source_id = source_id
        self.ttl = ttl
        self._clock = clock

    @property
    def directory(self) -> Path:
        return paths.cache_dir(self.source_id)

    def _file(self, key: str, suffix: str) -> Path:
        return self.directory / f"{hash_name(key)}{suffix}"

    def _write(self, target: Path, data: bytes) -> None:
        try:
            fd, tmp = tempfile.mkstemp(dir=target.parent, prefix="tmp-", suffix=".part")
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                os.replace(tmp, target)
            except BaseException:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)
                raise
        except OSError:
            pass  # the cache is an optimisation only

    # -- binary blobs (images) ---------------------------------------------
    def get_bytes(self, key: str) -> bytes | None:
        try:
            return self._file(key, ".bin").read_bytes()
        except OSError:
            return None

    def put_bytes(self, key: str, data: bytes) -> None:
        self._write(self._file(key, ".bin"), data)

    # -- JSON documents (indexes) ------------------------------------------
    def get_json(self, key: str) -> tuple[Any, float] | None:
        """Return ``(data, fetched_at)`` or None."""
        try:
            raw = json.loads(self._file(key, ".json").read_text("utf-8"))
            return raw["data"], float(raw["fetched_at"])
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def put_json(self, key: str, data: Any) -> None:
        payload = json.dumps({"fetched_at": self._clock(), "data": data}, separators=(",", ":"))
        self._write(self._file(key, ".json"), payload.encode("utf-8"))

    def is_fresh(self, fetched_at: float) -> bool:
        return 0 <= self._clock() - fetched_at < self.ttl
