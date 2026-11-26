## Why

Icons from external sources (SVG, PNG, JPEG, BMP, WebP, ICO, ICNS) are not directly usable as Windows folder icons. The app must adapt them so Explorer displays them well at every size, and must treat downloaded or user-supplied files as untrusted input.

## What Changes

- New `converter` package: safe image loading with format detection by content, SVG hardening, raster bomb limits.
- Smart adaptation: trim transparent margins, pad to square, inner padding, monochrome glyph detection, vector re-rendering for small sizes, high quality downscaling.
- Own ICO writer producing the standard Windows size set (PNG for 256, 32-bit BGRA DIB plus AND mask for smaller sizes).
- `convert_to_ico` pipeline, optionally composing the glyph on the folder base.
- `ConverterMaterializer`, an `IconMaterializer` for non-system entries.
- The folder base drawing code moves to `converter/folder_base.py`; `ui/folder_base.py` becomes a thin re-export (no behaviour change).

## Capabilities

### New Capabilities
- `icon-conversion`: converting untrusted external images into Windows-compatible multi-size ICO data.

### Modified Capabilities
None.

## Impact

- New code under `src/iconreplacer/converter/`, new tests `tests/test_converter_*.py`.
- `ui/folder_base.py` becomes a re-export. No new dependencies (Qt already reads ICO, ICNS and WebP).
