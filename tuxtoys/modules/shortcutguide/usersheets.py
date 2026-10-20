"""The user's own sheets: a JSON file per app in ~/.config/tuxtoys/shortcutguide/, which the
settings page writes and a user may write by hand.

    {
      "version": 1,
      "name": "GIMP",
      "icon": "gimp",
      "windows": ["gimp"],
      "groups": [
        {"title": "Layers",
         "items": [{"id": "1", "label": "New layer", "keys": ["<Primary><Shift>n"]}]}
      ]
    }

"windows" are the class parts of WM_CLASS, as the shipped sheets match them. The labels are
the user's own words, shown as written. A sheet for an app that has a shipped one adds its
groups after the shipped ones, on the same tab. Free of GTK, so it tests anywhere.
"""

import contextlib
import json
import logging
import os
import re
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from tuxtoys.core import accel
from tuxtoys.modules.shortcutguide.sheets import Group, Item, Sheet, Text

log = logging.getLogger(__name__)

VERSION = 1
SUFFIX = ".json"
# The icon of a sheet that names none, or one the theme does not have.
FALLBACK_ICON = "application-x-executable"
# What a user sheet's id starts with, so it never meets a shipped one's.
PREFIX = "user:"
# Larger than any sheet anyone writes by hand; a file past it is not read.
MAX_BYTES = 1 << 20


def folder(environ: Mapping[str, str] = os.environ) -> Path:
    """Where the files live, by the XDG base directory spec."""
    base = Path(environ.get("XDG_CONFIG_HOME", ""))
    root = base if base.is_absolute() else Path.home() / ".config"
    return root / "tuxtoys" / "shortcutguide"


@dataclass(frozen=True)
class Problem:
    """A file that could not be read, and why, in English for the log."""

    path: Path
    reason: str


