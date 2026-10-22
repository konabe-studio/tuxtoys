from dataclasses import dataclass, field

import pytest

from tuxtoys.modules.base import Context
from tuxtoys.modules.mousejump.layout import STYLES, jump_by_key, jump_to, layout
from tuxtoys.modules.mousejump.module import MouseJump
from tuxtoys.modules.mousejump.options import Options, custom_from
from tuxtoys.modules.mouseutilities.helper import MouseHelper

ONE = [(0, 0, 1280, 800)]
TWO = [(0, 0, 1920, 1080), (1920, 0, 1920, 1080)]


def test_the_defaults_are_powertoys() -> None:
    options = Options()
    assert (options.width, options.height, options.style) == (1600, 1200, "bezelled")


@pytest.mark.parametrize("change", [{"style": "fancy"}, {"width": 10}, {"height": "big"}])
def test_bad_settings_are_refused(change: dict[str, object]) -> None:
    with pytest.raises(ValueError, match=r"\S"):
        Options().update(change)


def test_the_styles_are_powertoys() -> None:
    compact, bezelled = STYLES["compact"], STYLES["bezelled"]
    assert (compact.border, compact.padding, compact.bezel) == (6, 0, 0)
    assert (bezelled.padding, bezelled.margin) == (4, 4)
    assert (bezelled.bezel, bezelled.bezel_depth) == (12, 4)


def test_one_monitor_fills_the_preview_as_large_as_the_monitor_lets_it() -> None:
    found = layout(ONE, (640, 400), (1600, 1200), STYLES["compact"])
    (screen,) = found.screens
    # The monitor is smaller than 1600 x 1200, so the preview fits in it, aspect kept:
    # 788 px of room for 800 scales the 1280 to 1261, and the 6 px frame goes round it.
    assert found.window == (4, 0, 1273, 800)
    assert screen.outer[0] == 6
    assert screen.content == screen.outer


def test_the_preview_is_centered_on_the_pointer_and_kept_on_its_monitor() -> None:
    found = layout(TWO, (2500, 100), (800, 600), STYLES["compact"])
    x, y, width, height = found.window
    assert (width, height) == (800, 234)
    assert x == 2500 - width // 2
    assert y == 0  # moved down into the monitor rather than off its top
    found = layout(TWO, (2000, 100), (800, 600), STYLES["compact"])
    assert found.window[0] == 1920  # not onto the monitor on the left
    found = layout(TWO, (3830, 1070), (800, 600), STYLES["compact"])
    x, y, width, height = found.window
    assert x + width == 3840
    assert y + height == 1080


def test_bezels_take_the_margin_and_the_border_from_each_picture() -> None:
    found = layout(TWO, (100, 100), (800, 600), STYLES["bezelled"])
    left, right = found.screens
    assert left.content[0] - left.outer[0] == 4 + 12
    assert right.outer[0] == left.outer[0] + left.outer[2]


def test_a_click_on_a_picture_sends_the_pointer_to_the_same_place() -> None:
    found = layout(TWO, (100, 100), (800, 600), STYLES["compact"])
    left, right = found.screens
    x = right.content[0] + right.content[2] // 2
    y = right.content[1] + right.content[3] // 2
    to_x, to_y = jump_to(found, x, y)
    assert abs(to_x - (1920 + 960)) < 10
    assert abs(to_y - 540) < 10
    assert jump_to(found, left.content[0], left.content[1]) == (1, 1)  # a pixel inside
    assert jump_to(found, 0, 0) is None  # the frame


def test_keys_jump_to_a_monitor_s_middle() -> None:
    assert jump_by_key("2", TWO, 0, 0) == (2880, 540)
    assert jump_by_key("3", TWO, 0, 0) is None
    assert jump_by_key("p", TWO, 1, 0) == (2880, 540)
    assert jump_by_key("Right", TWO, 0, 1) == (960, 540)
    assert jump_by_key("Left", TWO, 0, 0) == (2880, 540)
    assert jump_by_key("Home", TWO, 0, 1) == (960, 540)
    assert jump_by_key("End", TWO, 0, 0) == (2880, 540)
    assert jump_by_key("x", TWO, 0, 0) is None


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
    module = MouseJump(lambda: bindings, helper)
    module.enable(Context(None, MouseJump.read_settings({})))
    assert set(helper.tools) == {"mousejump"}
    assert [(c.command, c.binding) for c in bindings.customs] == [
        ("tuxtoys mousejump", ["<Shift><Super>d"])
    ]
    module.disable()
    module.switched_off()
    assert bindings.customs == []


def test_the_custom_style_starts_as_bezelled_and_draws_from_its_settings() -> None:
    options = Options()
    assert Options(style="custom").preview_style() == STYLES["bezelled"]
    custom = options.update(
        {"style": "custom", "custom_bezel": 20, "custom_bezel_color": "#FF0000"}
    )
    style = custom.preview_style()
    assert (style.bezel, style.bezel_color) == (20, "#ff0000")
    assert options.preview_style() == STYLES["bezelled"]


def test_copying_a_style_to_the_custom_one() -> None:
    copied = custom_from(STYLES["compact"])
    assert copied["custom_bezel"] == 0
    assert copied["custom_border_color"] == ""
    assert Options().update({**copied, "style": "custom"}).preview_style() == STYLES["compact"]


@pytest.mark.parametrize(
    "change", [{"custom_border": 101}, {"custom_bezel_color": ""}, {"custom_screen1": "blue"}]
)
def test_bad_custom_settings_are_refused(change: dict[str, object]) -> None:
    with pytest.raises(ValueError, match=r"\S"):
        Options().update(change)
