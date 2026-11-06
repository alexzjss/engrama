import json
from pathlib import Path


from engrama.app import cli, i18n
from engrama.app.integration import Autostart, MARKER, launch_command
from engrama.app.integration.linux import LinuxIntegration
from engrama.app.integration.windows import RUN_NAME, WindowsIntegration
from tests.app.test_menus import click, make, texts

CMD = ["/opt/py/python", "-m", "engrama"]


def linux(tmp_path, icon=None, env=None):
    return LinuxIntegration(env=env or {}, home=tmp_path, command=CMD, icon=icon)


def test_launch_command_frozen_vs_installed():
    assert launch_command(True, "/x/engrama") == ["/x/engrama"]
    assert launch_command(False, "/x/python") == ["/x/python", "-m", "engrama"]


def test_linux_install_uninstall_and_idempotence(tmp_path):
    icon = tmp_path / "src.png"
    icon.write_bytes(b"png")
    li = linux(tmp_path, icon)
    li.install()
    li.install()
    desk = tmp_path / ".local/share/applications/engrama.desktop"
    assert "Exec=/opt/py/python -m engrama" in desk.read_text() and MARKER in desk.read_text()
    assert (tmp_path / ".local/share/icons/hicolor/256x256/apps/engrama.png").read_bytes() == b"png"
    assert not li.autostart_file.exists()   # autostart is never part of install
    removed = li.uninstall()
    assert not desk.exists() and not li.icon_file.exists() and len(removed) == 2
    assert li.uninstall() == []


def test_linux_without_icon_source_still_installs(tmp_path):
    li = linux(tmp_path, tmp_path / "missing.png")
    assert li.install() == [li.desktop_file] and not li.icon_file.exists()


def test_linux_respects_xdg(tmp_path):
    li = linux(tmp_path, env={"XDG_DATA_HOME": str(tmp_path / "d"), "XDG_CONFIG_HOME": str(tmp_path / "c")})
    li.install()
    li.set_autostart(True)
    assert (tmp_path / "d/applications/engrama.desktop").is_file()
    assert (tmp_path / "c/autostart/engrama.desktop").is_file()


def test_linux_never_touches_foreign_files(tmp_path):
    li = linux(tmp_path)
    for p in (li.desktop_file, li.autostart_file):
        p.parent.mkdir(parents=True)
        p.write_text("[Desktop Entry]\nName=Mine\n")
    assert li.install() == []
    li.set_autostart(True)
    assert not li.autostart_enabled()
    li.set_autostart(False)
    assert li.uninstall() == []
    assert li.desktop_file.read_text().endswith("Name=Mine\n") and li.autostart_file.exists()


def test_linux_autostart_roundtrip_and_uninstall_removes_it(tmp_path):
    li = linux(tmp_path)
    assert not li.autostart_enabled()
    li.set_autostart(True)
    assert li.autostart_enabled()
    assert "X-GNOME-Autostart-enabled=true" in li.autostart_file.read_text()
    li.set_autostart(False)
    assert not li.autostart_enabled()
    li.set_autostart(True)
    li.uninstall()
    assert not li.autostart_file.exists()


def test_exec_quotes_paths_with_spaces(tmp_path):
    li = LinuxIntegration(env={}, home=tmp_path, command=["/opt/my app/engrama"])
    li.install()
    assert 'Exec="/opt/my app/engrama"' in li.desktop_file.read_text()


class FakeRegistry:
    def __init__(self, log):
        self.values, self.log = {}, log

    def get(self, name):
        return self.values.get(name)

    def set(self, name, value):
        self.log.append(("reg.set", name, value))
        self.values[name] = value

    def delete(self, name):
        self.log.append(("reg.delete", name))
        self.values.pop(name, None)


def windows(tmp_path):
    log = []
    holder = {}

    def ps(script):
        log.append(("ps", script))
        if "CreateShortcut" in script and ".Description" in script and "Save" not in script:
            return holder.get("desc", "")
        if "Save()" in script:
            (tmp_path / "Engrama.lnk").write_text("lnk")
            holder["desc"] = "Engrama (" + MARKER + ")" if MARKER in script else "other"
        return ""
    w = WindowsIntegration(tmp_path, FakeRegistry(log), ps, [r"C:\Eng rama\engrama.exe"], icon=None)
    return w, log, holder


def test_windows_sequence(tmp_path):
    w, log, _ = windows(tmp_path)
    assert w.install() == [w.shortcut]
    script = log[0][1]
    assert log[0][0] == "ps" and "WScript.Shell" in script and "engrama.exe" in script and script.endswith("$s.Save()")
    assert not w.autostart_enabled()
    w.set_autostart(True)
    assert w.autostart_enabled()
    assert log[-1] == ("reg.set", RUN_NAME, '"C:\\Eng rama\\engrama.exe"')
    w.install()   # idempotent: our own shortcut is rewritten, nothing breaks
    assert w.uninstall() == [w.shortcut]
    assert not w.shortcut.exists() and not w.autostart_enabled()
    assert log[-1] == ("reg.delete", RUN_NAME)


def test_windows_keeps_foreign_shortcut(tmp_path):
    w, log, holder = windows(tmp_path)
    w.shortcut.write_text("theirs")
    holder["desc"] = "someone else"
    assert w.install() == []
    assert w.uninstall() == [] and w.shortcut.read_text() == "theirs"
    assert not any("Save()" in e[1] for e in log if e[0] == "ps")


class FakeBackend:
    def __init__(self):
        self.on = False

    def autostart_enabled(self):
        return self.on

    def set_autostart(self, on):
        self.on = on


def test_settings_toggle_reflects_os_state():
    w = make()
    be = FakeBackend()
    w.autostart = Autostart(be)
    w.open_panel("settings")
    w.frame(1.0)
    row = dict(w.panel._rows)["autostart"]
    assert "[ ]" in texts(w)
    w.panel.handle_event(click(row.center))
    assert be.on is True and "[x]" in texts(w)
    be.on = False   # changed behind our back (user edited the OS): the panel follows the OS
    assert "[x]" not in texts(w)


def test_settings_autostart_disabled_in_dev():
    prev = i18n.get_lang()
    i18n.set_lang("en")
    try:
        w = make()
        be = FakeBackend()
        w.autostart = Autostart(be, dev=True)
        w.open_panel("settings")
        w.frame(1.0)
        w.panel.handle_event(click(dict(w.panel._rows)["autostart"].center))
        assert be.on is False
        assert i18n.t("settings.autostart_dev") in texts(w)
    finally:
        i18n.set_lang(prev)


def test_i18n_keys_in_both_languages():
    d = Path(i18n.__file__).parent
    for lang in ("pt", "en"):
        t = json.loads((d / f"{lang}.json").read_text(encoding="utf-8"))
        assert t["settings.autostart"] and t["settings.autostart_dev"]


def test_cli_install_and_uninstall_use_the_backend(tmp_path, capsys):
    li = linux(tmp_path)
    assert cli.desktop_command(True, li) == 0
    assert li.desktop_file.exists()
    assert cli.desktop_command(False, li) == 0
    assert not li.desktop_file.exists()
    assert "Removido" in capsys.readouterr().out
