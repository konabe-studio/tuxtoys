"""The editor of one of the user's own Shortcut Guide lists: its name, the windows it is for,
picked from the open ones or typed, and its groups of shortcuts in a tree, each shortcut's
keys recorded by pressing them, as Cinnamon's Keyboard settings record them (Escape
cancels, Backspace clears).
"""

from collections.abc import Callable, Sequence
from contextlib import suppress

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from tuxtoys.core.i18n import _  # noqa: E402
from tuxtoys.modules.shortcutguide import usersheets  # noqa: E402
from tuxtoys.modules.shortcutguide.sheets import Group, Item, Sheet, Text  # noqa: E402

# The tree's columns.
LABEL, KEYS, IS_GROUP, ID, MORE = range(5)


def app_for(wm_class: str) -> Gio.DesktopAppInfo | None:
    """The installed app whose windows have this class: the one whose menu entry says so,
    else the best match a search of the menu entries finds.
    """
    wanted = wm_class.lower()
    for app in Gio.AppInfo.get_all():
        if (
            isinstance(app, Gio.DesktopAppInfo)
            and (app.get_startup_wm_class() or "").lower() == wanted
        ):
            return app
    with suppress(TypeError):
        for ranked in Gio.DesktopAppInfo.search(wanted):
            for app_id in ranked:
                app = Gio.DesktopAppInfo.new(app_id)
                if app is not None:
                    return app
    return None


def icon_name(app: Gio.AppInfo | None) -> str:
    icon = app.get_icon() if app is not None else None
    if isinstance(icon, Gio.ThemedIcon) and icon.get_names():
        return icon.get_names()[0]
    return ""


def open_windows() -> list[tuple[str, str, str]]:
    """The open windows, as (class, name, icon), each app once."""
    classes: list[str] = []
    with suppress(ImportError, ValueError):
        from tuxtoys.platform.x11 import open_window_classes

        classes = open_window_classes()
    apps = {wm_class.lower(): app_for(wm_class) for wm_class in classes}
    named = [
        (wm_class, apps[wm_class.lower()].get_name() if apps[wm_class.lower()] else "")
        for wm_class in classes
    ]
    return [
        (wm_class, name, icon_name(apps.get(wm_class)))
        for wm_class, name in usersheets.window_choices(named)
    ]


def themed_image(icon: str, size: Gtk.IconSize) -> Gtk.Image:
    theme = Gtk.IconTheme.get_default()
    name = icon if icon and theme.has_icon(icon) else usersheets.FALLBACK_ICON
    return Gtk.Image.new_from_icon_name(name, size)


