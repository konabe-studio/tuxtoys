"""Find My Mouse's spotlight: the whole screen dimmed but for a circle around the pointer,
which follows it. A window over every monitor that takes no input, so every click goes
through to what is under it, as PowerToys' does. It fades in while the circle closes in from
`zoom` times its radius, and fades out when put away; at once while Cinnamon has its
animations off.
"""

import math

import cairo
import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from tuxtoys.modules.findmymouse.options import Options, rgba  # noqa: E402
from tuxtoys.modules.findmymouse.sonar import radius_at  # noqa: E402

FRAME_MS = 16


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
        self._timer = 0
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

    def move_to(self, pointer: tuple[int, int]) -> None:
        if pointer != self.pointer:
            self.pointer = pointer
            self.queue_draw()

    def put_away(self) -> None:
        self._head_for(0.0)

    def _head_for(self, target: float) -> None:
        self._target, self._from = target, self.progress
        self._started = GLib.get_monotonic_time() // 1000
        if not self.duration:
            self._set(target)
            return
        if not self._timer:
            self._timer = GLib.timeout_add(FRAME_MS, self._step)

    def _step(self) -> bool:
        elapsed = GLib.get_monotonic_time() // 1000 - self._started
        done = min(elapsed / self.duration, 1.0)
        self._set(self._from + (self._target - self._from) * done)
        if done >= 1.0:
            self._timer = 0
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _set(self, progress: float) -> None:
        self.progress = progress
        if progress <= 0.01 and self._target == 0.0:
            self.progress = 0.0
            self.hide()
        else:
            self.queue_draw()

    def _on_draw(self, _window: Gtk.Window, context: cairo.Context) -> bool:
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.set_source_rgba(0, 0, 0, 0)
        context.paint()
        context.push_group()
        context.set_source_rgba(*rgba(self.options.background))
        context.paint()
        x, y = self.pointer
        context.arc(x, y, radius_at(self.options, self.progress), 0, 2 * math.pi)
        context.set_source_rgba(*rgba(self.options.spotlight))
        context.fill()
        context.pop_group_to_source()
        context.set_operator(cairo.OPERATOR_OVER)
        context.paint_with_alpha(self.progress)
        return True
