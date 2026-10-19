"""Shortcut Guide's page, as PowerToys has it: whether it is on, its keyboard shortcut, where
the window opens, and the apps it does not open over; and the user's own lists, to add,
edit and remove. The settings go through the daemon; the shortcut's keys are read from
Cinnamon, where the user may have changed them; the lists are files of their own.
"""

from collections.abc import Callable, Mapping
from contextlib import suppress
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gio, GLib, Gtk  # noqa: E402
from xapp.SettingsWidgets import Button, ComboBox, SettingsWidget, Switch, Text  # noqa: E402

from tuxtoys.api import ModuleOff, NotRunning, Refused  # noqa: E402
from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.core.shortcut import CustomShortcut  # noqa: E402
from tuxtoys.modules.shortcutguide import usersheets  # noqa: E402
from tuxtoys.modules.shortcutguide.module import guide_command  # noqa: E402
from tuxtoys.modules.shortcutguide.options import (  # noqa: E402
    SHORTCUT_COMMAND,
    SHORTCUT_KEYS,
    SHORTCUT_NAME,
    Options,
)
from tuxtoys.modules.shortcutguide.sheets import Sheet  # noqa: E402
from tuxtoys.settings.alwaysontop_page import AppsRow  # noqa: E402
from tuxtoys.settings.awake_page import SAVE_AFTER_MS  # noqa: E402
from tuxtoys.settings.colorpicker_page import keys_label  # noqa: E402
from tuxtoys.settings.lightswitch_page import Client  # noqa: E402
from tuxtoys.settings.screenruler_page import with_detail  # noqa: E402
from tuxtoys.settings.sheet_editor import SheetEditor, themed_image  # noqa: E402
from tuxtoys.settings.simple_page import SimplePage  # noqa: E402
from tuxtoys.settings.widgets import open_keyboard_settings  # noqa: E402


def open_guide(show_error: Callable[[str], None]) -> None:
    try:
        Gio.Subprocess.new(guide_command(), Gio.SubprocessFlags.NONE)
    except GLib.Error as error:
        show_error(error.message)


def position_choices() -> list[tuple[str, str]]:
    return [
        # TRANSLATORS: where Shortcut Guide's window opens, at the left edge of the screen.
        ("left", _("Left")),
        # TRANSLATORS: where Shortcut Guide's window opens, at the right edge of the screen.
        ("right", _("Right")),
        # TRANSLATORS: where Shortcut Guide's window opens, in the middle of the screen.
        ("center", _("Center")),
    ]


def trash(path: Path) -> None:
    Gio.File.new_for_path(str(path)).trash(None)


def open_folder(path: Path, show_error: Callable[[str], None]) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        Gio.AppInfo.launch_default_for_uri(path.as_uri(), None)
    except OSError as error:
        show_error(str(error.strerror or error))
    except GLib.Error as error:
        show_error(error.message)


class SheetRow(SettingsWidget):
    """One of the user's lists: its icon, its name and the windows it is for, and Edit and
    Move to the trash in a menu.
    """

    def __init__(self, page: "ShortcutGuidePage", sheet: Sheet) -> None:
        super().__init__()
        icon = sheet.icons[0] if sheet.icons else ""
        self.pack_start(themed_image(icon, Gtk.IconSize.DND), False, False, 0)
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        texts.pack_start(Gtk.Label(label=sheet.name, xalign=0), False, False, 0)
        windows = Gtk.Label(label=usersheets.classes_text(sheet.wm_classes), xalign=0)
        windows.get_style_context().add_class("dim-label")
        texts.pack_start(windows, False, False, 0)
        self.pack_start(texts, True, True, 0)
        menu = Gtk.Menu()
        for label, action in (
            (_("Edit"), lambda: page.edit_sheet(sheet)),
            (_("Move to the trash"), lambda: page.trash_sheet(sheet)),
        ):
            item = Gtk.MenuItem(label=label)
            item.connect("activate", lambda _item, act=action: act())
            menu.append(item)
        menu.show_all()
        button = Gtk.MenuButton(popup=menu, relief=Gtk.ReliefStyle.NONE, valign=Gtk.Align.CENTER)
        button.set_image(Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.MENU))
        button.set_tooltip_text(_("More"))
        self.pack_end(button, False, False, 0)


