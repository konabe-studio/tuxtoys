from tuxtoys.inputwatch.detect import DoublePress, Key, KeyEvent, Motion, Shake
from tuxtoys.inputwatch.main import Debug, main

HERE = (10, 10)


def press(key: Key, time: int) -> KeyEvent:
    return KeyEvent(key, True, time)


def release(key: Key, time: int) -> KeyEvent:
    return KeyEvent(key, False, time)


def tap(detector: DoublePress, key: Key, time: int, where: tuple[int, int] = HERE) -> bool:
    found = detector.feed(press(key, time), where)
    detector.feed(release(key, time + 30), where)
    return found


def test_two_quick_presses_are_a_double_press() -> None:
    left = DoublePress(Key.CTRL_LEFT)
    assert not tap(left, Key.CTRL_LEFT, 1000)
    assert tap(left, Key.CTRL_LEFT, 1250)


def test_a_third_press_starts_over() -> None:
    left = DoublePress(Key.CTRL_LEFT)
    tap(left, Key.CTRL_LEFT, 1000)
    assert tap(left, Key.CTRL_LEFT, 1250)
    assert not tap(left, Key.CTRL_LEFT, 1500)
    assert tap(left, Key.CTRL_LEFT, 1750)


def test_presses_too_far_apart_or_too_close_are_not() -> None:
    left = DoublePress(Key.CTRL_LEFT)
    tap(left, Key.CTRL_LEFT, 1000)
    assert not tap(left, Key.CTRL_LEFT, 1500)  # 500 ms, past 400
    assert not tap(left, Key.CTRL_LEFT, 1550)  # 50 ms, a bounce
    assert left.min_ms == 80


def test_another_key_between_cancels_it() -> None:
    left = DoublePress(Key.CTRL_LEFT)
    tap(left, Key.CTRL_LEFT, 1000)
    left.feed(press(Key.OTHER, 1100), HERE)
    assert not tap(left, Key.CTRL_LEFT, 1200)


def test_the_other_ctrl_cancels_it() -> None:
    left = DoublePress(Key.CTRL_LEFT)
    tap(left, Key.CTRL_LEFT, 1000)
    tap(left, Key.CTRL_RIGHT, 1100)
    assert not tap(left, Key.CTRL_LEFT, 1200)


def test_ctrl_held_with_a_key_is_a_shortcut_not_a_press() -> None:
    left = DoublePress(Key.CTRL_LEFT)
    left.feed(press(Key.CTRL_LEFT, 1000), HERE)
    left.feed(press(Key.OTHER, 1050), HERE)  # Ctrl+C
    left.feed(release(Key.OTHER, 1080), HERE)
    left.feed(release(Key.CTRL_LEFT, 1100), HERE)
    assert not tap(left, Key.CTRL_LEFT, 1200)


def test_holding_the_key_is_not_pressing_it_again() -> None:
    left = DoublePress(Key.CTRL_LEFT)
    assert not left.feed(press(Key.CTRL_LEFT, 1000), HERE)
    assert not left.feed(press(Key.CTRL_LEFT, 1200), HERE)  # a repeat while held


def test_a_moved_pointer_between_presses_cancels_it() -> None:
    left = DoublePress(Key.CTRL_LEFT)
    tap(left, Key.CTRL_LEFT, 1000, (10, 10))
    assert not tap(left, Key.CTRL_LEFT, 1200, (40, 10))


def test_the_double_click_time_can_be_set() -> None:
    left = DoublePress(Key.CTRL_LEFT, 600)
    tap(left, Key.CTRL_LEFT, 1000)
    assert tap(left, Key.CTRL_LEFT, 1550)
    assert left.min_ms == 100


def moves(shake: Shake, points: list[tuple[int, int]], step_ms: int = 20) -> list[bool]:
    return [shake.feed(Motion(x, y, index * step_ms)) for index, (x, y) in enumerate(points)]


def test_shaking_left_and_right_is_a_shake() -> None:
    shake = Shake()
    points = [(500 + (200 if i % 2 else 0), 500) for i in range(8)]
    found = moves(shake, points)
    # 200 px a stroke: the fifth one reaches 1000 px, five times the 200 px box.
    assert found.index(True) == 5
    assert found.count(True) == 1


def test_one_long_straight_move_is_not() -> None:
    shake = Shake()
    assert not any(moves(shake, [(x, 300) for x in range(0, 2400, 100)]))


def test_moves_in_one_direction_count_as_one() -> None:
    shake = Shake()
    moves(shake, [(0, 0), (10, 0), (20, 0), (30, 0)])
    assert len(shake._history) == 1
    assert shake._history[0].dx == 30


def test_a_slow_shake_falls_out_of_the_interval() -> None:
    shake = Shake()
    points = [(500 + (200 if i % 2 else 0), 500) for i in range(8)]
    assert not any(moves(shake, points, step_ms=400))


def test_a_shake_needs_the_minimum_distance() -> None:
    shake = Shake(minimum_distance=5000)
    points = [(500 + (200 if i % 2 else 0), 500) for i in range(8)]
    assert not any(moves(shake, points))


def test_a_lower_factor_is_more_sensitive() -> None:
    # Two strokes back and forth, 600 px each on a 600 px box: 3 times the diagonal.
    points = [(0, 0), (600, 0), (0, 0), (600, 0), (0, 0)]
    assert not any(moves(Shake(minimum_distance=1000, factor=400), points))
    assert any(moves(Shake(minimum_distance=1000, factor=300), points))


def test_the_debug_lines_never_name_another_key() -> None:
    debug = Debug()
    assert debug.lines(press(Key.OTHER, 0)) == ["Another key down"]
    assert debug.lines(press(Key.CTRL_LEFT, 1000)) == ["Left Ctrl down"]
    debug.lines(release(Key.CTRL_LEFT, 1030))
    assert debug.lines(press(Key.CTRL_LEFT, 1200)) == [
        "Left Ctrl down",
        ">>> Left Ctrl pressed twice",
    ]


def test_the_debug_lines_show_the_pointer_now_and_then() -> None:
    debug = Debug()
    assert debug.lines(Motion(1, 2, 0)) == ["Pointer at 1, 2"]
    assert debug.lines(Motion(3, 4, 100)) == []
    assert debug.lines(Motion(5, 6, 600)) == ["Pointer at 5, 6"]


def test_without_debug_it_says_there_is_nothing_to_do() -> None:
    assert main([]) == 2
