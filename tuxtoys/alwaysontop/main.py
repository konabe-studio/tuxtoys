"""The frame helper: follows the windows Muffin keeps above the others while Always on Top is
on, until the daemon stops it, and draws a frame around each unless --no-border. It also lets
go of excluded applications' windows, and gives a window let go of the opacity it had.
Started by the Always on Top module, not by hand.
"""

import argparse
import logging
import signal
import sys

from tuxtoys.modules.alwaysontop.options import LEAST_OPACITY, MOST_RADIUS, MOST_WIDTH

log = logging.getLogger("tuxtoys-always-on-top")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tuxtoys-always-on-top")
    parser.add_argument("--width", type=int, default=4, choices=range(1, MOST_WIDTH + 1))
    parser.add_argument("--opacity", type=int, default=100, choices=range(LEAST_OPACITY, 101))
    parser.add_argument("--radius", type=int, default=8, choices=range(MOST_RADIUS + 1))
    parser.add_argument("--color", default="")
    parser.add_argument("--sound", action="store_true")
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--no-border", dest="border", action="store_false")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(levelname)s: %(message)s")
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import GLib, Gtk

        from tuxtoys.alwaysontop.border import Borders, Sounds, Style, parse_color, theme_accent
        from tuxtoys.platform.x11 import AboveWindows
    except (ImportError, ValueError) as error:
        log.error("cannot draw frames: %s", error)
        return 1
    if not Gtk.init_check(sys.argv)[0]:
        log.error("cannot draw frames: no display")
        return 1

    style = Style(parse_color(args.color) or theme_accent(), args.width, args.opacity, args.radius)
    borders = Borders(style, Sounds() if args.sound else None, frames=args.border)
    windows = AboveWindows(borders.show, args.exclude)
    for number in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, number, Gtk.main_quit)
    log.info("following windows kept above%s", "" if args.border else ", without frames")
    Gtk.main()
    windows.let_go()
    return 0
