"""When CursorHide hides the pointer and when it shows it again, as pure logic. Free of X, so
it tests anywhere; the times are seconds from any clock that only goes forward.

The pointer is hidden at a key press that is not a modifier, while no mouse button is held,
or once it has not moved for the delay set. It shows again at any button or wheel turn, or
when it moves further than a few pixels from where it was hidden, so a knock of the desk
does not bring it back.
"""

from enum import Enum
from math import hypot

from tuxtoys.inputwatch.detect import ButtonEvent, Event, Key, KeyEvent, Motion
from tuxtoys.modules.cursorhide.options import Options

# How far the pointer has to move from where it was hidden to show again, in pixels.
MOVE = 8
MODIFIERS = frozenset({Key.CTRL_LEFT, Key.CTRL_RIGHT, Key.SHIFT, Key.ALT, Key.SUPER})


class Change(Enum):
    HIDE = "hide"
    SHOW = "show"


class Hiding:
    def __init__(self, options: Options, now: float) -> None:
        self.options = options
        self.hidden = False
        # Where the pointer was last seen, and where it was when hidden.
        self._pointer: tuple[int, int] | None = None
        self._anchor: tuple[int, int] | None = None
        self._buttons: set[int] = set()
        self._resting_since = now

    def feed(self, event: Event, now: float) -> Change | None:
        """What this event changes, if anything."""
        if isinstance(event, KeyEvent):
            if (
                event.pressed
                and event.key not in MODIFIERS
                and self.options.after_typing
                and not self._buttons
            ):
                return self._hide()
            return None
        if isinstance(event, ButtonEvent):
            if event.pressed:
                self._buttons.add(event.button)
            else:
                self._buttons.discard(event.button)
            self._pointer = (event.x, event.y)
            self._resting_since = now
            return self._show() if event.pressed else None
        if isinstance(event, Motion):
            self._pointer = (event.x, event.y)
            if not self.hidden:
                self._resting_since = now
                return None
            if self._anchor is None:
                self._anchor = self._pointer
                return None
            moved = hypot(event.x - self._anchor[0], event.y - self._anchor[1])
            if moved > MOVE:
                self._resting_since = now
                return self._show()
        return None

    def tick(self, now: float) -> Change | None:
        """Whether the pointer has rested long enough to hide."""
        if (
            self.options.after_rest
            and not self._buttons
            and now - self._resting_since >= self.options.delay
        ):
            return self._hide()
        return None

    def configure(self, options: Options, now: float) -> Change | None:
        """New settings: the pointer shows again when nothing it was hidden by is left on,
        and its rest counts from now.
        """
        self.options = options
        self._resting_since = now
        if not (options.after_typing or options.after_rest):
            return self._show()
        return None

    def _hide(self) -> Change | None:
        if self.hidden:
            return None
        self.hidden = True
        self._anchor = self._pointer
        return Change.HIDE

    def _show(self) -> Change | None:
        if not self.hidden:
            return None
        self.hidden = False
        self._anchor = None
        return Change.SHOW
