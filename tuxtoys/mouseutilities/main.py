"""The mouse tools' helper: one process for every mouse tool that is on. It watches the
pointer and the modifier keys once, hands every event to each tool, and draws what they call
for, until the daemon stops it. Started by the daemon with a --tool id=settings for each,
not by hand. Its name on the session bus takes the tools' shortcuts, `tuxtoys findmymouse`
and `tuxtoys mousehighlighter`.
"""

import argparse
import json
import logging
import signal
import sys
import threading
from typing import Any

log = logging.getLogger("tuxtoys-mouse-utilities")

TOOLS = ("findmymouse", "mousehighlighter")
INTERFACE_XML = """
<node>
  <interface name="{interface}">
    <method name="FindMouse"/>
    <method name="ToggleHighlighter"/>
    <method name="Configure">
      <arg name="tool" type="s" direction="in"/>
      <arg name="settings" type="s" direction="in"/>
    </method>
  </interface>
</node>
"""


def tool_settings(arguments: list[str]) -> dict[str, dict[str, Any]]:
    """The --tool id=settings arguments, by tool; ValueError for one that is not."""
    found = {}
    for argument in arguments:
        tool_id, _equals, settings = argument.partition("=")
        if tool_id not in TOOLS:
            raise ValueError(f"no such mouse tool: {tool_id!r}")
        value = json.loads(settings or "{}")
        if not isinstance(value, dict):
            raise ValueError(f"{tool_id}'s settings are not a JSON object")
        found[tool_id] = value
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tuxtoys-mouse-utilities")
    parser.add_argument(
        "--tool", action="append", default=[], help="a tool to run, as id=settings in JSON"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(levelname)s: %(message)s")
    try:
        tools = tool_settings(args.tool)
    except ValueError as error:
        log.error("bad settings: %s", error)
        return 2
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gio, GLib, Gtk

        from tuxtoys.platform.x11 import watch_input
    except (ImportError, ValueError) as error:
        log.error("cannot watch the mouse: %s", error)
        return 1
    if not Gtk.init_check(sys.argv)[0]:
        log.error("cannot watch the mouse: no display")
        return 1

    from tuxtoys.api import MOUSE_BUS_NAME, MOUSE_INTERFACE, MOUSE_PATH
    from tuxtoys.inputwatch.detect import Event

    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    running: dict[str, Any] = {}
    if "findmymouse" in tools:
        from tuxtoys.modules.findmymouse.options import Options
        from tuxtoys.mouseutilities.findmymouse import FindMyMouseTool

        running["findmymouse"] = FindMyMouseTool(Options.read(tools["findmymouse"]), bus)
    if "mousehighlighter" in tools:
        from tuxtoys.modules.mousehighlighter.options import Options as HighlighterOptions
        from tuxtoys.mouseutilities.highlighter import HighlighterTool

        running["mousehighlighter"] = HighlighterTool(
            HighlighterOptions.read(tools["mousehighlighter"])
        )

    def handle(event: Event) -> None:
        """In the watcher's thread: every tool hears every event."""
        for tool in running.values():
            tool.handle(event)

    def watch() -> None:
        try:
            watch_input(handle)
        except Exception:
            log.exception("stopped watching the mouse")

    def on_call(*arguments: Any) -> None:  # noqa: ANN401, Gio's method call arguments
        method, parameters, invocation = arguments[4], arguments[5], arguments[6]
        if method == "Configure":
            configure(*parameters.unpack(), invocation)
            return
        if method == "FindMouse" and "findmymouse" in running:
            running["findmymouse"].toggle()
        elif method == "ToggleHighlighter" and "mousehighlighter" in running:
            running["mousehighlighter"].toggle()
        invocation.return_value(None)

    def configure(tool_id: str, settings: str, invocation: Any) -> None:  # noqa: ANN401
        """A running tool's new settings; one that is not running is the daemon's to start."""
        try:
            found = tool_settings([f"{tool_id}={settings}"])
        except ValueError as error:
            invocation.return_dbus_error("org.freedesktop.DBus.Error.InvalidArgs", str(error))
            return
        if tool_id not in running:
            invocation.return_dbus_error("org.freedesktop.DBus.Error.Failed", "not running")
            return
        if tool_id == "findmymouse":
            from tuxtoys.modules.findmymouse.options import Options

            running[tool_id].configure(Options.read(found[tool_id]))
        else:
            from tuxtoys.modules.mousehighlighter.options import Options as HighlighterOptions

            running[tool_id].configure(HighlighterOptions.read(found[tool_id]))
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
    log.info("running %s", ", ".join(sorted(running)) or "no tool")
    Gtk.main()
    return 0
