"""The mouse tools' page, as PowerToys' Mouse Utilities: one page with a part for each tool,
which each tool's row in the sidebar scrolls to. Each part has its tool's switch and its
settings, which go through the daemon.

Find My Mouse's part: how it starts (either Ctrl twice, a shake with its three numbers, or
a shortcut), when it holds back, how the spotlight looks, and the apps it does not start
over. It says when Cinnamon's own pointer locator also answers the left Ctrl, and when
Cinnamon has its animations off.

Mouse Highlighter's part: its shortcut, whether it starts on, the mode, and the settings of
the mode chosen, as PowerToys shows them.

Mouse Pointer Crosshairs' part: its shortcut, whether it starts on, the crosshairs' look,
and the gliding cursor's shortcut and speeds.
"""

from collections.abc import Callable, Mapping
from contextlib import suppress

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402
from xapp.SettingsWidgets import (  # noqa: E402
    Button,
    ComboBox,
    SettingsPage,
    SettingsWidget,
    Switch,
    Text,
)

from tuxtoys.api import ModuleInfo, ModuleOff, NotRunning, Refused  # noqa: E402
from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.core.shortcut import CustomShortcut  # noqa: E402
from tuxtoys.modules.crosshairs import options as crosshairs  # noqa: E402
from tuxtoys.modules.findmymouse import options as findmymouse  # noqa: E402
from tuxtoys.modules.mousehighlighter import options as highlighter  # noqa: E402
from tuxtoys.settings.alwaysontop_page import AppsRow, ColorRow, SliderRow  # noqa: E402
from tuxtoys.settings.awake_page import SAVE_AFTER_MS  # noqa: E402
from tuxtoys.settings.colorpicker_page import keys_label  # noqa: E402
from tuxtoys.settings.hosts_page import NumberRow  # noqa: E402
from tuxtoys.settings.lightswitch_page import Client  # noqa: E402
from tuxtoys.settings.screenruler_page import with_detail  # noqa: E402
from tuxtoys.settings.widgets import open_keyboard_settings  # noqa: E402

MOUSE_SCHEMA = "org.cinnamon.desktop.peripherals.mouse"
INTERFACE_SCHEMA = "org.cinnamon.desktop.interface"
# How often a number or a slider being changed is sent, so the tool follows it as it moves.
LIVE_EVERY_MS = 60

Flag = Callable[[str, str, bool], bool]


def cinnamon_flag(schema: str, key: str, default: bool) -> bool:
    """One of Cinnamon's own switches, or `default` where Cinnamon's settings are missing."""
    source = Gio.SettingsSchemaSource.get_default()
    found = source.lookup(schema, True) if source is not None else None
    if found is None or not found.has_key(key):
        return default
    return Gio.Settings.new(schema).get_boolean(key)


def open_cinnamon_settings(module: str, show_error: Callable[[str], None]) -> None:
    try:
        Gio.Subprocess.new(["cinnamon-settings", module], Gio.SubprocessFlags.NONE)
    except GLib.Error as error:
        show_error(error.message)


def activations() -> list[tuple[str, str]]:
    return [
        ("ctrl-left", _("Press the left Ctrl twice")),
        ("ctrl-right", _("Press the right Ctrl twice")),
        ("shake", _("Shake the mouse")),
        ("shortcut", _("A keyboard shortcut")),
    ]


def highlight_modes() -> list[tuple[str, str]]:
    return [
        # TRANSLATORS: a Mouse Highlighter mode: the screen dimmed around the pointer.
        ("spotlight", _("Spotlight")),
        # TRANSLATORS: a Mouse Highlighter mode: a circle under the pointer at each click.
        ("circle", _("Circle highlight")),
        # TRANSLATORS: a Mouse Highlighter mode: a ring going out from each click.
        ("ripple", _("Ripple")),
    ]


def orientations() -> list[tuple[str, str]]:
    return [
        ("both", _("Vertical and horizontal lines")),
        ("vertical", _("Vertical only")),
        ("horizontal", _("Horizontal only")),
    ]


def to_hex(rgba: Gdk.RGBA) -> str:
    parts = (rgba.red, rgba.green, rgba.blue, rgba.alpha)
    return "#" + "".join(f"{round(part * 255):02x}" for part in parts)


