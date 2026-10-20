from dataclasses import dataclass, field

import pytest

from tuxtoys.modules.base import Context
from tuxtoys.modules.crosshairs.drawing import Glide, Step, arms, crosshairs
from tuxtoys.modules.crosshairs.module import Crosshairs
from tuxtoys.modules.crosshairs.options import Options
from tuxtoys.modules.mouseutilities.helper import MouseHelper
from tuxtoys.modules.mouseutilities.shapes import Layer, Rect

MONITOR = (0, 0, 1000, 800)


def test_the_defaults_are_powertoys() -> None:
    options = Options()
    assert (options.color, options.opacity, options.radius, options.thickness) == (
        "#ff0000",
        75,
        20,
        5,
    )
    assert (options.border_color, options.border, options.orientation) == ("#ffffff", 1, "both")
    assert (options.glide_speed, options.glide_slow) == (25, 5)
    assert not options.auto_hide
    assert not options.fixed


@pytest.mark.parametrize(
    "change",
    [{"orientation": "diagonal"}, {"opacity": 101}, {"glide_speed": 4}, {"color": "#ff000080"}],
)
def test_bad_settings_are_refused(change: dict[str, object]) -> None:
    with pytest.raises(ValueError, match=r"\S"):
        Options().update(change)


def test_the_arms_reach_the_monitor_s_edges_from_the_gap() -> None:
    left, right, top, bottom = arms(Options(), (400, 300), MONITOR, "both")
    assert (left.x, left.y, left.width, left.height) == (0, 298, 380, 5)
    assert (right.x, right.width) == (420, 580)
    assert (top.x, top.y, top.width, top.height) == (398, 0, 5, 280)
    assert (bottom.y, bottom.height) == (320, 480)


def test_a_fixed_length_and_one_orientation() -> None:
    options = Options(fixed=True, fixed_length=50)
    found = arms(options, (400, 300), MONITOR, "vertical")
    assert [(arm.y, arm.height) for arm in found] == [(230, 50), (320, 50)]


def test_an_arm_with_no_room_is_left_out() -> None:
    assert len(arms(Options(), (10, 300), MONITOR, "horizontal")) == 1


def test_the_crosshairs_are_one_layer_with_borders_behind() -> None:
    (layer,) = crosshairs(Options(), (400, 300), MONITOR)
    assert isinstance(layer, Layer)
    assert layer.opacity == 0.75
    borders, lines = layer.shapes[:4], layer.shapes[4:]
    assert all(isinstance(shape, Rect) for shape in layer.shapes)
    assert borders[0].color == (1.0, 1.0, 1.0, 1.0)
    assert lines[0].color == (1.0, 0.0, 0.0, 1.0)
    assert (borders[0].height, lines[0].height) == (7, 5)
    (layer,) = crosshairs(Options(border=0), (400, 300), MONITOR)
    assert len(layer.shapes) == 4


def test_a_glide_sweeps_across_then_down_and_clicks() -> None:
    glide = Glide(Options())
    assert glide.press((500, 500), MONITOR) is Step.STARTED
    assert glide.pointer == (0, 400)
    assert glide.tick(200) == (25, 400)  # 25 pixels in 200 ms
    assert glide.press((25, 400), MONITOR) is Step.SLOWED
    assert glide.tick(200) == (30, 400)
    assert glide.press((30, 400), MONITOR) is Step.TURNED
    assert glide.pointer == (30, 0)
    assert glide.tick(400) == (30, 50)
    assert glide.press((30, 50), MONITOR) is Step.SLOWED
    assert glide.press((30, 50), MONITOR) is Step.CLICK
    assert not glide.active


def test_slow_steps_carry_their_fractions() -> None:
    glide = Glide(Options(glide_speed=5))
    glide.press((0, 0), MONITOR)
    for _tick in range(4):
        glide.tick(10)  # 0.25 px each
    assert glide.pointer == (1, 400)


def test_a_line_that_reaches_the_edge_starts_again_at_the_first_speed() -> None:
    glide = Glide(Options(glide_speed=60))
    glide.press((0, 0), (0, 0, 100, 100))
    glide.press((0, 0), (0, 0, 100, 100))  # slowed to 5
    glide.tick(4000)
    assert glide.pointer == (0, 50)
    assert glide.tick(200)[0] == 60


def test_escape_cancels_a_glide() -> None:
    glide = Glide(Options())
    glide.press((0, 0), MONITOR)
    glide.cancel()
    assert not glide.active
    assert glide.press((0, 0), MONITOR) is Step.STARTED


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


def test_the_module_keeps_both_shortcuts_and_shares_the_helper() -> None:
    bindings = FakeKeybindings()
    helper = MouseHelper(FakeProcess, lambda *_: True)
    module = Crosshairs(lambda: bindings, helper)
    module.enable(Context(None, Crosshairs.read_settings({})))
    assert set(helper.tools) == {"crosshairs"}
    assert sorted((c.command, c.binding[0]) for c in bindings.customs) == [
        ("tuxtoys crosshairs", "<Alt><Super>p"),
        ("tuxtoys glidingcursor", "<Alt><Super>period"),
    ]
    module.apply_settings(Options(glide_shortcut=False).settings())
    assert [c.command for c in bindings.customs] == ["tuxtoys crosshairs"]
    module.disable()
    module.switched_off()
    assert bindings.customs == []
    assert helper.tools == {}
