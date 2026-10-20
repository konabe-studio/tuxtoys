"""Find My Mouse's spotlight: the whole screen dimmed but for a circle around the pointer,
which follows it. A window over every monitor that takes no input, so every click goes
through to what is under it, as PowerToys' does. It fades in while the circle closes in from
`zoom` times its radius, and fades out when put away; at once while Cinnamon has its
animations off.

It moves with the screen's frames: once a frame it asks where the pointer is and redraws
only the squares the circle leaves and enters, not the whole screen, so a quick mouse does
not leave it behind.
"""

import math

import cairo
import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from tuxtoys.modules.findmymouse.options import Options, rgba  # noqa: E402
from tuxtoys.modules.findmymouse.sonar import radius_at  # noqa: E402

# Room around the circle for its smoothed edge.
EDGE = 3


class Spotlight(Gtk.Window):
    def __init__(self, options: Options, animations: bool = True) -> None:
        super().__init__(type=Gtk.WindowType.POPUP)
        self.options = options
        self.duration = options.duration if animations else 0
        self.pointer = (0, 0)
        # How far it has faded in, 0 to 1, and where it is heading.
        self.progress = 0.0
        self._target = 0.0
        self._from = 0.0
        self._started = 0
        self._tick = 0
        visual = self.get_screen().get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        self.set_app_paintable(True)
        root = Gdk.get_default_root_window()
        self.move(0, 0)
        if root is not None:
            self.set_default_size(root.get_width(), root.get_height())
        self.connect("realize", self._on_realize)
        self.connect("draw", self._on_draw)

    def _on_realize(self, _window: Gtk.Window) -> None:
        # No input region: the pointer and its clicks go to the windows below.
        self.get_window().input_shape_combine_region(cairo.Region(), 0, 0)

    def show_at(self, pointer: tuple[int, int]) -> None:
        self.pointer = pointer
        if not self.get_visible():
            self.show()
        window = self.get_window()
        if window is not None:
            window.raise_()
        self._head_for(1.0)

    def put_away(self) -> None:
        self._head_for(0.0)

    def _head_for(self, target: float) -> None:
        self._target, self._from = target, self.progress
        self._started = GLib.get_monotonic_time() // 1000
        if not self.duration:
            self.progress = target
        if target == 0.0 and not self.duration:
            self._hide()
            return
        self.queue_draw()
        if not self._tick:
            self._tick = self.add_tick_callback(self._on_tick)

    def _hide(self) -> None:
        if self._tick:
            self.remove_tick_callback(self._tick)
            self._tick = 0
        self.progress = 0.0
        self.hide()

    def _where(self) -> tuple[int, int]:
        display = Gdk.Display.get_default()
        if display is None:
            return self.pointer
        _screen, x, y = display.get_default_seat().get_pointer().get_position()
        return x, y

    def _on_tick(self, _widget: Gtk.Widget, _clock: Gdk.FrameClock) -> bool:
        if self.progress != self._target:
            elapsed = GLib.get_monotonic_time() // 1000 - self._started
            done = min(elapsed / self.duration, 1.0) if self.duration else 1.0
            self.progress = self._from + (self._target - self._from) * done
            if self._target == 0.0 and done >= 1.0:
                self._tick = 0
                self.progress = 0.0
                self.hide()
                return GLib.SOURCE_REMOVE
            # The fade changes the whole screen.
            self.pointer = self._where()
            self.queue_draw()
            return GLib.SOURCE_CONTINUE
        pointer = self._where()
        if pointer != self.pointer:
            self._redraw_around(self.pointer)
            self.pointer = pointer
            self._redraw_around(pointer)
        return GLib.SOURCE_CONTINUE

    def _redraw_around(self, pointer: tuple[int, int]) -> None:
        radius = math.ceil(radius_at(self.options, self.progress)) + EDGE
        x, y = pointer
        self.queue_draw_area(x - radius, y - radius, 2 * radius, 2 * radius)

    def _on_draw(self, _window: Gtk.Window, context: cairo.Context) -> bool:
        # Drawn straight, without a group: GTK has clipped it to the squares that changed.
        context.set_operator(cairo.OPERATOR_SOURCE)
        red, green, blue, alpha = rgba(self.options.background)
        context.set_source_rgba(red, green, blue, alpha * self.progress)
        context.paint()
        x, y = self.pointer
        context.arc(x, y, radius_at(self.options, self.progress), 0, 2 * math.pi)
        red, green, blue, alpha = rgba(self.options.spotlight)
        context.set_source_rgba(red, green, blue, alpha * self.progress)
        context.fill()
        return True
