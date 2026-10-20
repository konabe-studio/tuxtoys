"""Find My Mouse in the helper: the sonar fed by the watcher, and the spotlight it calls for.

The watcher's thread feeds the sonar every event, as many as the mouse sends; the main loop
hears only what they call for. Both reach the sonar, one at a time.
"""

import threading
from contextlib import suppress
from typing import Any

from gi.repository import Gdk, GLib

from tuxtoys.inputwatch.detect import Event
from tuxtoys.modules.findmymouse.options import Options
from tuxtoys.modules.findmymouse.sonar import Action, Sonar
from tuxtoys.mouseutilities.desktop import animations_on, gamemode_active
from tuxtoys.mouseutilities.spotlight import Spotlight
from tuxtoys.platform.x11 import active_window_class, active_window_fullscreen

# How often the spotlight looks whether the pointer has rested long enough.
TICK_MS = 100


def now() -> int:
    return GLib.get_monotonic_time() // 1000


class FindMyMouseTool:
    def __init__(self, options: Options, bus: Any) -> None:  # noqa: ANN401, a Gio.DBusConnection
        self.options = options
        self._bus = bus
        self._sonar = Sonar(options)
        self._lock = threading.Lock()
        self._spotlight = Spotlight(options, animations_on())
        self._ticking = 0

    def handle(self, event: Event) -> None:
        """In the watcher's thread."""
        with self._lock:
            action = self._sonar.feed(event, now())
        if action is not None:
            GLib.idle_add(self._act, action)

    def toggle(self) -> None:
        """Its shortcut, through the helper's FindMouse."""
        display = Gdk.Display.get_default()
        with self._lock:
            if display is not None:
                _screen, x, y = display.get_default_seat().get_pointer().get_position()
                self._sonar.pointer = (x, y)
            action = self._sonar.toggle()
        self._act(action)

    def _allowed(self) -> bool:
        """Not over an excluded app, a full-screen window, or a game GameMode runs."""
        with suppress(OSError, RuntimeError):
            if active_window_class().lower() in self.options.excluded_apps:
                return False
            if self.options.skip_fullscreen and active_window_fullscreen():
                return False
        return not (self.options.skip_gamemode and gamemode_active(self._bus))

    def _tick(self) -> bool:
        with self._lock:
            action = self._sonar.tick(now())
            shown = self._sonar.shown
        if action is Action.STOP:
            self._spotlight.put_away()
        if not shown:
            self._ticking = 0
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _act(self, action: Action | None) -> bool:
        if action is Action.SHOW:
            if not self._allowed():
                with self._lock:
                    self._sonar.cancel()
                return GLib.SOURCE_REMOVE
            with self._lock:
                pointer = self._sonar.pointer
            self._spotlight.show_at(pointer)
            if not self._ticking:
                self._ticking = GLib.timeout_add(TICK_MS, self._tick)
        elif action is Action.STOP:
            self._spotlight.put_away()
        return GLib.SOURCE_REMOVE
