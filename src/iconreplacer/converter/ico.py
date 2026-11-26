"""Own ICO writer: PNG for 256 px, 32-bit BGRA DIB + 1-bit AND mask for smaller sizes."""

from __future__ import annotations

import struct

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage

STANDARD_SIZES: tuple[int, ...] = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def _png_bytes(image: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buf, "PNG"):
        raise ValueError("could not encode PNG")
    buf.close()
    return bytes(ba.data())


def _dib_bytes(image: QImage) -> bytes:
    """BITMAPINFOHEADER (doubled height) + bottom-up BGRA pixels + 1-bit AND mask."""
    w, h = image.width(), image.height()
    px = bytes(image.constBits())  # ARGB32 little-endian == BGRA byte order
    rows = [px[y * w * 4 : (y + 1) * w * 4] for y in range(h)]
    xor = b"".join(reversed(rows))
    mask_stride = ((w + 31) // 32) * 4
    mask_rows = []
    for row in reversed(rows):
        bits = bytearray(mask_stride)
        alpha = row[3::4]
        for x in range(w):
            if alpha[x] == 0:
                bits[x >> 3] |= 0x80 >> (x & 7)
        mask_rows.append(bytes(bits))
    mask = b"".join(mask_rows)
    header = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, len(xor) + len(mask), 0, 0, 0, 0)
    return header + xor + mask


def build_ico(images: dict[int, QImage]) -> bytes:
    """Build ICO data from ``{size: square image}``; entries are written sorted by size."""
    if not images:
        raise ValueError("no images to write")
    blobs: list[tuple[int, bytes]] = []
    for size in sorted(images):
        if not 1 <= size <= 256:
            raise ValueError(f"unsupported ICO size {size}")
        img = images[size]
        if img.isNull() or img.width() != size or img.height() != size:
            raise ValueError(f"image for size {size} must be {size}x{size}")
        img = img.convertToFormat(QImage.Format.Format_ARGB32)
        blobs.append((size, _png_bytes(img) if size == 256 else _dib_bytes(img)))
    offset = 6 + 16 * len(blobs)
    out = bytearray(struct.pack("<HHH", 0, 1, len(blobs)))
    for size, blob in blobs:
        dim = 0 if size == 256 else size
        out += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    for _, blob in blobs:
        out += blob
    return bytes(out)