class ProblemRow(SettingsWidget):
    """A file in the lists' folder that could not be read, and why, in English as the
    reader says it.
    """

    def __init__(self, problem: usersheets.Problem) -> None:
        super().__init__()
        warning = Gtk.Image.new_from_icon_name("dialog-warning-symbolic", Gtk.IconSize.MENU)
        self.pack_start(warning, False, False, 0)
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title = _("{file} could not be read").format(file=problem.path.name)
        texts.pack_start(Gtk.Label(label=title, xalign=0), False, False, 0)
        reason = Gtk.Label(label=problem.reason, xalign=0, wrap=True, selectable=True)
        reason.get_style_context().add_class("dim-label")
        texts.pack_start(reason, False, False, 0)
        self.pack_start(texts, True, True, 0)


class ShortcutGuidePage(SimplePage):
    def __init__(
        self,
        client: Client,
        show_error: Callable[[str], None],
        opener: Callable[[Callable[[str], None]], None] = open_guide,
        shortcut: CustomShortcut | None = None,
        sheets_folder: Path | None = None,
        to_trash: Callable[[Path], None] = trash,
    ) -> None:
        """The tests hand in an opener, a shortcut, a folder and a trash of their own."""
        self._opener = opener
        self._folder = sheets_folder or usersheets.folder()
        self._trash = to_trash
        self._sheets: list[Sheet] = []
        self._shortcut = shortcut or CustomShortcut(SHORTCUT_NAME, SHORTCUT_COMMAND, SHORTCUT_KEYS)
        self._loading = False
        self._shown: dict[str, object] = {}
        self._pending: dict[str, object] = {}
        self._save_timer = 0
        super().__init__(
            client,
            show_error,
            "shortcutguide",
            _("Shortcut Guide"),
            _("Shows the keyboard shortcuts of Cinnamon and of the active app."),
            _("Use Shortcut Guide"),
            [
                _(
                    "Press the shortcut to see Cinnamon's keyboard shortcuts, TuxToys' and the"
                    " active app's, for Nemo, Xed, the Terminal, Firefox and the apps you add"
                    " below. Search them, and"
                    " click one to pin it to the top. Press the shortcut again, or Escape, to"
                    " put it away."
                ),
            ],
        )
        self.keys_section = self.add_section(
            _("Activation"),
            _("Change its keys in the Keyboard settings, under TuxToys: Shortcut Guide."),
        )
        self.shortcut = Switch(_("Open Shortcut Guide with a keyboard shortcut"))
        self.shortcut.content_widget.connect("notify::active", self._on_shortcut)
        self.keys_section.add_row(self.shortcut)
        keys = Text("")
        self.keys = keys.content_widget
        self.keys_section.add_row(keys)
        self.keys_section.add_row(
            Button(_("Open the Keyboard settings"), lambda *_a: open_keyboard_settings(show_error))
        )
        self.keys_section.add_row(
            Button(_("Open Shortcut Guide now"), lambda *_a: self._opener(show_error))
        )

        self.look_section = self.add_section(_("Appearance and behavior"))
        self.position = ComboBox(_("Window position"), position_choices())
        with_detail(self.position, _("The edge of the screen it opens at, or the middle."))
        self.position.content_widget.connect("changed", self._on_position)
        self.look_section.add_row(self.position)

        self.excluded_section = self.add_section(
            _("Excluded applications"),
            _(
                "Shortcut Guide does not open over these. One on each line, by the name X11"
                " knows it by (its WM_CLASS), for example firefox."
            ),
        )
        self.excluded = AppsRow()
        self.excluded.content_widget.get_buffer().connect("changed", self._on_excluded)
        self.excluded_section.add_row(self.excluded)

        self.sheets_section = self.add_section(
            _("Your own lists"),
            _(
                "The shortcuts of any app, shown while its window is active. For an app"
                " Shortcut Guide knows, they follow its own."
            ),
        )
        self.sheets_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.sheets_section.add_row(self.sheets_list)
        self.sheets_section.add_row(Button(_("Add a list"), lambda *_a: self.edit_sheet(None)))
        self.sheets_section.add_row(
            Button(_("Open the folder"), lambda *_a: open_folder(self._folder, show_error))
        )
        self.sections = (
            self.keys_section,
            self.look_section,
            self.excluded_section,
            self.sheets_section,
        )
        self.refresh()

    def refresh(self) -> None:
        super().refresh()
        if not hasattr(self, "sections"):
            return  # still being built
        settings = None
        with suppress(NotRunning, ModuleOff, Refused):
            settings = self._client.module_settings("shortcutguide")
        if settings is not None:
            self.show_settings(settings)
        self.show_sheets()
        for section in self.sections:
            section.set_sensitive(self._shown_enabled is True)

    def show_sheets(self) -> None:
        """The lists in the folder as they are now, and the files that are not lists."""
        self._sheets, problems = usersheets.load(self._folder)
        for child in self.sheets_list.get_children():
            child.destroy()
        for sheet in self._sheets:
            self.sheets_list.pack_start(SheetRow(self, sheet), False, False, 0)
        for problem in problems:
            self.sheets_list.pack_start(ProblemRow(problem), False, False, 0)
        self.sheets_list.show_all()

    def edit_sheet(self, sheet: Sheet | None) -> None:
        """Opens the editor on a list, or on a new one, and saves what it hands back."""
        parent = self.get_toplevel()
        editor = SheetEditor(parent if isinstance(parent, Gtk.Window) else None, sheet)
        try:
            if editor.run() != Gtk.ResponseType.OK:
                return
            edited = editor.sheet()
        finally:
            editor.destroy()
        self.save_sheet(sheet, edited)

    def save_sheet(self, old: Sheet | None, edited: Sheet) -> None:
        """A list saved in its own file, or a new one in a file named after it."""
        if old is not None:
            path = usersheets.path_of(old, self._folder)
        else:
            taken = []
            with suppress(OSError):
                taken = [entry.name for entry in self._folder.iterdir()]
            path = self._folder / usersheets.file_name(edited.name, taken)
        try:
            usersheets.save(edited, path)
        except OSError as error:
            reason = error.strerror or str(error)
            self._show_error(_("The list could not be saved: {reason}").format(reason=reason))
        self.show_sheets()

    def trash_sheet(self, sheet: Sheet) -> None:
        try:
            self._trash(usersheets.path_of(sheet, self._folder))
        except OSError as error:
            self._show_error(str(error.strerror or error))
        except GLib.Error as error:
            self._show_error(error.message)
        self.show_sheets()

    def show_settings(self, settings: object) -> None:
        if not isinstance(settings, Mapping):
            return
        options = Options.read(settings)
        self._shown = dict(options.settings())
        self._loading = True
        try:
            self.shortcut.content_widget.set_active(options.shortcut)
            self.keys.set_text(self._keys_text(options.shortcut))
            self.position.content_widget.set_active_id(options.position)
            # Not while it is being typed in: the cursor would jump.
            if (
                not self.excluded.content_widget.has_focus()
                and self.excluded.text != options.excluded
            ):
                self.excluded.text = options.excluded
        finally:
            self._loading = False

    def _keys_text(self, wanted: bool) -> str:
        """The keys as the Keyboard settings name them, or why there are none."""
        if not wanted or self._shown_enabled is not True:
            return ""
        try:
            keys = self._shortcut.current_keys()
        except Exception:  # Cinnamon's settings missing: nothing to show
            return ""
        if keys:
            return keys_label(keys)
        return _(
            "{keys} is in use already. Give Shortcut Guide other keys in the Keyboard settings."
        ).format(keys=keys_label(SHORTCUT_KEYS))

    def _on_shortcut(self, switch: Gtk.Switch, _spec: object) -> None:
        self._save({"shortcut": switch.get_active()})

    def _on_position(self, combo: Gtk.ComboBox) -> None:
        if combo.get_active_id():
            self._save({"position": combo.get_active_id()})

    def _on_excluded(self, _buffer: Gtk.TextBuffer) -> None:
        self._save({"excluded": self.excluded.text}, later=True)

    def _save(self, changes: Mapping[str, object], *, later: bool = False) -> None:
        if self._loading:
            return
        changes = {key: value for key, value in changes.items() if self._shown.get(key) != value}
        if not changes:
            return
        self._pending.update(changes)
        if self._save_timer:
            GLib.source_remove(self._save_timer)
            self._save_timer = 0
        if later:
            self._save_timer = GLib.timeout_add(SAVE_AFTER_MS, self._save_now)
        else:
            self._save_now()

    def _save_now(self) -> bool:
        self._save_timer = 0
        changes, self._pending = self._pending, {}
        try:
            self._client.set_module_settings("shortcutguide", changes)
            self._shown.update(changes)
        except NotRunning:
            pass  # refresh() says so
        except (ModuleOff, Refused) as error:
            self._show_error(_("TuxToys refused: {reason}").format(reason=error))
        self.refresh()
        return GLib.SOURCE_REMOVE
