"""What Mouse Pointer Crosshairs draws, and how the gliding cursor moves, as pure logic after
PowerToys' (InclusiveCrosshairs.cpp, MousePointerCrosshairs/dllmain.cpp). Free of GTK, so
it tests anywhere; the helper draws the shapes and moves the pointer.

The crosshairs are four arms from a gap of `radius` around the pointer to the edges of the
monitor it is on, or `fixed_length` long, `thickness` wide, each over a border `border`
wider all round, the whole at one opacity.

The gliding cursor places the pointer and clicks with its shortcut alone: the first press
sends a vertical line across the monitor from its left edge, the second slows it, the third
holds it there and sends a horizontal line down from the top, the fourth slows that, the
fifth clicks where they cross. A line that reaches the far edge starts again from the near
one at the first speed. Escape stops it without a click.
"""

from enum import Enum

from tuxtoys.modules.crosshairs.options import Options
from tuxtoys.modules.mouseutilities.shapes import Layer, Rect, Shape, rgba

# A monitor's area: left, top, width, height.
Monitor = tuple[int, int, int, int]
# PowerToys' speeds are pixels in this many milliseconds.
SPEED_PERIOD_MS = 200


def arms(
    options: Options, pointer: tuple[int, int], monitor: Monitor, orientation: str
) -> list[Rect]:
    """The arms, without their border, as rectangles of the crosshairs' color."""
    x, y = pointer
    left, top, width, height = monitor
    gap, thick = options.radius, options.thickness
    half = thick // 2
    color = rgba(options.color)

    def length(room: int) -> int:
        return options.fixed_length if options.fixed else room

    found = []
    if orientation in ("both", "horizontal"):
        reach = length(x - left - gap)
        found.append(Rect(x - gap - reach, y - half, reach, thick, color))
        reach = length(left + width - x - gap)
        found.append(Rect(x + gap, y - half, reach, thick, color))
    if orientation in ("both", "vertical"):
        reach = length(y - top - gap)
        found.append(Rect(x - half, y - gap - reach, thick, reach, color))
        reach = length(top + height - y - gap)
        found.append(Rect(x - half, y + gap, thick, reach, color))
    return [arm for arm in found if arm.width > 0 and arm.height > 0]


def crosshairs(
    options: Options, pointer: tuple[int, int], monitor: Monitor, orientation: str = ""
) -> list[Shape]:
    """The crosshairs at the pointer: each arm over its border, all at the opacity set."""
    found = arms(options, pointer, monitor, orientation or options.orientation)
    if not found:
        return []
    border = options.border
    edge = rgba(options.border_color)
    borders = [
        Rect(arm.x - border, arm.y - border, arm.width + 2 * border, arm.height + 2 * border, edge)
        for arm in found
        if border
    ]
    return [Layer((*borders, *found), options.opacity / 100)]


class Step(Enum):
    STARTED = "started"
    SLOWED = "slowed"
    TURNED = "turned"
    CLICK = "click"


class Glide:
    """The gliding cursor's sweep: which line moves, how fast, and where the pointer is."""

    def __init__(self, options: Options) -> None:
        self.options = options
        self.stage = 0
        self.pointer = (0, 0)
        self._monitor: Monitor = (0, 0, 0, 0)
        self._speed = options.glide_speed
        self._carry = 0.0

    @property
    def active(self) -> bool:
        return self.stage > 0

    def press(self, pointer: tuple[int, int], monitor: Monitor) -> Step:
        """The shortcut once more: what it did."""
        left, top, _width, height = monitor if self.stage == 0 else self._monitor
        if self.stage == 0:
            self._monitor = monitor
            self.pointer = (left, top + height // 2)
            self._speed, self._carry = self.options.glide_speed, 0.0
            self.stage = 1
            return Step.STARTED
        if self.stage in (1, 3):
            self._speed = self.options.glide_slow
            self.stage += 1
            return Step.SLOWED
        if self.stage == 2:
            self.pointer = (self.pointer[0], top)
            self._speed, self._carry = self.options.glide_speed, 0.0
            self.stage = 3
            return Step.TURNED
        self.stage = 0
        return Step.CLICK

    def cancel(self) -> None:
        self.stage = 0

    def tick(self, elapsed_ms: float) -> tuple[int, int]:
        """The pointer after this long, its line moved on and wrapped at the far edge."""
        if not self.active:
            return self.pointer
        left, top, width, height = self._monitor
        travel = self._speed * elapsed_ms / SPEED_PERIOD_MS + self._carry
        step = int(travel)
        self._carry = travel - step
        x, y = self.pointer
        if self.stage <= 2:
            x += step
            if x >= left + width:
                x, self._speed = left, self.options.glide_speed
        else:
            y += step
            if y >= top + height:
                y, self._speed = top, self.options.glide_speed
        self.pointer = (x, y)
        return self.pointer