def from_hex(color: str) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    red, green, blue, alpha = (int(color[index : index + 2], 16) for index in (1, 3, 5, 7))
    rgba.red, rgba.green, rgba.blue, rgba.alpha = red / 255, green / 255, blue / 255, alpha / 255
    return rgba


class Notice(SettingsWidget):
    """A line that tells of something outside TuxToys, with a button to where it is set."""

    def __init__(self, text: str, button: str, action: Callable[[], None]) -> None:
        super().__init__()
        self.pack_start(
            Gtk.Image.new_from_icon_name("dialog-information-symbolic", Gtk.IconSize.MENU),
            False,
            False,
            0,
        )
        label = Gtk.Label(label=text, xalign=0, wrap=True, max_width_chars=60)
        self.pack_start(label, True, True, 0)
        go = Gtk.Button(label=button, valign=Gtk.Align.CENTER)
        go.connect("clicked", lambda _button: action())
        self.pack_end(go, False, False, 0)


def color_row(label: str) -> ColorRow:
    row = ColorRow(label)
    row.content_widget.set_use_alpha(True)
    return row


def number_row(label: str, detail: str, limits: tuple[int, int]) -> NumberRow:
    row = NumberRow(label, detail, limits[1])
    row.content_widget.set_range(*limits)
    return row


class MousePart:
    """One tool's part of the page: its switch, a line saying why it cannot be used, and
    its settings, saved through the daemon. A subclass builds the sections and shows the
    settings.
    """

    module_id = ""

    def __init__(
        self, page: SettingsPage, client: Client, show_error: Callable[[str], None]
    ) -> None:
        self._page = page
        self._client = client
        self._show_error = show_error
        self._loading = False
        self._shown: dict[str, object] = {}
        self._shown_enabled: bool | None = None
        self._pending: dict[str, object] = {}
        self._save_timer = 0
        self._live_timer = 0
        self.sections: tuple[Gtk.Widget, ...] = ()

    def top(self, title: str, description: str, switch: str) -> Gtk.Widget:
        """The part's first section, with its switch and the line saying what is wrong."""
        section = self._page.add_section(title, description)
        self.problem = Text("")
        self.problem_revealer = section.add_reveal_row(self.problem)
        self.enabled = Switch(switch)
        self.enabled.content_widget.connect("notify::active", self._on_enabled)
        section.add_row(self.enabled)
        return section

    def refresh(self) -> None:
        info: ModuleInfo | None = None
        problem = ""
        try:
            info = next((i for i in self._client.modules() if i.id == self.module_id), None)
        except NotRunning:
            problem = _("TuxToys is not running.")
        except Refused as error:
            problem = _("TuxToys refused: {reason}").format(reason=error)
        if info is None and not problem:
            problem = _(
                "The TuxToys service running now does not have this tool. Log out and back"
                " in to start the new one."
            )
        if info and info.state == "failed":
            problem = _("Could not be switched on: {error}").format(error=info.error)
        self._shown_enabled = info.state == "on" if info else None
        self._loading = True
        try:
            self.enabled.set_sensitive(info is not None)
            self.enabled.content_widget.set_active(bool(self._shown_enabled))
        finally:
            self._loading = False
        self.problem.content_widget.set_text(problem)
        self.problem_revealer.set_reveal_child(bool(problem))
        settings = None
        with suppress(NotRunning, ModuleOff, Refused):
            settings = self._client.module_settings(self.module_id)
        if settings is not None:
            self.show_settings(settings)
        for section in self.sections:
            section.set_sensitive(self._shown_enabled is True)

    def show_settings(self, settings: object) -> None:
        raise NotImplementedError

    def _on_enabled(self, switch: Gtk.Switch, _spec: object) -> None:
        enabled = switch.get_active()
        if self._loading or self._shown_enabled is None or enabled == self._shown_enabled:
            return
        try:
            self._client.set_module_enabled(self.module_id, enabled)
        except NotRunning:
            pass  # refresh() says so
        except Refused as error:
            self._show_error(_("TuxToys refused: {reason}").format(reason=error))
        self.refresh()

    def _on_flag(self, switch: Gtk.Switch, _spec: object, key: str) -> None:
        self._save({key: switch.get_active()})

    def _on_choice(self, combo: Gtk.ComboBox, key: str) -> None:
        if combo.get_active_id():
            self._save({key: combo.get_active_id()})

    def _on_color(self, button: Gtk.ColorButton, key: str) -> None:
        self._save({key: to_hex(button.get_rgba())})

    def _on_number(self, field: Gtk.SpinButton, key: str) -> None:
        self._save({key: field.get_value_as_int()}, live=True)

    def _on_slider(self, scale: Gtk.Scale, key: str) -> None:
        self._save({key: round(scale.get_value())}, live=True)

    def _save(
        self, changes: Mapping[str, object], *, later: bool = False, live: bool = False
    ) -> None:
        """Saves at once; `later`, once typing has stopped; `live`, at once and then at most
        every LIVE_EVERY_MS while the value keeps changing, so the tool follows a slider or
        the + and - buttons as they move.
        """
        if self._loading:
            return
        changes = {key: value for key, value in changes.items() if self._shown.get(key) != value}
        if not changes:
            return
        self._pending.update(changes)
        if live:
            if not self._live_timer:
                self._save_now()
                self._live_timer = GLib.timeout_add(LIVE_EVERY_MS, self._live_tick)
            return
        if self._save_timer:
            GLib.source_remove(self._save_timer)
            self._save_timer = 0
        if later:
            self._save_timer = GLib.timeout_add(SAVE_AFTER_MS, self._save_now)
        else:
            self._save_now()

    def _live_tick(self) -> bool:
        """What changed since the last send goes now; with nothing, the stretch is over."""
        if self._pending:
            self._save_now()
            return GLib.SOURCE_CONTINUE
        self._live_timer = 0
        return GLib.SOURCE_REMOVE

    def _save_now(self) -> bool:
        self._save_timer = 0
        changes, self._pending = self._pending, {}
        try:
            self._client.set_module_settings(self.module_id, changes)
            self._shown.update(changes)
        except NotRunning:
            pass  # refresh() says so
        except (ModuleOff, Refused) as error:
            self._show_error(_("TuxToys refused: {reason}").format(reason=error))
        self.refresh()
        return GLib.SOURCE_REMOVE

    def _keys_text(self, shortcut: CustomShortcut, default: str, tool: str) -> str:
        """The keys as the Keyboard settings name them, or why there are none."""
        if self._shown_enabled is not True:
            return ""
        try:
            keys = shortcut.current_keys()
        except Exception:  # Cinnamon's settings missing: nothing to show
            return ""
        if keys:
            return keys_label(keys)
        return _(
            "{keys} is in use already. Give {tool} other keys in the Keyboard settings."
        ).format(keys=keys_label(default), tool=tool)


