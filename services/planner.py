"""Runs the five deterministic planners in dependency order, with a small repair loop
(more parallel judges if the timetable overflows, cheaper catering if over budget)."""
from __future__ import annotations

from agents import budget as budget_a
from agents import food as food_a
from agents import judging as judging_a
from agents import schedule as schedule_a
from agents import venue as venue_a
from core.calculations import headcount, participants
from core.knowledge import Facts, Ledger


def build_plan(ledger: Ledger, cache: dict, settings: dict) -> dict:
    f = Facts(ledger)
    policy = settings.get("food_policy", "standard-first")
    start = settings.get("default_start", "10:00")
    extra, squeeze, notes = 0, False, []
    for _ in range(40):
        j = judging_a.plan(f, extra)
        hc = headcount(f, j.get("judges_used"))
        v = venue_a.plan(f, hc["total"], cache)
        fd = food_a.plan(f, hc["total"], cache, policy)
        s = schedule_a.plan(f, j.get("judging_minutes"), bool(fd["options"]), start, squeeze)
        if s.get("duration") is not None and not s["ok"]:
            if not squeeze:
                squeeze = True; notes.append("Timetable overflowed: shortened default activities."); continue
            avail = j.get("judges_available")
            if avail and j["judges_used"] < avail and j.get("rounds", 1) > 1:
                extra += 1; notes.append("Timetable overflowed: added a parallel judge."); continue
        break
    b = budget_a.plan(f, v.get("cost") or 0, fd.get("cost") or 0, j.get("cost") or 0,
                      (v.get("chosen") or {}).get("venue"), (fd.get("chosen") or {}).get("option"))
    if b["budget"] is not None and b["total"] > b["budget"] and fd.get("chosen"):
        over = b["total"] - b["budget"]
        fd2 = food_a.plan(f, hc["total"], cache, policy, max_cost=fd["cost"] - over)
        if fd2.get("chosen") and fd2["cost"] < fd["cost"]:
            notes.append(f"Over budget: switched catering to '{fd2['chosen']['option']}'.")
            fd = fd2
            b = budget_a.plan(f, v.get("cost") or 0, fd.get("cost") or 0, j.get("cost") or 0,
                              (v.get("chosen") or {}).get("venue"), fd["chosen"]["option"])
    return {"participants": participants(f), "headcount": hc, "venue": v, "food": fd, "judging": j,
            "schedule": s, "budget": b, "planner_notes": notes}


WHAT_IF_KINDS = {"students": "students", "staff": "staff", "budget_total": "budget", "judges_available": "judges available",
                 "judge_max_teams": "max teams per judge", "event_duration_minutes": "duration (min)"}


def what_if(ledger: Ledger, cache: dict, settings: dict, overrides: dict) -> tuple[dict, dict]:
    """Deterministic scenario: replace selected facts with hypothetical values and re-plan.
    Pure Python on a copy of the ledger: no model call, nothing persisted."""
    import copy

    from core.models import Claim
    from core.validator import validate
    from core.knowledge import Facts
    claims = copy.deepcopy(ledger.claims)
    for kind, val in overrides.items():
        for c in claims:
            if c.kind == kind and c.active:
                c.status = "superseded"
        claims.append(Claim(id=f"W-{kind}", msg="what-if", kind=kind, value=val, status="confirmed", authority=9,
                            domain="general", date="9999-12-31"))
    lg = Ledger(claims)
    plan = build_plan(lg, dict(cache), settings)
    return plan, validate(plan, Facts(lg))
