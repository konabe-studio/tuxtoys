"""Mouse Highlighter, as the daemon runs it.

The clicks are watched and drawn by the mouse tools' helper (tuxtoys.mouseutilities): the
module hands it its settings while it is on. Its shortcut, Super+Shift+H as in PowerToys,
is a custom shortcut among Cinnamon's running `tuxtoys mousehighlighter`, which turns the
highlighting on and off.
"""

from collections.abc import Callable, Mapping
from typing import Any, ClassVar

from tuxtoys.api import MOUSEHIGHLIGHTER_SETTINGS
from tuxtoys.core.i18n import _
from tuxtoys.core.shortcut import CustomShortcut, Keybindings, cinnamon_keybindings
from tuxtoys.modules.base import Context, Module
from tuxtoys.modules.mousehighlighter.options import (
    SHORTCUT_COMMAND,
    SHORTCUT_KEYS,
    SHORTCUT_NAME,
    Options,
)
from tuxtoys.modules.mouseutilities.helper import MouseHelper, shared


class MouseHighlighter(Module):
    id: ClassVar[str] = "mousehighlighter"
    name: ClassVar[str] = _("Mouse Highlighter")
    description: ClassVar[str] = _("Shows your clicks on the screen, after Super+Shift+H.")
    settings_types: ClassVar[Mapping[str, str]] = MOUSEHIGHLIGHTER_SETTINGS

    def __init__(
        self,
        make_keybindings: Callable[[], Keybindings] = cinnamon_keybindings,
        helper: MouseHelper | None = None,
    ) -> None:
        """The daemon uses the defaults; the tests hand in stand-ins for both."""
        self.shortcut = CustomShortcut(
            SHORTCUT_NAME, SHORTCUT_COMMAND, SHORTCUT_KEYS, make_keybindings
        )
        self._helper = helper or shared()

    @classmethod
    def read_settings(cls, section: Mapping[str, Any]) -> dict[str, Any]:
        return Options.read(section).settings()

    @classmethod
    def check_settings(
        cls, settings: Mapping[str, Any], changes: Mapping[str, Any]
    ) -> dict[str, Any]:
        return Options.read(settings).update(changes).settings()

    def enable(self, context: Context) -> None:
        self.apply_settings(context.settings)

    def apply_settings(self, settings: Mapping[str, Any]) -> None:
        options = Options.read(settings)
        if options.shortcut:
            self.shortcut.keep()
        else:
            self.shortcut.drop()
        self._helper.set_tool(self.id, options.settings())

    def disable(self) -> None:
        self._helper.set_tool(self.id, None)

    def switched_off(self) -> None:
        self.shortcut.drop()
