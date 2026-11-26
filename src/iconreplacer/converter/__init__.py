"""Adapt icons from external sources for Windows compatibility."""

from iconreplacer.converter.adapt import Adapter, content_bbox, detect_glyph
from iconreplacer.converter.convert import ConversionResult, compose_ico, convert_to_ico
from iconreplacer.converter.ico import STANDARD_SIZES, build_ico
from iconreplacer.converter.loader import ConversionError, SourceImage, load_image
from iconreplacer.converter.materializer import ConverterMaterializer

__all__ = [
    "STANDARD_SIZES",
    "Adapter",
    "ConversionError",
    "ConversionResult",
    "ConverterMaterializer",
    "SourceImage",
    "build_ico",
    "compose_ico",
    "content_bbox",
    "convert_to_ico",
    "detect_glyph",
    "load_image",
]
