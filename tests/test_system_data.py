import json
from importlib import resources

from iconreplacer.catalog.system_source import curated_icons, system_libraries
from iconreplacer.core.models import CATEGORIES

REQUIRED = {
    "imageres.dll", "shell32.dll", "ddores.dll", "wmploc.dll", "mmres.dll", "netshell.dll",
    "networkexplorer.dll", "pnidui.dll", "wpdshext.dll", "wiashext.dll", "setupapi.dll",
    "dmdskres.dll", "dsuiext.dll", "accessibilitycpl.dll", "sensorscpl.dll", "powercpl.dll",
    "mstscax.dll", "ieframe.dll", "mmcndmgr.dll", "compstui.dll", "pifmgr.dll", "moricons.dll",
}  # fmt: skip
COMPANIONS = {"powrprof.dll", "mstsc.exe", "shdocvw.dll"}


def _raw(name):
    return json.loads(
        resources.files("iconreplacer.catalog").joinpath("system_data", name).read_text("utf-8")
    )


def test_library_metadata_schema():
    libs = system_libraries()
    files = [lib.file for lib in libs]
    assert len(files) == len(set(files))
    assert set(files) == REQUIRED | COMPANIONS
    for lib in libs:
        assert lib.description.strip()
        assert lib.categories and set(lib.categories) <= set(CATEGORIES)
        assert lib.default_categories and set(lib.default_categories) <= set(lib.categories)
        if lib.file in COMPANIONS:
            assert lib.companion_of in REQUIRED
        else:
            assert lib.companion_of is None


def test_curated_tags_schema():
    raw = _raw("system_icon_tags.json")
    assert raw["version"] == 1
    known = {lib.file for lib in system_libraries()}
    total = 0
    for lib, items in raw["libraries"].items():
        assert lib in known
        for rid, item in items.items():
            assert rid.isdigit() and int(rid) > 0
            assert set(item) <= {"name", "categories", "tags"}
            assert isinstance(item["name"], str) and item["name"].strip()
            assert item["categories"] and set(item["categories"]) <= set(CATEGORIES)
            assert all(isinstance(t, str) and t.strip() for t in item.get("tags", []))
            total += 1
    assert total >= 150
    curated = curated_icons()
    assert len(curated["imageres.dll"]) >= 100
    assert len(curated["shell32.dll"]) >= 100
