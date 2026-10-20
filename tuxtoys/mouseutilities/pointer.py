"""Where the pointer is now, for a tool that has not seen it move yet."""

from gi.repository import Gdk


def pointer_now(default: tuple[int, int] = (0, 0)) -> tuple[int, int]:
    display = Gdk.Display.get_default()
    if display is None:
        return default
    _screen, x, y = display.get_default_seat().get_pointer().get_position()
    return x, y
