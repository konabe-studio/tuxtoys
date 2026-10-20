"""Mouse Jump's preview, as pure logic after PowerToys' Mouse Jump (StyleHelper.cs,
LayoutHelper.cs, PreviewWindow.xaml.cs): its styles, where the preview goes and how big it is,
where each monitor's picture sits in it, and where a click in it, or a key, sends the
pointer. Free of GTK, so it tests anywhere; the helper draws it.

The preview is the whole desktop scaled to fit the largest size set, never larger than the
monitor the pointer is on, centered on the pointer and kept inside that monitor. A left click
on a monitor's picture moves the pointer to the same place on that monitor; it does not
click there.
"""

from dataclasses import dataclass

# Left, top, width, height, in pixels.
Box = tuple[int, int, int, int]
Color = tuple[float, float, float]


def _hex(color: str) -> Color:
    red, green, blue = (int(color[index : index + 2], 16) / 255 for index in (1, 3, 5))
    return red, green, blue


@dataclass(frozen=True)
class Style:
    # Around the whole preview, in the theme's highlight color.
    canvas_border: int
    canvas_padding: int
    # The preview's background, a gradient from the first color to the second.
    canvas_colors: tuple[Color, Color]
    # Around each monitor's picture.
    screen_margin: int
    screen_border: int
    # How much of the border is drawn raised, lighter above and darker below.
    screen_depth: int
    screen_border_color: Color
    screen_background: Color


BLUE = (_hex("#0d57d2"), _hex("#0344c0"))
MIDNIGHT_BLUE = _hex("#191970")
BEZEL = _hex("#222222")

# PowerToys' two styles, its Compact (the old look) and Bezelled.
STYLES = {
    "compact": Style(6, 0, BLUE, 0, 0, 0, BEZEL, MIDNIGHT_BLUE),
    "bezelled": Style(6, 4, BLUE, 4, 12, 4, BEZEL, MIDNIGHT_BLUE),
}


@dataclass(frozen=True)
class Screen:
    """One monitor in the preview: the box it takes, its border included, the part its
    picture fills, both relative to the preview, and where it is on the desktop.
    """

    outer: Box
    content: Box
    monitor: Box


@dataclass(frozen=True)
class Layout:
    # Where the preview window goes on the desktop.
    window: Box
    screens: tuple[Screen, ...]


def _union(boxes: list[Box]) -> Box:
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[0] + box[2] for box in boxes)
    bottom = max(box[1] + box[3] for box in boxes)
    return left, top, right - left, bottom - top


def _inside(box: Box, area: Box) -> Box:
    """The box moved, not resized, so as much of it as fits is inside the area."""
    x, y, width, height = box
    left, top, area_width, area_height = area
    x = max(left, min(x, left + area_width - width))
    y = max(top, min(y, top + area_height - height))
    return x, y, width, height


def layout(
    monitors: list[Box],
    pointer: tuple[int, int],
    largest: tuple[int, int],
    style: Style,
) -> Layout:
    """The preview for these monitors, opened with the pointer here."""
    active = next(
        (
            m
            for m in monitors
            if m[0] <= pointer[0] < m[0] + m[2] and m[1] <= pointer[1] < m[1] + m[3]
        ),
        monitors[0],
    )
    most_width = min(largest[0], active[2])
    most_height = min(largest[1], active[3])
    frame = style.canvas_border + style.canvas_padding
    room_width, room_height = most_width - 2 * frame, most_height - 2 * frame
    desktop = _union(monitors)
    scale = min(room_width / desktop[2], room_height / desktop[3])
    screens = []
    for monitor in monitors:
        left = frame + round((monitor[0] - desktop[0]) * scale)
        top = frame + round((monitor[1] - desktop[1]) * scale)
        right = frame + round((monitor[0] + monitor[2] - desktop[0]) * scale)
        bottom = frame + round((monitor[1] + monitor[3] - desktop[1]) * scale)
        outer = (left, top, right - left, bottom - top)
        inset = style.screen_margin + style.screen_border
        content = (left + inset, top + inset, outer[2] - 2 * inset, outer[3] - 2 * inset)
        screens.append(Screen(outer, content, monitor))
    used = _union([screen.outer for screen in screens])
    width, height = used[0] + used[2] + frame, used[1] + used[3] + frame
    window = _inside((pointer[0] - width // 2, pointer[1] - height // 2, width, height), active)
    return Layout(window, tuple(screens))


def jump_to(found: Layout, x: int, y: int) -> tuple[int, int] | None:
    """Where a click at (x, y) in the preview sends the pointer: the same place on the
    monitor whose picture it is on, kept a pixel inside its edges; None outside them all.
    """
    for screen in found.screens:
        left, top, width, height = screen.outer
        if not (left <= x < left + width and top <= y < top + height):
            continue
        c_left, c_top, c_width, c_height = screen.content
        m_left, m_top, m_width, m_height = screen.monitor
        to_x = m_left + (x - c_left) * m_width / max(c_width, 1)
        to_y = m_top + (y - c_top) * m_height / max(c_height, 1)
        to_x = min(max(to_x, m_left + 1), m_left + m_width - 1)
        to_y = min(max(to_y, m_top + 1), m_top + m_height - 1)
        return int(to_x), int(to_y)
    return None


def center(monitor: Box) -> tuple[int, int]:
    return monitor[0] + monitor[2] // 2, monitor[1] + monitor[3] // 2


def jump_by_key(
    key: str, monitors: list[Box], primary: int, current: int
) -> tuple[int, int] | None:
    """Where a key sends the pointer, to the middle of a monitor, as PowerToys' keys do:
    1 to 9 that monitor, P the primary, Left and Right the one before and after, Home and End
    the first and the last; None for a key that does nothing.
    """
    if not monitors:
        return None
    count = len(monitors)
    if key.isdigit() and key != "0":
        number = int(key) - 1
        return center(monitors[number]) if number < count else None
    index = {
        "p": primary,
        "Left": (current - 1) % count,
        "Right": (current + 1) % count,
        "Home": 0,
        "End": count - 1,
    }.get("p" if key in ("p", "P") else key)
    return center(monitors[index]) if index is not None else None
