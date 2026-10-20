"""What the mouse tools ask of the desktop around them: whether Cinnamon has its animations
on, and whether Feral GameMode runs a game.
"""

from typing import Any

GAMEMODE_NAME = "com.feralinteractive.GameMode"
GAMEMODE_PATH = "/com/feralinteractive/GameMode"


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
