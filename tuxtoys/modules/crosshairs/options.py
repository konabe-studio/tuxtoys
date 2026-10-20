"""Mouse Pointer Crosshairs' settings, read and checked without GTK or D-Bus, with PowerToys'
defaults (InclusiveCrosshairs.h, the gliding cursor's in its dllmain.cpp and settings page):
the crosshairs' shortcut and look, and the gliding cursor's shortcut and two speeds.

Colors are "#rrggbb"; the opacity is a percentage of the whole, border and all.
"""

import re
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

ORIENTATIONS = ("both", "vertical", "horizontal")
# PowerToys' Win+Alt+P and Win+Alt+Period.
SHORTCUT_KEYS = "<Alt><Super>p"
SHORTCUT_NAME = "TuxToys: Mouse Pointer Crosshairs"
SHORTCUT_COMMAND = "tuxtoys crosshairs"
GLIDE_KEYS = "<Alt><Super>period"
GLIDE_NAME = "TuxToys: Gliding cursor"
GLIDE_COMMAND = "tuxtoys glidingcursor"
OPACITY = (0, 100)
RADIUS = (0, 500)
THICKNESS = (1, 50)
BORDER = (0, 50)
LENGTH = (1, 10000)
# Pixels the line travels in 200 ms, PowerToys' range.
SPEED = (5, 60)
_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


@dataclass(frozen=True)
class Options:
    shortcut: bool = True
    # Whether the crosshairs show from the start, without the shortcut.
    auto_activate: bool = False
    color: str = "#ff0000"
    opacity: int = 75
    # The gap around the pointer, on each side.
    radius: int = 20
    thickness: int = 5
    border_color: str = "#ffffff"
    border: int = 1
    orientation: str = "both"
    # Whether they go while the pointer is hidden, as in a video.
    auto_hide: bool = False
    # Whether each arm is `fixed_length` long rather than reaching the edge of the monitor.
    fixed: bool = False
    fixed_length: int = 1
    glide_shortcut: bool = True
    glide_speed: int = 25
    glide_slow: int = 5

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
            raise ValueError(f"{key} is a color such as #ff0000, not {value!r}")
        return value.lower()

    return check


def _orientation(value: object) -> str:
    if value not in ORIENTATIONS:
        raise ValueError(f"orientation is one of {', '.join(ORIENTATIONS)}, not {value!r}")
    return str(value)


_CHECKS: dict[str, Callable[[object], object]] = {
    "shortcut": _flag("shortcut"),
    "auto_activate": _flag("auto_activate"),
    "color": _color("color"),
    "opacity": _number("opacity", OPACITY),
    "radius": _number("radius", RADIUS),
    "thickness": _number("thickness", THICKNESS),
    "border_color": _color("border_color"),
    "border": _number("border", BORDER),
    "orientation": _orientation,
    "auto_hide": _flag("auto_hide"),
    "fixed": _flag("fixed"),
    "fixed_length": _number("fixed_length", LENGTH),
    "glide_shortcut": _flag("glide_shortcut"),
    "glide_speed": _number("glide_speed", SPEED),
    "glide_slow": _number("glide_slow", SPEED),
}
