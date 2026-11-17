"""The panel icon with real GTK and XApp, a stand-in client, and a D-Bus daemon of the
test's own. Needs a display: xvfb in CI, the desktop otherwise.
"""

from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

gi = pytest.importorskip("gi", reason="PyGObject is not installed")
try:
    gi.require_version("Gtk", "3.0")
    gi.require_version("XApp", "1.0")
except ValueError as error:
    pytest.skip(f"GTK 3 or XApp is missing: {error}", allow_module_level=True)

from gi.repository import Gio, GLib, Gtk  # noqa: E402

if not Gtk.init_check()[0]:
    pytest.skip("no display to open", allow_module_level=True)

from tuxtoys import BUS_NAME, OBJECT_PATH  # noqa: E402
from tuxtoys.api import (  # noqa: E402
    AWAKE_INTERFACE,
    AWAKE_PATH,
    DAEMON_INTERFACE,
    ModuleInfo,
    ModuleOff,
)
from tuxtoys.tray import app, view  # noqa: E402

NOW = datetime(2026, 6, 1, 10, 0, tzinfo=ZoneInfo("Europe/Budapest"))
OFF = {"mode": "off", "keep_screen": False, "ends_at": 0}
ON = {"mode": "indefinite", "keep_screen": True, "ends_at": 0}
SIGNATURES = {"mode": "s", "keep_screen": "b", "ends_at": "x"}


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.state: dict | None = OFF
        self.module_list: list[ModuleInfo] = []

    def modules(self) -> list[ModuleInfo]:
        return self.module_list

    def awake_state(self) -> dict:
        if self.state is None:
            raise ModuleOff
        return self.state

    def awake_start(self, mode: str, minutes: int, until: str, keep_screen: bool) -> None:
        self.calls.append(("start", mode, minutes, until, keep_screen))

    def awake_stop(self) -> None:
        self.calls.append(("stop",))

    def awake_toggle(self) -> None:
        self.calls.append(("toggle",))

    def awake_set_keep_screen(self, keep_screen: bool) -> None:
        self.calls.append(("keep_screen", keep_screen))


def module(module_id: str, state: str = "on") -> ModuleInfo:
    return ModuleInfo(module_id, module_id, "", state, "")


class Harness:
    def __init__(
        self,
        tray: app.Tray,
        client: FakeClient,
        service: Gio.DBusConnection,
        spawned: list[list[str]],
    ) -> None:
        self.tray = tray
        self.client = client
        self.service = service
        self.spawned = spawned

    def item(self, label: str) -> Gtk.MenuItem:
        for child in self.tray.menu.get_children():
            if child.get_label() == label:
                return child
        raise LookupError(label)

    def status(self) -> str:
        return self.tray.menu.get_children()[0].get_label()


@pytest.fixture
def harness(
    private_bus: tuple[Gio.DBusConnection, Gio.DBusConnection], pump: Callable[..., bool]
) -> Iterator[Harness]:
    service, client_bus = private_bus
    client = FakeClient()
    spawned: list[list[str]] = []
    tray = app.Tray(
        client_bus,
        client,
        now=lambda: NOW,
        spawn=spawned.append,
        package_root=Path("/usr/lib/tuxtoys"),
    )
    # The name watcher reports, once, that nobody owns the daemon's name yet.
    pump(lambda: False, seconds=0.2)
    yield Harness(tray, client, service, spawned)
    # Run on a desktop, the test icons would otherwise stay in the panel until pytest ends.
    tray.status_icon.set_visible(False)
    tray.main_icon.set_visible(False)


def test_without_the_daemon_it_says_so_and_offers_nothing(harness: Harness) -> None:
    assert harness.status() == "TuxToys is not running."
    assert harness.tray.tooltip == "TuxToys is not running."
    assert not harness.item("Until turned off").get_sensitive()
    assert not harness.item("Keep the screen on").get_sensitive()


def test_shows_the_state(harness: Harness) -> None:
    harness.tray.update(ON)
    assert harness.tray.icon_name == app.icon(view.ICON_ON)
    assert harness.status() == "Awake is on until you turn it off."
    assert harness.item("Turn off").get_sensitive()
    assert harness.item("Keep the screen on").get_active()
    assert harness.client.calls == []  # showing the check box ticked is not a click on it


def test_left_click_toggles(harness: Harness) -> None:
    harness.tray.update(OFF)
    harness.tray.status_icon.emit("activate", 1, 0)
    assert harness.client.calls == [("toggle",)]


def test_left_click_without_the_daemon_does_nothing(harness: Harness) -> None:
    harness.tray.status_icon.emit("activate", 1, 0)
    assert harness.client.calls == []


