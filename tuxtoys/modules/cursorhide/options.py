"""CursorHide's settings, read and checked without GTK or D-Bus, with PowerToys' defaults: hide
the pointer while typing, or once it has rested for a while.
"""

from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import Any

# How long the pointer has to rest, in seconds.
DELAY_LIMITS = (1, 60)


@dataclass(frozen=True)
class Options:
    # Hidden at a key press; the modifier keys alone do not count.
    after_typing: bool = True
    # Hidden once the pointer has rested for `delay` seconds.
    after_rest: bool = False
    delay: int = 5

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


_CHECKS: dict[str, Callable[[object], object]] = {
    "after_typing": _flag("after_typing"),
    "after_rest": _flag("after_rest"),
    "delay": _number("delay", DELAY_LIMITS),
}