class FindMyMousePart(MousePart):
    module_id = "findmymouse"

    def __init__(
        self,
        page: SettingsPage,
        client: Client,
        show_error: Callable[[str], None],
        shortcut: CustomShortcut,
        flag: Flag,
    ) -> None:
        super().__init__(page, client, show_error)
        self._shortcut = shortcut
        self._flag = flag
        self.first = self.top(
            _("Find My Mouse"),
            _(
                "Shines a spotlight on the pointer. A click or a key puts it away, and so"
                " does a second of stillness once the pointer has moved."
            ),
            _("Use Find My Mouse"),
        )

        self.activation_section = page.add_section(_("Activation"))
        # python3-xapp's ComboBox needs its choices from the start.
        self.activation = ComboBox(_("Activation method"), activations())
        self.activation.content_widget.connect("changed", self._on_choice, "activation")
        self.activation_section.add_row(self.activation)
        self.locate_notice = Notice(
            _(
                "Cinnamon's own pointer locator also answers the left Ctrl: one press shows"
                " where the pointer is."
            ),
            _("Mouse settings"),
            lambda: open_cinnamon_settings("mouse", show_error),
        )
        self.locate_revealer = self.activation_section.add_reveal_row(self.locate_notice)
        self.shake_rows = []
        self.shake_revealers = []
        for key, label, detail, limits in (
            (
                "shake_distance",
                _("Minimum shake distance"),
                _("How far the pointer has to travel to count as a shake. Less is more sensitive."),
                findmymouse.SHAKE_DISTANCE,
            ),
            (
                "shake_interval",
                _("Shake detection interval (ms)"),
                _("How long a stretch of movement is looked at. Shorter catches quicker shakes."),
                findmymouse.SHAKE_INTERVAL,
            ),
            (
                "shake_factor",
                _("Shake sensitivity factor (percent)"),
                _(
                    "How many times the size of the area it moved in the pointer has to"
                    " travel. Less is more sensitive."
                ),
                findmymouse.SHAKE_FACTOR,
            ),
        ):
            row = number_row(label, detail, limits)
            row.content_widget.connect("value-changed", self._on_number, key)
            self.shake_revealers.append(self.activation_section.add_reveal_row(row))
            self.shake_rows.append(row)
        keys = Text("")
        self.keys = keys.content_widget
        self.keys_revealer = self.activation_section.add_reveal_row(keys)
        self.keyboard_revealer = self.activation_section.add_reveal_row(
            Button(_("Open the Keyboard settings"), lambda *_a: open_keyboard_settings(show_error))
        )
        self.skip_fullscreen = Switch(_("Not over a full-screen window"))
        with_detail(self.skip_fullscreen, _("Such as a game, a video or a presentation."))
        self.skip_fullscreen.content_widget.connect(
            "notify::active", self._on_flag, "skip_fullscreen"
        )
        self.activation_section.add_row(self.skip_fullscreen)
        self.skip_gamemode = Switch(_("Not while GameMode runs a game"))
        with_detail(
            self.skip_gamemode,
            _("Feral GameMode, which Steam and Lutris can start for a game, if it is installed."),
        )
        self.skip_gamemode.content_widget.connect("notify::active", self._on_flag, "skip_gamemode")
        self.activation_section.add_row(self.skip_gamemode)

        self.look_section = page.add_section(_("Appearance and behavior"))
        self.background = color_row(_("Background color"))
        self.spotlight = color_row(_("Spotlight color"))
        for key, row in (("background", self.background), ("spotlight", self.spotlight)):
            row.content_widget.connect("color-set", self._on_color, key)
            self.look_section.add_row(row)
        self.radius = number_row(
            _("Spotlight radius (px)"), _("The size of the circle of light."), findmymouse.RADIUS
        )
        self.radius.content_widget.connect("value-changed", self._on_number, "radius")
        self.look_section.add_row(self.radius)
        self.zoom = SliderRow(_("Spotlight initial zoom"), *findmymouse.ZOOM, 1)
        with_detail(self.zoom, _("How many times larger the circle starts, closing in."))
        self.zoom.content_widget.connect("value-changed", self._on_slider, "zoom")
        self.look_section.add_row(self.zoom)
        self.duration = number_row(
            _("Animation duration (ms)"),
            _("How long it takes the spotlight to fade in and close in."),
            findmymouse.DURATION,
        )
        self.duration.content_widget.connect("value-changed", self._on_number, "duration")
        self.look_section.add_row(self.duration)
        self.animations_revealer = self.look_section.add_reveal_row(
            Notice(
                _("Animations are off in Cinnamon's settings, so the spotlight appears at once."),
                _("Effects settings"),
                lambda: open_cinnamon_settings("effects", show_error),
            )
        )

        self.excluded_section = page.add_section(
            _("Excluded applications"),
            _(
                "Find My Mouse does not start over these. One on each line, by the name X11"
                " knows it by (its WM_CLASS), for example firefox."
            ),
        )
        self.excluded = AppsRow()
        self.excluded.content_widget.get_buffer().connect("changed", self._on_excluded)
        self.excluded_section.add_row(self.excluded)
        self.sections = (self.activation_section, self.look_section, self.excluded_section)

    def show_settings(self, settings: object) -> None:
        if not isinstance(settings, Mapping):
            return
        options = findmymouse.Options.read(settings)
        self._shown = dict(options.settings())
        self._loading = True
        try:
            self.activation.content_widget.set_active_id(options.activation)
            for row, value in zip(
                self.shake_rows,
                (options.shake_distance, options.shake_interval, options.shake_factor),
                strict=True,
            ):
                row.content_widget.set_value(value)
            self.skip_fullscreen.content_widget.set_active(options.skip_fullscreen)
            self.skip_gamemode.content_widget.set_active(options.skip_gamemode)
            self.background.content_widget.set_rgba(from_hex(options.background))
            self.spotlight.content_widget.set_rgba(from_hex(options.spotlight))
            self.radius.content_widget.set_value(options.radius)
            self.zoom.content_widget.set_value(options.zoom)
            self.duration.content_widget.set_value(options.duration)
            # Not while it is being typed in: the cursor would jump.
            if (
                not self.excluded.content_widget.has_focus()
                and self.excluded.text != options.excluded
            ):
                self.excluded.text = options.excluded
            self._show_activation(options.activation)
            animations = self._flag(INTERFACE_SCHEMA, "enable-animations", True)
            self.duration.set_sensitive(animations)
            self.animations_revealer.set_reveal_child(not animations)
        finally:
            self._loading = False

    def _show_activation(self, activation: str) -> None:
        for revealer in self.shake_revealers:
            revealer.set_reveal_child(activation == "shake")
        by_shortcut = activation == "shortcut"
        keys = self._keys_text(self._shortcut, findmymouse.SHORTCUT_KEYS, "Find My Mouse")
        self.keys.set_text(keys if by_shortcut else "")
        self.keys_revealer.set_reveal_child(by_shortcut)
        self.keyboard_revealer.set_reveal_child(by_shortcut)
        locator = self._flag(MOUSE_SCHEMA, "locate-pointer", False)
        self.locate_revealer.set_reveal_child(activation == "ctrl-left" and locator)

    def _on_excluded(self, _buffer: Gtk.TextBuffer) -> None:
        self._save({"excluded": self.excluded.text}, later=True)


