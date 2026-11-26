## 1. Folder base move

- [x] 1.1 Move folder drawing code to `converter/folder_base.py`; make `ui/folder_base.py` a re-export. Verify: existing UI tests pass.

## 2. Loading and safety

- [x] 2.1 Implement `load_image` with magic-byte detection, SVG hardening, raster limits. Verify: `tests/test_converter_load.py`.

## 3. Adaptation

- [x] 3.1 Implement trim/pad/square, glyph detection, small-size rendering and downscaling. Verify: `tests/test_converter_adapt.py`.

## 4. ICO and pipeline

- [x] 4.1 Implement `build_ico` and `convert_to_ico` with composition. Verify: `tests/test_converter_ico.py` round-trips every size.
- [x] 4.2 Implement `ConverterMaterializer`. Verify: `tests/test_converter_materializer.py`.

## 5. Finish

- [x] 5.1 `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check`, `openspec validate icon-converter --strict` all pass.
