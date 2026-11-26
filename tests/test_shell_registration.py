import subprocess
import sys

import pytest

from iconreplacer import cli
from iconreplacer.shell import registration as reg
from iconreplacer.shell.registration import (
    COMMAND_KEY,
    VERB_KEY,
    RegistrationState,
    ShellRegistration,
    WinregBackend,
    build_command,
    parse_launcher,
)


class FakeBackend:
    def __init__(self) -> None:
        self.keys: dict[str, dict[str, str]] = {}

    def read_values(self, key):
        v = self.keys.get(key.lower())
        return None if v is None else dict(v)

    def write_values(self, key, values):
        self.keys.setdefault(key.lower(), {}).update(values)

    def delete_key(self, key):
        self.keys.pop(key.lower(), None)


@pytest.fixture
def exe(tmp_path):
    d = tmp_path / "My Apps" / "Icon Replacer"
    d.mkdir(parents=True)
    f = d / "IconReplacer.exe"
    f.write_bytes(b"")
    return str(f)


def test_register_writes_expected_values(exe):
    be = FakeBackend()
    ShellRegistration(be, launcher=exe, extra_args=()).register()
    assert be.keys[VERB_KEY.lower()] == {"": "Replace Icon", "MUIVerb": "Replace Icon", "Icon": exe}
    assert be.keys[COMMAND_KEY.lower()] == {"": f'"{exe}" --folder "%1"'}
    assert set(be.keys) == {VERB_KEY.lower(), COMMAND_KEY.lower()}


def test_dev_command_quotes_launcher_with_spaces():
    cmd = build_command(r"C:\My Repo\.venv\Scripts\pythonw.exe", ("-m", "iconreplacer"))
    assert cmd == r'"C:\My Repo\.venv\Scripts\pythonw.exe" -m iconreplacer --folder "%1"'
    assert parse_launcher(cmd) == r"C:\My Repo\.venv\Scripts\pythonw.exe"


def test_parse_launcher_edge_cases():
    assert parse_launcher("") is None
    assert parse_launcher('"unterminated') is None
    assert parse_launcher(r"C:\x.exe --folder %1") == r"C:\x.exe"


def test_status_lifecycle(exe):
    be = FakeBackend()
    r = ShellRegistration(be, launcher=exe, extra_args=())
    assert r.status().state is RegistrationState.NOT_REGISTERED
    r.register()
    st = r.status()
    assert st.state is RegistrationState.REGISTERED and st.path == exe
    r.register()  # idempotent
    assert r.status().state is RegistrationState.REGISTERED
    r.unregister()
    assert r.status().state is RegistrationState.NOT_REGISTERED
    r.unregister()  # absent is fine


def test_stale_when_app_moved(exe, tmp_path):
    be = FakeBackend()
    ShellRegistration(be, launcher=exe, extra_args=()).register()
    moved = tmp_path / "elsewhere" / "IconReplacer.exe"
    moved.parent.mkdir()
    moved.write_bytes(b"")
    st = ShellRegistration(be, launcher=str(moved), extra_args=()).status()
    assert st.state is RegistrationState.STALE and st.path == exe


def test_stale_when_registered_path_missing(tmp_path):
    be = FakeBackend()
    ghost = str(tmp_path / "gone.exe")
    r = ShellRegistration(be, launcher=ghost, extra_args=())
    r.register()
    assert r.status().state is RegistrationState.STALE


def test_unregister_leaves_siblings(exe):
    be = FakeBackend()
    be.keys[r"software\classes\directory\shell\other"] = {"": "x"}
    r = ShellRegistration(be, launcher=exe, extra_args=())
    r.register()
    r.unregister()
    assert list(be.keys) == [r"software\classes\directory\shell\other"]


def test_winreg_backend_refuses_other_keys():
    be = WinregBackend()
    for bad in (r"Software\Classes\Directory\shell", r"Software\Classes\*\shell\IconReplacer"):
        with pytest.raises(PermissionError):
            be.write_values(bad, {"": "x"})
        with pytest.raises(PermissionError):
            be.delete_key(bad)
        with pytest.raises(PermissionError):
            be.read_values(bad)


def test_default_launcher_dev_mode():
    exe_path, args = reg.default_launcher()
    assert args == ("-m", "iconreplacer")
    assert exe_path.lower().endswith(("python.exe", "pythonw.exe"))


def test_default_launcher_frozen(monkeypatch, tmp_path):
    fake = tmp_path / "IconReplacer.exe"
    fake.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake))
    assert reg.default_launcher() == (str(fake.resolve()), ())


# ---- CLI --------------------------------------------------------------------------


def test_cli_parse_shell_flags():
    assert cli.parse_args(["--register"]).shell_action == "register"
    assert cli.parse_args(["--unregister"]).shell_action == "unregister"
    assert cli.parse_args(["--status"]).shell_action == "status"
    assert cli.parse_args(["--folder", r"C:\A"]).shell_action is None
    with pytest.raises(SystemExit):
        cli.parse_args(["--register", "--unregister"])


def test_run_shell_action_exit_codes(exe, capsys):
    r = ShellRegistration(FakeBackend(), launcher=exe, extra_args=())
    assert cli.run_shell_action("status", r) == 1
    assert "not registered" in capsys.readouterr().out
    assert cli.run_shell_action("register", r) == 0
    assert cli.run_shell_action("status", r) == 0
    assert "registered" in capsys.readouterr().out
    assert cli.run_shell_action("unregister", r) == 0
    assert cli.run_shell_action("status", r) == 1


def test_shell_flags_do_not_import_qt_gui():
    code = (
        "import sys\n"
        "from iconreplacer.cli import parse_args, run_shell_action\n"
        "from iconreplacer.shell.registration import ShellRegistration\n"
        "print(any(m.startswith('PySide6') for m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert out.stdout.strip().endswith("False")


# ---- Real registry (R1): only HKCU\Software\Classes\Directory\shell\IconReplacer -----


@pytest.mark.registry
def test_real_registry_roundtrip_with_rollback(exe, capsys):
    be = WinregBackend()
    snapshot = {k: be.read_values(k) for k in (VERB_KEY, COMMAND_KEY)}
    assert snapshot[VERB_KEY] is None and snapshot[COMMAND_KEY] is None, (
        "IconReplacer verb already exists; refusing to run the R1 test over a real registration"
    )
    r = ShellRegistration(be, launcher=exe, extra_args=("-m", "iconreplacer"))
    try:
        r.register()
        assert be.read_values(VERB_KEY) == {
            "": "Replace Icon",
            "MUIVerb": "Replace Icon",
            "Icon": exe,
        }
        assert be.read_values(COMMAND_KEY) == {"": f'"{exe}" -m iconreplacer --folder "%1"'}
        assert r.status().state is RegistrationState.REGISTERED
    finally:
        r.unregister()
        absent = be.read_values(VERB_KEY) is None and be.read_values(COMMAND_KEY) is None
        with capsys.disabled():
            print(f"\n[R1] IconReplacer verb key removed and verified absent: {absent}")
        assert absent