class HighlighterPart(MousePart):
    module_id = "mousehighlighter"

    def __init__(
        self,
        page: SettingsPage,
        client: Client,
        show_error: Callable[[str], None],
        shortcut: CustomShortcut,
    ) -> None:
        super().__init__(page, client, show_error)
        self._shortcut = shortcut
        self.first = self.top(
            _("Mouse Highlighter"),
            _("Shows your clicks. Its shortcut turns it on and off."),
            _("Use Mouse Highlighter"),
        )

        self.keys_section = page.add_section(
            _("Activation"),
            _("Change its keys in the Keyboard settings, under TuxToys: Mouse Highlighter."),
        )
        self.shortcut = Switch(_("Turn it on and off with a keyboard shortcut"))
        self.shortcut.content_widget.connect("notify::active", self._on_flag, "shortcut")
        self.keys_section.add_row(self.shortcut)
        keys = Text("")
        self.keys = keys.content_widget
        self.keys_section.add_row(keys)
        self.keys_section.add_row(
            Button(_("Open the Keyboard settings"), lambda *_a: open_keyboard_settings(show_error))
        )
        self.auto_activate = Switch(_("On from the start"))
        with_detail(self.auto_activate, _("Shows your clicks from login on, without the shortcut."))
        self.auto_activate.content_widget.connect("notify::active", self._on_flag, "auto_activate")
        self.keys_section.add_row(self.auto_activate)

        self.mode_section = page.add_section(_("Highlight mode"))
        self.mode = ComboBox(_("Highlight mode"), highlight_modes())
        with_detail(self.mode, _("The style of the highlight, and its look below."))
        self.mode.content_widget.connect("changed", self._on_choice, "mode")
        self.mode_section.add_row(self.mode)
        # Each row with the modes it belongs to.
        self.rows: dict[str, tuple[Gtk.Revealer, tuple[str, ...]]] = {}

        def add(key: str, row: SettingsWidget, modes: tuple[str, ...]) -> SettingsWidget:
            self.rows[key] = (self.mode_section.add_reveal_row(row), modes)
            return row

        self.colors = {}
        for key, label, modes in (
            ("primary_color", _("Primary button highlight color"), ("circle", "ripple")),
            ("secondary_color", _("Secondary button highlight color"), ("circle", "ripple")),
            ("always_color", _("Always highlight color"), ("circle",)),
            ("spotlight_color", _("Background color"), ("spotlight",)),
        ):
            row = color_row(label)
            row.content_widget.connect("color-set", self._on_color, key)
            self.colors[key] = add(key, row, modes)
        with_detail(
            self.colors["always_color"],
            _("Under the pointer when no button is held. Fully transparent, it is off."),
        )
        self.numbers = {}
        for key, label, detail, limits, modes in (
            (
                "radius",
                _("Radius (px)"),
                _("The size of the circle or of the spotlight."),
                highlighter.RADIUS,
                ("circle", "spotlight"),
            ),
            (
                "fade_delay",
                _("Fade delay (ms)"),
                _("How long the circle stays after the button is let go of."),
                highlighter.DELAY,
                ("circle",),
            ),
            (
                "fade_duration",
                _("Fade duration (ms)"),
                _("How long it then takes to fade."),
                highlighter.DURATION,
                ("circle",),
            ),
            (
                "ripple_size",
                _("Size (px)"),
                _("How far the ripple goes out."),
                highlighter.SIZE,
                ("ripple",),
            ),
        ):
            row = number_row(label, detail, limits)
            row.content_widget.connect("value-changed", self._on_number, key)
            self.numbers[key] = add(key, row, modes)
        self.intensity = SliderRow(_("Intensity"), *highlighter.INTENSITY, 5)
        self.intensity.content_widget.connect(
            "format-value", lambda _scale, value: f"{value / 100:.2f}"
        )
        self.intensity.content_widget.connect("value-changed", self._on_slider, "intensity")
        add("intensity", self.intensity, ("ripple",))
        row = number_row(
            _("Duration (ms)"), _("How long a ripple takes."), highlighter.RIPPLE_DURATION
        )
        row.content_widget.connect("value-changed", self._on_number, "ripple_duration")
        self.numbers["ripple_duration"] = add("ripple_duration", row, ("ripple",))
        self.follow = Switch(_("Follow the pointer while a button is held"))
        self.follow.content_widget.connect("notify::active", self._on_flag, "follow")
        add("follow", self.follow, ("ripple",))
        self.crosshairs = Switch(_("Crosshairs when the right button is let go of"))
        self.crosshairs.content_widget.connect("notify::active", self._on_flag, "crosshairs")
        add("crosshairs", self.crosshairs, ("ripple",))
        self.sections = (self.keys_section, self.mode_section)

    def show_settings(self, settings: object) -> None:
        if not isinstance(settings, Mapping):
            return
        options = highlighter.Options.read(settings)
        self._shown = dict(options.settings())
        self._loading = True
        try:
            self.shortcut.content_widget.set_active(options.shortcut)
            self.keys.set_text(
                self._keys_text(self._shortcut, highlighter.SHORTCUT_KEYS, "Mouse Highlighter")
                if options.shortcut
                else ""
            )
            self.auto_activate.content_widget.set_active(options.auto_activate)
            self.mode.content_widget.set_active_id(options.mode)
            for key, row in self.colors.items():
                row.content_widget.set_rgba(from_hex(getattr(options, key)))
            for key, row in self.numbers.items():
                row.content_widget.set_value(getattr(options, key))
            self.intensity.content_widget.set_value(options.intensity)
            self.follow.content_widget.set_active(options.follow)
            self.crosshairs.content_widget.set_active(options.crosshairs)
            for revealer, modes in self.rows.values():
                revealer.set_reveal_child(options.mode in modes)
        finally:
            self._loading = False


