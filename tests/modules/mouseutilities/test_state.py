from pathlib import Path

from tuxtoys.modules.mouseutilities.state import read_active, state_path, write_active


def test_the_state_lives_in_the_session_s_runtime_folder(tmp_path: Path) -> None:
    assert (
        state_path({"XDG_RUNTIME_DIR": str(tmp_path)}) == tmp_path / "tuxtoys" / "mouse-tools.json"
    )
    assert state_path({}) is None
    assert state_path({"XDG_RUNTIME_DIR": "relative"}) is None


def test_a_tool_s_state_is_kept_beside_the_others(tmp_path: Path) -> None:
    path = tmp_path / "tuxtoys" / "mouse-tools.json"
    assert read_active(path, "mousehighlighter") is None
    write_active(path, "mousehighlighter", True)
    write_active(path, "crosshairs", False)
    assert read_active(path, "mousehighlighter") is True
    assert read_active(path, "crosshairs") is False
    write_active(path, "mousehighlighter", False)
    assert read_active(path, "mousehighlighter") is False
    assert [entry.name for entry in path.parent.iterdir()] == ["mouse-tools.json"]


def test_a_broken_file_or_no_folder_keeps_nothing(tmp_path: Path) -> None:
    path = tmp_path / "mouse-tools.json"
    path.write_text("[", encoding="utf-8")
    assert read_active(path, "mousehighlighter") is None
    write_active(None, "mousehighlighter", True)
    assert read_active(None, "mousehighlighter") is None
