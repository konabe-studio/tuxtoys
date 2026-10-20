"""Mouse Highlighter's settings, read and checked without GTK or D-Bus, with PowerToys'
defaults (MouseHighlighter.h and its settings page): the shortcut that turns it on and off,
whether it starts on, the mode, and each mode's look.

Colors are "#rrggbbaa", the last two digits their opacity, as PowerToys keeps them: the
buttons' 166 of 255. A color with no opacity at all switches that part off, as in PowerToys.
The primary and secondary buttons' colors serve both the circle and the ripple.
"""

import re
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

MODES = ("spotlight", "circle", "ripple")
# PowerToys' Win+Shift+H.
SHORTCUT_KEYS = "<Shift><Super>h"
SHORTCUT_NAME = "TuxToys: Mouse Highlighter"
SHORTCUT_COMMAND = "tuxtoys mousehighlighter"
RADIUS = (5, 500)
DELAY = (0, 5000)
DURATION = (0, 5000)
SIZE = (10, 500)
# Intensity in hundredths, PowerToys' 0.15 to 1.35.
INTENSITY = (15, 135)
RIPPLE_DURATION = (60, 2000)
_COLOR = re.compile(r"#[0-9a-fA-F]{8}")


@dataclass(frozen=True)
class Options:
    # Whether it keeps its shortcut among Cinnamon's.
    shortcut: bool = True
    # Whether it is highlighting from the start, without the shortcut.
    auto_activate: bool = False
    mode: str = "ripple"
    primary_color: str = "#bfff00a6"
    secondary_color: str = "#00bfffa6"
    # The circle always under the pointer in the circle mode; off by default, as in
    # PowerToys, whose own is transparent.
    always_color: str = "#ff000000"
    # The screen around the spotlight in the spotlight mode.
    spotlight_color: str = "#00000080"
    radius: int = 30
    # Milliseconds a circle stays after the button is let go, then fades for.
    fade_delay: int = 400
    fade_duration: int = 400
    ripple_size: int = 60
    intensity: int = 70
    ripple_duration: int = 480
    # Whether a held button's ripple follows the pointer.
    follow: bool = True
    # Whether letting go of the right button sends crosshairs out of the ripple.
    crosshairs: bool = True

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


def _number(key: str, limits: tuple[int, int]) -> Callable[[object], int]:
    least, most = limits

    def check(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not least <= value <= most:
            raise ValueError(f"{key} is a whole number from {least} to {most}, not {value!r}")
        return value

    return check


def _color(key: str) -> Callable[[object], str]:
    def check(value: object) -> str:
        if not isinstance(value, str) or not _COLOR.fullmatch(value):
            raise ValueError(f"{key} is a color such as #bfff00a6, not {value!r}")
        return value.lower()

    return check


def _mode(value: object) -> str:
    if value not in MODES:
        raise ValueError(f"mode is one of {', '.join(MODES)}, not {value!r}")
    return str(value)


_CHECKS: dict[str, Callable[[object], object]] = {
    "shortcut": _flag("shortcut"),
    "auto_activate": _flag("auto_activate"),
    "mode": _mode,
    "primary_color": _color("primary_color"),
    "secondary_color": _color("secondary_color"),
    "always_color": _color("always_color"),
    "spotlight_color": _color("spotlight_color"),
    "radius": _number("radius", RADIUS),
    "fade_delay": _number("fade_delay", DELAY),
    "fade_duration": _number("fade_duration", DURATION),
    "ripple_size": _number("ripple_size", SIZE),
    "intensity": _number("intensity", INTENSITY),
    "ripple_duration": _number("ripple_duration", RIPPLE_DURATION),
    "follow": _flag("follow"),
    "crosshairs": _flag("crosshairs"),
}
