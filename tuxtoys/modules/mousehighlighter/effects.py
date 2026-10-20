"""What Mouse Highlighter draws, as pure logic: the clicks it is told of turned into shapes for
a given moment, after PowerToys' Mouse Highlighter (MouseHighlighter.cpp). Free of GTK, so
it tests anywhere; the helper draws the shapes.

- Circle: a circle under the pointer while a button is held, which shrinks to 70 % after
  150 ms over 180 ms, follows the pointer, and fades when let go of, after a delay. A circle
  in the "always" color under the pointer the rest of the time, if that color is not
  transparent.
- Spotlight: the screen dimmed but for a circle around the pointer, which closes in to 85 %
  over 120 ms while a button is held and opens again over 200 ms.
- Ripple: a quick click sends a ring and a glow out from 0.20 and 0.30 of the size to 1.05
  and 1.40; a button held past 180 ms shows them at 0.55 and 0.65 until let go of, then they
  go out from there. With crosshairs on, letting go of the right button sends four lines
  out with them.

Times are milliseconds on one clock the caller keeps.
"""

from dataclasses import dataclass

from tuxtoys.inputwatch.detect import ButtonEvent, Event, Motion
from tuxtoys.modules.mousehighlighter.options import Options
from tuxtoys.modules.mouseutilities.shapes import (
    Color,
    Dim,
    Disc,
    Line,
    Ring,
    Shape,
    faded,
    rgba,
)

__all__ = ["Color", "Dim", "Disc", "Highlighter", "Line", "Ring", "Shape", "rgba"]

LEFT = 1
RIGHT = 3
PRESS_DELAY_MS = 150
PRESS_SHRINK_MS = 180
PRESSED_CIRCLE = 0.70
SPOT_IN_MS = 120
SPOT_OUT_MS = 200
PRESSED_SPOT = 0.85
HOLD_MS = 180
HOLD_FADE_IN_MS = 120


def lerp(start: float, end: float, progress: float) -> float:
    return start + (end - start) * min(max(progress, 0.0), 1.0)


def ease_out(progress: float) -> float:
    progress = min(max(progress, 0.0), 1.0)
    return 1 - (1 - progress) ** 3


@dataclass
class _Press:
    button: int
    start: int
    x: int
    y: int


@dataclass
class _Fade:
    button: int
    start: int
    x: int
    y: int
    radius: float


@dataclass
class _Ripple:
    button: int
    start: int
    x: int
    y: int
    ring: tuple[float, float]
    glow: tuple[float, float]


