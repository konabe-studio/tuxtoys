"""CursorWrap, as the daemon runs it.

The pointer is watched and moved by the mouse tools' helper (tuxtoys.mouseutilities): the
module hands it its settings while it is on. Its shortcut, Super+Alt+U as in PowerToys, is a
custom shortcut among Cinnamon's running `tuxtoys cursorwrap`, which turns the wrapping on
and off.
"""

from collections.abc import Callable, Mapping
from typing import Any, ClassVar

from tuxtoys.api import CURSORWRAP_SETTINGS
from tuxtoys.core.i18n import _
from tuxtoys.core.shortcut import CustomShortcut, Keybindings, cinnamon_keybindings
from tuxtoys.modules.base import Context, Module
from tuxtoys.modules.cursorwrap.options import (
    SHORTCUT_COMMAND,
    SHORTCUT_KEYS,
    SHORTCUT_NAME,
    Options,
)
from tuxtoys.modules.mouseutilities.helper import MouseHelper, shared


class CursorWrap(Module):
    id: ClassVar[str] = "cursorwrap"
    name: ClassVar[str] = _("CursorWrap")
    description: ClassVar[str] = _(
        "Takes the pointer out at one edge of the screens and back in at the other."
    )
    settings_types: ClassVar[Mapping[str, str]] = CURSORWRAP_SETTINGS

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
