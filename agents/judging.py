"""Judging planner (deterministic): minimum judges, load per judge, parallel rounds, allocation."""
from __future__ import annotations

from typing import Optional

from core.calculations import ceil_div, participants
from core.knowledge import Facts


def plan(f: Facts, extra_judges: int = 0) -> dict:
    p = participants(f)
    teams = p["teams"]
    max_per = f.num("judge_max_teams")
    if max_per is None:  # same rule sometimes expressed as a cap
        max_per = next((c.num() for c in f.all("cap") if c.subject and "per judge" in str(c.subject).replace("_", " ")), None)
    mpt = f.num("judge_minutes_per_team")
    avail = f.num("judges_available")
    hon = f.num("judge_honorarium") or 0
    warnings, assumptions = [], []
    if teams is None:
        return {"ok": False, "error": "Number of teams unknown", "judges_used": 0, "judging_minutes": 0,
                "cost": 0, "warnings": ["Team count could not be determined."], "allocation": []}
    if max_per:
        needed = ceil_div(teams, max_per)
    else:
        needed = 1
        assumptions.append("No max-teams-per-judge rule stated; minimum is 1 judge (time permitting).")
    used = needed + extra_judges
    if avail is not None and used > avail:
        used = max(needed, int(avail)) if avail >= needed else int(avail)
    rounds = ceil_div(teams, used) if used else None
    minutes = int(rounds * mpt) if (rounds and mpt) else None
    if mpt is None:
        warnings.append("Judging minutes per team not stated; judging duration unknown.")
    alloc, start = [], 1
    if used:
        base, rem = divmod(teams, used)
        for j in range(used):
            k = base + (1 if j < rem else 0)
            alloc.append({"judge": f"Judge {j + 1}", "teams": f"T{start}–T{start + k - 1}" if k > 1 else f"T{start}",
                          "team_count": k, "minutes": int(k * mpt) if mpt else None})
            start += k
    late = [{"who": c.subject, "minutes": c.num(), "claim": c.id} for c in f.all("judge_late_minutes")]
    return {"ok": True, "teams": teams, "max_teams_per_judge": max_per, "minutes_per_team": mpt,
            "judges_available": int(avail) if avail is not None else None, "judges_needed": needed,
            "judges_used": used, "rounds": rounds, "judging_minutes": minutes, "honorarium": hon,
            "cost": used * hon, "max_load": max((a["team_count"] for a in alloc), default=0),
            "allocation": alloc, "late": late, "warnings": warnings, "assumptions": assumptions,
            "evidence": [c.id for k in ("judge_max_teams", "judge_minutes_per_team", "judges_available",
                                        "judge_honorarium") for c in [f.one(k)] if c]}
