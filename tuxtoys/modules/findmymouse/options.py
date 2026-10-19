"""Find My Mouse's settings, read and checked without GTK or D-Bus, with PowerToys' defaults
(FindMyMouse.h): how it starts, the shake it watches for, when it holds back, and how the
spotlight looks.

Colors are "#rrggbbaa", the last two digits their opacity: PowerToys keeps the backdrop's
opacity in its color the same way, 128 of 255 by default.
"""

import re
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

ACTIVATIONS = ("ctrl-left", "ctrl-right", "shake", "shortcut")
# The custom shortcut for the "shortcut" activation. PowerToys leaves it to the user; F
# for find, with Super and Shift as the other mouse tools have theirs.
SHORTCUT_KEYS = "<Shift><Super>f"
SHORTCUT_NAME = "TuxToys: Find My Mouse"
SHORTCUT_COMMAND = "tuxtoys findmymouse"
# The ranges the page offers, as PowerToys' settings do.
SHAKE_DISTANCE = (100, 10000)
SHAKE_INTERVAL = (100, 10000)
SHAKE_FACTOR = (100, 10000)
RADIUS = (5, 500)
ZOOM = (1, 40)
DURATION = (0, 5000)
_COLOR = re.compile(r"#[0-9a-fA-F]{8}")
# An application as X11 names it, its WM_CLASS: letters, digits and . _ -
_APP = re.compile(r"[\w.-]+")


@dataclass(frozen=True)
class Options:
    activation: str = "ctrl-left"
    shake_distance: int = 1000
    # Milliseconds.
    shake_interval: int = 1000
    # Percent of the diagonal of the box the pointer's path fits in.
    shake_factor: int = 400
    # PowerToys' "do not activate when Game Mode is on", as Linux has it: over a full-screen
    # window, and while Feral GameMode runs a game.
    skip_fullscreen: bool = True
    skip_gamemode: bool = True
    background: str = "#00000080"
    spotlight: str = "#ffffff80"
    radius: int = 100
    # How many times the radius the spotlight starts at, closing in to it.
    zoom: int = 9
    # Milliseconds; nothing moves while Cinnamon has its animations off.
    duration: int = 500
    # Applications it does not start over, by WM_CLASS, one per line.
    excluded: str = ""

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

    @property
    def excluded_apps(self) -> list[str]:
        return [line.lower() for line in self.excluded.splitlines() if line]


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
            raise ValueError(f"{key} is a color such as #00000080, not {value!r}")
        return value.lower()

    return check


def _activation(value: object) -> str:
    if value not in ACTIVATIONS:
        raise ValueError(f"activation is one of {', '.join(ACTIVATIONS)}, not {value!r}")
    return str(value)


def _excluded(value: object) -> str:
    """One application per line, blank lines and surrounding spaces dropped."""
    if not isinstance(value, str):
        raise ValueError(f"excluded is text, not {value!r}")
    apps = [line.strip() for line in value.splitlines() if line.strip()]
    for app in apps:
        if not _APP.fullmatch(app):
            raise ValueError(f"excluded holds application names such as firefox, not {app!r}")
    return "\n".join(apps)


_CHECKS: dict[str, Callable[[object], object]] = {
    "activation": _activation,
    "shake_distance": _number("shake_distance", SHAKE_DISTANCE),
    "shake_interval": _number("shake_interval", SHAKE_INTERVAL),
    "shake_factor": _number("shake_factor", SHAKE_FACTOR),
    "skip_fullscreen": _flag("skip_fullscreen"),
    "skip_gamemode": _flag("skip_gamemode"),
    "background": _color("background"),
    "spotlight": _color("spotlight"),
    "radius": _number("radius", RADIUS),
    "zoom": _number("zoom", ZOOM),
    "duration": _number("duration", DURATION),
    "excluded": _excluded,
}


def rgba(color: str) -> tuple[float, float, float, float]:
    """A "#rrggbbaa" color as cairo takes it, each part from 0 to 1."""
    red, green, blue, alpha = (int(color[index : index + 2], 16) / 255 for index in (1, 3, 5, 7))
    return red, green, blue, alpha
