from pathlib import Path

from tuxtoys.api import ModuleInfo
from tuxtoys.settings.catalog import TOOLS
from tuxtoys.tray import quick


def module(module_id: str, state: str = "on") -> ModuleInfo:
    return ModuleInfo(module_id, module_id, "", state, "")


def test_only_the_tools_that_are_on_and_open_something_in_the_sidebars_order() -> None:
    modules = [
        module("mousejump"),
        module("awake"),
        module("colorpicker"),
        module("hosts", "off"),
        module("screenruler", "failed"),
        module("envvars"),
    ]
    shown = quick.entries(modules)
    assert [entry.module_id for entry in shown] == ["envvars", "colorpicker", "mousejump"]
    assert shown[0] == quick.Entry(
        "envvars", "Environment Variables", "utilities-terminal-symbolic", "env"
    )


def test_nothing_on_lists_nothing() -> None:
    assert quick.entries([module("awake"), module("colorpicker", "off")]) == []


def test_every_tool_it_can_open_is_in_the_catalog() -> None:
    assert set(quick.COMMANDS) <= {tool.id for tool in TOOLS}


def test_installed_it_runs_the_command_from_a_checkout_the_module() -> None:
    assert quick.argv("colorpicker", Path("/usr/lib/tuxtoys")) == [
        "/usr/bin/tuxtoys",
        "colorpicker",
    ]
    assert quick.argv("env", Path("/home/ben/tuxtoys"), "/usr/bin/python3") == [
        "/usr/bin/python3",
        "-m",
        "tuxtoys",
        "env",
    ]


def test_every_command_is_one_the_command_line_takes() -> None:
    from tuxtoys.cli import parser

    for module_id, command in quick.COMMANDS.items():
        assert parser().parse_args([command]).command == command, module_id
