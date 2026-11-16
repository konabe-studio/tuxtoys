from dataclasses import dataclass

import pytest

from tuxtoys.inputwatch.detect import ButtonEvent, Key, KeyEvent, Motion
from tuxtoys.modules.base import Context
from tuxtoys.modules.cursorhide.hiding import MOVE, Change, Hiding
from tuxtoys.modules.cursorhide.module import CursorHide
from tuxtoys.modules.cursorhide.options import Options
from tuxtoys.modules.mouseutilities.helper import MouseHelper


def key(name: Key = Key.OTHER, pressed: bool = True) -> KeyEvent:
    return KeyEvent(name, pressed, 0)


def move(x: int, y: int) -> Motion:
    return Motion(x, y, 0)


def button(number: int, pressed: bool = True) -> ButtonEvent:
    return ButtonEvent(number, pressed, 100, 100, 0)


def test_the_defaults_are_powertoys() -> None:
    options = Options()
    assert options.after_typing
    assert not options.after_rest
    assert options.delay == 5


@pytest.mark.parametrize("change", [{"delay": 0}, {"delay": 61}, {"after_rest": 1}, {"x": 1}])
def test_bad_settings_are_refused(change: dict[str, object]) -> None:
    with pytest.raises(ValueError, match=r"\S"):
        Options().update(change)


def test_a_bad_value_in_the_config_gives_the_default() -> None:
    assert Options.read({"delay": "soon", "after_rest": True}) == Options(after_rest=True)


def test_a_key_hides_it_but_a_modifier_alone_does_not() -> None:
    hiding = Hiding(Options(), 0)
    for modifier in (Key.CTRL_LEFT, Key.CTRL_RIGHT, Key.SHIFT, Key.ALT, Key.SUPER):
        assert hiding.feed(key(modifier), 0) is None
    assert hiding.feed(key(Key.OTHER, pressed=False), 0) is None
    assert hiding.feed(key(), 0) == Change.HIDE
    assert hiding.hidden
    # Typing on keeps it hidden, with nothing to change.
    assert hiding.feed(key(), 0) is None


def test_escape_counts_as_typing() -> None:
    assert Hiding(Options(), 0).feed(key(Key.ESCAPE), 0) == Change.HIDE


def test_typing_leaves_it_alone_when_that_is_off() -> None:
    assert Hiding(Options(after_typing=False), 0).feed(key(), 0) is None


def test_not_while_a_button_is_held() -> None:
    hiding = Hiding(Options(), 0)
    hiding.feed(button(1), 0)
    assert hiding.feed(key(), 0) is None
    hiding.feed(button(1, pressed=False), 0)
    assert hiding.feed(key(), 0) == Change.HIDE


def test_a_small_move_keeps_it_hidden_a_larger_one_shows_it() -> None:
    hiding = Hiding(Options(), 0)
    hiding.feed(move(500, 500), 0)
    hiding.feed(key(), 0)
    assert hiding.feed(move(500 + MOVE, 500), 1) is None
    assert hiding.feed(move(500, 500 - MOVE), 1) is None
    assert hiding.feed(move(500 + MOVE + 1, 500), 1) == Change.SHOW
    assert not hiding.hidden


def test_without_a_known_place_the_first_move_marks_it() -> None:
    hiding = Hiding(Options(), 0)
    hiding.feed(key(), 0)
    assert hiding.feed(move(10, 10), 0) is None
    assert hiding.feed(move(30, 10), 0) == Change.SHOW


@pytest.mark.parametrize("number", [1, 2, 3, 4, 5, 6, 7])
def test_a_button_or_the_wheel_shows_it(number: int) -> None:
    hiding = Hiding(Options(), 0)
    hiding.feed(key(), 0)
    assert hiding.feed(button(number), 0) == Change.SHOW


def test_it_hides_once_it_has_rested_for_the_delay() -> None:
    hiding = Hiding(Options(after_typing=False, after_rest=True, delay=5), 0)
    hiding.feed(move(10, 10), 2)
    assert hiding.tick(6.9) is None
    assert hiding.tick(7) == Change.HIDE
    assert hiding.tick(8) is None
    assert hiding.feed(move(40, 10), 9) == Change.SHOW
    # The rest counts again from the move that showed it.
    assert hiding.tick(13.9) is None
    assert hiding.tick(14) == Change.HIDE


def test_resting_leaves_it_alone_when_that_is_off_or_a_button_is_held() -> None:
    assert Hiding(Options(), 0).tick(100) is None
    hiding = Hiding(Options(after_rest=True, delay=1), 0)
    hiding.feed(button(1), 0)
    assert hiding.tick(100) is None


def test_switching_both_off_shows_it_again() -> None:
    hiding = Hiding(Options(), 0)
    hiding.feed(key(), 0)
    assert hiding.configure(Options(after_rest=True), 1) is None
    assert hiding.hidden
    assert hiding.configure(Options(after_typing=False), 2) == Change.SHOW


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


def test_the_module_shares_the_helper() -> None:
    helper = MouseHelper(FakeProcess, lambda *_: True)
    module = CursorHide(helper)
    module.enable(Context(None, CursorHide.read_settings({})))
    assert helper.tools == {"cursorhide": Options().settings()}
    module.disable()
    assert helper.tools == {}
