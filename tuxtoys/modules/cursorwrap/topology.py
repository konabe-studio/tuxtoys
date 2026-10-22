"""Where CursorWrap sends the pointer, as pure logic after PowerToys' CursorWrap
(CursorWrapCore.cpp, MonitorTopology.cpp). Free of X, so it tests anywhere.

Only outer edges wrap: those with no monitor beside them, within 50 pixels. The pointer
wraps once it is within a pixel of one, to the opposite kind of outer edge furthest in that
direction, keeping its other coordinate where a monitor has it there and moved onto the
nearest one otherwise; with nowhere to go, to its own monitor's other side. It is not
wrapped again until it has moved away from where it landed, so it does not bounce.
"""

from dataclasses import dataclass
from enum import Enum
from math import hypot

# Left, top, width, height.
Monitor = tuple[int, int, int, int]
# PowerToys' adjacency tolerance, and how near an edge the pointer has to be.
TOLERANCE = 50
EDGE = 1
# How far from where it landed the pointer has to move before it can wrap again.
SETTLE = 10


class Side(Enum):
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


OPPOSITE = {
    Side.LEFT: Side.RIGHT,
    Side.RIGHT: Side.LEFT,
    Side.TOP: Side.BOTTOM,
    Side.BOTTOM: Side.TOP,
}
HORIZONTAL = (Side.LEFT, Side.RIGHT)


@dataclass(frozen=True)
class Edge:
    side: Side
    # The pixel column or row the edge is on.
    position: int
    # The range it covers along itself, end not included.
    start: int
    end: int
    monitor: int


def edges(monitors: list[Monitor]) -> list[Edge]:
    found = []
    for index, (left, top, width, height) in enumerate(monitors):
        found.append(Edge(Side.LEFT, left, top, top + height, index))
        found.append(Edge(Side.RIGHT, left + width - 1, top, top + height, index))
        found.append(Edge(Side.TOP, top, left, left + width, index))
        found.append(Edge(Side.BOTTOM, top + height - 1, left, left + width, index))
    return found


def _adjacent(one: Edge, other: Edge) -> bool:
    """Whether a monitor's edge meets another's facing it: a right edge against a left one."""
    if other.side is not OPPOSITE[one.side] or one.monitor == other.monitor:
        return False
    # A right edge at x - 1 meets a left edge at x.
    gap = abs(one.position - other.position)
    if gap > TOLERANCE + 1:
        return False
    overlap = min(one.end, other.end) - max(one.start, other.start)
    return overlap > TOLERANCE


def outer_edges(monitors: list[Monitor]) -> list[Edge]:
    every = edges(monitors)
    return [edge for edge in every if not any(_adjacent(edge, other) for other in every)]


def _at(edge: Edge, x: int, y: int) -> bool:
    along, across = (y, x) if edge.side in HORIZONTAL else (x, y)
    if not edge.start <= along < edge.end:
        return False
    if edge.side in (Side.LEFT, Side.TOP):
        return across <= edge.position + EDGE
    return across >= edge.position - EDGE


def destination(
    outer: list[Edge],
    monitors: list[Monitor],
    pointer: tuple[int, int],
    mode: str,
    moving: tuple[int, int] = (0, 0),
) -> tuple[int, int] | None:
    """Where the pointer wraps to from here, or None where it does not."""
    x, y = pointer
    sides = {
        "both": tuple(Side),
        "horizontal": HORIZONTAL,
        "vertical": (Side.TOP, Side.BOTTOM),
    }[mode]
    found = [edge for edge in outer if edge.side in sides and _at(edge, x, y)]
    if not found:
        return None
    if len(found) > 1:
        # A corner: the edge the pointer is moving towards.
        dx, dy = moving
        if abs(dx) >= abs(dy):
            wanted = Side.LEFT if dx < 0 else Side.RIGHT
        else:
            wanted = Side.TOP if dy < 0 else Side.BOTTOM
        found = [edge for edge in found if edge.side is wanted] or found
    source = found[0]
    target_side = OPPOSITE[source.side]
    along = y if source.side in HORIZONTAL else x
    targets = [edge for edge in outer if edge.side is target_side]
    # The furthest that way: going out on the left, in on the rightmost right edge.
    furthest = max if target_side in (Side.RIGHT, Side.BOTTOM) else min
    direct = [edge for edge in targets if edge.start <= along < edge.end]
    if direct:
        target = furthest(direct, key=lambda edge: edge.position)
        landing = along
    elif targets:
        target = min(
            targets, key=lambda edge: min(abs(along - edge.start), abs(along - (edge.end - 1)))
        )
        landing = target.start + 1 if along < target.start else target.end - 1
        landing = max(target.start, min(landing, target.end - 1))
    else:
        left, top, width, height = monitors[source.monitor]
        inside = {
            Side.LEFT: (left + width - 2, y),
            Side.RIGHT: (left + 1, y),
            Side.TOP: (x, top + height - 2),
            Side.BOTTOM: (x, top + 1),
        }
        return inside[source.side]
    if source.side in HORIZONTAL:
        return target.position, landing
    return landing, target.position


class Wrapper:
    """CursorWrap's state: where the pointer was, the buttons and keys that hold it back,
    and where it last landed.
    """

    def __init__(self, monitors: list[Monitor], mode: str = "both") -> None:
        self.monitors = monitors
        self.mode = mode
        self._outer = outer_edges(monitors)
        self._last: tuple[int, int] | None = None
        self._landed: tuple[int, int] | None = None

    def move(self, pointer: tuple[int, int]) -> tuple[int, int] | None:
        """The pointer moved here: where to put it, or None to leave it."""
        last, self._last = self._last, pointer
        if self._landed is not None:
            if hypot(pointer[0] - self._landed[0], pointer[1] - self._landed[1]) <= SETTLE:
                return None
            self._landed = None
        moving = (pointer[0] - last[0], pointer[1] - last[1]) if last else (0, 0)
        found = destination(self._outer, self.monitors, pointer, self.mode, moving)
        if found is None or found == pointer:
            return None
        self._landed = found
        self._last = found
        return found
