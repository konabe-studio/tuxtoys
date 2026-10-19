import json
from pathlib import Path

import pytest

from tuxtoys.modules.shortcutguide import apps, reading, usersheets
from tuxtoys.modules.shortcutguide.sheets import Group, Item, Sheet, Text
from tuxtoys.modules.shortcutguide.usersheets import (
    FALLBACK_ICON,
    dump,
    file_name,
    folder,
    for_window,
    load,
    parse,
    save,
)

GIMP = {
    "version": 1,
    "name": "GIMP",
    "icon": "gimp",
    "windows": ["Gimp", "gimp-2.10"],
    "groups": [
        {
            "title": "Layers",
            "items": [
                {"id": "new-layer", "label": "New layer", "keys": ["<Primary><Shift>n"]},
                {"id": "anchor", "label": "Anchor_layer", "keys": ["<Primary>h", "<Super>a"]},
            ],
        }
    ],
}


def text(data: object) -> str:
    return json.dumps(data)


def test_a_file_becomes_a_sheet_of_the_users_own_words() -> None:
    sheet = parse(text(GIMP), "user:gimp")
    assert sheet.id == "user:gimp"
    assert sheet.name == "GIMP"
    assert sheet.icons == ("gimp", FALLBACK_ICON)
    assert sheet.wm_classes == ("gimp", "gimp-2.10")
    (group,) = sheet.groups
    assert group.title == Text("Layers", own=True)
    assert [item.id for item in group.items] == ["new-layer", "anchor"]
    assert group.items[1].keys == ("<Primary>h", "<Super>a")


def test_the_users_words_are_shown_as_written() -> None:
    # Not translated, and an underscore is not a mnemonic.
    assert reading.translate(Text("Anchor_layer", own=True)) == "Anchor_layer"
    assert reading.translate(Text("Copy", own=True)) == "Copy"


def test_its_rows_read_as_the_shipped_ones_do() -> None:
    sheet = parse(text(GIMP), "user:gimp")
    (section,) = reading.read(sheet, lambda _setting: None)
    assert section.title == "Layers"
    assert [row.id for row in section.rows] == ["user:gimp/new-layer", "user:gimp/anchor"]
    assert section.rows[0].keys == (("Ctrl", "Shift", "N"),)


