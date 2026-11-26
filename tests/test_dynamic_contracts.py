from iconreplacer.core.contracts import (
    DynamicIconSource,
    IconBytesProvider,
    IconSource,
    SearchableIconSource,
)
from iconreplacer.core.models import IconEntry, IconRef, RefKind, Section, SourceInfo, SourceState


class StubDynamic:
    def __init__(self) -> None:
        self._subs: list = []
        self._entries: list[IconEntry] = []
        self._network = True

    @property
    def info(self) -> SourceInfo:
        return SourceInfo("stub", "Stub", "", Section.ONLINE, requires_network=True)

    def entries(self):
        return self._entries

    def render(self, entry, size):
        raise NotImplementedError

    def state(self) -> SourceState:
        return SourceState.READY if self._network else SourceState.OFFLINE

    def last_error(self):
        return None

    def subscribe(self, callback):
        self._subs.append(callback)
        return lambda: self._subs.remove(callback)

    def refresh(self) -> None:
        self._entries = [IconEntry("stub:1", "One", "stub", IconRef(RefKind.REMOTE, "stub/one"))]
        for cb in list(self._subs):
            cb()

    def set_network_allowed(self, allowed: bool) -> None:
        self._network = allowed

    def search(self, query: str) -> None:
        self.refresh()

    def fetch_bytes(self, entry) -> bytes:
        return b"<svg/>"


def test_stub_satisfies_protocols():
    s = StubDynamic()
    for proto in (IconSource, DynamicIconSource, SearchableIconSource, IconBytesProvider):
        assert isinstance(s, proto), proto


def test_subscribe_notifies_and_unsubscribes():
    s = StubDynamic()
    calls: list[int] = []
    unsubscribe = s.subscribe(lambda: calls.append(1))
    s.refresh()
    unsubscribe()
    s.refresh()
    assert calls == [1]
    assert len(s.entries()) == 1


def test_offline_state():
    s = StubDynamic()
    s.set_network_allowed(False)
    assert s.state() is SourceState.OFFLINE
