import xml.etree.ElementTree as ET
from pathlib import Path

from iconreplacer.ui.settings_view import available_languages

TS = Path(__file__).resolve().parents[1] / "src" / "iconreplacer" / "i18n" / "iconreplacer_en.ts"

EXPECTED = {
    "MainWindow": {"Browse", "Settings", "About", "Search name, tag or resource ID…"},
    "TargetHeader": {"Apply", "Undo", "Restore default", "No target folder", "%n folders"},
    "SettingsView": {"Allow network access", "Language", "Theme", "Add local folder…"},
    "AboutDialog": {"About IconReplacer", "Version %1 (build %2)", "MIT License"},
    "PreviewPanel": {"Compose on folder base", "Preview"},
    "IconGrid": {"No icons match"},
    "Categories": {"Folders", "Legacy"},
}


def test_template_contains_ui_strings():
    root = ET.parse(TS).getroot()
    found: dict[str, set[str]] = {}
    for ctx in root.iter("context"):
        name = ctx.findtext("name")
        found[name] = {m.findtext("source") for m in ctx.iter("message")}
    for ctx, strings in EXPECTED.items():
        missing = strings - found.get(ctx, set())
        assert not missing, f"{ctx}: {missing}"


def test_language_list_from_available_translations(tmp_path):
    assert available_languages(tmp_path) == [("en", "English")]
    (tmp_path / "iconreplacer_de.qm").write_bytes(b"")
    codes = [c for c, _ in available_languages(tmp_path)]
    assert codes == ["en", "de"]
