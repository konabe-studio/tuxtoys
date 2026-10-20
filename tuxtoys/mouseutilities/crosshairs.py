"""Mouse Pointer Crosshairs in the helper: the crosshairs drawn on the canvas once a frame
where the pointer is, and the gliding cursor moving the pointer every 10 ms while it sweeps.
Whether the crosshairs are on is kept for the session, as Mouse Highlighter's is.
"""

import logging
import threading
from collections.abc import Sequence

from gi.repository import GLib

from tuxtoys.inputwatch.detect import Event, Key, KeyEvent
from tuxtoys.modules.crosshairs.drawing import Glide, Step, crosshairs
from tuxtoys.modules.crosshairs.options import Options
from tuxtoys.modules.mouseutilities.shapes import Shape
from tuxtoys.modules.mouseutilities.state import read_active, state_path, write_active
from tuxtoys.mouseutilities.canvas import Canvas
from tuxtoys.mouseutilities.pointer import monitor_at, pointer_now
from tuxtoys.platform.x11 import click, move_pointer, pointer_hidden

log = logging.getLogger("tuxtoys-mouse-utilities")

# PowerToys' gliding cursor moves every 10 ms, and looks at the pointer's visibility once a
# second for auto hide.
GLIDE_TICK_MS = 10
HIDDEN_EVERY_MS = 1000


class CrosshairsTool:
    def __init__(self, options: Options) -> None:
        self.options = options
        self._state = state_path()
        kept = read_active(self._state, "crosshairs")
        self.active = options.auto_activate if kept is None else kept
        self._glide = Glide(options)
        self._lock = threading.Lock()
        self._hidden = False
        self._glide_timer = 0
        self._last_tick = 0
        self._canvas = Canvas(self._frame)
        if self.active:
            GLib.idle_add(self._canvas.wake)
        GLib.timeout_add(HIDDEN_EVERY_MS, self._look_at_pointer)

    def handle(self, event: Event) -> None:
        """In the watcher's thread: Escape stops a glide."""
        if isinstance(event, KeyEvent) and event.pressed and event.key is Key.ESCAPE:
            with self._lock:
                gliding = self._glide.active
            if gliding:
                GLib.idle_add(self._cancel)

    def toggle(self) -> None:
        """Its shortcut: the crosshairs on or off; during a glide, the glide stops."""
        if self._glide.active:
            self._cancel()
            return
        self.active = not self.active
        write_active(self._state, "crosshairs", self.active)
        self._canvas.wake()

    def glide(self) -> None:
        """The gliding cursor's shortcut, once more."""
        pointer = pointer_now()
        with self._lock:
            step = self._glide.press(pointer, monitor_at(*pointer))
            where = self._glide.pointer
        if step is Step.STARTED:
            move_pointer(*where)
            self._last_tick = GLib.get_monotonic_time() // 1000
            self._glide_timer = GLib.timeout_add(GLIDE_TICK_MS, self._glide_tick)
        elif step is Step.TURNED:
            move_pointer(*where)
        elif step is Step.CLICK:
            self._stop_timer()
            try:
                click()
            except RuntimeError as error:
                log.warning("no click: %s", error)
        self._canvas.wake()

    def configure(self, options: Options) -> None:
        """New settings, from the daemon, without starting the helper again."""
        with self._lock:
            self.options = options
            self._glide.options = options
        self._canvas.wake()

    def _cancel(self) -> bool:
        with self._lock:
            self._glide.cancel()
        self._stop_timer()
        self._canvas.wake()
        return GLib.SOURCE_REMOVE

    def _stop_timer(self) -> None:
        if self._glide_timer:
            GLib.source_remove(self._glide_timer)
            self._glide_timer = 0

    def _glide_tick(self) -> bool:
        moment = GLib.get_monotonic_time() // 1000
        elapsed, self._last_tick = moment - self._last_tick, moment
        with self._lock:
            if not self._glide.active:
                self._glide_timer = 0
                return GLib.SOURCE_REMOVE
            where = self._glide.tick(elapsed)
        move_pointer(*where)
        return GLib.SOURCE_CONTINUE

    def _look_at_pointer(self) -> bool:
        """Auto hide: once a second, whether the pointer is hidden, as PowerToys looks."""
        if self.options.auto_hide and self.active:
            hidden = pointer_hidden()
            if hidden != self._hidden:
                self._hidden = hidden
                self._canvas.wake()
        elif self._hidden:
            self._hidden = False
            self._canvas.wake()
        return GLib.SOURCE_CONTINUE

    def _frame(self) -> tuple[Sequence[Shape], bool]:
        with self._lock:
            gliding = self._glide.active
            options = self.options
        if not (self.active or gliding) or (self._hidden and not gliding):
            return [], False
        pointer = pointer_now()
        # A glide shows both lines, whatever the crosshairs are set to, as PowerToys does.
        shapes = crosshairs(options, pointer, monitor_at(*pointer), "both" if gliding else "")
        return shapes, True
