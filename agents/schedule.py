"""Schedule planner (deterministic): non-overlapping timetable that fits the stated duration,
contains every mandatory break/activity, and runs judging after hacking."""
from __future__ import annotations

from core.calculations import fmt_time
from core.knowledge import Facts
from core.models import norm

# Planner defaults for activities the messages usually do not specify. Shown as assumptions.
DEFAULTS = {"opening": 10, "lunch": 30, "closing": 15}
MIN_DEFAULTS = {"opening": 5, "lunch": 20, "closing": 10}


def plan(f: Facts, judging_minutes, has_food: bool, default_start: str = "10:00", squeeze: bool = False) -> dict:
    dur_c = f.one("event_duration_minutes")
    duration = int(dur_c.num()) if dur_c else None
    start_c = f.one("event_start")
    start = str(start_c.value) if start_c else default_start
    assumptions = [] if start_c else [f"Start time not stated; assumed {default_start}."]
    end_c = f.one("event_end_by")
    if not start_c and end_c and duration:
        try:  # latest-end rule with no start time: start early enough to finish on time
            eh, em = [int(x) for x in str(end_c.value).split(":")[:2]]
            sh, sm = [int(x) for x in start.split(":")[:2]]
            if sh * 60 + sm + duration > eh * 60 + em:
                t = eh * 60 + em - duration
                start = f"{t // 60:02d}:{t % 60:02d}"
                assumptions = [f"Start time not stated; set to {start} to finish by {end_c.value}."]
        except Exception:  # noqa: BLE001
            pass
    if duration is None:
        return {"ok": False, "duration": None, "blocks": [], "warnings": ["Event duration not stated."],
                "assumptions": assumptions, "start": start, "evidence": []}
    d = MIN_DEFAULTS if squeeze else DEFAULTS
    breaks = [(c.subject or "break", int(c.num() or 0), c.id) for c in f.all("break_required")]
    acts = [(c.subject or "activity", int(c.num() or 0), c.id) for c in f.all("activity_required")]
    named = {norm(n) for n, _, _ in breaks + acts}
    opening = next((a for a in acts if "open" in norm(a[0])), ("Opening & briefing", d["opening"], None))
    closing = next((a for a in acts if "clos" in norm(a[0]) or "prize" in norm(a[0]) or "result" in norm(a[0])),
                   ("Results & closing", d["closing"], None))
    lunch = next((b for b in breaks if "lunch" in norm(b[0]) or "meal" in norm(b[0])), None)
    if lunch is None and has_food and "lunch" not in named:
        lunch = ("Lunch", d["lunch"], None)
    other_breaks = [b for b in breaks if b is not lunch]
    other_acts = [a for a in acts if a is not opening and a is not closing]
    jm = int(judging_minutes or 0)
    fixed = opening[1] + closing[1] + jm + (lunch[1] if lunch else 0) + sum(b[1] for b in other_breaks) + \
        sum(a[1] for a in other_acts)
    hacking = duration - fixed
    for n, m, i in (opening, closing, lunch or (None, None, None)):
        if n and i is None:
            assumptions.append(f"'{n}' duration {m} min is a planner default (not stated in messages).")
    seq = []
    h1 = (max(hacking, 0) // 2 // 5) * 5
    h2 = max(hacking, 0) - h1
    seq.append((opening[0], opening[1], "activity", opening[2]))
    seq.append(("Hacking session 1", h1, "hacking", None))
    if lunch:
        seq.append((lunch[0], lunch[1], "break", lunch[2]))
    for n, m, i in other_breaks:
        seq.append((n, m, "break (mandatory)", i))
    seq.append(("Hacking session 2", h2, "hacking", None))
    for n, m, i in other_acts:
        seq.append((n, m, "activity (mandatory)", i))
    if jm:
        seq.append(("Judging (parallel)", jm, "judging", None))
    seq.append((closing[0], closing[1], "activity", closing[2]))
    blocks, t = [], 0
    for n, m, typ, cid in seq:
        if m <= 0:
            continue
        blocks.append({"activity": n, "type": typ, "start_min": t, "end_min": t + m, "minutes": m,
                       "start": fmt_time(start, t), "end": fmt_time(start, t + m), "evidence": cid})
        t += m
    judging_start = next((b["start_min"] for b in blocks if b["type"] == "judging"), None)
    return {"ok": hacking >= 0, "duration": duration, "start": start, "blocks": blocks, "total_minutes": t,
            "hacking_minutes": hacking, "judging_start_min": judging_start,
            "required_breaks": [{"name": n, "minutes": m, "claim": i} for n, m, i in breaks],
            "required_activities": [{"name": n, "minutes": m, "claim": i} for n, m, i in acts],
            "warnings": ([] if hacking >= 0 else [f"Activities exceed duration by {-hacking} min."]) +
                        ([f"Only {hacking} min of hacking time."] if 0 <= hacking < duration * 0.4 else []),
            "assumptions": assumptions, "evidence": [dur_c.id] + [i for _, _, i in breaks]}
