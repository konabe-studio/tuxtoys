"""Where the frame around a pinned window goes, and the opacity steps. Free of GTK."""

from collections.abc import Sequence
from dataclasses import dataclass

# X11's _NET_WM_WINDOW_OPACITY: 0 is clear, this is opaque.
OPAQUE = 0xFFFFFFFF
# One press of the opacity shortcuts, in percent, and the least a window goes to.
OPACITY_STEP = 10
LEAST_WINDOW_OPACITY = 20


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int


def around(window: Rect, width: int) -> Rect:
    """The frame's area: the window's, grown by `width` on every side, so the frame sits
    outside the window and covers none of it.
    """
    return Rect(
        window.x - width, window.y - width, window.width + 2 * width, window.height + 2 * width
    )


def hex_to_rgb(color: str) -> tuple[float, float, float]:
    """ "#rrggbb" as red, green and blue from 0 to 1, as cairo takes them."""
    value = color.lstrip("#")
    red, green, blue = (int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return red, green, blue


# The opacity a window had before the opacity shortcuts first changed it, kept on the
# window itself (see platform.x11) so that letting it go puts it back, as PowerToys does:
# [1, its _NET_WM_WINDOW_OPACITY], or [0, 0] when it had none.
BEFORE_PROPERTY = "_TUXTOYS_OPACITY_BEFORE"


def opacity_record(current: int | None) -> list[int]:
    return [0, 0] if current is None else [1, current]


def recorded_opacity(record: Sequence[int]) -> int | None:
    """The opacity to put back from a record: None for none at all, as the window had."""
    if len(record) < 2 or not record[0]:
        return None
    return record[1]


def step_opacity(current: int | None, up: bool) -> int:
    """The next _NET_WM_WINDOW_OPACITY: one step up or down in percent, from opaque when
    the window has none set, kept between LEAST_WINDOW_OPACITY and opaque.
    """
    percent = round((OPAQUE if current is None else current) * 100 / OPAQUE)
    percent = percent + OPACITY_STEP if up else percent - OPACITY_STEP
    percent = max(LEAST_WINDOW_OPACITY, min(100, percent))
    return OPAQUE if percent == 100 else round(percent * OPAQUE / 100)
