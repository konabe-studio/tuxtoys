"""When Find My Mouse's spotlight comes and goes, as pure logic, after PowerToys' Find My
Mouse (FindMyMouse.cpp): it starts on a double press of the chosen Ctrl, a shake, or its
shortcut; it follows the pointer; any click or key press puts it away, and so does a second
of stillness once the pointer has moved. Until the pointer first moves it waits.

Times are milliseconds on one clock the caller keeps; the events carry the X server's own,
which only the double press compares among themselves.
"""

from enum import Enum

from tuxtoys.inputwatch.detect import (
    ButtonEvent,
    DoublePress,
    Event,
    Key,
    KeyEvent,
    Motion,
    Shake,
)
from tuxtoys.modules.findmymouse.options import Options

# PowerToys' IdlePeriod: how long the pointer may rest before the spotlight goes.
IDLE_MS = 1000


class Action(Enum):
    SHOW = "show"
    STOP = "stop"


class Sonar:
    def __init__(self, options: Options) -> None:
        self.options = options
        self.shown = False
        self.pointer = (0, 0)
        self._moved_at: int | None = None
        self._double = {
            "ctrl-left": DoublePress(Key.CTRL_LEFT),
            "ctrl-right": DoublePress(Key.CTRL_RIGHT),
        }.get(options.activation)
        self._shake = (
            Shake(options.shake_distance, options.shake_interval, options.shake_factor)
            if options.activation == "shake"
            else None
        )

    def feed(self, event: Event, now: int) -> Action | None:
        """What this event calls for, if anything."""
        if isinstance(event, Motion):
            self.pointer = (event.x, event.y)
            if self.shown:
                self._moved_at = now
                return None
            if self._shake is not None and self._shake.feed(event):
                return self._show()
            return None
        if isinstance(event, ButtonEvent):
            self.pointer = (event.x, event.y)
            if self.shown and event.pressed:
                return self._stop()
            return None
        if isinstance(event, KeyEvent):
            # Fed while shown too, so the double press knows the Ctrl was let go of.
            double = self._double is not None and self._double.feed(event, self.pointer)
            if self.shown:
                return self._stop() if event.pressed else None
            if double:
                return self._show()
        return None

    def toggle(self) -> Action:
        """The shortcut: the spotlight on, or off again if it is on."""
        return self._stop() if self.shown else self._show()

    def cancel(self) -> None:
        """A spotlight that was called for but is not wanted here, over a game for one."""
        self._stop()

    def tick(self, now: int) -> Action | None:
        """Called now and then while it is shown: a second of stillness puts it away."""
        if self.shown and self._moved_at is not None and now - self._moved_at >= IDLE_MS:
            return self._stop()
        return None

    def _show(self) -> Action:
        self.shown = True
        self._moved_at = None
        return Action.SHOW

    def _stop(self) -> Action:
        self.shown = False
        self._moved_at = None
        return Action.STOP


def lerp(start: float, end: float, progress: float) -> float:
    return start + (end - start) * min(max(progress, 0.0), 1.0)


def radius_at(options: Options, progress: float) -> float:
    """The spotlight's radius as it fades in: `zoom` times the radius at first, closing in
    to the radius, as PowerToys interpolates it with the window's opacity.
    """
    return lerp(options.radius * options.zoom, options.radius, progress)
