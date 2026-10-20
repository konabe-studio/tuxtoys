"""A window over every monitor that takes no input and draws shapes the mouse tools hand it:
every click goes through to what is under it. Drawn whole, once a frame while it is told
something changes, as Find My Mouse's spotlight is.
"""

import math
from collections.abc import Callable, Sequence

import cairo
import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from tuxtoys.modules.mousehighlighter.effects import Dim, Disc, Line, Ring, Shape  # noqa: E402

# What the canvas asks for each frame: the shapes, and whether more frames are wanted.
Frame = Callable[[], tuple[Sequence[Shape], bool]]


class Canvas(Gtk.Window):
    def __init__(self, frame: Frame) -> None:
        super().__init__(type=Gtk.WindowType.POPUP)
        self._frame = frame
        self._shapes: Sequence[Shape] = ()
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

    def wake(self) -> bool:
        """Something changed: draw frames until the tool says nothing moves any more."""
        if not self.get_visible():
            self.show()
            window = self.get_window()
            if window is not None:
                window.raise_()
        if not self._tick:
            self._tick = self.add_tick_callback(self._on_tick)
        return GLib.SOURCE_REMOVE

    def _on_tick(self, _widget: Gtk.Widget, _clock: Gdk.FrameClock) -> bool:
        self._shapes, more = self._frame()
        self.queue_draw()
        if more:
            return GLib.SOURCE_CONTINUE
        self._tick = 0
        if not self._shapes:
            self.hide()
        return GLib.SOURCE_REMOVE

    def _on_draw(self, _window: Gtk.Window, context: cairo.Context) -> bool:
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.set_source_rgba(0, 0, 0, 0)
        context.paint()
        for shape in self._shapes:
            draw(context, shape)
        return True


def draw(context: cairo.Context, shape: Shape) -> None:
    if isinstance(shape, Dim):
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.set_source_rgba(*shape.color)
        context.paint()
        context.arc(shape.x, shape.y, shape.radius, 0, 2 * math.pi)
        context.set_source_rgba(0, 0, 0, 0)
        context.fill()
        return
    context.set_operator(cairo.OPERATOR_OVER)
    if isinstance(shape, Disc):
        context.arc(shape.x, shape.y, shape.radius, 0, 2 * math.pi)
        if shape.soft:
            red, green, blue, alpha = shape.color
            gradient = cairo.RadialGradient(shape.x, shape.y, 0, shape.x, shape.y, shape.radius)
            gradient.add_color_stop_rgba(0, red, green, blue, alpha)
            gradient.add_color_stop_rgba(1, red, green, blue, 0)
            context.set_source(gradient)
        else:
            context.set_source_rgba(*shape.color)
        context.fill()
    elif isinstance(shape, Ring):
        context.arc(shape.x, shape.y, shape.radius, 0, 2 * math.pi)
        context.set_line_width(shape.width)
        context.set_source_rgba(*shape.color)
        context.stroke()
    elif isinstance(shape, Line):
        context.move_to(shape.x1, shape.y1)
        context.line_to(shape.x2, shape.y2)
        context.set_line_width(shape.width)
        context.set_line_cap(cairo.LINE_CAP_ROUND)
        context.set_source_rgba(*shape.color)
        context.stroke()