def test_a_hand_written_file_may_leave_out_the_ids_and_the_icon() -> None:
    data = {
        "version": 1,
        "name": "Inkscape",
        "windows": ["inkscape"],
        "groups": [{"title": "Tools", "items": [{"label": "Pen", "keys": ["b"]}]}],
    }
    sheet = parse(text(data), "user:inkscape")
    assert sheet.icons == (FALLBACK_ICON,)
    assert sheet.groups[0].items[0].id == "Pen"


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"version": 2}, "version"),
        ({"name": ""}, "name"),
        ({"name": 5}, "name"),
        ({"icon": ["gimp"]}, "icon"),
        ({"windows": "gimp"}, "windows"),
        ({"windows": [""]}, "window class"),
        ({"groups": {}}, "groups"),
        ({"groups": [{"items": []}]}, "title"),
        ({"groups": [{"title": "A", "items": [{"label": "X", "keys": ["<Bogus>x"]}]}]}, "shortcut"),
        ({"groups": [{"title": "A", "items": [{"label": "X", "keys": "x"}]}]}, "keys"),
        ({"groups": [{"title": "A", "items": [{"keys": ["x"]}]}]}, "label"),
        (
            {"groups": [{"title": "A", "items": [{"label": "X", "keys": ["x"]}] * 2}]},
            "used twice",
        ),
    ],
)
def test_a_bad_file_says_what_is_wrong(change: dict[str, object], reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        parse(text({**GIMP, **change}), "user:gimp")


@pytest.mark.parametrize("content", ["{", "[]", '"gimp"'])
def test_what_is_not_a_json_object_is_refused(content: str) -> None:
    with pytest.raises(ValueError, match="JSON"):
        parse(content, "user:gimp")


def test_a_sheet_survives_its_file() -> None:
    sheet = parse(text(GIMP), "user:gimp")
    assert parse(dump(sheet), "user:gimp") == sheet
    assert json.loads(dump(sheet))["icon"] == "gimp"


def test_a_sheet_without_an_icon_writes_none() -> None:
    sheet = parse(text({**GIMP, "icon": ""}), "user:gimp")
    assert json.loads(dump(sheet))["icon"] == ""


def test_the_folder_follows_xdg(tmp_path: Path) -> None:
    assert folder({"XDG_CONFIG_HOME": str(tmp_path)}) == tmp_path / "tuxtoys" / "shortcutguide"
    assert folder({"XDG_CONFIG_HOME": "relative"}) == (
        Path.home() / ".config" / "tuxtoys" / "shortcutguide"
    )


def test_loading_reads_every_file_by_name_and_reports_the_bad_ones(tmp_path: Path) -> None:
    (tmp_path / "b-gimp.json").write_text(text(GIMP), encoding="utf-8")
    (tmp_path / "a-broken.json").write_text("{", encoding="utf-8")
    (tmp_path / "c-latin1.json").write_bytes(b'{"name": "\xe9"}')
    (tmp_path / "notes.txt").write_text("not a sheet", encoding="utf-8")
    (tmp_path / ".gimp.json.123.tmp").write_text("{", encoding="utf-8")
    (tmp_path / ".hidden.json").write_text("{", encoding="utf-8")
    sheets, problems = load(tmp_path)
    assert [sheet.id for sheet in sheets] == ["user:b-gimp"]
    assert [problem.path.name for problem in problems] == ["a-broken.json", "c-latin1.json"]


def test_a_missing_folder_has_no_sheets(tmp_path: Path) -> None:
    assert load(tmp_path / "none") == ([], [])


def test_saving_writes_the_file_and_leaves_no_temporary(tmp_path: Path) -> None:
    sheet = parse(text(GIMP), "user:gimp")
    path = tmp_path / "shortcutguide" / "gimp.json"
    save(sheet, path)
    save(sheet, path)
    assert [entry.name for entry in path.parent.iterdir()] == ["gimp.json"]
    assert load(path.parent)[0] == [sheet]


def test_a_new_file_is_named_after_the_app_and_never_twice() -> None:
    assert file_name("GIMP", []) == "gimp.json"
    assert file_name("GNU Image / Manipulation", []) == "gnu-image-manipulation.json"
    assert file_name("Szövegszerkesztő", []) == "szövegszerkesztő.json"
    assert file_name("GIMP", ["gimp.json", "gimp-2.json"]) == "gimp-3.json"
    assert file_name(" / ", []) == "app.json"


def sheet(sheet_id: str, *classes: str, items: tuple[str, ...] = ("a",)) -> Sheet:
    group = Group(Text("Group", own=True), tuple(Item(i, Text(i, own=True), ("x",)) for i in items))
    return Sheet(sheet_id, sheet_id, (), (group,), classes)


def test_a_window_with_no_sheet_has_none() -> None:
    assert for_window("gimp", apps.APPS, []) is None


def test_a_shipped_sheet_stays_as_it_is_without_the_users() -> None:
    assert for_window("Nemo", apps.APPS, [sheet("user:gimp", "gimp")]) is apps.NEMO


def test_the_users_sheet_serves_an_app_with_no_shipped_one() -> None:
    gimp = sheet("user:gimp", "gimp")
    assert for_window("Gimp", apps.APPS, [gimp]) is gimp


def test_the_users_groups_follow_the_shipped_ones_with_ids_of_their_own() -> None:
    own = sheet("user:nemo", "nemo", items=("NewTab",))
    found = for_window("nemo", apps.APPS, [own])
    assert found is not None
    assert found.id == "nemo"
    assert found.name == "Nemo"
    assert found.groups[: len(apps.NEMO.groups)] == apps.NEMO.groups
    added = found.groups[-1]
    assert [item.id for item in added.items] == ["user:nemo:NewTab"]
    rows = [row.id for section in reading.read(found, lambda _s: None) for row in section.rows]
    assert "nemo/NewTab" in rows
    assert "nemo/user:nemo:NewTab" in rows


def test_more_sheets_for_one_app_join_the_first_in_file_order() -> None:
    first = sheet("user:a", "gimp", items=("one",))
    second = sheet("user:b", "gimp", items=("two",))
    found = for_window("gimp", apps.APPS, [first, second])
    assert found is not None
    assert found.id == "user:a"
    assert [item.id for group in found.groups for item in group.items] == ["one", "user:b:two"]


def test_the_module_knows_its_prefix() -> None:
    assert usersheets.sheet_id(Path("/x/gimp.json")) == "user:gimp"