class Highlighter:
    def __init__(self, options: Options) -> None:
        self.options = options
        self.active = options.auto_activate
        self.pointer = (0, 0)
        self._presses: dict[int, _Press] = {}
        self._fades: list[_Fade] = []
        self._ripples: list[_Ripple] = []
        # The spotlight's radius: where it was, where it is going, since when, how long.
        self._spot = (1.0, 1.0, 0, 1)

    def color(self, button: int) -> Color | None:
        """A button's color, or None for a button it leaves alone or a transparent color."""
        if button == LEFT:
            found = rgba(self.options.primary_color)
        elif button == RIGHT:
            found = rgba(self.options.secondary_color)
        else:
            return None
        return found if found[3] > 0 else None

    def toggle(self) -> None:
        self.active = not self.active
        self._presses.clear()
        self._fades.clear()
        self._ripples.clear()

    def feed(self, event: Event, now: int) -> bool:
        """Whether this event changes what is drawn."""
        if isinstance(event, Motion):
            self.pointer = (event.x, event.y)
            return self.active and self._follows()
        if not isinstance(event, ButtonEvent) or not self.active:
            return False
        self.pointer = (event.x, event.y)
        mode = self.options.mode
        if mode == "spotlight":
            if event.button in (LEFT, RIGHT):
                self._spot_to(PRESSED_SPOT if event.pressed else 1.0, now)
                return True
            return False
        if self.color(event.button) is None:
            return False
        if event.pressed:
            self._presses[event.button] = _Press(event.button, now, event.x, event.y)
            return True
        press = self._presses.pop(event.button, None)
        if press is None:
            return False
        if mode == "circle":
            radius = self._circle_radius(press, now)
            self._fades.append(_Fade(event.button, now, event.x, event.y, radius))
        else:
            self._ripples.append(self._ripple_from(press, now))
        return True

    def _follows(self) -> bool:
        """Whether anything drawn now goes where the pointer goes."""
        mode = self.options.mode
        if mode == "spotlight":
            return True
        if mode == "circle":
            return bool(self._presses) or rgba(self.options.always_color)[3] > 0
        return bool(self._presses) and self.options.follow

    def _spot_to(self, target: float, now: int) -> None:
        current = self._spot_scale(now)
        duration = SPOT_IN_MS if target < 1.0 else SPOT_OUT_MS
        self._spot = (current, target, now, duration)

    def _spot_scale(self, now: int) -> float:
        start, end, since, duration = self._spot
        return lerp(start, end, (now - since) / duration)

    def _circle_radius(self, press: _Press, now: int) -> float:
        radius = self.options.radius
        shrink = (now - press.start - PRESS_DELAY_MS) / PRESS_SHRINK_MS
        return lerp(radius, radius * PRESSED_CIRCLE, shrink)

    def _ripple_from(self, press: _Press, now: int) -> _Ripple:
        x, y = self.pointer if self.options.follow else (press.x, press.y)
        if now - press.start >= HOLD_MS:
            return _Ripple(press.button, now, x, y, (0.55, 1.05), (0.65, 1.40))
        return _Ripple(press.button, now, x, y, (0.20, 1.05), (0.30, 1.40))

    def busy(self, now: int) -> bool:
        """Whether what it draws still changes, so it wants another frame."""
        if not self.active:
            return False
        if self.options.mode == "spotlight":
            return True  # it follows the pointer the whole time
        self._drop_finished(now)
        always = self.options.mode == "circle" and rgba(self.options.always_color)[3] > 0
        return bool(self._presses or self._fades or self._ripples or always)

    def _drop_finished(self, now: int) -> None:
        options = self.options
        self._fades = [
            fade
            for fade in self._fades
            if now - fade.start < options.fade_delay + options.fade_duration
        ]
        self._ripples = [
            ripple for ripple in self._ripples if now - ripple.start < options.ripple_duration
        ]

    def frame(self, now: int) -> list[Shape]:
        """The shapes to draw at this moment."""
        if not self.active:
            return []
        self._drop_finished(now)
        mode = self.options.mode
        if mode == "spotlight":
            x, y = self.pointer
            radius = self.options.radius * self._spot_scale(now)
            return [Dim(x, y, radius, rgba(self.options.spotlight_color))]
        if mode == "circle":
            return self._circles(now)
        return self._ripple_shapes(now)

    def _circles(self, now: int) -> list[Shape]:
        options = self.options
        shapes: list[Shape] = []
        for fade in self._fades:
            color = self.color(fade.button)
            if color is None:
                continue
            gone = (now - fade.start - options.fade_delay) / max(options.fade_duration, 1)
            shapes.append(Disc(fade.x, fade.y, fade.radius, faded(color, 1 - gone)))
        x, y = self.pointer
        for press in self._presses.values():
            color = self.color(press.button)
            if color is not None:
                shapes.append(Disc(x, y, self._circle_radius(press, now), color))
        always = rgba(options.always_color)
        if not self._presses and always[3] > 0:
            shapes.append(Disc(x, y, options.radius, always))
        return shapes

    def _ripple_shapes(self, now: int) -> list[Shape]:
        options = self.options
        size = options.ripple_size
        intensity = options.intensity / 100
        ring_width = max(2.25, size * (0.035 + intensity * 0.045))
        line_width = max(1.25, size * (0.025 + intensity * 0.03))
        ring_strength = min(0.18 + intensity * 0.78, 1.0)
        glow_strength = 0.30 * intensity
        shapes: list[Shape] = []
        for ripple in self._ripples:
            color = self.color(ripple.button)
            if color is None:
                continue
            progress = (now - ripple.start) / options.ripple_duration
            grown = ease_out(progress)
            left = 1 - progress
            glow = lerp(*ripple.glow, grown) * size
            ring = lerp(*ripple.ring, grown) * size
            shapes.append(Disc(ripple.x, ripple.y, glow, faded(color, glow_strength * left), True))
            ring_color = faded(color, ring_strength * left)
            shapes.append(Ring(ripple.x, ripple.y, ring, ring_width, ring_color))
            if ripple.button == RIGHT and options.crosshairs:
                inner = ring + ring_width
                outer = inner + 0.35 * size
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    shapes.append(
                        Line(
                            ripple.x + dx * inner,
                            ripple.y + dy * inner,
                            ripple.x + dx * outer,
                            ripple.y + dy * outer,
                            line_width,
                            ring_color,
                        )
                    )
        x, y = self.pointer
        for press in self._presses.values():
            held = now - press.start - HOLD_MS
            color = self.color(press.button)
            if held < 0 or color is None:
                continue
            shown = held / HOLD_FADE_IN_MS
            px, py = (x, y) if options.follow else (press.x, press.y)
            shapes.append(Disc(px, py, 0.65 * size, faded(color, glow_strength * shown), True))
            ring_color = faded(color, ring_strength * shown)
            shapes.append(Ring(px, py, 0.55 * size, ring_width, ring_color))
        return shapes
