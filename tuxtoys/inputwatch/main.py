"""The input watcher as a program. For now it has one use: with --debug it prints what it
sees and what it detects (a double press of either Ctrl, a shake of the mouse), to check on
a desktop that the X server reports it. Which other key was pressed is never printed, nor
known. The mouse tools will start it as their helper.
"""

import argparse
import sys

from tuxtoys.inputwatch.detect import (
    ButtonEvent,
    DoublePress,
    Event,
    Key,
    KeyEvent,
    Motion,
    Shake,
)

# How often the pointer's position is printed while it moves, in milliseconds.
MOTION_EVERY_MS = 500

KEY_NAMES = {
    Key.CTRL_LEFT: "Left Ctrl",
    Key.CTRL_RIGHT: "Right Ctrl",
    Key.SHIFT: "Shift",
    Key.ALT: "Alt",
    Key.SUPER: "Super",
    Key.OTHER: "Another key",
}


class Debug:
    """Turns events into lines for the terminal."""

    def __init__(self) -> None:
        self.left = DoublePress(Key.CTRL_LEFT)
        self.right = DoublePress(Key.CTRL_RIGHT)
        self.shake = Shake()
        self.pointer = (0, 0)
        self._motion_shown = -MOTION_EVERY_MS

    def lines(self, event: Event) -> list[str]:
        found = []
        if isinstance(event, KeyEvent):
            found.append(f"{KEY_NAMES[event.key]} {'down' if event.pressed else 'up'}")
            if self.left.feed(event, self.pointer):
                found.append(">>> Left Ctrl pressed twice")
            if self.right.feed(event, self.pointer):
                found.append(">>> Right Ctrl pressed twice")
        elif isinstance(event, ButtonEvent):
            state = "down" if event.pressed else "up"
            found.append(f"Button {event.button} {state} at {event.x}, {event.y}")
            self.pointer = (event.x, event.y)
        elif isinstance(event, Motion):
            self.pointer = (event.x, event.y)
            if event.time - self._motion_shown >= MOTION_EVERY_MS:
                self._motion_shown = event.time
                found.append(f"Pointer at {event.x}, {event.y}")
            if self.shake.feed(event):
                found.append(">>> Mouse shaken")
        return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tuxtoys-inputwatch",
        description="Watches the pointer and the modifier keys for TuxToys' mouse tools.",
    )
    parser.add_argument(
        "--debug", action="store_true", help="print what is seen and detected, until Ctrl+C"
    )
    options = parser.parse_args(argv)
    if not options.debug:
        parser.print_usage(sys.stderr)
        print("Nothing to do without --debug yet.", file=sys.stderr)
        return 2
    from tuxtoys.platform.x11 import watch_input

    debug = Debug()
    print("Watching. Press Ctrl+C here to stop.", flush=True)

    def show(event: Event) -> None:
        for line in debug.lines(event):
            print(line, flush=True)

    try:
        watch_input(show)
    except KeyboardInterrupt:
        return 0
    except ImportError as error:
        print(f"python3-xlib is needed: {error}", file=sys.stderr)
        return 1
    except RuntimeError as error:
        print(f"Cannot watch: {error}", file=sys.stderr)
        return 1
    return 0
