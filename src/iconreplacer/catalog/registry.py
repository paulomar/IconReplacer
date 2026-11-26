"""Aggregates icon sources and exposes a unified catalog."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from iconreplacer.core.contracts import IconSource
from iconreplacer.core.models import IconEntry, Section, SourceInfo


class SourceRegistry:
    def __init__(self, sources: Iterable[IconSource] = ()) -> None:
        self._sources: dict[str, IconSource] = {}
        self._enabled: dict[str, bool] = {}
        for s in sources:
            self.add(s)

    def add(self, source: IconSource) -> None:
        sid = source.info.id
        if sid in self._sources:
            raise ValueError(f"duplicate source id: {sid}")
        self._sources[sid] = source
        self._enabled[sid] = True

    def sources(self, section: Section | None = None) -> list[IconSource]:
        return [s for s in self._sources.values() if section is None or s.info.section is section]

    def get(self, source_id: str) -> IconSource:
        return self._sources[source_id]

    def info(self, source_id: str) -> SourceInfo:
        return self._sources[source_id].info

    def set_enabled(self, source_id: str, enabled: bool) -> None:
        self._enabled[source_id] = enabled

    def is_enabled(self, source_id: str) -> bool:
        return self._enabled.get(source_id, False)

    def is_available(self, source_id: str, network_allowed: bool) -> bool:
        info = self.info(source_id)
        return self.is_enabled(source_id) and (network_allowed or not info.requires_network)

    def all_entries(self) -> Sequence[IconEntry]:
        out: list[IconEntry] = []
        for s in self._sources.values():
            out.extend(s.entries())
        return out

    def count(self, source_id: str) -> int:
        return len(self._sources[source_id].entries())