class CrosshairsPart(MousePart):
    module_id = "crosshairs"

    def __init__(
        self,
        page: SettingsPage,
        client: Client,
        show_error: Callable[[str], None],
        shortcut: CustomShortcut,
        glide_shortcut: CustomShortcut,
    ) -> None:
        super().__init__(page, client, show_error)
        self._shortcut = shortcut
        self._glide_shortcut = glide_shortcut
        self.first = self.top(
            _("Mouse Pointer Crosshairs"),
            _("Draws crosshairs through the pointer. Its shortcut shows and hides them."),
            _("Use Mouse Pointer Crosshairs"),
        )

        self.keys_section = page.add_section(
            _("Activation"),
            _("Change its keys in the Keyboard settings, under TuxToys: Mouse Pointer Crosshairs."),
        )
        self.shortcut = Switch(_("Show and hide them with a keyboard shortcut"))
        self.shortcut.content_widget.connect("notify::active", self._on_flag, "shortcut")
        self.keys_section.add_row(self.shortcut)
        keys = Text("")
        self.keys = keys.content_widget
        self.keys_section.add_row(keys)
        self.keys_section.add_row(
            Button(_("Open the Keyboard settings"), lambda *_a: open_keyboard_settings(show_error))
        )
        self.auto_activate = Switch(_("On from the start"))
        with_detail(self.auto_activate, _("Shows them from login on, without the shortcut."))
        self.auto_activate.content_widget.connect("notify::active", self._on_flag, "auto_activate")
        self.keys_section.add_row(self.auto_activate)

        self.look_section = page.add_section(_("Appearance and behavior"))
        self.color = ColorRow(_("Crosshairs color"))
        self.color.content_widget.connect("color-set", self._on_plain_color, "color")
        self.look_section.add_row(self.color)
        self.opacity = SliderRow(_("Crosshairs opacity (%)"), *crosshairs.OPACITY, 5)
        self.opacity.content_widget.connect("value-changed", self._on_slider, "opacity")
        self.look_section.add_row(self.opacity)
        self.numbers = {}
        for key, label, limits in (
            ("radius", _("Crosshairs center radius (px)"), crosshairs.RADIUS),
            ("thickness", _("Crosshairs thickness (px)"), crosshairs.THICKNESS),
        ):
            row = NumberRow(label, "", limits[1])
            row.content_widget.set_range(*limits)
            row.content_widget.connect("value-changed", self._on_number, key)
            self.look_section.add_row(row)
            self.numbers[key] = row
        self.border_color = ColorRow(_("Crosshairs border color"))
        self.border_color.content_widget.connect("color-set", self._on_plain_color, "border_color")
        self.look_section.add_row(self.border_color)
        row = NumberRow(_("Crosshairs border size (px)"), "", crosshairs.BORDER[1])
        row.content_widget.set_range(*crosshairs.BORDER)
        row.content_widget.connect("value-changed", self._on_number, "border")
        self.look_section.add_row(row)
        self.numbers["border"] = row
        self.orientation = ComboBox(_("Crosshairs orientation"), orientations())
        self.orientation.content_widget.connect("changed", self._on_choice, "orientation")
        self.look_section.add_row(self.orientation)
        self.auto_hide = Switch(_("Hide the crosshairs while the pointer is hidden"))
        self.auto_hide.content_widget.connect("notify::active", self._on_flag, "auto_hide")
        self.look_section.add_row(self.auto_hide)
        self.fixed = Switch(_("Fixed crosshairs length"))
        with_detail(self.fixed, _("Each line as long as set, rather than to the screen's edge."))
        self.fixed.content_widget.connect("notify::active", self._on_flag, "fixed")
        self.look_section.add_row(self.fixed)
        row = NumberRow(_("Crosshairs fixed length (px)"), "", crosshairs.LENGTH[1])
        row.content_widget.set_range(*crosshairs.LENGTH)
        row.content_widget.connect("value-changed", self._on_number, "fixed_length")
        self.fixed_revealer = self.look_section.add_reveal_row(row)
        self.numbers["fixed_length"] = row

        self.glide_section = page.add_section(
            _("Gliding cursor"),
            _(
                "Places the pointer anywhere on the screen and clicks, with the keyboard"
                " alone. Press its shortcut to send a line across the screen, again to slow"
                " it, again to hold it and send a line down, again to slow that, and once more"
                " to click where they cross. Escape stops it."
            ),
        )
        self.glide_shortcut = Switch(_("Glide with a keyboard shortcut"))
        self.glide_shortcut.content_widget.connect(
            "notify::active", self._on_flag, "glide_shortcut"
        )
        self.glide_section.add_row(self.glide_shortcut)
        glide_keys = Text("")
        self.glide_keys = glide_keys.content_widget
        self.glide_section.add_row(glide_keys)
        self.speeds = {}
        for key, label, detail in (
            (
                "glide_speed",
                _("Initial speed"),
                _("How fast the line moves as it starts out."),
            ),
            (
                "glide_slow",
                _("Reduced speed"),
                _("How fast it moves once a second press has slowed it."),
            ),
        ):
            slider = SliderRow(label, *crosshairs.SPEED, 1)
            with_detail(slider, detail)
            slider.content_widget.connect("value-changed", self._on_slider, key)
            self.glide_section.add_row(slider)
            self.speeds[key] = slider
        self.sections = (self.keys_section, self.look_section, self.glide_section)

    def _on_plain_color(self, button: Gtk.ColorButton, key: str) -> None:
        self._save({key: to_hex(button.get_rgba())[:7]})

    def show_settings(self, settings: object) -> None:
        if not isinstance(settings, Mapping):
            return
        options = crosshairs.Options.read(settings)
        self._shown = dict(options.settings())
        self._loading = True
        try:
            self.shortcut.content_widget.set_active(options.shortcut)
            self.keys.set_text(
                self._keys_text(
                    self._shortcut, crosshairs.SHORTCUT_KEYS, "Mouse Pointer Crosshairs"
                )
                if options.shortcut
                else ""
            )
            self.auto_activate.content_widget.set_active(options.auto_activate)
            self.color.content_widget.set_rgba(from_hex(options.color + "ff"))
            self.opacity.content_widget.set_value(options.opacity)
            for key, row in self.numbers.items():
                row.content_widget.set_value(getattr(options, key))
            self.border_color.content_widget.set_rgba(from_hex(options.border_color + "ff"))
            self.orientation.content_widget.set_active_id(options.orientation)
            self.auto_hide.content_widget.set_active(options.auto_hide)
            self.fixed.content_widget.set_active(options.fixed)
            self.fixed_revealer.set_reveal_child(options.fixed)
            self.glide_shortcut.content_widget.set_active(options.glide_shortcut)
            self.glide_keys.set_text(
                self._keys_text(self._glide_shortcut, crosshairs.GLIDE_KEYS, "Gliding cursor")
                if options.glide_shortcut
                else ""
            )
            for key, slider in self.speeds.items():
                slider.content_widget.set_value(getattr(options, key))
        finally:
            self._loading = False


