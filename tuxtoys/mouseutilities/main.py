"""The mouse tools' helper: watches the pointer and the modifier keys, and shows Find My
Mouse's spotlight when they call for it, until the daemon stops it. Started by the Find My
Mouse module with its settings, not by hand. Its name on the session bus takes the
shortcut's `tuxtoys findmymouse`.
"""

import argparse
import json
import logging
import signal
import sys
import threading
from contextlib import suppress
from typing import Any

log = logging.getLogger("tuxtoys-mouse-utilities")

GAMEMODE_NAME = "com.feralinteractive.GameMode"
GAMEMODE_PATH = "/com/feralinteractive/GameMode"
# How often the spotlight looks whether the pointer has rested long enough.
TICK_MS = 100
INTERFACE_XML = """
<node>
  <interface name="{interface}">
    <method name="FindMouse"/>
  </interface>
</node>
"""


def animations_on() -> bool:
    """Cinnamon's own setting, which PowerToys' follows as Windows': on, unless it is off."""
    from gi.repository import Gio

    source = Gio.SettingsSchemaSource.get_default()
    if source is None or source.lookup("org.cinnamon.desktop.interface", True) is None:
        return True
    return Gio.Settings.new("org.cinnamon.desktop.interface").get_boolean("enable-animations")


def gamemode_active(bus: Any) -> bool:  # noqa: ANN401, a Gio.DBusConnection
    """Whether Feral GameMode runs a game now. Never starts GameMode to ask."""
    from gi.repository import Gio, GLib

    try:
        reply = bus.call_sync(
            GAMEMODE_NAME,
            GAMEMODE_PATH,
            "org.freedesktop.DBus.Properties",
            "Get",
            GLib.Variant("(ss)", (GAMEMODE_NAME, "ClientCount")),
            GLib.VariantType("(v)"),
            Gio.DBusCallFlags.NO_AUTO_START,
            500,
            None,
        )
    except GLib.Error:
        return False
    (count,) = reply.unpack()
    return isinstance(count, int) and count > 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tuxtoys-mouse-utilities")
    parser.add_argument("--findmymouse", default="{}", help="Find My Mouse's settings, as JSON")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(levelname)s: %(message)s")
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, Gio, GLib, Gtk

        from tuxtoys.mouseutilities.spotlight import Spotlight
        from tuxtoys.platform.x11 import (
            active_window_class,
            active_window_fullscreen,
            watch_input,
        )
    except (ImportError, ValueError) as error:
        log.error("cannot watch the mouse: %s", error)
        return 1
    if not Gtk.init_check(sys.argv)[0]:
        log.error("cannot watch the mouse: no display")
        return 1

    from tuxtoys.api import MOUSE_BUS_NAME, MOUSE_INTERFACE, MOUSE_PATH
    from tuxtoys.inputwatch.detect import Event, Motion
    from tuxtoys.modules.findmymouse.options import Options
    from tuxtoys.modules.findmymouse.sonar import Action, Sonar

    try:
        options = Options.read(json.loads(args.findmymouse))
    except ValueError as error:
        log.error("bad settings: %s", error)
        return 2
    sonar = Sonar(options)
    spotlight = Spotlight(options, animations_on())
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    ticking = 0

    def now() -> int:
        return GLib.get_monotonic_time() // 1000

    def allowed() -> bool:
        """Not over an excluded app, a full-screen window, or a game GameMode runs."""
        with suppress(OSError, RuntimeError):
            if active_window_class().lower() in options.excluded_apps:
                return False
            if options.skip_fullscreen and active_window_fullscreen():
                return False
        return not (options.skip_gamemode and gamemode_active(bus))

    def tick() -> bool:
        nonlocal ticking
        if sonar.tick(now()) is Action.STOP:
            spotlight.put_away()
        if not sonar.shown:
            ticking = 0
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def act(action: Action | None) -> None:
        nonlocal ticking
        if action is Action.SHOW:
            if not allowed():
                sonar.cancel()
                return
            spotlight.show_at(sonar.pointer)
            if not ticking:
                ticking = GLib.timeout_add(TICK_MS, tick)
        elif action is Action.STOP:
            spotlight.put_away()

    def handle(event: Event) -> bool:
        act(sonar.feed(event, now()))
        if sonar.shown and isinstance(event, Motion):
            spotlight.move_to(sonar.pointer)
        return GLib.SOURCE_REMOVE

    def watch() -> None:
        try:
            watch_input(lambda event: GLib.idle_add(handle, event))
        except Exception:
            log.exception("stopped watching the mouse")

    def on_call(*arguments: Any) -> None:  # noqa: ANN401, Gio's method call arguments
        method, invocation = arguments[4], arguments[6]
        if method == "FindMouse":
            display = Gdk.Display.get_default()
            if display is not None:
                _screen, x, y = display.get_default_seat().get_pointer().get_position()
                sonar.pointer = (x, y)
            act(sonar.toggle())
        invocation.return_value(None)

    def on_bus(connection: Any, _name: str) -> None:  # noqa: ANN401, a Gio.DBusConnection
        node = Gio.DBusNodeInfo.new_for_xml(INTERFACE_XML.format(interface=MOUSE_INTERFACE))
        connection.register_object(MOUSE_PATH, node.interfaces[0], on_call, None, None)

    Gio.bus_own_name_on_connection(
        bus, MOUSE_BUS_NAME, Gio.BusNameOwnerFlags.NONE, on_bus, lambda *_: Gtk.main_quit()
    )
    threading.Thread(target=watch, name="inputwatch", daemon=True).start()
    for number in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, number, Gtk.main_quit)
    log.info("watching the mouse for Find My Mouse (%s)", options.activation)
    Gtk.main()
    return 0
