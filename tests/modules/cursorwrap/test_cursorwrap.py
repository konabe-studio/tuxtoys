from dataclasses import dataclass, field

import pytest

from tuxtoys.modules.base import Context
from tuxtoys.modules.cursorwrap.module import CursorWrap
from tuxtoys.modules.cursorwrap.options import Options
from tuxtoys.modules.cursorwrap.topology import Side, Wrapper, destination, outer_edges
from tuxtoys.modules.mouseutilities.helper import MouseHelper

ONE = [(0, 0, 1280, 800)]
TWO = [(0, 0, 1920, 1080), (1920, 0, 1920, 1080)]
# A smaller monitor to the right, its top level with the first's.
STEP = [(0, 0, 1920, 1080), (1920, 0, 1280, 720)]


def test_the_defaults_are_powertoys() -> None:
    options = Options()
    assert (options.mode, options.activation) == ("both", "always")
    assert options.not_while_dragging
    assert not options.auto_activate
    assert not options.not_with_one_monitor


@pytest.mark.parametrize("change", [{"mode": "diagonal"}, {"activation": "alt"}])
def test_bad_settings_are_refused(change: dict[str, object]) -> None:
    with pytest.raises(ValueError, match=r"\S"):
        Options().update(change)


def test_the_edges_two_monitors_share_are_not_outer() -> None:
    sides = sorted((edge.monitor, edge.side.value) for edge in outer_edges(TWO))
    assert (0, "right") not in sides
    assert (1, "left") not in sides
    assert (0, "left") in sides
    assert (1, "right") in sides


def test_one_monitor_wraps_to_its_own_other_side() -> None:
    outer = outer_edges(ONE)
    assert destination(outer, ONE, (0, 300), "both") == (1279, 300)
    assert destination(outer, ONE, (1279, 300), "both") == (0, 300)
    assert destination(outer, ONE, (500, 0), "both") == (500, 799)
    assert destination(outer, ONE, (500, 799), "both") == (500, 0)
    assert destination(outer, ONE, (500, 300), "both") is None


def test_the_mode_leaves_the_other_edges_alone() -> None:
    outer = outer_edges(ONE)
    assert destination(outer, ONE, (0, 300), "vertical") is None
    assert destination(outer, ONE, (500, 0), "horizontal") is None


def test_two_monitors_wrap_from_the_far_left_to_the_far_right() -> None:
    outer = outer_edges(TWO)
    assert destination(outer, TWO, (0, 500), "both") == (3839, 500)
    assert destination(outer, TWO, (3839, 500), "both") == (0, 500)
    # Between the two monitors nothing happens.
    assert destination(outer, TWO, (1919, 500), "both") is None


def test_with_no_monitor_level_with_it_the_pointer_goes_to_the_nearest() -> None:
    outer = outer_edges(STEP)
    # From the first monitor's left edge low down: the second ends at 720, so its right edge
    # takes the pointer near its bottom.
    assert destination(outer, STEP, (0, 1000), "both") == (3199, 719)


def test_a_corner_takes_the_edge_the_pointer_moves_towards() -> None:
    outer = outer_edges(ONE)
    assert destination(outer, ONE, (0, 0), "both", (-5, -1)) == (1279, 0)
    assert destination(outer, ONE, (0, 0), "both", (-1, -5)) == (0, 799)


def test_after_a_wrap_it_waits_for_the_pointer_to_move_away() -> None:
    wrapper = Wrapper(ONE)
    assert wrapper.move((0, 300)) == (1279, 300)
    assert wrapper.move((1279, 302)) is None  # where it landed: no bounce
    assert wrapper.move((1200, 300)) is None
    assert wrapper.move((0, 300)) == (1279, 300)


def test_sides_are_their_own_opposites() -> None:
    assert {side.value for side in Side} == {"left", "right", "top", "bottom"}


@dataclass
class Found:
    path: str
    name: str
    command: str
    binding: list[str]


@dataclass
class FakeKeybindings:
    customs: list[Found] = field(default_factory=list)

    def find(self, name: str, command: str) -> Found | None:
        return next((c for c in self.customs if c.name == name and c.command == command), None)

    def taken_by(self, keys: str) -> list[str]:
        return []

    def add(self, name: str, command: str, keys: str) -> None:
        self.customs.append(Found(f"custom{len(self.customs)}", name, command, [keys]))

    def remove(self, path: str) -> None:
        self.customs = [c for c in self.customs if c.path != path]


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


def test_the_module_keeps_its_shortcut_and_shares_the_helper() -> None:
    bindings = FakeKeybindings()
    helper = MouseHelper(FakeProcess, lambda *_: True)
    module = CursorWrap(lambda: bindings, helper)
    module.enable(Context(None, CursorWrap.read_settings({})))
    assert set(helper.tools) == {"cursorwrap"}
    assert [(c.command, c.binding) for c in bindings.customs] == [
        ("tuxtoys cursorwrap", ["<Alt><Super>u"])
    ]
    module.disable()
    module.switched_off()
    assert bindings.customs == []
