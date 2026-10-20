"""The mouse tools' helper, as the daemon keeps it: one process for every mouse tool that is
on, started with each one's settings, started again when any of them change, and stopped
when the last one goes off. The tools' modules share the one MouseHelper of the daemon.
"""

import json
import logging
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol

from tuxtoys.core.nemo_action import INSTALLED_ROOT, LIBEXEC, PACKAGE_ROOT

log = logging.getLogger(__name__)

HELPER = "tuxtoys-mouse-utilities"


class Process(Protocol):
    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...


def start_process(command: list[str]) -> Process:
    environment = {**os.environ, "PYTHONPATH": str(PACKAGE_ROOT)}
    return subprocess.Popen(command, env=environment)


def helper_command(
    tools: Mapping[str, Mapping[str, Any]], package_root: Path = PACKAGE_ROOT
) -> list[str]:
    """The helper's command line, a --tool id=settings for each tool, the settings as JSON:
    the installed launcher, or the checkout's module.
    """
    arguments = []
    for tool_id in sorted(tools):
        arguments += ["--tool", f"{tool_id}={json.dumps(dict(tools[tool_id]))}"]
    installed = LIBEXEC / HELPER
    if package_root == INSTALLED_ROOT and installed.exists():
        return [str(installed), *arguments]
    return [sys.executable, "-m", "tuxtoys.mouseutilities", *arguments]


class MouseHelper:
    def __init__(self, start: Callable[[list[str]], Process] = start_process) -> None:
        """The tests hand in a start of their own."""
        self._start = start
        self._tools: dict[str, dict[str, Any]] = {}
        self._process: Process | None = None

    @property
    def tools(self) -> dict[str, dict[str, Any]]:
        return dict(self._tools)

    def set_tool(self, tool_id: str, settings: Mapping[str, Any] | None) -> None:
        """A tool on with these settings, or off for None. The helper starts again only
        when something changed, or when it is not running.
        """
        old = dict(self._tools)
        if settings is None:
            self._tools.pop(tool_id, None)
        else:
            self._tools[tool_id] = dict(settings)
        running = self._process is not None and self._process.poll() is None
        if self._tools == old and (running or not self._tools):
            return
        self._restart()

    def _restart(self) -> None:
        self._stop()
        if not self._tools:
            return
        try:
            self._process = self._start(helper_command(self._tools))
        except OSError:
            log.exception("the mouse tools' helper could not start")

    def _stop(self) -> None:
        process, self._process = self._process, None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            log.warning("the mouse tools' helper did not stop")


_shared: MouseHelper | None = None


def shared() -> MouseHelper:
    """The daemon's one helper, which every mouse tool's module uses."""
    global _shared
    if _shared is None:
        _shared = MouseHelper()
    return _shared
