"""The conversion pipeline: untrusted bytes -> Windows-compatible multi-size ICO."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from PySide6.QtGui import QImage

from iconreplacer.converter.adapt import Adapter
from iconreplacer.converter.folder_base import DEFAULT_TINT, compose_on_folder, glyph_box
from iconreplacer.converter.ico import STANDARD_SIZES, build_ico
from iconreplacer.converter.loader import load_image


@dataclass(frozen=True, slots=True)
class ConversionResult:
    ico: bytes
    is_glyph: bool
    sizes: tuple[int, ...]
    warnings: list[str] = field(default_factory=list)


def compose_ico(
    render: Callable[[int], QImage],
    tint: str = DEFAULT_TINT,
    *,
    recolor_glyph: bool = True,
    sizes: tuple[int, ...] = STANDARD_SIZES,
) -> bytes:
    """Compose ``render(glyph_edge_px)`` on the folder base for every size and build an ICO."""
    images = {
        s: compose_on_folder(render(glyph_box(s)), s, tint, recolor_glyph=recolor_glyph)
        for s in sizes
    }
    return build_ico(images)


def convert_to_ico(
    data: bytes,
    *,
    compose_on_folder: bool = False,
    tint: str = DEFAULT_TINT,
    hint: str | None = None,
) -> ConversionResult:
    """Convert image ``data`` (any supported format) into ICO data.

    With ``compose_on_folder`` the artwork is drawn on the tinted folder base at each size
    (recoloured to a contrasting ink only when it is glyph-like).
    """
    adapter = Adapter(load_image(data, hint))
    warnings = list(adapter.warnings)
    if compose_on_folder:
        if not adapter.is_glyph:
            warnings.append("full-colour artwork composed on folder base keeps its own colours")
        ico = compose_ico(
            lambda edge: adapter.render(edge, padding=0.0),
            tint,
            recolor_glyph=adapter.is_glyph,
        )
    else:
        ico = build_ico({s: adapter.render(s) for s in STANDARD_SIZES})
    return ConversionResult(ico, adapter.is_glyph, STANDARD_SIZES, warnings)
