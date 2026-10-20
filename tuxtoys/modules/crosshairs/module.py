"""Mouse Pointer Crosshairs, as the daemon runs it.

The crosshairs are drawn, and the gliding cursor moved, by the mouse tools' helper
(tuxtoys.mouseutilities): the module hands it its settings while it is on. It keeps two
custom shortcuts among Cinnamon's, PowerToys' Super+Alt+P running `tuxtoys crosshairs` and
Super+Alt+Period running `tuxtoys glidingcursor`, each while its own setting is on.
"""

from collections.abc import Callable, Mapping
from typing import Any, ClassVar

from tuxtoys.api import CROSSHAIRS_SETTINGS
from tuxtoys.core.i18n import _
from tuxtoys.core.shortcut import CustomShortcut, Keybindings, cinnamon_keybindings
from tuxtoys.modules.base import Context, Module
from tuxtoys.modules.crosshairs.options import (
    GLIDE_COMMAND,
    GLIDE_KEYS,
    GLIDE_NAME,
    SHORTCUT_COMMAND,
    SHORTCUT_KEYS,
    SHORTCUT_NAME,
    Options,
)
from tuxtoys.modules.mouseutilities.helper import MouseHelper, shared


class Crosshairs(Module):
    id: ClassVar[str] = "crosshairs"
    name: ClassVar[str] = _("Mouse Pointer Crosshairs")
    description: ClassVar[str] = _(
        "Draws crosshairs through the pointer with Super+Alt+P, and places it with the keyboard."
    )
    settings_types: ClassVar[Mapping[str, str]] = CROSSHAIRS_SETTINGS

    def __init__(
        self,
        make_keybindings: Callable[[], Keybindings] = cinnamon_keybindings,
        helper: MouseHelper | None = None,
    ) -> None:
        """The daemon uses the defaults; the tests hand in stand-ins for both."""
        self.shortcut = CustomShortcut(
            SHORTCUT_NAME, SHORTCUT_COMMAND, SHORTCUT_KEYS, make_keybindings
        )
        self.glide_shortcut = CustomShortcut(
            GLIDE_NAME, GLIDE_COMMAND, GLIDE_KEYS, make_keybindings
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
        for shortcut, wanted in (
            (self.shortcut, options.shortcut),
            (self.glide_shortcut, options.glide_shortcut),
        ):
            if wanted:
                shortcut.keep()
            else:
                shortcut.drop()
        self._helper.set_tool(self.id, options.settings())

    def disable(self) -> None:
        self._helper.set_tool(self.id, None)

    def switched_off(self) -> None:
        self.shortcut.drop()
        self.glide_shortcut.drop()
