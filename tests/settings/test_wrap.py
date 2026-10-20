"""A settings page can get narrower than its longest description. Needs a display: xvfb in
CI, the desktop otherwise.
"""

import pytest

gi = pytest.importorskip("gi", reason="PyGObject is not installed")
try:
    gi.require_version("Gtk", "3.0")
except ValueError as error:
    pytest.skip(f"GTK 3 is missing: {error}", allow_module_level=True)
pytest.importorskip("xapp.SettingsWidgets", reason="python3-xapp is not installed")

from gi.repository import Gtk  # noqa: E402

if not Gtk.init_check()[0]:
    pytest.skip("no display to open", allow_module_level=True)

from xapp.SettingsWidgets import SettingsPage  # noqa: E402

from tuxtoys.settings.widgets import wrap_descriptions  # noqa: E402

LONG = " ".join(["A description much longer than any window would want to be."] * 6)


def test_a_section_s_description_wraps_and_the_page_can_be_narrow() -> None:
    page = SettingsPage()
    page.add_section("Title", LONG)
    # A hidden widget asks for no width at all.
    page.show_all()
    before = page.get_preferred_width().minimum_width
    wrap_descriptions(page)
    after = page.get_preferred_width().minimum_width
    assert after < before
    assert after < 400


def test_labels_that_are_not_descriptions_are_left_alone() -> None:
    box = Gtk.Box()
    label = Gtk.Label(label="A row's own label")
    box.add(label)
    wrap_descriptions(box)
    assert not label.get_line_wrap()
