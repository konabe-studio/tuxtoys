"""What the mouse tools watch for, as pure logic: the pointer and the modifier keys as events,
a key pressed twice in a row, and a shake of the mouse. Free of X11, so it tests anywhere.

Only the modifier keys and Escape are told apart. Every other key arrives as OTHER, without
saying which one it was: a key pressed in between is all a double press needs to know, and
Escape is how the gliding cursor is stopped.

The double press and the shake follow PowerToys' Find My Mouse (FindMyMouse.cpp).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from math import hypot


class Key(Enum):
    CTRL_LEFT = "ctrl-left"
    CTRL_RIGHT = "ctrl-right"
    SHIFT = "shift"
    ALT = "alt"
    SUPER = "super"
    ESCAPE = "escape"
    # Any other key, which is never named.
    OTHER = "other"


@dataclass(frozen=True)
class KeyEvent:
    key: Key
    pressed: bool
    # The X server's time, in milliseconds.
    time: int


@dataclass(frozen=True)
class Motion:
    x: int
    y: int
    time: int


@dataclass(frozen=True)
class ButtonEvent:
    button: int
    pressed: bool
    x: int
    y: int
    time: int


Event = KeyEvent | Motion | ButtonEvent

# GTK's double-click time, which Cinnamon's mouse settings start from.
DOUBLE_PRESS_MS = 400
# PowerToys' MIN_DOUBLE_CLICK_TIME: a second press sooner than this is a bounce, not a press.
MIN_DOUBLE_PRESS_MS = 100


class DoublePress:
    """A key pressed twice within the double-click time, the pointer not moved in between,
    with no other key between the two presses. The key has to be let go of in between, so
    holding it down never counts.
    """

    def __init__(self, key: Key, interval_ms: int = DOUBLE_PRESS_MS) -> None:
        self.key = key
        self.interval_ms = interval_ms
        self.min_ms = min(MIN_DOUBLE_PRESS_MS, interval_ms // 5)
        self._last: tuple[int, tuple[int, int]] | None = None
        self._down = False

    def feed(self, event: KeyEvent, pointer: tuple[int, int]) -> bool:
        """Whether this event completes a double press."""
        if event.key != self.key:
            if event.pressed:
                self._last = None
            return False
        if not event.pressed:
            self._down = False
            return False
        if self._down:
            return False  # still held, as a key repeat
        self._down = True
        last, self._last = self._last, (event.time, pointer)
        if last is None:
            return False
        interval = event.time - last[0]
        if self.min_ms <= interval <= self.interval_ms and last[1] == pointer:
            self._last = None
            return True
        return False


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


@dataclass
class _Movement:
    dx: int
    dy: int
    time: int


# PowerToys' defaults, as its settings page shows them.
SHAKE_MINIMUM_DISTANCE = 1000
SHAKE_INTERVAL_MS = 1000
SHAKE_FACTOR = 400


class Shake:
    """A shake of the mouse: within the last `interval_ms`, the pointer travelled at least
    `minimum_distance` pixels and more than `factor` percent of the diagonal of the box its
    path fits in. Movements in the same direction one after the other count as one.
    """

    def __init__(
        self,
        minimum_distance: int = SHAKE_MINIMUM_DISTANCE,
        interval_ms: int = SHAKE_INTERVAL_MS,
        factor: int = SHAKE_FACTOR,
    ) -> None:
        self.minimum_distance = minimum_distance
        self.interval_ms = interval_ms
        self.factor = factor
        self._history: list[_Movement] = []
        self._last: Motion | None = None

    def feed(self, motion: Motion) -> bool:
        """Whether the pointer has been shaken, as of this motion."""
        last, self._last = self._last, motion
        if last is None:
            return False
        dx, dy = motion.x - last.x, motion.y - last.y
        if not dx and not dy:
            return False
        start = motion.time - self.interval_ms
        self._history = [movement for movement in self._history if movement.time >= start]
        if self._history:
            previous = self._history[-1]
            if _sign(previous.dx) == _sign(dx) and _sign(previous.dy) == _sign(dy):
                previous.dx += dx
                previous.dy += dy
                previous.time = motion.time
            else:
                self._history.append(_Movement(dx, dy, motion.time))
        else:
            self._history.append(_Movement(dx, dy, motion.time))
        if self._shaken(self._history):
            self._history = []
            return True
        return False

    def _shaken(self, history: Iterable[_Movement]) -> bool:
        distance = 0.0
        x = y = left = right = top = bottom = 0
        for movement in history:
            distance += hypot(movement.dx, movement.dy)
            x, y = x + movement.dx, y + movement.dy
            left, right = min(left, x), max(right, x)
            top, bottom = min(top, y), max(bottom, y)
        if distance < self.minimum_distance:
            return False
        diagonal = hypot(right - left, bottom - top)
        return diagonal > 0 and distance / diagonal > self.factor / 100
