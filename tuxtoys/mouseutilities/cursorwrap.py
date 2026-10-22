"""CursorWrap in the helper: every pointer motion the watcher sees is checked in its thread
against the monitors' outer edges, and the pointer moved to the other side when it reaches
one. The left button and Ctrl and Shift are followed for "not while dragging" and "only
while Ctrl or Shift is held". Whether it is on is kept for the session, as the crosshairs'
is; the monitors are read again whenever they change.
"""

import threading

from gi.repository import Gdk

from tuxtoys.inputwatch.detect import ButtonEvent, Event, Key, KeyEvent, Motion
from tuxtoys.modules.cursorwrap.options import Options
from tuxtoys.modules.cursorwrap.topology import Monitor, Wrapper
from tuxtoys.modules.mouseutilities.state import read_active, state_path, write_active
from tuxtoys.platform.x11 import move_pointer

LEFT_BUTTON = 1


def monitors() -> list[Monitor]:
    display = Gdk.Display.get_default()
    found = []
    for index in range(display.get_n_monitors()):
        area = display.get_monitor(index).get_geometry()
        found.append((area.x, area.y, area.width, area.height))
    return found


class CursorWrapTool:
    def __init__(self, options: Options) -> None:
        self.options = options
        self._state = state_path()
        kept = read_active(self._state, "cursorwrap")
        self.active = options.auto_activate if kept is None else kept
        self._lock = threading.Lock()
        self._held: set[Key] = set()
        self._dragging = False
        self._wrapper = Wrapper(monitors(), options.mode)
        screen = Gdk.Screen.get_default()
        if screen is not None:
            screen.connect("monitors-changed", lambda _screen: self._read_monitors())

    def _read_monitors(self) -> None:
        found = monitors()
        with self._lock:
            self._wrapper = Wrapper(found, self.options.mode)

    def handle(self, event: Event) -> None:
        """In the watcher's thread."""
        if isinstance(event, KeyEvent):
            with self._lock:
                if event.pressed:
                    self._held.add(event.key)
                else:
                    self._held.discard(event.key)
            return
        if isinstance(event, ButtonEvent):
            if event.button == LEFT_BUTTON:
                with self._lock:
                    self._dragging = event.pressed
            return
        if not isinstance(event, Motion):
            return
        with self._lock:
            if not self._wanted():
                return
            found = self._wrapper.move((event.x, event.y))
        if found is not None:
            move_pointer(*found)

    def _wanted(self) -> bool:
        """Whether a motion now may wrap; under the lock."""
        options = self.options
        if not self.active:
            return False
        if options.not_while_dragging and self._dragging:
            return False
        if options.not_with_one_monitor and len(self._wrapper.monitors) <= 1:
            return False
        if options.activation == "ctrl":
            return bool(self._held & {Key.CTRL_LEFT, Key.CTRL_RIGHT})
        if options.activation == "shift":
            return Key.SHIFT in self._held
        return True

    def toggle(self) -> None:
        """Its shortcut: the wrapping on or off."""
        with self._lock:
            self.active = not self.active
            active = self.active
        write_active(self._state, "cursorwrap", active)

    def configure(self, options: Options) -> None:
        """New settings, from the daemon, without starting the helper again."""
        found = monitors()
        with self._lock:
            self.options = options
            self._wrapper = Wrapper(found, options.mode)
