"""Constraint validation engine. Deterministic; the plan is FEASIBLE only if every hard check passes."""
from __future__ import annotations

from core.calculations import pkr
from core.knowledge import Facts
from core.models import norm


def _chk(cid, domain, hard, passed, constraint, detail, evidence=None, suggestion=""):
    return {"id": cid, "domain": domain, "hard": hard, "passed": bool(passed), "constraint": constraint,
            "detail": detail, "evidence": [e for e in (evidence or []) if e], "suggestion": "" if passed else suggestion}


def validate(plan: dict, f: Facts) -> dict:
    c = []
    hc, v, fd, j, s, b = (plan[k] for k in ("headcount", "venue", "food", "judging", "schedule", "budget"))
    p = plan["participants"]
    c.append(_chk("participants_known", "general", True, p["students"] and p["teams"],
                  "Student and team counts known", f"{p['students']} students in {p['teams']} teams",
                  suggestion="Need the approved number of students/teams."))
    if not hc.get("staff_stated"):
        c.append(_chk("staff_known", "food", False, False, "Staff count stated", "No staff count in messages; 0 assumed",
                      suggestion="Confirm staff on duty."))
    # venue
    ch = v.get("chosen")
    c.append(_chk("venue_selected", "venue", True, ch, "A venue satisfying all constraints is selected",
                  ch["venue"] if ch else "none feasible", v.get("evidence"),
                  "Find a larger venue, relax a requirement, or reduce attendance."))
    if ch:
        c.append(_chk("venue_capacity", "venue", True, (ch["capacity"] or 0) >= hc["total"],
                      "Venue capacity ≥ people on site", f"{int(ch['capacity'])} seats for {hc['total']} people",
                      ch["evidence"], "Choose a venue with more seats."))
        c.append(_chk("venue_requirements", "venue", True, True, "Venue meets stated requirements",
                      ", ".join(v["requirements"]) or "no special requirements stated", ch["evidence"]))
    for r in v.get("unverified", []):
        c.append(_chk(f"venue_unverified_{r}", "venue", False, False, f"Venue requirement '{r}' verified",
                      "no message says whether any venue meets it", suggestion="Confirm with the venue."))
    # food
    fch = fd.get("chosen")
    for r in fd.get("unverified", []):
        c.append(_chk(f"food_unverified_{r}", "food", False, False, f"Food requirement '{r}' verified",
                      "no caterer message confirms it", suggestion="Confirm with the caterer."))
    c.append(_chk("food_selected", "food", True, fch, "A catering option meeting requirements is selected",
                  fch["option"] if fch else "none feasible", fd.get("evidence"), "Get a compliant catering quote."))
    c.append(_chk("food_quantity", "food", True, fd["quantity"] >= hc["total"], "Meals ≥ people to feed",
                  f"{fd['quantity']} meals for {hc['total']} people (students {hc['students']}, staff {hc['staff']}, "
                  f"judges {hc['judges']}{', other ' + str(sum(hc['other_groups'].values())) if hc['other_groups'] else ''})",
                  [fd.get("order_quantity_claim")], f"Order at least {hc['total']} meals."))
    # judging
    if j.get("ok"):
        avail = j.get("judges_available")
        c.append(_chk("judges_enough", "judging", True, avail is not None and avail >= j["judges_needed"],
                      "Confirmed judges ≥ judges needed",
                      f"{avail if avail is not None else 'unknown'} available, {j['judges_needed']} needed "
                      f"(ceil({j['teams']} teams / {j.get('max_teams_per_judge') or '?'} per judge))", j.get("evidence"),
                      f"Confirm at least {j['judges_needed']} judges."))
        if j.get("max_teams_per_judge"):
            c.append(_chk("judge_load", "judging", True, j["max_load"] <= j["max_teams_per_judge"],
                          "Teams per judge ≤ stated maximum", f"max load {j['max_load']} ≤ {int(j['max_teams_per_judge'])}",
                          j.get("evidence"), "Add judges."))
        c.append(_chk("judging_time_known", "judging", False, j.get("judging_minutes") is not None,
                      "Judging duration computable", f"{j.get('rounds')} rounds × {j.get('minutes_per_team')} min = "
                      f"{j.get('judging_minutes')} min", j.get("evidence"), "State minutes per team."))
    else:
        c.append(_chk("judging_plan", "judging", True, False, "Judging plan", j.get("error", "failed")))
    # schedule
    if s.get("duration") is not None:
        c.append(_chk("schedule_duration", "schedule", True, s["ok"] and s["total_minutes"] == s["duration"],
                      "Timetable fills exactly the approved duration",
                      f"{s['total_minutes']} of {s['duration']} min (hacking {s['hacking_minutes']} min)", s.get("evidence"),
                      "Shorten activities or add judges to shorten judging."))
        names = [norm(bk["activity"]) for bk in s["blocks"]]
        miss = [b_["name"] for b_ in s["required_breaks"] + s["required_activities"] if norm(b_["name"]) not in names]
        c.append(_chk("schedule_mandatory", "schedule", True, not miss, "All mandatory breaks/activities scheduled",
                      "missing: " + ", ".join(miss) if miss else
                      ", ".join(f"{x['name']} {x['minutes']}m" for x in s["required_breaks"] + s["required_activities"]) or "none stated",
                      [x["claim"] for x in s["required_breaks"]], "Insert the missing block."))
        end_by = f.one("event_end_by")
        if end_by and s["blocks"]:
            def _m(t):
                try:
                    h, mm = [int(x) for x in str(t).split(":")[:2]]; return h * 60 + mm
                except Exception:  # noqa: BLE001
                    return None
            lim, end = _m(end_by.value), _m(s["blocks"][-1]["end"])
            if lim is not None and end is not None:
                c.append(_chk("schedule_end_by", "schedule", True, end <= lim, f"Event ends by {end_by.value}",
                              f"ends {s['blocks'][-1]['end']}", [end_by.id], "Start earlier or shorten activities."))
        ok_seq = all(a["end_min"] == bb["start_min"] for a, bb in zip(s["blocks"], s["blocks"][1:]))
        c.append(_chk("schedule_no_overlap", "schedule", True, ok_seq, "Blocks are sequential, no overlaps", "checked"))
        if j.get("judging_minutes"):
            hack_end = max((bk["end_min"] for bk in s["blocks"] if bk["type"] == "hacking"), default=0)
            c.append(_chk("judging_after_hacking", "schedule", True, (s["judging_start_min"] or 0) >= hack_end,
                          "Judging starts after hacking ends", f"judging at +{s['judging_start_min']} min"))
        for lt in j.get("late", []):
            okl = s.get("judging_start_min") is not None and (lt["minutes"] or 0) <= s["judging_start_min"]
            c.append(_chk(f"late_{lt['claim']}", "judging", False, okl, "Late arrival before judging starts",
                          f"{lt['who'] or 'someone'} up to {lt['minutes']} min late; judging starts at +{s.get('judging_start_min')} min",
                          [lt["claim"]], "Move that judge to a later slot."))
    else:
        c.append(_chk("schedule_duration", "schedule", True, False, "Event duration known", "not stated",
                      suggestion="Need the approved event duration."))
    # budget
    c.append(_chk("budget_known", "budget", True, b["budget"] is not None, "Approved budget known",
                  pkr(b["budget"]) if b["budget"] is not None else "not stated", b.get("evidence")))
    if b["budget"] is not None:
        c.append(_chk("budget_within", "budget", True, b["total"] <= b["budget"], "Total cost ≤ approved budget",
                      f"{pkr(b['total'])} of {pkr(b['budget'])} (remaining {pkr(b['remaining'])})", b.get("evidence"),
                      "Cheaper catering/venue or ask for more budget."))
    metrics = {"total cost": b["total"], "venue cost": v.get("cost"), "food cost": fd.get("cost"),
               "judging cost": j.get("cost"), "judges": j.get("judges_used"), "headcount": hc["total"],
               "teams per judge": j.get("max_load"), "food price per head": (fch or {}).get("price_per_head"),
               "venue price": (ch or {}).get("price")}
    for cap in b.get("caps", []):
        val = metrics.get(cap["metric"])
        if val is not None and cap["max"] is not None:
            c.append(_chk(f"cap_{cap['claim']}", "budget", True, val <= cap["max"], f"{cap['metric']} ≤ {cap['max']:,.0f}",
                          f"{val:,.0f}", [cap["claim"]], "Reduce that cost."))
    # coverage
    cov = all([ch, fch, j.get("ok"), s.get("blocks"), b["budget"] is not None])
    c.append(_chk("all_areas", "general", True, cov, "All five areas planned", "venue, schedule, food, judging, budget"))
    # honesty: unresolved items
    for cl in f.claims:
        if cl.status == "uncertain" and cl.kind != "judge_late_minutes":
            c.append(_chk(f"uncertain_{cl.id}", cl.domain, False, False, "Uncertain fact used",
                          f"{cl.kind} {cl.subject or ''}={cl.value}: {cl.reason or ''}", [cl.id], "Confirm with sender."))
        if cl.kind == "note":
            c.append(_chk(f"note_{cl.id}", cl.domain, False, False, "Unstructured constraint – review",
                          f"{cl.value}", [cl.id], "Human review: constraint has no automatic check."))
    for cl in f.pending:
        c.append(_chk(f"pending_{cl.id}", cl.domain, False, False, "Proposal awaiting approval",
                      f"{cl.kind} {cl.subject or ''}={cl.value}", [cl.id], "Needs approval before it can apply."))
    hard_fail = [x for x in c if x["hard"] and not x["passed"]]
    return {"feasible": not hard_fail, "checks": c, "hard_failures": len(hard_fail),
            "warnings": sum(1 for x in c if not x["hard"] and not x["passed"])}
