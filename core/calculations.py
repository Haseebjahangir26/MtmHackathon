"""Pure arithmetic helpers. All quantities in the plan are computed here or in the
planners with plain Python, never by a model."""
from __future__ import annotations

import math
from typing import Optional

from core.knowledge import Facts


def ceil_div(a: float, b: float) -> int:
    return int(math.ceil(a / b))


def participants(f: Facts) -> dict:
    """Students and teams, derived from whichever of (students, teams, team_size) were stated."""
    students, teams, size = f.num("students"), f.num("teams"), f.num("team_size")
    derived = []
    if students is None and teams and size:
        students = teams * size; derived.append("students = teams x team_size")
    if teams is None and students and size:
        teams = ceil_div(students, size); derived.append("teams = ceil(students / team_size)")
    return {"students": int(students) if students is not None else None,
            "teams": int(teams) if teams is not None else None,
            "team_size": int(size) if size is not None else None, "derived": derived}


def headcount(f: Facts, judges_used: Optional[int]) -> dict:
    p = participants(f)
    staff = int(f.num("staff") or 0)
    groups = {str(c.subject or "other"): int(c.num() or 0) for c in f.all("attendee_group")}
    total = (p["students"] or 0) + staff + (judges_used or 0) + sum(groups.values())
    return {"students": p["students"], "staff": staff, "judges": judges_used or 0, "other_groups": groups,
            "total": total, "staff_stated": f.one("staff") is not None}


def fmt_time(start: str, offset_min: int) -> str:
    try:
        h, m = [int(x) for x in start.split(":")[:2]]
    except Exception:  # noqa: BLE001
        h, m = 0, 0
    t = h * 60 + m + offset_min
    return f"{(t // 60) % 24:02d}:{t % 60:02d}"


def pkr(x) -> str:
    try:
        return f"Rs {int(round(float(x))):,}"
    except Exception:  # noqa: BLE001
        return "—"