class MouseUtilitiesPage(SettingsPage):
    def __init__(
        self,
        client: Client,
        show_error: Callable[[str], None],
        shortcuts: Mapping[str, CustomShortcut] | None = None,
        flag: Flag = cinnamon_flag,
    ) -> None:
        """The tests hand in the tools' shortcuts and Cinnamon's switches of their own."""
        super().__init__()
        found = dict(shortcuts or {})
        self.findmymouse = FindMyMousePart(
            self,
            client,
            show_error,
            found.get("findmymouse")
            or CustomShortcut(
                findmymouse.SHORTCUT_NAME, findmymouse.SHORTCUT_COMMAND, findmymouse.SHORTCUT_KEYS
            ),
            flag,
        )
        self.highlighter = HighlighterPart(
            self,
            client,
            show_error,
            found.get("mousehighlighter")
            or CustomShortcut(
                highlighter.SHORTCUT_NAME, highlighter.SHORTCUT_COMMAND, highlighter.SHORTCUT_KEYS
            ),
        )
        self.crosshairs = CrosshairsPart(
            self,
            client,
            show_error,
            found.get("crosshairs")
            or CustomShortcut(
                crosshairs.SHORTCUT_NAME, crosshairs.SHORTCUT_COMMAND, crosshairs.SHORTCUT_KEYS
            ),
            found.get("glidingcursor")
            or CustomShortcut(
                crosshairs.GLIDE_NAME, crosshairs.GLIDE_COMMAND, crosshairs.GLIDE_KEYS
            ),
        )
        self.parts: dict[str, MousePart] = {
            part.module_id: part for part in (self.findmymouse, self.highlighter, self.crosshairs)
        }
        self.refresh()

    def refresh(self) -> None:
        for part in self.parts.values():
            part.refresh()

    def show_settings(self, settings: object) -> None:
        """For the window's sake; the parts are told by show_module_settings."""

    def show_module_settings(self, module_id: str, settings: object) -> None:
        part = self.parts.get(module_id)
        if part is not None:
            part.show_settings(settings)

    def scroll_to(self, tool: str) -> None:
        """Brings a tool's part into view, once the page has its size."""
        part = self.parts.get(tool)
        if part is None:
            return

        def scroll() -> bool:
            scroller = self.get_ancestor(Gtk.ScrolledWindow)
            if scroller is not None:
                found = part.first.translate_coordinates(self, 0, 0)
                if found is not None:
                    scroller.get_vadjustment().set_value(max(found[1] - 12, 0))
            return GLib.SOURCE_REMOVE

        GLib.idle_add(scroll)
