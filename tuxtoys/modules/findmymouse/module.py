"""Find My Mouse, as the daemon runs it.

The spotlight is drawn, and the keys and the pointer watched, by the mouse tools' helper
(tuxtoys.mouseutilities), since the daemon has no GTK: started while Find My Mouse is on,
restarted with the new settings when they change, stopped when it goes off. With the
"shortcut" activation it keeps a custom shortcut among Cinnamon's, which runs
`tuxtoys findmymouse`, as the screen tools keep theirs.
"""

import json
import logging
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, ClassVar, Protocol

from tuxtoys.api import FINDMYMOUSE_SETTINGS
from tuxtoys.core.i18n import _
from tuxtoys.core.nemo_action import INSTALLED_ROOT, LIBEXEC, PACKAGE_ROOT
from tuxtoys.core.shortcut import CustomShortcut, Keybindings, cinnamon_keybindings
from tuxtoys.modules.base import Context, Module
from tuxtoys.modules.findmymouse.options import (
    SHORTCUT_COMMAND,
    SHORTCUT_KEYS,
    SHORTCUT_NAME,
    Options,
)

log = logging.getLogger(__name__)

HELPER = "tuxtoys-mouse-utilities"


def helper_command(options: Options, package_root: Path = PACKAGE_ROOT) -> list[str]:
    """The helper's command line: the installed launcher, or the checkout's module."""
    arguments = ["--findmymouse", json.dumps(options.settings())]
    installed = LIBEXEC / HELPER
    if package_root == INSTALLED_ROOT and installed.exists():
        return [str(installed), *arguments]
    return [sys.executable, "-m", "tuxtoys.mouseutilities", *arguments]


class Helper(Protocol):
    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...


def start_helper(command: list[str]) -> Helper:
    environment = {**os.environ, "PYTHONPATH": str(PACKAGE_ROOT)}
    return subprocess.Popen(command, env=environment)


class FindMyMouse(Module):
    id: ClassVar[str] = "findmymouse"
    name: ClassVar[str] = _("Find My Mouse")
    description: ClassVar[str] = _(
        "Shines a spotlight on the pointer when you press the left Ctrl twice."
    )
    settings_types: ClassVar[Mapping[str, str]] = FINDMYMOUSE_SETTINGS

    def __init__(
        self,
        make_keybindings: Callable[[], Keybindings] = cinnamon_keybindings,
        start: Callable[[list[str]], Helper] = start_helper,
    ) -> None:
        """The daemon uses the defaults; the tests hand in stand-ins for both."""
        self.shortcut = CustomShortcut(
            SHORTCUT_NAME, SHORTCUT_COMMAND, SHORTCUT_KEYS, make_keybindings
        )
        self._start = start
        self._helper: Helper | None = None
        self._options = Options()

    @classmethod
    def read_settings(cls, section: Mapping[str, Any]) -> dict[str, Any]:
        return Options.read(section).settings()

    @classmethod
    def check_settings(
        cls, settings: Mapping[str, Any], changes: Mapping[str, Any]
    ) -> dict[str, Any]:
        return Options.read(settings).update(changes).settings()

    def enable(self, context: Context) -> None:
        self._options = Options.read(context.settings)
        self._keep_shortcut()
        self._run_helper()

    def apply_settings(self, settings: Mapping[str, Any]) -> None:
        old, self._options = self._options, Options.read(settings)
        self._keep_shortcut()
        if old != self._options or self._helper is None or self._helper.poll() is not None:
            self._run_helper()

    def disable(self) -> None:
        self._stop_helper()

    def switched_off(self) -> None:
        self.shortcut.drop()

    def _keep_shortcut(self) -> None:
        if self._options.activation == "shortcut":
            self.shortcut.keep()
        else:
            self.shortcut.drop()

    def _run_helper(self) -> None:
        self._stop_helper()
        try:
            self._helper = self._start(helper_command(self._options))
        except OSError:
            log.exception("the mouse tools' helper could not start")

    def _stop_helper(self) -> None:
        helper, self._helper = self._helper, None
        if helper is None or helper.poll() is not None:
            return
        helper.terminate()
        try:
            helper.wait(timeout=2)
        except subprocess.TimeoutExpired:
            log.warning("the mouse tools' helper did not stop")
