"""A window let go of gets back the opacity it had, read from what was written on it before
the opacity shortcuts first changed it. Real X windows: needs a display, xvfb in CI.
"""

import pytest

gi = pytest.importorskip("gi", reason="PyGObject is not installed")
Xlib = pytest.importorskip("Xlib", reason="python3-xlib is not installed")
try:
    gi.require_version("Gtk", "3.0")
except ValueError as error:
    pytest.skip(f"GTK 3 is missing: {error}", allow_module_level=True)

from gi.repository import Gtk  # noqa: E402
from Xlib import Xatom, display  # noqa: E402

if not Gtk.init_check()[0]:
    pytest.skip("no display to open", allow_module_level=True)

from tuxtoys.modules.alwaysontop.frame import (  # noqa: E402
    BEFORE_PROPERTY,
    OPAQUE,
    opacity_record,
)
from tuxtoys.platform.x11 import restore_opacity  # noqa: E402

SEE_THROUGH = round(0.6 * OPAQUE)


@pytest.fixture
def window() -> int:
    shown = Gtk.Window()
    shown.realize()
    xid = shown.get_window().get_xid()
    shown.get_display().flush()  # so that the X server has it for the other connection
    yield xid
    shown.destroy()


def write(xid: int, opacity: int | None, before: list[int] | None) -> None:
    screen = display.Display()
    window = screen.create_resource_object("window", xid)
    atom = screen.intern_atom("_NET_WM_WINDOW_OPACITY")
    if opacity is not None:
        window.change_property(atom, Xatom.CARDINAL, 32, [opacity])
    if before is not None:
        window.change_property(screen.intern_atom(BEFORE_PROPERTY), Xatom.CARDINAL, 32, before)
    screen.sync()
    screen.close()


def read(xid: int) -> tuple[list[int] | None, list[int] | None]:
    screen = display.Display()
    window = screen.create_resource_object("window", xid)
    found = []
    for name in ("_NET_WM_WINDOW_OPACITY", BEFORE_PROPERTY):
        value = window.get_full_property(screen.intern_atom(name), Xatom.CARDINAL)
        found.append(list(value.value) if value is not None else None)
    screen.close()
    return found[0], found[1]


def test_back_to_no_opacity_at_all(window: int) -> None:
    write(window, SEE_THROUGH, opacity_record(None))
    restore_opacity([window])
    assert read(window) == (None, None)


def test_back_to_the_opacity_it_had(window: int) -> None:
    write(window, SEE_THROUGH, opacity_record(round(0.8 * OPAQUE)))
    restore_opacity([window])
    assert read(window) == ([round(0.8 * OPAQUE)], None)


def test_a_window_the_shortcuts_never_changed_is_left_alone(window: int) -> None:
    write(window, SEE_THROUGH, None)
    restore_opacity([window])
    assert read(window) == ([SEE_THROUGH], None)


def test_a_window_already_gone_is_skipped(window: int) -> None:
    restore_opacity([0x7FFFFFF0, window])  # no such window, then a real one
