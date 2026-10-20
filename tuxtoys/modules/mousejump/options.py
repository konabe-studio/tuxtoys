"""Mouse Jump's settings, read and checked without GTK or D-Bus, with PowerToys' defaults: its
shortcut, the largest size of the preview, and the preview's style.
"""

from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

from tuxtoys.modules.mousejump.layout import STYLES

# PowerToys' Win+Shift+D.
SHORTCUT_KEYS = "<Shift><Super>d"
SHORTCUT_NAME = "TuxToys: Mouse Jump"
SHORTCUT_COMMAND = "tuxtoys mousejump"
WIDTH = (160, 8000)
HEIGHT = (120, 8000)


@dataclass(frozen=True)
class Options:
    shortcut: bool = True
    # The largest the preview gets; never larger than the monitor the pointer is on.
    width: int = 1600
    height: int = 1200
    style: str = "bezelled"

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


def _flag(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"shortcut is true or false, not {value!r}")
    return value


def _number(key: str, limits: tuple[int, int]) -> Callable[[object], int]:
    least, most = limits

    def check(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not least <= value <= most:
            raise ValueError(f"{key} is a whole number from {least} to {most}, not {value!r}")
        return value

    return check


def _style(value: object) -> str:
    if value not in STYLES:
        raise ValueError(f"style is one of {', '.join(STYLES)}, not {value!r}")
    return str(value)


_CHECKS: dict[str, Callable[[object], object]] = {
    "shortcut": _flag,
    "width": _number("width", WIDTH),
    "height": _number("height", HEIGHT),
    "style": _style,
}
