from dataclasses import dataclass, field

import pytest

from tuxtoys.inputwatch.detect import ButtonEvent, Motion
from tuxtoys.modules.base import Context
from tuxtoys.modules.mousehighlighter.effects import (
    Dim,
    Disc,
    Highlighter,
    Line,
    Ring,
)
from tuxtoys.modules.mousehighlighter.module import MouseHighlighter
from tuxtoys.modules.mousehighlighter.options import Options
from tuxtoys.modules.mouseutilities.helper import MouseHelper


def press(button: int, x: int = 100, y: int = 100) -> ButtonEvent:
    return ButtonEvent(button, True, x, y, 0)


def release(button: int, x: int = 100, y: int = 100) -> ButtonEvent:
    return ButtonEvent(button, False, x, y, 0)


def on(**changes: object) -> Highlighter:
    model = Highlighter(Options().update(changes))
    model.toggle()
    return model


def test_the_defaults_are_powertoys() -> None:
    options = Options()
    assert options.mode == "ripple"
    assert (options.primary_color, options.secondary_color) == ("#bfff00a6", "#00bfffa6")
    assert (options.radius, options.fade_delay, options.fade_duration) == (30, 400, 400)
    assert (options.ripple_size, options.intensity, options.ripple_duration) == (60, 70, 480)
    assert options.follow
    assert options.crosshairs
    assert not options.auto_activate


@pytest.mark.parametrize(
    "change",
    [{"mode": "sparkle"}, {"intensity": 10}, {"radius": 0}, {"primary_color": "#fff"}],
)
def test_bad_settings_are_refused(change: dict[str, object]) -> None:
    with pytest.raises(ValueError, match=r"\S"):
        Options().update(change)


def test_it_draws_nothing_until_turned_on() -> None:
    model = Highlighter(Options())
    assert not model.feed(press(1), 0)
    assert model.frame(0) == []
    model.toggle()
    assert model.feed(press(1), 0)
    assert Highlighter(Options(auto_activate=True)).active


def test_a_held_circle_shrinks_and_fades_when_let_go_of() -> None:
    model = on(mode="circle")
    model.feed(press(1), 0)
    (disc,) = model.frame(100)
    assert isinstance(disc, Disc)
    assert disc.radius == 30
    (disc,) = model.frame(150 + 180)
    assert disc.radius == pytest.approx(21)
    model.feed(release(1), 400)
    (disc,) = model.frame(400 + 400 + 200)
    assert disc.color[3] == pytest.approx(0.65 * 0.5, abs=0.01)
    assert model.frame(400 + 800) == []
    assert not model.busy(400 + 800)


def test_the_right_button_has_its_own_color_and_the_middle_none() -> None:
    model = on(mode="circle")
    model.feed(press(3), 0)
    (disc,) = model.frame(0)
    assert disc.color[:3] == (0.0, 191 / 255, 1.0)
    assert not model.feed(press(2), 0)


def test_a_transparent_color_switches_its_button_off() -> None:
    model = on(mode="circle", primary_color="#bfff0000")
    assert not model.feed(press(1), 0)


def test_the_always_circle_follows_the_pointer_unless_a_button_is_held() -> None:
    model = on(mode="circle", always_color="#ff000080")
    assert model.feed(Motion(5, 6, 0), 0)
    (disc,) = model.frame(0)
    assert (disc.x, disc.y) == (5, 6)
    model.feed(press(1, 5, 6), 0)
    assert len(model.frame(0)) == 1  # the pressed circle alone


def test_the_spotlight_closes_in_while_held() -> None:
    model = on(mode="spotlight")
    model.feed(Motion(10, 20, 0), 0)
    (dim,) = model.frame(0)
    assert isinstance(dim, Dim)
    assert dim.radius == 30
    model.feed(press(1, 10, 20), 1000)
    (dim,) = model.frame(1120)
    assert dim.radius == pytest.approx(30 * 0.85)
    model.feed(release(1, 10, 20), 2000)
    (dim,) = model.frame(2200)
    assert dim.radius == pytest.approx(30)


def test_a_quick_click_sends_a_ripple_out() -> None:
    model = on()
    model.feed(press(1), 0)
    assert model.frame(100) == []  # not held long enough to show yet
    model.feed(release(1), 100)
    glow, ring = model.frame(100)
    assert isinstance(ring, Ring)
    assert ring.radius == pytest.approx(0.20 * 60)
    assert glow.soft
    _glow, ring = model.frame(100 + 480 - 1)
    assert ring.radius == pytest.approx(1.05 * 60, abs=0.1)
    assert model.frame(100 + 480) == []


def test_a_held_button_shows_its_ring_and_it_follows_the_pointer() -> None:
    model = on()
    model.feed(press(1, 100, 100), 0)
    model.feed(Motion(150, 160, 0), 200)
    _glow, ring = model.frame(400)
    assert (ring.x, ring.y, ring.radius) == (150, 160, pytest.approx(0.55 * 60))
    model.feed(release(1, 150, 160), 400)
    _glow, ring = model.frame(400)
    assert ring.radius == pytest.approx(0.55 * 60)


def test_without_follow_the_ring_stays_where_it_was_pressed() -> None:
    model = on(follow=False)
    model.feed(press(1, 100, 100), 0)
    assert not model.feed(Motion(150, 160, 0), 200)
    _glow, ring = model.frame(400)
    assert (ring.x, ring.y) == (100, 100)


def test_the_right_button_sends_crosshairs_out() -> None:
    model = on()
    model.feed(press(3), 0)
    model.feed(release(3), 50)
    lines = [shape for shape in model.frame(100) if isinstance(shape, Line)]
    assert len(lines) == 4
    assert [shape for shape in on(crosshairs=False).frame(0) if isinstance(shape, Line)] == []


def test_intensity_makes_the_ring_stronger() -> None:
    weak, strong = on(intensity=15), on(intensity=135)
    for model in (weak, strong):
        model.feed(press(1), 0)
        model.feed(release(1), 50)
    weak_ring = weak.frame(50)[1]
    strong_ring = strong.frame(50)[1]
    assert strong_ring.color[3] > weak_ring.color[3]
    assert strong_ring.width > weak_ring.width


def test_turning_it_off_clears_what_it_draws() -> None:
    model = on(mode="circle")
    model.feed(press(1), 0)
    model.toggle()
    assert model.frame(0) == []
    assert not model.busy(0)


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
    helper.set_tool("findmymouse", {})
    module = MouseHighlighter(lambda: bindings, helper)
    module.enable(Context(None, MouseHighlighter.read_settings({})))
    assert set(helper.tools) == {"findmymouse", "mousehighlighter"}
    assert [(c.command, c.binding) for c in bindings.customs] == [
        ("tuxtoys mousehighlighter", ["<Shift><Super>h"])
    ]
    module.apply_settings(Options(shortcut=False).settings())
    assert bindings.customs == []
    module.disable()
    assert set(helper.tools) == {"findmymouse"}
