"""CursorWrap's settings, read and checked without GTK or D-Bus, with PowerToys' defaults: its
shortcut, whether it starts on, and when it wraps.
"""

from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

MODES = ("both", "vertical", "horizontal")
ACTIVATIONS = ("always", "ctrl", "shift")
# PowerToys' Win+Alt+U.
SHORTCUT_KEYS = "<Alt><Super>u"
SHORTCUT_NAME = "TuxToys: CursorWrap"
SHORTCUT_COMMAND = "tuxtoys cursorwrap"


@dataclass(frozen=True)
class Options:
    shortcut: bool = True
    # Whether it wraps from the start, without the shortcut.
    auto_activate: bool = False
    # Whether it leaves the pointer alone while the left button is held, as in a drag.
    not_while_dragging: bool = True
    mode: str = "both"
    # Always, or only while Ctrl or Shift is held.
    activation: str = "always"
    not_with_one_monitor: bool = False

    @classmethod
    def read(cls, settings: Mapping[str, Any]) -> "Options":
        """From the tool's section of the config; a value of the wrong kind gives its
        default, so a config edited by hand cannot keep the tool from working.
        """
        options = cls()
        for key in _CHECKS:
            if key in settings:
                with suppress(ValueError, TypeError):
                    options = options.update({key: settings[key]})
        return options

    def update(self, changes: Mapping[str, Any]) -> "Options":
        """These settings with `changes` made, all or none: ValueError for an unknown key
        or a value its key does not take.
        """
        fields = {}
        for key, value in changes.items():
            if key not in _CHECKS:
                raise ValueError(f"unknown setting: {key!r}")
            fields[key] = _CHECKS[key](value)
        return replace(self, **fields)

    def settings(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in _CHECKS}


def _flag(key: str) -> Callable[[object], bool]:
    def check(value: object) -> bool:
        if not isinstance(value, bool):
            raise ValueError(f"{key} is true or false, not {value!r}")
        return value

    return check


def _one_of(key: str, choices: tuple[str, ...]) -> Callable[[object], str]:
    def check(value: object) -> str:
        if value not in choices:
            raise ValueError(f"{key} is one of {', '.join(choices)}, not {value!r}")
        return str(value)

    return check


_CHECKS: dict[str, Callable[[object], object]] = {
    "shortcut": _flag("shortcut"),
    "auto_activate": _flag("auto_activate"),
    "not_while_dragging": _flag("not_while_dragging"),
    "mode": _one_of("mode", MODES),
    "activation": _one_of("activation", ACTIVATIONS),
    "not_with_one_monitor": _flag("not_with_one_monitor"),
}
