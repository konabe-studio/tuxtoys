"""What the mouse tools draw on their overlay, as plain data the helper's canvas paints:
circles, rings, lines, rectangles, the screen dimmed around a hole, and a layer that gives
the shapes in it one opacity together. Free of GTK, so the tools' models test anywhere.
"""

from dataclasses import dataclass

Color = tuple[float, float, float, float]


@dataclass(frozen=True)
class Disc:
    """A filled circle; `soft` fades from its color at the middle to nothing at its edge."""

    x: float
    y: float
    radius: float
    color: Color
    soft: bool = False


@dataclass(frozen=True)
class Ring:
    x: float
    y: float
    radius: float
    width: float
    color: Color


@dataclass(frozen=True)
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    width: float
    color: Color


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float
    color: Color


@dataclass(frozen=True)
class Dim:
    """The whole screen in `color` but for a circle around (x, y)."""

    x: float
    y: float
    radius: float
    color: Color


@dataclass(frozen=True)
class Layer:
    """Shapes drawn together and then laid on the screen at one opacity, so a shape over
    another does not let it show through.
    """

    shapes: tuple["Shape", ...]
    opacity: float


Shape = Disc | Ring | Line | Rect | Dim | Layer


def rgba(color: str) -> Color:
    """ "#rrggbbaa", or "#rrggbb" fully opaque, as each part from 0 to 1."""
    digits = color[1:] if len(color) == 9 else color[1:] + "ff"
    red, green, blue, alpha = (int(digits[index : index + 2], 16) / 255 for index in (0, 2, 4, 6))
    return red, green, blue, alpha


def faded(color: Color, factor: float) -> Color:
    red, green, blue, alpha = color
    return red, green, blue, alpha * min(max(factor, 0.0), 1.0)
