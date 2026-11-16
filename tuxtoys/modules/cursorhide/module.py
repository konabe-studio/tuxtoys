"""CursorHide, as the daemon runs it.

The pointer is watched, hidden and shown by the mouse tools' helper (tuxtoys.mouseutilities):
the module hands it its settings while it is on. It has no shortcut: switched on, it works.
"""

from collections.abc import Mapping
from typing import Any, ClassVar

from tuxtoys.api import CURSORHIDE_SETTINGS
from tuxtoys.core.i18n import _
from tuxtoys.modules.base import Context, Module
from tuxtoys.modules.cursorhide.options import Options
from tuxtoys.modules.mouseutilities.helper import MouseHelper, shared


class CursorHide(Module):
    id: ClassVar[str] = "cursorhide"
    name: ClassVar[str] = _("CursorHide")
    description: ClassVar[str] = _("Hides the pointer while you type, or once it rests.")
    settings_types: ClassVar[Mapping[str, str]] = CURSORHIDE_SETTINGS

    def __init__(self, helper: MouseHelper | None = None) -> None:
        """The daemon uses the shared helper; the tests hand in their own."""
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
        self._helper.set_tool(self.id, Options.read(settings).settings())

    def disable(self) -> None:
        self._helper.set_tool(self.id, None)
