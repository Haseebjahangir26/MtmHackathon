"""JSON persistence for state (messages, ledger, versions, trace)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
STATE_FILE = DATA / "state.json"


def save(state: dict, path: Path = STATE_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, default=str)
    os.replace(tmp, path)  # atomic: a crash never leaves a half-written state


def load(path: Path = STATE_FILE) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
