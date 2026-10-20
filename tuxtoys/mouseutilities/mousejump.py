"""Mouse Jump in the helper: its shortcut takes a picture of every monitor, then shows the
preview around the pointer. A left click on a monitor's picture puts the pointer there; any
other click, a click outside, or Escape closes it; 1 to 9, P, Left, Right, Home and End jump
to a monitor's middle, as PowerToys' keys do.

The preview holds the pointer and the keyboard while it is open, as the screen tools'
overlay does, so a click outside it reaches it and closes it.
"""

import cairo
from gi.repository import Gdk, Gtk

from tuxtoys.alwaysontop.border import theme_accent
from tuxtoys.modules.mousejump.layout import (
    Box,
    Layout,
    Style,
    jump_by_key,
    jump_to,
    layout,
    rgb,
)
from tuxtoys.modules.mousejump.options import Options
from tuxtoys.mouseutilities.pointer import pointer_now
from tuxtoys.platform.x11 import capture_screen, move_pointer

KEYS = {
    Gdk.KEY_Left: "Left",
    Gdk.KEY_Right: "Right",
    Gdk.KEY_Home: "Home",
    Gdk.KEY_End: "End",
    Gdk.KEY_p: "p",
    Gdk.KEY_P: "p",
}


def monitors() -> tuple[list[Box], int]:
    """Every monitor's area, and which one is the primary."""
    display = Gdk.Display.get_default()
    found = []
    primary = 0
    for index in range(display.get_n_monitors()):
        monitor = display.get_monitor(index)
        area = monitor.get_geometry()
        found.append((area.x, area.y, area.width, area.height))
        if monitor.is_primary():
            primary = index
    return found, primary


class Preview(Gtk.Window):
    def __init__(
        self,
        found: Layout,
        picture: object,
        style: Style,
        screens: list[Box],
        primary: int,
    ) -> None:
        super().__init__(type=Gtk.WindowType.POPUP)
        self.found = found
        self.picture = picture
        self.style = style
        self.screens = screens
        self.primary = primary
        x, y, width, height = found.window
        self.move(x, y)
        self.set_default_size(width, height)
        self.set_app_paintable(True)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.KEY_PRESS_MASK)
        self.connect("draw", self._on_draw)
        self.connect("map-event", self._on_map)
        self.connect("button-press-event", self._on_button)
        self.connect("key-press-event", self._on_key)

    def _on_map(self, _window: Gtk.Window, _event: Gdk.Event) -> bool:
        window = self.get_window()
        cursor = Gdk.Cursor.new_from_name(window.get_display(), "default")
        seat = window.get_display().get_default_seat()
        seat.grab(window, Gdk.SeatCapabilities.ALL, False, cursor, None, None, None)
        self.present()
        return False

    def close_preview(self) -> None:
        window = self.get_window()
        if window is not None:
            window.get_display().get_default_seat().ungrab()
        self.destroy()

    def _jump(self, where: tuple[int, int] | None) -> None:
        self.close_preview()
        if where is not None:
            move_pointer(*where)

    def _on_button(self, _window: Gtk.Window, event: Gdk.EventButton) -> bool:
        if event.button != 1:
            self.close_preview()
            return True
        self._jump(jump_to(self.found, int(event.x), int(event.y)))
        return True

    def _on_key(self, _window: Gtk.Window, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.close_preview()
            return True
        key = KEYS.get(event.keyval)
        if key is None:
            character = chr(Gdk.keyval_to_unicode(event.keyval) or 0)
            key = character if character.isdigit() else ""
        x, y = pointer_now()
        current = next(
            (
                index
                for index, (left, top, width, height) in enumerate(self.screens)
                if left <= x < left + width and top <= y < top + height
            ),
            0,
        )
        where = jump_by_key(key, self.screens, self.primary, current) if key else None
        if where is not None:
            self._jump(where)
        return True

    def _on_draw(self, _window: Gtk.Window, context: cairo.Context) -> bool:
        style = self.style
        _x, _y, width, height = self.found.window
        gradient = cairo.LinearGradient(0, 0, 0, height)
        gradient.add_color_stop_rgb(0, *rgb(style.color1))
        gradient.add_color_stop_rgb(1, *rgb(style.color2))
        context.set_source(gradient)
        context.paint()
        border = style.border
        if border:
            color = rgb(style.border_color) if style.border_color else theme_accent()
            context.set_source_rgb(*color)
            context.set_line_width(border)
            context.rectangle(border / 2, border / 2, width - border, height - border)
            context.stroke()
            self._draw_depth(context, (0, 0, width, height), min(style.border_depth, border))
        for screen in self.found.screens:
            self._draw_screen(context, screen.outer, screen.content, screen.monitor)
        return True

    def _draw_screen(self, context: cairo.Context, outer: Box, content: Box, monitor: Box) -> None:
        style = self.style
        margin = style.margin
        left, top, width, height = outer
        bezel = (left + margin, top + margin, width - 2 * margin, height - 2 * margin)
        if style.bezel:
            context.set_source_rgb(*rgb(style.bezel_color))
            context.rectangle(*bezel)
            context.fill()
            self._draw_depth(context, bezel, min(style.bezel_depth, style.bezel))
        x, y, w, h = content
        gradient = cairo.LinearGradient(0, y, 0, y + h)
        gradient.add_color_stop_rgb(0, *rgb(style.screen1))
        gradient.add_color_stop_rgb(1, *rgb(style.screen2))
        context.set_source(gradient)
        context.rectangle(x, y, w, h)
        context.fill()
        if self.picture is None or not w or not h:
            return
        context.save()
        context.rectangle(x, y, w, h)
        context.clip()
        context.translate(x, y)
        context.scale(w / monitor[2], h / monitor[3])
        Gdk.cairo_set_source_pixbuf(context, self.picture, -monitor[0], -monitor[1])
        context.get_source().set_filter(cairo.FILTER_GOOD)
        context.paint()
        context.restore()

    @staticmethod
    def _draw_depth(context: cairo.Context, box: Box, depth: int) -> None:
        """A raised edge `depth` wide: lighter along the top and left, darker below."""
        if depth <= 0:
            return
        left, top, width, height = box
        for index in range(depth):
            shade = 0.12 * (depth - index) / depth
            context.set_line_width(1)
            context.set_source_rgba(1, 1, 1, shade)
            context.move_to(left + index + 0.5, top + height - index)
            context.line_to(left + index + 0.5, top + index + 0.5)
            context.line_to(left + width - index, top + index + 0.5)
            context.stroke()
            context.set_source_rgba(0, 0, 0, shade * 2)
            context.move_to(left + width - index - 0.5, top + index)
            context.line_to(left + width - index - 0.5, top + height - index - 0.5)
            context.line_to(left + index, top + height - index - 0.5)
            context.stroke()


class MouseJumpTool:
    def __init__(self, options: Options) -> None:
        self.options = options
        self._preview: Preview | None = None

    def handle(self, _event: object) -> None:
        """Mouse Jump watches nothing: its shortcut and its own window are enough."""

    def configure(self, options: Options) -> None:
        self.options = options

    def jump(self) -> None:
        """Its shortcut: the preview, or the preview put away if it is open."""
        if self._preview is not None and self._preview.get_visible():
            self._preview.close_preview()
            self._preview = None
            return
        screens, primary = monitors()
        if not screens:
            return
        # Taken before the preview shows, so it is not in its own picture.
        picture = capture_screen()
        style = self.options.preview_style()
        found = layout(screens, pointer_now(), (self.options.width, self.options.height), style)
        self._preview = Preview(found, picture, style, screens, primary)
        self._preview.show()
