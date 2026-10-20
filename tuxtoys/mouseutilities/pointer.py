"""Where the pointer is now, for a tool that has not seen it move yet."""

from gi.repository import Gdk


def pointer_now(default: tuple[int, int] = (0, 0)) -> tuple[int, int]:
    display = Gdk.Display.get_default()
    if display is None:
        return default
    _screen, x, y = display.get_default_seat().get_pointer().get_position()
    return x, y


def monitor_at(x: int, y: int) -> tuple[int, int, int, int]:
    """The area of the monitor (x, y) is on: left, top, width, height."""
    display = Gdk.Display.get_default()
    monitor = display.get_monitor_at_point(x, y) if display is not None else None
    if monitor is None:
        return (0, 0, 0, 0)
    area = monitor.get_geometry()
    return area.x, area.y, area.width, area.height
