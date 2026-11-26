"""IconMaterializer for non-system icon entries."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QImage

from iconreplacer.converter.convert import compose_ico, convert_to_ico
from iconreplacer.converter.loader import ConversionError
from iconreplacer.core.models import ApplyOptions, IconEntry, IconKind, IconPayload, RefKind


class ConverterMaterializer:
    """Turns a chosen entry into an :class:`IconPayload`.

    * FILE / REMOTE entries: ``bytes_provider(entry)`` returns the raw image bytes, which are
      converted to ICO (composed on the folder base when ``options.compose_on_folder_base``).
    * RESOURCE entries: referenced in place (``IconPayload.resource``) unless composition is
      requested; then pixels are needed, taken from ``render_provider(entry, size)`` (the
      source's ``render``), and an ICO payload is produced. Glyph entries are recoloured,
      full-colour entries keep their colours.
    """

    def __init__(
        self,
        bytes_provider: Callable[[IconEntry], bytes],
        render_provider: Callable[[IconEntry, int], QImage] | None = None,
    ) -> None:
        self._bytes = bytes_provider
        self._render = render_provider

    def materialize(self, entry: IconEntry, options: ApplyOptions) -> IconPayload:
        if entry.ref.kind is RefKind.RESOURCE:
            if not options.compose_on_folder_base:
                if entry.ref.resource_id is None:
                    raise ConversionError(f"{entry.name}: resource entry without resource id")
                return IconPayload.resource(entry.ref.location, entry.ref.resource_id)
            if self._render is None:
                raise ConversionError("composing a resource icon needs a render provider")
            render = self._render
            ico = compose_ico(
                lambda edge: render(entry, edge),
                options.tint,
                recolor_glyph=entry.kind is IconKind.GLYPH,
            )
            return IconPayload.from_ico(ico)
        result = convert_to_ico(
            self._bytes(entry),
            compose_on_folder=options.compose_on_folder_base,
            tint=options.tint,
            hint=entry.name,
        )
        return IconPayload.from_ico(result.ico)