def test_the_menu_starts_the_modes_with_the_screen_setting(harness: Harness) -> None:
    harness.tray.update({**OFF, "keep_screen": True})
    harness.item("Until turned off").activate()
    harness.item("For 30 minutes").activate()
    harness.item("For 2 hours").activate()
    assert harness.client.calls == [
        ("start", "indefinite", 0, "", True),
        ("start", "duration", 30, "", True),
        ("start", "duration", 120, "", True),
    ]


def test_the_check_box_sets_the_screen_setting(harness: Harness) -> None:
    harness.tray.update(OFF)
    harness.item("Keep the screen on").set_active(True)
    assert harness.client.calls == [("keep_screen", True)]


def test_turn_off(harness: Harness) -> None:
    harness.tray.update(ON)
    harness.item("Turn off").activate()
    assert harness.client.calls == [("stop",)]


def test_follows_the_daemon_on_the_bus(harness: Harness, pump: Callable[..., bool]) -> None:
    harness.client.state = OFF
    harness.service.call_sync(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "RequestName",
        GLib.Variant("(su)", (BUS_NAME, 4)),
        GLib.VariantType("(u)"),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
    )
    assert pump(lambda: harness.status() == "Awake is off.")

    on = {key: GLib.Variant(kind, ON[key]) for key, kind in SIGNATURES.items()}
    harness.service.emit_signal(
        None, AWAKE_PATH, AWAKE_INTERFACE, "StateChanged", GLib.Variant("(a{sv})", (on,))
    )
    assert pump(lambda: harness.status() == "Awake is on until you turn it off.")


@pytest.mark.parametrize("name", [view.ICON_ON, view.ICON_OFF])
def test_an_icon_not_installed_reaches_the_panel_as_a_file_it_can_load(name: str) -> None:
    if Gtk.IconTheme.get_default().has_icon(name):
        pytest.skip("the icons are installed, so they go by name")
    path = Path(app.icon(name))
    # Cinnamon's applet looks up anything with "symbolic" in it by name, path or not.
    assert "symbolic" not in str(path)
    assert path.read_bytes() == (app.CHECKOUT_ICONS / f"{name}.svg").read_bytes()


def test_settings_is_on_the_menu_even_without_the_daemon(harness: Harness) -> None:
    assert harness.item("Settings…").get_sensitive()


def test_without_the_daemon_the_cup_is_hidden_and_quick_access_says_so(
    harness: Harness,
) -> None:
    assert not harness.tray.awake_shown
    assert not harness.tray.quick_items["TuxToys is not running."].get_sensitive()
    assert harness.tray.quick_items["Settings…"].get_sensitive()
    assert harness.tray.quick_items["Report a bug"].get_sensitive()


def test_the_cup_shows_only_while_awake_is_on(harness: Harness) -> None:
    harness.tray.update(OFF)
    assert harness.tray.awake_shown
    harness.tray.update(None, "Awake is switched off in TuxToys.")
    assert not harness.tray.awake_shown


def test_quick_access_lists_the_tools_on_and_opens_them(harness: Harness) -> None:
    harness.tray.show_modules(
        [module("awake"), module("mousejump"), module("colorpicker"), module("hosts", "off")]
    )
    items = list(harness.tray.quick_items)
    assert items == ["Color Picker", "Mouse Jump", "Settings…", "Documentation", "Report a bug"]
    harness.tray.quick_items["Color Picker"].activate()
    assert harness.spawned == [["/usr/bin/tuxtoys", "colorpicker"]]


def test_quick_access_with_nothing_to_open_says_how_to_get_something(harness: Harness) -> None:
    harness.tray.show_modules([module("awake"), module("colorpicker", "off")])
    item = harness.tray.quick_items["Switch on a tool to open it from here."]
    assert not item.get_sensitive()


def test_follows_tools_switched_on_and_off(harness: Harness, pump: Callable[..., bool]) -> None:
    # The tray hears only signals from the daemon's name, so the test's side takes it.
    harness.service.call_sync(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "RequestName",
        GLib.Variant("(su)", (BUS_NAME, 4)),
        GLib.VariantType("(u)"),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
    )
    assert pump(lambda: "Switch on a tool to open it from here." in harness.tray.quick_items)
    assert harness.tray.awake_shown

    harness.client.state = None  # Awake switched off
    rows = [tuple(module("mousejump")), tuple(module("awake", "off"))]
    harness.service.emit_signal(
        None, OBJECT_PATH, DAEMON_INTERFACE, "ModulesChanged", GLib.Variant("(a(sssss))", (rows,))
    )
    assert pump(lambda: "Mouse Jump" in harness.tray.quick_items)
    assert not harness.tray.awake_shown
