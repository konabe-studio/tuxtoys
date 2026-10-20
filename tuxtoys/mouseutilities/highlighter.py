"""Mouse Highlighter in the helper: the clicks the watcher sees handed to the pure model in
its thread, under a lock, and the canvas woken in the main loop to draw what the model says.
Whether it is on is kept for the session, so a change of settings, which starts the helper
again, leaves it as it was.
"""

import threading
from collections.abc import Sequence

from gi.repository import Gdk, GLib

from tuxtoys.inputwatch.detect import Event
from tuxtoys.modules.mousehighlighter.effects import Highlighter, Shape
from tuxtoys.modules.mousehighlighter.options import Options
from tuxtoys.modules.mouseutilities.state import read_active, state_path, write_active
from tuxtoys.mouseutilities.canvas import Canvas


def now() -> int:
    return GLib.get_monotonic_time() // 1000


class HighlighterTool:
    def __init__(self, options: Options) -> None:
        self._model = Highlighter(options)
        self._state = state_path()
        kept = read_active(self._state, "mousehighlighter")
        if kept is not None:
            self._model.active = kept
        self._lock = threading.Lock()
        self._waking = False
        self._canvas = Canvas(self._frame)
        if self._model.active:
            GLib.idle_add(self._canvas.wake)

    def handle(self, event: Event) -> None:
        """In the watcher's thread. The canvas is woken once for however many events come
        before the main loop gets to it.
        """
        with self._lock:
            changed = self._model.feed(event, now())
            wake = changed and not self._waking
            self._waking = self._waking or changed
        if wake:
            GLib.idle_add(self._wake)

    def _wake(self) -> bool:
        with self._lock:
            self._waking = False
        return self._canvas.wake()

    def toggle(self) -> None:
        """Its shortcut, through the helper's ToggleHighlighter."""
        display = Gdk.Display.get_default()
        with self._lock:
            self._model.toggle()
            active = self._model.active
            if display is not None:
                _screen, x, y = display.get_default_seat().get_pointer().get_position()
                self._model.pointer = (x, y)
        write_active(self._state, "mousehighlighter", active)
        self._canvas.wake()

    def _frame(self) -> tuple[Sequence[Shape], bool]:
        moment = now()
        with self._lock:
            return self._model.frame(moment), self._model.busy(moment)