def _text(value: object, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must be a text that is not empty")
    return value.strip()


def _list(value: object, what: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{what} must be a list")
    return value


def _item(data: object, where: str, seen: set[str]) -> Item:
    if not isinstance(data, dict):
        raise ValueError(f"{where} must be an object")
    label = _text(data.get("label"), f"{where}'s label")
    # A hand-written file may leave the id out: the label is one, as long as it is unique.
    item_id = _text(data.get("id", label), f"{where}'s id")
    if item_id in seen:
        raise ValueError(f"{where}'s id {item_id!r} is used twice")
    seen.add(item_id)
    shortcuts = tuple(
        _text(shortcut, f"{where}'s keys")
        for shortcut in _list(data.get("keys"), f"{where}'s keys")
    )
    for shortcut in shortcuts:
        if accel.parse(shortcut) is None:
            raise ValueError(f"{where}'s keys {shortcut!r} are not a shortcut")
    return Item(item_id, Text(label, own=True), shortcuts)


def _group(data: object, where: str, seen: set[str]) -> Group:
    if not isinstance(data, dict):
        raise ValueError(f"{where} must be an object")
    title = _text(data.get("title"), f"{where}'s title")
    items = _list(data.get("items", []), f"{where}'s items")
    return Group(
        Text(title, own=True),
        tuple(_item(item, f"{where}, item {number}", seen) for number, item in enumerate(items, 1)),
    )


def parse(text: str, sheet_id: str) -> Sheet:
    """A sheet from a file's text, or ValueError saying what is wrong with it."""
    try:
        data = json.loads(text)
    except ValueError as error:
        raise ValueError(f"not JSON: {error}") from None
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    if data.get("version") != VERSION:
        raise ValueError(f"version must be {VERSION}")
    name = _text(data.get("name"), "the name")
    icon = data.get("icon", "")
    if not isinstance(icon, str):
        raise ValueError("the icon must be a text")
    windows = tuple(
        _text(window, "a window class").lower() for window in _list(data.get("windows"), "windows")
    )
    seen: set[str] = set()
    groups = tuple(
        _group(group, f"group {number}", seen)
        for number, group in enumerate(_list(data.get("groups"), "groups"), 1)
    )
    icons = (icon.strip(), FALLBACK_ICON) if icon.strip() else (FALLBACK_ICON,)
    return Sheet(sheet_id, name, icons, groups, windows)


def dump(sheet: Sheet) -> str:
    """A sheet as its file has it."""
    icon = sheet.icons[0] if sheet.icons and sheet.icons[0] != FALLBACK_ICON else ""
    data = {
        "version": VERSION,
        "name": sheet.name,
        "icon": icon,
        "windows": list(sheet.wm_classes),
        "groups": [
            {
                "title": group.title.msgid,
                "items": [
                    {"id": item.id, "label": item.label.msgid, "keys": list(item.keys)}
                    for item in group.items
                ],
            }
            for group in sheet.groups
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def sheet_id(path: Path) -> str:
    return PREFIX + path.stem


def path_of(sheet: Sheet, directory: Path) -> Path:
    """The file a user sheet was read from, in that folder."""
    return directory / (sheet.id.removeprefix(PREFIX) + SUFFIX)


def load(directory: Path, log_problems: bool = True) -> tuple[list[Sheet], list[Problem]]:
    """Every sheet in the folder, in the order of their file names, and the files that
    could not be read, logged unless the caller shows them itself. A missing folder has
    none.
    """
    sheets: list[Sheet] = []
    problems: list[Problem] = []
    try:
        paths = sorted(path for path in directory.iterdir() if path.suffix == SUFFIX)
    except FileNotFoundError:
        return sheets, problems
    for path in paths:
        if path.name.startswith(".") or not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                raise ValueError("too large")
            sheets.append(parse(path.read_text(encoding="utf-8"), sheet_id(path)))
        except (OSError, ValueError) as error:  # UnicodeDecodeError is a ValueError
            if log_problems:
                log.warning("Shortcut Guide skipped %s: %s", path, error)
            problems.append(Problem(path, str(error)))
    return sheets, problems


_UNSAFE = re.compile(r"[^\w-]+")


def file_name(name: str, taken: Iterable[str]) -> str:
    """A file name for a new sheet, from the app's name, that no other sheet has."""
    stem = _UNSAFE.sub("-", name.strip().lower()).strip("-") or "app"
    names = set(taken)
    candidate, number = stem, 2
    while candidate + SUFFIX in names:
        candidate, number = f"{stem}-{number}", number + 1
    return candidate + SUFFIX


def save(sheet: Sheet, path: Path) -> None:
    """Writes the sheet atomically: a temporary file next to it, then a rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(dump(sheet))
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)
        raise


def _added(sheet: Sheet) -> tuple[Group, ...]:
    """A user sheet's groups as they join another sheet: their ids made its own, so its
    pins never meet the other sheet's.
    """
    return tuple(
        Group(
            group.title,
            tuple(replace(item, id=f"{sheet.id}:{item.id}") for item in group.items),
        )
        for group in sheet.groups
    )


def for_window(wm_class: str, shipped: Sequence[Sheet], own: Sequence[Sheet]) -> Sheet | None:
    """The sheet for a window of this class: the shipped one with the user's groups for the
    same app after its own, or the user's first sheet for it with any further ones' groups,
    or None.
    """
    wanted = wm_class.lower()
    base = next((sheet for sheet in shipped if wanted in sheet.wm_classes), None)
    extra = [sheet for sheet in own if wanted in sheet.wm_classes]
    if base is None:
        if not extra:
            return None
        base, extra = extra[0], extra[1:]
    if not extra:
        return base
    added = tuple(group for sheet in extra for group in _added(sheet))
    return replace(base, groups=(*base.groups, *added))


_SEPARATORS = re.compile(r"[\s,;]+")


def parse_classes(text: str) -> tuple[str, ...]:
    """Window classes as the editor takes them, "firefox, firefox-esr": lower-cased, each
    once, in the order written.
    """
    found: dict[str, None] = {}
    for name in _SEPARATORS.split(text.lower()):
        if name:
            found[name] = None
    return tuple(found)


def classes_text(classes: Iterable[str]) -> str:
    return ", ".join(classes)


def next_id(taken: Iterable[str]) -> str:
    """An id for a new shortcut in a sheet: the lowest number none of the others has."""
    ids = set(taken)
    number = 1
    while str(number) in ids:
        number += 1
    return str(number)


def window_choices(windows: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """The open windows the editor offers, as (class, name): each class once, lower-cased,
    by name, the window's class standing in for a missing name.
    """
    found: dict[str, str] = {}
    for wm_class, name in windows:
        key = wm_class.strip().lower()
        if key and key not in found:
            found[key] = name.strip() or wm_class.strip()
    return sorted(found.items(), key=lambda choice: (choice[1].casefold(), choice[0]))
