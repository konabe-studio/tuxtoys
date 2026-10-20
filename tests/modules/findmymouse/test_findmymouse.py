from dataclasses import dataclass, field

import pytest

from tuxtoys.inputwatch.detect import ButtonEvent, Key, KeyEvent, Motion
from tuxtoys.modules.base import Context
from tuxtoys.modules.findmymouse.module import FindMyMouse
from tuxtoys.modules.findmymouse.options import Options, rgba
from tuxtoys.modules.findmymouse.sonar import IDLE_MS, Action, Sonar, radius_at
from tuxtoys.modules.mouseutilities.helper import MouseHelper


def test_the_defaults_are_powertoys_but_quicker() -> None:
    options = Options()
    assert options.activation == "ctrl-left"
    assert (options.shake_distance, options.shake_interval, options.shake_factor) == (
        1000,
        1000,
        400,
    )
    assert (options.radius, options.zoom, options.duration) == (50, 5, 250)
    assert rgba(options.background) == (0.0, 0.0, 0.0, 128 / 255)
    assert rgba(options.spotlight) == (1.0, 1.0, 1.0, 128 / 255)


@pytest.mark.parametrize(
    "change",
    [
        {"activation": "triple-click"},
        {"radius": 0},
        {"zoom": 41},
        {"duration": -1},
        {"background": "#000000"},
        {"spotlight": "white"},
        {"skip_gamemode": 1},
        {"excluded": "fire fox"},
        {"nonsense": True},
    ],
)
def test_bad_settings_are_refused(change: dict[str, object]) -> None:
    with pytest.raises(ValueError, match=r"\S"):
        Options().update(change)


def test_a_bad_value_in_the_config_falls_back_to_its_default() -> None:
    options = Options.read({"radius": "big", "zoom": 4, "background": "#FF000040"})
    assert options.radius == 50
    assert options.zoom == 4
    assert options.background == "#ff000040"


def test_excluded_apps_are_lower_case_one_a_line() -> None:
    assert Options().update({"excluded": " Firefox \n\nvlc"}).excluded_apps == ["firefox", "vlc"]


def double_ctrl(sonar: Sonar, key: Key = Key.CTRL_LEFT) -> Action | None:
    sonar.feed(KeyEvent(key, True, 1000), 0)
    sonar.feed(KeyEvent(key, False, 1030), 0)
    found = sonar.feed(KeyEvent(key, True, 1200), 0)
    sonar.feed(KeyEvent(key, False, 1230), 0)
    return found


def test_the_left_ctrl_twice_shows_it() -> None:
    assert double_ctrl(Sonar(Options())) is Action.SHOW


def test_the_right_ctrl_only_when_chosen() -> None:
    assert double_ctrl(Sonar(Options()), Key.CTRL_RIGHT) is None
    right = Sonar(Options(activation="ctrl-right"))
    assert double_ctrl(right, Key.CTRL_RIGHT) is Action.SHOW


def test_a_shake_shows_it_only_when_chosen() -> None:
    points = [(500 + (200 if i % 2 else 0), 500) for i in range(8)]
    for activation, wanted in (("shake", True), ("ctrl-left", False)):
        sonar = Sonar(Options(activation=activation))
        found = [sonar.feed(Motion(x, y, i * 20), i * 20) for i, (x, y) in enumerate(points)]
        assert (Action.SHOW in found) is wanted


def test_a_click_or_a_key_puts_it_away_and_letting_go_does_not() -> None:
    sonar = Sonar(Options())
    double_ctrl(sonar)
    assert sonar.feed(ButtonEvent(1, False, 5, 5, 2000), 2000) is None
    assert sonar.feed(ButtonEvent(1, True, 5, 5, 2000), 2000) is Action.STOP
    double_ctrl(sonar)
    assert sonar.feed(KeyEvent(Key.OTHER, False, 2000), 2000) is None
    assert sonar.feed(KeyEvent(Key.OTHER, True, 2000), 2000) is Action.STOP


def test_it_follows_the_pointer_and_goes_after_a_second_of_stillness() -> None:
    sonar = Sonar(Options())
    double_ctrl(sonar)
    assert sonar.tick(10_000) is None  # it waits for the pointer to move first
    assert sonar.feed(Motion(40, 50, 0), 10_000) is None
    assert sonar.pointer == (40, 50)
    assert sonar.tick(10_000 + IDLE_MS - 1) is None
    assert sonar.tick(10_000 + IDLE_MS) is Action.STOP
    assert not sonar.shown


def test_the_shortcut_toggles_it() -> None:
    sonar = Sonar(Options(activation="shortcut"))
    assert double_ctrl(sonar) is None
    assert sonar.toggle() is Action.SHOW
    assert sonar.toggle() is Action.STOP


def test_a_cancelled_spotlight_is_not_shown() -> None:
    sonar = Sonar(Options())
    double_ctrl(sonar)
    sonar.cancel()
    assert not sonar.shown


def test_the_circle_closes_in_from_zoom_times_the_radius() -> None:
    options = Options(radius=100, zoom=9)
    assert radius_at(options, 0) == 900
    assert radius_at(options, 0.5) == 500
    assert radius_at(options, 1) == 100
    assert radius_at(options, 2) == 100


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


def test_the_module_hands_the_helper_its_settings_while_on() -> None:
    started: list[FakeProcess] = []
    helper = MouseHelper(lambda command: started.append(FakeProcess(command)) or started[-1])
    module = FindMyMouse(FakeKeybindings, helper)
    module.enable(Context(None, FindMyMouse.read_settings({})))
    assert helper.tools["findmymouse"]["activation"] == "ctrl-left"
    assert len(started) == 1
    module.apply_settings(Options(radius=150).settings())
    assert helper.tools["findmymouse"]["radius"] == 150
    module.disable()
    assert helper.tools == {}


def test_the_shortcut_is_kept_only_for_the_shortcut_activation() -> None:
    bindings = FakeKeybindings()
    module = FindMyMouse(lambda: bindings, MouseHelper(FakeProcess))
    module.enable(Context(None, FindMyMouse.read_settings({})))
    assert bindings.customs == []
    module.apply_settings(Options(activation="shortcut").settings())
    assert [(c.name, c.command, c.binding) for c in bindings.customs] == [
        ("TuxToys: Find My Mouse", "tuxtoys findmymouse", ["<Shift><Super>f"])
    ]
    module.disable()
    assert len(bindings.customs) == 1
    module.switched_off()
    assert bindings.customs == []


def test_ctrl_twice_works_again_after_the_spotlight() -> None:
    # The Ctrl let go of while the spotlight shows still counts as let go.
    sonar = Sonar(Options())
    assert double_ctrl(sonar) is Action.SHOW
    sonar.feed(ButtonEvent(1, True, 0, 0, 1500), 1500)
    assert double_ctrl(sonar) is Action.SHOW