class SheetEditor(Gtk.Dialog):
    def __init__(
        self,
        parent: Gtk.Window | None,
        sheet: Sheet | None,
        windows: Callable[[], Sequence[tuple[str, str, str]]] = open_windows,
    ) -> None:
        """A new list when `sheet` is None. The tests hand in windows of their own."""
        super().__init__(
            title=_("Shortcut list"), transient_for=parent, modal=True, destroy_with_parent=True
        )
        self.set_default_size(560, 560)
        self._windows = windows
        self._sheet_id = sheet.id if sheet is not None else ""
        self._icon = sheet.icons[0] if sheet is not None and sheet.icons else ""
        if self._icon == usersheets.FALLBACK_ICON:
            self._icon = ""
        self.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        self.ok = self.add_button(_("Save"), Gtk.ResponseType.OK)
        self.ok.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)

        grid = Gtk.Grid(column_spacing=12, row_spacing=8, margin=18)
        grid.attach(Gtk.Label(label=_("Name"), xalign=0), 0, 0, 1, 1)
        name_box = Gtk.Box(spacing=8)
        self.image = themed_image(self._icon, Gtk.IconSize.LARGE_TOOLBAR)
        name_box.pack_start(self.image, False, False, 0)
        self.name = Gtk.Entry(text=sheet.name if sheet is not None else "", hexpand=True)
        self.name.set_activates_default(True)
        name_box.pack_start(self.name, True, True, 0)
        grid.attach(name_box, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Windows"), xalign=0), 0, 1, 1, 1)
        window_box = Gtk.Box(spacing=0)
        window_box.get_style_context().add_class("linked")
        self.classes = Gtk.Entry(
            text=usersheets.classes_text(sheet.wm_classes) if sheet is not None else "",
            hexpand=True,
        )
        self.classes.set_placeholder_text(_("For example gimp"))
        window_box.pack_start(self.classes, True, True, 0)
        self.pick = Gtk.Button()
        self.pick.set_image(Gtk.Image.new_from_icon_name("pan-down-symbolic", Gtk.IconSize.MENU))
        self.pick.set_tooltip_text(_("Pick an open window"))
        self.pick.connect("clicked", self._on_pick)
        window_box.pack_start(self.pick, False, False, 0)
        grid.attach(window_box, 1, 1, 1, 1)
        hint = Gtk.Label(
            label=_(
                "The windows it is shown for, by the name X11 knows them by (WM_CLASS). Pick"
                " one of the open windows, or type it; separate more than one with commas."
            ),
            xalign=0,
            wrap=True,
            max_width_chars=60,
        )
        hint.get_style_context().add_class("dim-label")
        grid.attach(hint, 1, 2, 1, 1)

        self.store = Gtk.TreeStore(str, str, bool, str, str)
        self.tree = Gtk.TreeView(model=self.store, headers_visible=True, reorderable=False)
        self.tree.set_enable_search(False)
        label_cell = Gtk.CellRendererText(editable=True)
        label_cell.connect("edited", self._on_label_edited)
        label_column = Gtk.TreeViewColumn(_("Shortcut"), label_cell, text=LABEL)
        label_column.set_expand(True)
        label_column.set_cell_data_func(label_cell, self._label_data)
        self.tree.append_column(label_column)
        self.label_column = label_column
        keys_cell = Gtk.CellRendererAccel(editable=True, accel_mode=Gtk.CellRendererAccelMode.OTHER)
        keys_cell.connect("accel-edited", self._on_keys_edited)
        keys_cell.connect("accel-cleared", self._on_keys_cleared)
        keys_column = Gtk.TreeViewColumn(_("Keys"), keys_cell)
        keys_column.set_cell_data_func(keys_cell, self._keys_data)
        self.tree.append_column(keys_column)
        self.tree.get_selection().connect("changed", lambda _selection: self._update_buttons())
        scroller = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN, vexpand=True)
        scroller.set_size_request(-1, 240)
        scroller.add(self.tree)

        toolbar = Gtk.Toolbar(
            icon_size=Gtk.IconSize.MENU, toolbar_style=Gtk.ToolbarStyle.BOTH_HORIZ
        )
        toolbar.get_style_context().add_class("inline-toolbar")
        self.add_group_button = self._tool(toolbar, "folder-new-symbolic", _("Add a group"), True)
        self.add_group_button.connect("clicked", lambda _b: self.add_group())
        self.add_item_button = self._tool(toolbar, "list-add-symbolic", _("Add a shortcut"), True)
        self.add_item_button.connect("clicked", lambda _b: self.add_item())
        self.remove_button = self._tool(toolbar, "list-remove-symbolic", _("Remove"), False)
        self.remove_button.connect("clicked", lambda _b: self.remove_selected())
        self.up_button = self._tool(toolbar, "go-up-symbolic", _("Move up"), False)
        self.up_button.connect("clicked", lambda _b: self.move_selected(-1))
        self.down_button = self._tool(toolbar, "go-down-symbolic", _("Move down"), False)
        self.down_button.connect("clicked", lambda _b: self.move_selected(1))
        shortcuts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        shortcuts.pack_start(scroller, True, True, 0)
        shortcuts.pack_start(toolbar, False, False, 0)
        grid.attach(shortcuts, 0, 3, 2, 1)

        self.problem = Gtk.Label(xalign=0, wrap=True)
        self.problem.get_style_context().add_class("dim-label")
        grid.attach(self.problem, 0, 4, 2, 1)

        if sheet is not None:
            self._fill(sheet)
        self.tree.expand_all()
        for field in (self.name, self.classes):
            field.connect("changed", lambda _field: self.check())
        self.get_content_area().pack_start(grid, True, True, 0)
        self.get_content_area().show_all()
        self._update_buttons()
        self.check()

    @staticmethod
    def _tool(toolbar: Gtk.Toolbar, icon: str, label: str, important: bool) -> Gtk.ToolButton:
        button = Gtk.ToolButton(icon_name=icon, label=label)
        button.set_tooltip_text(label)
        button.set_is_important(important)
        toolbar.insert(button, -1)
        return button

    def _fill(self, sheet: Sheet) -> None:
        for group in sheet.groups:
            parent = self.store.append(None, [group.title.msgid, "", True, "", ""])
            for item in group.items:
                first, *more = item.keys or ("",)
                self.store.append(
                    parent, [item.label.msgid, first, False, item.id, "\n".join(more)]
                )

    def sheet(self) -> Sheet:
        """The list as it is in the editor."""
        groups = []
        for group_iter in self._children(None):
            items = []
            for item_iter in self._children(group_iter):
                row = self.store[item_iter]
                keys = tuple(keys for keys in (row[KEYS], *row[MORE].split("\n")) if keys)
                items.append(Item(row[ID], Text(row[LABEL], own=True), keys))
            title = self.store[group_iter][LABEL]
            groups.append(Group(Text(title, own=True), tuple(items)))
        icons = (
            (self._icon, usersheets.FALLBACK_ICON) if self._icon else (usersheets.FALLBACK_ICON,)
        )
        return Sheet(
            self._sheet_id,
            self.name.get_text().strip(),
            icons,
            tuple(groups),
            usersheets.parse_classes(self.classes.get_text()),
        )

    def _children(self, parent: Gtk.TreeIter | None) -> list[Gtk.TreeIter]:
        """The shortcuts in a group, or the groups for None, walked by their iters."""
        found = []
        child = self.store.iter_children(parent)
        while child is not None:
            found.append(child)
            child = self.store.iter_next(child)
        return found

    def problem_text(self) -> str:
        """Why the list cannot be saved yet, or ""."""
        if not self.name.get_text().strip():
            return _("Give the list a name.")
        if not usersheets.parse_classes(self.classes.get_text()):
            return _("Name the windows it is for.")
        for group_iter in self._children(None):
            items = (self.store[item_iter] for item_iter in self._children(group_iter))
            if any(not row[KEYS] and not row[MORE] for row in items):
                return _("Press the keys of every shortcut: click its Keys cell first.")
        return ""

    def check(self) -> None:
        problem = self.problem_text()
        self.problem.set_text(problem)
        self.ok.set_sensitive(not problem)

    # The tree.

    def _label_data(
        self,
        _column: Gtk.TreeViewColumn,
        cell: Gtk.CellRendererText,
        model: Gtk.TreeModel,
        tree_iter: Gtk.TreeIter,
        _data: object = None,
    ) -> None:
        cell.set_property("weight", 700 if model[tree_iter][IS_GROUP] else 400)

    def _keys_data(
        self,
        _column: Gtk.TreeViewColumn,
        cell: Gtk.CellRendererAccel,
        model: Gtk.TreeModel,
        tree_iter: Gtk.TreeIter,
        _data: object = None,
    ) -> None:
        row = model[tree_iter]
        cell.set_property("visible", not row[IS_GROUP])
        key, mods = Gtk.accelerator_parse(row[KEYS]) if row[KEYS] else (0, 0)
        cell.set_property("accel-key", key)
        cell.set_property("accel-mods", mods)
        if not key:
            # TRANSLATORS: in the editor of a Shortcut Guide list, a shortcut whose keys
            # are not set yet; a click on it records them.
            cell.set_property("text", _("Not set"))

    def _on_label_edited(self, _cell: Gtk.CellRendererText, path: str, text: str) -> None:
        if text.strip():
            self.store[path][LABEL] = text.strip()
        self.check()

    def _on_keys_edited(
        self, _cell: Gtk.CellRendererAccel, path: str, key: int, mods: int, _code: int
    ) -> None:
        self.store[path][KEYS] = Gtk.accelerator_name(
            key, Gtk.accelerator_get_default_mod_mask() & mods
        )
        self.check()

    def _on_keys_cleared(self, _cell: Gtk.CellRendererAccel, path: str) -> None:
        self.store[path][KEYS] = ""
        self.store[path][MORE] = ""
        self.check()

    def _selected(self) -> Gtk.TreeIter | None:
        _model, tree_iter = self.tree.get_selection().get_selected()
        return tree_iter

    def _update_buttons(self) -> None:
        tree_iter = self._selected()
        self.remove_button.set_sensitive(tree_iter is not None)
        self.up_button.set_sensitive(
            tree_iter is not None and self.store.iter_previous(tree_iter) is not None
        )
        self.down_button.set_sensitive(
            tree_iter is not None and self.store.iter_next(tree_iter) is not None
        )

    def _edit(self, tree_iter: Gtk.TreeIter) -> None:
        path = self.store.get_path(tree_iter)
        self.tree.expand_to_path(path)
        self.tree.set_cursor(path, self.label_column, True)

    def add_group(self) -> None:
        # TRANSLATORS: the name a new group of shortcuts gets in the list editor, which
        # the user then types over.
        tree_iter = self.store.append(None, [_("New group"), "", True, "", ""])
        self._edit(tree_iter)
        self.check()

    def add_item(self) -> None:
        """A shortcut in the selected group, or the selected shortcut's, or the last one."""
        parent = self._selected()
        if parent is not None and not self.store[parent][IS_GROUP]:
            parent = self.store.iter_parent(parent)
        if parent is None:
            count = self.store.iter_n_children(None)
            parent = self.store.iter_nth_child(None, count - 1) if count else None
        if parent is None:
            parent = self.store.append(None, [_("New group"), "", True, "", ""])
        taken = [
            self.store[item_iter][ID]
            for group_iter in self._children(None)
            for item_iter in self._children(group_iter)
        ]
        # TRANSLATORS: the name a new shortcut gets in the list editor, which the user
        # then types over.
        values = [_("New shortcut"), "", False, usersheets.next_id(taken), ""]
        self._edit(self.store.append(parent, values))
        self.check()

    def remove_selected(self) -> None:
        tree_iter = self._selected()
        if tree_iter is not None:
            self.store.remove(tree_iter)
        self._update_buttons()
        self.check()

    def move_selected(self, step: int) -> None:
        tree_iter = self._selected()
        if tree_iter is None:
            return
        other = self.store.iter_previous(tree_iter) if step < 0 else self.store.iter_next(tree_iter)
        if other is not None:
            self.store.swap(tree_iter, other)
        self._update_buttons()

    # The open windows.

    def _on_pick(self, button: Gtk.Button) -> None:
        """A menu of the open windows, made as it opens, so it has the ones open now."""
        menu = Gtk.Menu()
        choices = self._windows()
        for wm_class, name, icon in choices:
            item = Gtk.MenuItem()
            box = Gtk.Box(spacing=8)
            box.pack_start(themed_image(icon, Gtk.IconSize.MENU), False, False, 0)
            box.pack_start(Gtk.Label(label=name, xalign=0), True, True, 0)
            shown_class = Gtk.Label(label=wm_class, xalign=1)
            shown_class.get_style_context().add_class("dim-label")
            box.pack_start(shown_class, False, False, 0)
            item.add(box)
            item.connect("activate", lambda _item, c=(wm_class, name, icon): self.pick_window(*c))
            menu.append(item)
        if not choices:
            empty = Gtk.MenuItem(label=_("No open windows found"), sensitive=False)
            menu.append(empty)
        menu.show_all()
        menu.attach_to_widget(button, None)
        menu.connect("deactivate", lambda m: GLib.idle_add(m.destroy))
        menu.popup_at_widget(button, Gdk.Gravity.SOUTH_EAST, Gdk.Gravity.NORTH_EAST, None)

    def pick_window(self, wm_class: str, name: str, icon: str) -> None:
        """A window picked: its class, and its name and icon unless the list has them."""
        self.classes.set_text(wm_class)
        if not self.name.get_text().strip():
            self.name.set_text(name)
        if icon:
            self._icon = icon
            self.image.set_from_icon_name(icon, Gtk.IconSize.LARGE_TOOLBAR)
        self.check()
