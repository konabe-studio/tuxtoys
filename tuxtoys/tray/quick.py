"""What the TuxToys panel icon's Quick Access menu lists, decided without GTK so it can be
tested anywhere.

As in PowerToys' Quick Access, it lists the tools that are switched on and have something
to open, in the settings window's order. Each opens through the `tuxtoys` command, which
checks again that the tool is on, so the menu and the command line open a tool the same way.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

from tuxtoys import PROJECT_URL
from tuxtoys.api import ModuleInfo
from tuxtoys.core.nemo_action import INSTALLED_ROOT
from tuxtoys.settings.catalog import TOOLS

INSTALLED_COMMAND = "/usr/bin/tuxtoys"

# The tools Quick Access can open, by module id, with the `tuxtoys` command for each.
COMMANDS = {
    "hosts": "hosts",
    "envvars": "env",
    "colorpicker": "colorpicker",
    "screenruler": "screenruler",
    "textextractor": "textextractor",
    "shortcutguide": "shortcutguide",
    "mousejump": "mousejump",
}

DOCUMENTATION = f"{PROJECT_URL}#readme"
REPORT_A_BUG = f"{PROJECT_URL}/issues/new?labels=bug"


@dataclass(frozen=True)
class Entry:
    module_id: str
    # The tool's name, which stays the same in every language.
    name: str
    icon: str
    command: str


def entries(modules: list[ModuleInfo]) -> list[Entry]:
    """The tools to list, of `modules` as ListModules reports them."""
    on = {info.id for info in modules if info.state == "on"}
    return [
        Entry(tool.id, tool.name, tool.icon, COMMANDS[tool.id])
        for tool in TOOLS
        if tool.id in COMMANDS and tool.id in on
    ]


def argv(command: str, package_root: Path, python: str = sys.executable) -> list[str]:
    """How to run `tuxtoys command`: the installed command, or the checkout's module before
    TuxToys is installed, run with the checkout as the working folder.
    """
    if package_root == INSTALLED_ROOT:
        return [INSTALLED_COMMAND, command]
    return [python, "-m", "tuxtoys", command]
