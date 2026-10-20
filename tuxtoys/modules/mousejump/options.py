"""Mouse Jump's settings, read and checked without GTK or D-Bus, with PowerToys' defaults: its
shortcut, the largest size of the preview, and the preview's style: one of PowerToys' two, or
the custom one, whose parts are the custom_ settings, Bezelled's to start with.
"""

import re
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

from tuxtoys.modules.mousejump.layout import STYLE_FIELDS, STYLES, Style

# PowerToys' Win+Shift+D.
SHORTCUT_KEYS = "<Shift><Super>d"
SHORTCUT_NAME = "TuxToys: Mouse Jump"
SHORTCUT_COMMAND = "tuxtoys mousejump"
WIDTH = (160, 8000)
HEIGHT = (120, 8000)
SIZE = (0, 100)
STYLE_NAMES = (*STYLES, "custom")
_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


@dataclass(frozen=True)
class Options:
    shortcut: bool = True
    # The largest the preview gets; never larger than the monitor the pointer is on.
    width: int = 1600
    height: int = 1200
    style: str = "bezelled"
    custom_color1: str = "#0d57d2"
    custom_color2: str = "#0344c0"
    custom_border: int = 6
    # "" for the theme's highlight color, as PowerToys' own styles have it.
    custom_border_color: str = ""
    custom_border_depth: int = 0
    custom_padding: int = 4
    custom_bezel: int = 12
    custom_bezel_color: str = "#222222"
    custom_bezel_depth: int = 4
    custom_margin: int = 4
    custom_screen1: str = "#191970"
    custom_screen2: str = "#191970"

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

    def preview_style(self) -> Style:
        """The style the preview is drawn in."""
        if self.style == "custom":
            return Style(**{field: getattr(self, f"custom_{field}") for field in STYLE_FIELDS})
        return STYLES[self.style]


def custom_from(style: Style) -> dict[str, Any]:
    """The custom settings that draw a preview as `style` does, for PowerToys' "Copy to
    custom preview style".
    """
    return {f"custom_{field}": getattr(style, field) for field in STYLE_FIELDS}


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
    if value not in STYLE_NAMES:
        raise ValueError(f"style is one of {', '.join(STYLE_NAMES)}, not {value!r}")
    return str(value)


def _color(key: str, theme: bool = False) -> Callable[[object], str]:
    def check(value: object) -> str:
        if theme and value == "":
            return ""
        if not isinstance(value, str) or not _COLOR.fullmatch(value):
            raise ValueError(f"{key} is a color such as #222222, not {value!r}")
        return value.lower()

    return check


_CHECKS: dict[str, Callable[[object], object]] = {
    "shortcut": _flag,
    "width": _number("width", WIDTH),
    "height": _number("height", HEIGHT),
    "style": _style,
    "custom_color1": _color("custom_color1"),
    "custom_color2": _color("custom_color2"),
    "custom_border": _number("custom_border", SIZE),
    "custom_border_color": _color("custom_border_color", theme=True),
    "custom_border_depth": _number("custom_border_depth", SIZE),
    "custom_padding": _number("custom_padding", SIZE),
    "custom_bezel": _number("custom_bezel", SIZE),
    "custom_bezel_color": _color("custom_bezel_color"),
    "custom_bezel_depth": _number("custom_bezel_depth", SIZE),
    "custom_margin": _number("custom_margin", SIZE),
    "custom_screen1": _color("custom_screen1"),
    "custom_screen2": _color("custom_screen2"),
}
