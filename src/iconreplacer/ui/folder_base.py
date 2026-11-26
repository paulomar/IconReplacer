"""Compatibility re-export: the folder base now lives in ``iconreplacer.converter``."""

from __future__ import annotations

from iconreplacer.converter.folder_base import (
    DEFAULT_TINT,
    GLYPH_SCALE,
    compose_on_folder,
    draw_folder,
    front_panel_rect,
    recolor,
)

__all__ = [
    "DEFAULT_TINT",
    "GLYPH_SCALE",
    "compose_on_folder",
    "draw_folder",
    "front_panel_rect",
    "recolor",
]
