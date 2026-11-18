"""Dependency graph between planning areas: a change in one area invalidates the areas downstream."""
from __future__ import annotations

import json

# area -> areas whose decisions depend on it
GRAPH = {
    "general": ["judging", "venue", "food", "schedule", "budget"],  # attendance drives everything
    "judging": ["food", "venue", "schedule", "budget"],  # judges eat, sit, take time, cost money
    "venue": ["budget"],
    "food": ["schedule", "budget"],  # lunch block exists only if food is served
    "schedule": ["judging"],  # schedule window may force more parallel judges
    "budget": ["food"],  # budget pressure may force cheaper catering
}
AREAS = ["venue", "schedule", "food", "judging", "budget"]


def affected(domains: set[str]) -> set[str]:
    seen, stack = set(), list(domains)
    while stack:
        d = stack.pop()
        if d in seen:
            continue
        seen.add(d)
        stack.extend(GRAPH.get(d, []))
    return {d for d in seen if d in AREAS}


def domain_summary(plan: dict) -> dict:
    """Compact, comparable figures per area (used for before/after diffs)."""
    v, fd, j, s, b, hc = (plan[k] for k in ("venue", "food", "judging", "schedule", "budget", "headcount"))
    return {
        "venue": {"venue": (v.get("chosen") or {}).get("venue"), "cost": v.get("cost"), "seats_needed": v.get("seats_needed")},
        "food": {"option": (fd.get("chosen") or {}).get("option"), "meals": fd.get("quantity"), "cost": fd.get("cost"),
                 "price_per_head": (fd.get("chosen") or {}).get("price_per_head")},
        "judging": {"judges": j.get("judges_used"), "rounds": j.get("rounds"), "minutes": j.get("judging_minutes"),
                    "cost": j.get("cost")},
        "schedule": {"blocks": [f"{x['start']}-{x['end']} {x['activity']}" for x in s.get("blocks", [])]},
        "budget": {"total": b.get("total"), "remaining": b.get("remaining"), "budget": b.get("budget"),
                   "lines": {l["item"]: l["amount"] for l in b.get("lines", [])},
                   "proposed": {p["item"]: p["amount"] for p in b.get("proposed", [])}},
        "headcount": {"total": hc.get("total")},
    }


def diff(old: dict | None, new: dict) -> dict:
    if not old:
        return {a: {"before": None, "after": new[a]} for a in AREAS}
    out = {}
    for a in AREAS:
        if json.dumps(old.get(a), sort_keys=True, default=str) != json.dumps(new.get(a), sort_keys=True, default=str):
            out[a] = {"before": old.get(a), "after": new.get(a)}
    return out
