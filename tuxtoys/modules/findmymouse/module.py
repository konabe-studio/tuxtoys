"""Find My Mouse, as the daemon runs it.

The spotlight is drawn, and the keys and the pointer watched, by the mouse tools' helper
(tuxtoys.mouseutilities), since the daemon has no GTK: the module hands it its settings
while it is on, and takes them back when it goes off. With the "shortcut" activation it
keeps a custom shortcut among Cinnamon's, which runs `tuxtoys findmymouse`, as the screen
tools keep theirs.
"""

from collections.abc import Callable, Mapping
from typing import Any, ClassVar

from tuxtoys.api import FINDMYMOUSE_SETTINGS
from tuxtoys.core.i18n import _
from tuxtoys.core.shortcut import CustomShortcut, Keybindings, cinnamon_keybindings
from tuxtoys.modules.base import Context, Module
from tuxtoys.modules.findmymouse.options import (
    SHORTCUT_COMMAND,
    SHORTCUT_KEYS,
    SHORTCUT_NAME,
    Options,
)
from tuxtoys.modules.mouseutilities.helper import MouseHelper, shared


class FindMyMouse(Module):
    id: ClassVar[str] = "findmymouse"
    name: ClassVar[str] = _("Find My Mouse")
    description: ClassVar[str] = _(
        "Shines a spotlight on the pointer when you press the left Ctrl twice."
    )
    settings_types: ClassVar[Mapping[str, str]] = FINDMYMOUSE_SETTINGS

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
        self._options = Options()

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
        self._options = Options.read(settings)
        if self._options.activation == "shortcut":
            self.shortcut.keep()
        else:
            self.shortcut.drop()
        self._helper.set_tool(self.id, self._options.settings())

    def disable(self) -> None:
        self._helper.set_tool(self.id, None)

    def switched_off(self) -> None:
        self.shortcut.drop()
