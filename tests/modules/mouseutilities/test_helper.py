import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from tuxtoys.modules.mouseutilities.helper import MouseHelper, helper_command
from tuxtoys.mouseutilities.main import tool_settings


@dataclass
class FakeProcess:
    command: list[str]
    stopped: bool = False

    def poll(self) -> int | None:
        return 0 if self.stopped else None

    def terminate(self) -> None:
        self.stopped = True

    def wait(self, timeout: float | None = None) -> int:
        return 0


def refuse(_tool: str, _settings: object) -> bool:
    return False


def sent(process: FakeProcess) -> dict[str, dict]:
    command = process.command
    return tool_settings(
        [command[index + 1] for index, part in enumerate(command) if part == "--tool"]
    )


def test_one_process_serves_every_tool_and_starts_again_on_a_change() -> None:
    started: list[FakeProcess] = []
    helper = MouseHelper(
        lambda command: started.append(FakeProcess(command)) or started[-1], refuse
    )
    helper.set_tool("findmymouse", {"radius": 50})
    assert len(started) == 1
    assert sent(started[0]) == {"findmymouse": {"radius": 50}}
    helper.set_tool("findmymouse", {"radius": 50})
    assert len(started) == 1  # nothing changed
    helper.set_tool("findmymouse", {"radius": 60})
    assert len(started) == 2
    assert started[0].stopped
    helper.set_tool("findmymouse", None)
    assert started[1].stopped
    assert len(started) == 2


def test_a_helper_that_died_is_started_again() -> None:
    started: list[FakeProcess] = []
    helper = MouseHelper(
        lambda command: started.append(FakeProcess(command)) or started[-1], refuse
    )
    helper.set_tool("findmymouse", {})
    started[0].stopped = True
    helper.set_tool("findmymouse", {})
    assert len(started) == 2


def test_with_no_tool_on_nothing_starts() -> None:
    started: list[FakeProcess] = []
    helper = MouseHelper(
        lambda command: started.append(FakeProcess(command)) or started[-1], refuse
    )
    helper.set_tool("findmymouse", None)
    assert started == []


def test_from_a_checkout_the_helper_is_the_module(tmp_path: Path) -> None:
    command = helper_command({"findmymouse": {"zoom": 5}}, tmp_path)
    assert command[1:3] == ["-m", "tuxtoys.mouseutilities"]
    assert command[3:] == ["--tool", "findmymouse=" + json.dumps({"zoom": 5})]


def test_the_helper_refuses_a_tool_it_does_not_know() -> None:
    with pytest.raises(ValueError, match="no such mouse tool"):
        tool_settings(["nonsense={}"])
    with pytest.raises(ValueError, match="not a JSON object"):
        tool_settings(["findmymouse=[]"])


def test_new_settings_go_to_the_running_helper_without_a_restart() -> None:
    started: list[FakeProcess] = []
    handed: list[tuple[str, object]] = []
    helper = MouseHelper(
        lambda command: started.append(FakeProcess(command)) or started[-1],
        lambda tool, settings: handed.append((tool, settings)) or True,
    )
    helper.set_tool("findmymouse", {"radius": 50})
    helper.set_tool("findmymouse", {"radius": 80})
    assert len(started) == 1
    assert handed == [("findmymouse", {"radius": 80})]
    helper.set_tool("mousehighlighter", {})  # a tool coming on starts it again
    assert len(started) == 2
