"""CursorHide in the helper: every event the watcher sees is weighed in its thread, and the
pointer hidden or shown in the main thread, which alone talks to X for it. A timer looks
four times a second whether the pointer has rested long enough, while that is set.
"""

import logging
import threading
from time import monotonic

from gi.repository import GLib

from tuxtoys.inputwatch.detect import Event
from tuxtoys.modules.cursorhide.hiding import Hiding
from tuxtoys.modules.cursorhide.options import Options
from tuxtoys.platform.x11 import HiddenCursor

log = logging.getLogger("tuxtoys-mouse-utilities")

TICK_MS = 250


class CursorHideTool:
    def __init__(self, options: Options) -> None:
        self._lock = threading.Lock()
        self._hiding = Hiding(options, monotonic())
        self._cursor = HiddenCursor()
        self._timer = 0
        self._broken = False
        self._watch_rest(options)

    def handle(self, event: Event) -> None:
        """In the watcher's thread."""
        with self._lock:
            change = self._hiding.feed(event, monotonic())
        if change is not None:
            GLib.idle_add(self._apply)

    def configure(self, options: Options) -> None:
        """New settings, from the daemon, without starting the helper again."""
        with self._lock:
            change = self._hiding.configure(options, monotonic())
        if change is not None:
            self._apply()
        self._watch_rest(options)

    def _watch_rest(self, options: Options) -> None:
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0
        if options.after_rest:
            self._timer = GLib.timeout_add(TICK_MS, self._tick)

    def _tick(self) -> bool:
        with self._lock:
            change = self._hiding.tick(monotonic())
        if change is not None:
            self._apply()
        return True

    def _apply(self) -> bool:
        """In the main thread: the pointer as the hiding has it now."""
        with self._lock:
            hidden = self._hiding.hidden
        if self._broken:
            return False
        try:
            self._cursor.set_hidden(hidden)
        except Exception:
            self._broken = True
            log.exception("cannot hide the pointer")
        return False
