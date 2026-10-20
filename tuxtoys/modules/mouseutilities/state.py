"""Whether a mouse tool that is turned on and off by its shortcut is on, kept for the session
in $XDG_RUNTIME_DIR, so the helper starting again with new settings does not turn it off.
The folder goes when the session ends, so the next login starts from the tool's settings.
"""

import contextlib
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path


def state_path(environ: Mapping[str, str] = os.environ) -> Path | None:
    """The session's file, or None where the session has no runtime folder."""
    runtime = environ.get("XDG_RUNTIME_DIR", "")
    if not runtime or not Path(runtime).is_absolute():
        return None
    return Path(runtime) / "tuxtoys" / "mouse-tools.json"


def _read(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def read_active(path: Path | None, tool: str) -> bool | None:
    """Whether the tool was on in this session, or None if nothing was kept."""
    if path is None:
        return None
    value = _read(path).get(tool)
    return value if isinstance(value, bool) else None


def write_active(path: Path | None, tool: str, active: bool) -> None:
    """Keeps whether the tool is on, written atomically; a session without a runtime folder
    keeps nothing.
    """
    if path is None:
        return
    data = {**_read(path), tool: active}
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".mouse-tools.", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                json.dump(data, file)
            os.replace(temporary, path)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temporary)
            raise
