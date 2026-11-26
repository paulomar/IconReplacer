"""IconMaterializer that resolves a chosen entry through its own source."""

from __future__ import annotations

from iconreplacer.catalog.registry import SourceRegistry
from iconreplacer.converter import ConversionError, ConverterMaterializer
from iconreplacer.core.contracts import IconBytesProvider, IconSource
from iconreplacer.core.models import ApplyOptions, IconEntry, IconPayload


class CompositeMaterializer:
    """Route each entry to the source that owns it.

    * RESOURCE entries (system DLLs, local DLL/EXE files) are referenced in place, or composed
      on the folder base from the source's ``render`` when composition is requested.
    * Every other entry needs a source implementing :class:`IconBytesProvider`; its raw bytes go
      through the converter (optionally composed and tinted).

    Errors are raised as :class:`ConversionError` with a short English reason. The folder service
    turns them into a failed result before any folder is touched. May block (network, decoding):
    call from a worker thread.
    """

    def __init__(self, registry: SourceRegistry) -> None:
        self._registry = registry

    def _source(self, entry: IconEntry) -> IconSource:
        try:
            return self._registry.get(entry.source_id)
        except KeyError:
            raise ConversionError(f"unknown icon source: {entry.source_id}") from None

    def materialize(self, entry: IconEntry, options: ApplyOptions) -> IconPayload:
        source = self._source(entry)

        def fetch(e: IconEntry) -> bytes:
            if not isinstance(source, IconBytesProvider):
                raise ConversionError(f"{source.info.name} cannot provide image data")
            try:
                return source.fetch_bytes(e)
            except ConversionError:
                raise
            except (OSError, ValueError) as exc:
                raise ConversionError(f"{source.info.name}: {exc}") from exc

        return ConverterMaterializer(fetch, source.render).materialize(entry, options)
