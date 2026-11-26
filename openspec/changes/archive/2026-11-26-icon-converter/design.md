## Context

See proposal.md. Sources will hand raw bytes (online or local files) that must become Explorer-friendly ICO data. Qt (PySide6-Essentials) is already a dependency.

## Goals / Non-Goals

**Goals:** safe, deterministic conversion; no new dependencies; reusable folder-base drawing.
**Non-Goals:** network fetching, caching, applying icons to folders, animated formats, CMYK colour management.

## Decisions

- **No Pillow.** The venv Qt image plugins list `ico`, `icns`, `webp`, `png`, `jpeg`, `bmp`, `svg`; QImageReader covers every input format. ICO multi-frame reading uses `QImageReader.imageCount()` and `jumpToImage`. Fewer dependencies keeps the portable build small.
- **Format sniffing by magic bytes**: PNG signature, JPEG `FFD8FF`, `BM`, `RIFF....WEBP`, ICO `00 00 01 00`, `icns`, otherwise SVG if the text contains an `<svg` root. The hint is ignored for detection (kept for messages only).
- **Raster safety**: `QImageReader.size()` before `read()`; QImageReader allocation limit is also set low (`setAllocationLimit`) as a second guard.
- **SVG safety**: pre-check on the decoded text (case-insensitive) for DOCTYPE/ENTITY, `<script`, `<foreignObject`, `on*=` attributes; then parse with `xml.etree.ElementTree` (which does not resolve external entities, and DOCTYPE is already rejected) and inspect every `href`/`xlink:href`. QSvgRenderer is fed the original bytes only after validation. `currentColor` is replaced by `#000000` in the text before rendering. Embedded `data:image` URIs are allowed only for png/jpeg base64.
- **Source abstraction**: `SourceImage` holds either an SVG (renderable at any size) or a raster QImage. `render(size)` returns a square-agnostic image at a target box; the adapter then computes a trimmed bounding box.
- **Adaptation**: for SVG, render once at 512 px (viewBox aspect), compute the alpha bounding box, then re-render each size by pointing the renderer at a target rect derived from that box (vector, not upscaled). For raster: crop to alpha bbox, then fit into the inner box (94% of size) centred; downscale via step-down halving (`SmoothTransformation` each step) until within 2x of target, then a final smooth scale; light sharpen (3x3 unsharp kernel at 25 %) for sizes <= 32. Glyph detection: opaque pixels sample; glyph if the colour spread (max channel stddev across opaque pixels weighted) is very low or the image is greyscale-ish single hue with at most a few distinct quantised colours.
- **ICO writer**: hand-written. Entries sorted ascending. Sizes < 256 use BITMAPINFOHEADER (height doubled, 32 bpp), bottom-up BGRA rows, then 1-bit AND mask rows padded to 32 bits (mask set where alpha is 0). 256 uses PNG from `QImage.save` into a QBuffer. Entry width/height byte 0 means 256.
- **Compose**: the glyph per size is the adapted glyph image (with padding), recoloured by the existing `compose_on_folder` logic. Code moves to `converter/folder_base.py`; `ui/folder_base.py` re-exports.
- **Materializer**: `ConverterMaterializer(bytes_provider, render_provider=None)`. RESOURCE without compose returns `IconPayload.resource`; with compose needs `render_provider(entry, size)` (raises `ConversionError` if missing). Others convert bytes. Glyph/compose decision: compose when `options.compose_on_folder_base` is set.

## Risks / Trade-offs

- Qt's SVG Tiny 1.2 renderer lacks some features (filters, CSS corner cases); such parts may render differently. Accepted.
- Xml pre-checks are textual and conservative: some legitimate SVGs with `on*=` in text may be rejected. Accepted for safety.
