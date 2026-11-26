"""Safe loading of untrusted images (SVG, PNG, JPEG, BMP, WebP, ICO, ICNS)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF
from PySide6.QtGui import QImage, QImageReader
from PySide6.QtSvg import QSvgRenderer

MAX_SVG_BYTES = 2 * 1024 * 1024
MAX_RASTER_BYTES = 20 * 1024 * 1024
MAX_DIMENSION = 4096
_ALLOCATION_LIMIT_MB = 256

_SVG_FORBIDDEN = (
    (re.compile(rb"<!\s*doctype", re.I), "DOCTYPE declarations are not allowed"),
    (re.compile(rb"<!\s*entity", re.I), "ENTITY declarations are not allowed"),
    (re.compile(rb"<\s*script", re.I), "script elements are not allowed"),
    (re.compile(rb"<\s*foreignobject", re.I), "foreignObject elements are not allowed"),
    (re.compile(rb"<\?\s*xml-stylesheet", re.I), "stylesheet instructions are not allowed"),
    (re.compile(rb"""[\s"'/]on[a-z]+\s*=""", re.I), "event handler attributes are not allowed"),
    (re.compile(rb"@import", re.I), "CSS imports are not allowed"),
)
_CSS_URL = re.compile(r"url\(\s*['\"]?\s*([^)'\"\s]*)", re.I)
_CURRENT_COLOR = re.compile(rb"currentcolor", re.I)
_DATA_URI = re.compile(r"^data:image/(png|jpeg);base64,[A-Za-z0-9+/=\s]*$", re.I)


class ConversionError(ValueError):
    """Raised when an image is unsafe, unsupported or unusable."""


@dataclass(frozen=True, slots=True)
class SourceImage:
    """A validated source: either a vector (SVG) or a raster image."""

    format: str
    raster: QImage | None = None
    svg: bytes | None = None
    width: float = 0.0  # natural size (viewBox size for SVG)
    height: float = 0.0

    @property
    def is_vector(self) -> bool:
        return self.svg is not None


def sniff_format(data: bytes) -> str | None:
    """Detect the format from content only (never from a file name)."""
    head = data[:16]
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"BM"):
        return "bmp"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head.startswith(b"\x00\x00\x01\x00"):
        return "ico"
    if head.startswith(b"icns"):
        return "icns"
    probe = data[:4096].lstrip(b"\xef\xbb\xbf \t\r\n")
    if probe.startswith((b"<?xml", b"<svg", b"<!--", b"<!DOCTYPE", b"<!doctype")) and (
        b"<svg" in data[:65536].lower()
    ):
        return "svg"
    return None


def load_image(data: bytes, hint: str | None = None) -> SourceImage:
    """Validate and decode ``data``. ``hint`` (e.g. a file name) is used only in messages."""
    label = hint or "image"
    if not data:
        raise ConversionError(f"{label}: empty data")
    fmt = sniff_format(data)
    if fmt is None:
        raise ConversionError(f"{label}: unrecognized image format")
    if fmt == "svg":
        return _load_svg(data, label)
    return _load_raster(data, fmt, label)


# ---------------------------------------------------------------- SVG


def _validate_svg(data: bytes, label: str) -> bytes:
    if len(data) > MAX_SVG_BYTES:
        raise ConversionError(f"{label}: SVG larger than {MAX_SVG_BYTES // 1024} KiB limit")
    for pattern, message in _SVG_FORBIDDEN:
        if pattern.search(data):
            raise ConversionError(f"{label}: {message}")
    try:
        root = ET.fromstring(data)  # noqa: S314 - DOCTYPE/ENTITY rejected above
    except ET.ParseError as exc:
        raise ConversionError(f"{label}: invalid SVG XML ({exc})") from exc
    if root.tag.rsplit("}", 1)[-1].lower() != "svg":
        raise ConversionError(f"{label}: root element is not <svg>")
    for el in root.iter():
        for name, value in el.attrib.items():
            local = name.rsplit("}", 1)[-1].lower()
            if local == "href":
                v = value.strip()
                if not (v.startswith("#") or _DATA_URI.match(v)):
                    raise ConversionError(f"{label}: external reference is not allowed")
            elif local == "style" or "url(" in value.lower():
                _check_css_urls(value, label)
        if el.tag.rsplit("}", 1)[-1].lower() == "style" and el.text:
            _check_css_urls(el.text, label)
    return _CURRENT_COLOR.sub(b"#000000", data)


def _check_css_urls(text: str, label: str) -> None:
    for m in _CSS_URL.finditer(text):
        if not m.group(1).startswith("#"):
            raise ConversionError(f"{label}: external url() reference is not allowed")


def _load_svg(data: bytes, label: str) -> SourceImage:
    clean = _validate_svg(data, label)
    renderer = QSvgRenderer(QByteArray(clean))
    if not renderer.isValid():
        raise ConversionError(f"{label}: SVG could not be rendered")
    vb = viewbox(renderer)
    if vb.width() <= 0 or vb.height() <= 0:
        raise ConversionError(f"{label}: SVG has no usable size")
    return SourceImage("svg", svg=clean, width=vb.width(), height=vb.height())


def viewbox(renderer: QSvgRenderer) -> QRectF:
    vb = renderer.viewBoxF()
    if vb.isEmpty():
        size = renderer.defaultSize()
        vb = QRectF(0, 0, size.width(), size.height())
    return vb


# ---------------------------------------------------------------- raster


def _load_raster(data: bytes, fmt: str, label: str) -> SourceImage:
    if len(data) > MAX_RASTER_BYTES:
        raise ConversionError(f"{label}: image larger than {MAX_RASTER_BYTES // 2**20} MB limit")
    buf = QBuffer()
    buf.setData(QByteArray(data))
    buf.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buf, fmt.encode())
    reader.setAllocationLimit(_ALLOCATION_LIMIT_MB)
    if not reader.canRead():
        raise ConversionError(f"{label}: cannot decode {fmt.upper()} data")
    frames = max(1, reader.imageCount()) if fmt in ("ico", "icns") else 1
    best, best_area = 0, -1
    image = QImage()
    for i in range(frames):
        if frames > 1 and not reader.jumpToImage(i):
            continue
        size = reader.size()  # header only, nothing decoded yet
        if size.isValid():
            _check_dimensions(size.width(), size.height(), label)
            candidate = QImage()
        elif fmt == "icns":
            # the ICNS plugin cannot report sizes up front: decode (bounded by the 20 MB
            # data limit and the reader allocation limit), then check
            candidate = reader.read()
            if candidate.isNull():
                continue
            size = candidate.size()
            _check_dimensions(size.width(), size.height(), label)
        else:
            raise ConversionError(f"{label}: unreadable image size")
        if size.width() * size.height() > best_area:
            best_area = size.width() * size.height()
            image = candidate
            best = i
    if best_area < 0:
        raise ConversionError(f"{label}: no readable frames")
    if image.isNull():
        if frames > 1:
            reader.jumpToImage(best)
        image = reader.read()
    if image.isNull():
        raise ConversionError(f"{label}: cannot decode {fmt.upper()} data")
    _check_dimensions(image.width(), image.height(), label)
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    return SourceImage(fmt, raster=image, width=image.width(), height=image.height())


def _check_dimensions(w: int, h: int, label: str) -> None:
    if w <= 0 or h <= 0 or w > MAX_DIMENSION or h > MAX_DIMENSION:
        raise ConversionError(
            f"{label}: dimensions {w}x{h} exceed the {MAX_DIMENSION}x{MAX_DIMENSION} limit"
        )
