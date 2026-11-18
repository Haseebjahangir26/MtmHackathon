"""Human-readable exports of the plan and the rejected messages."""
from __future__ import annotations

from core.calculations import pkr


def plan_markdown(cur: dict, state: dict) -> str:
    P, V = cur["plan"], cur["validation"]
    v, fd, j, s, b, hc = (P[k] for k in ("venue", "food", "judging", "schedule", "budget", "headcount"))
    L = [f"# CONCORD (Event Planner) — plan — version {cur['n']} ({cur['run']})",
         f"**Status: {'FEASIBLE' if V['feasible'] else 'NOT FEASIBLE'}** — {V['hard_failures']} hard failures, "
         f"{V['warnings']} warnings · {cur['timestamp']}", "",
         f"People on site: **{hc['total']}** = {hc['students']} students + {hc['staff']} staff + {hc['judges']} judges"
         + "".join(f" + {n} {k}" for k, n in hc["other_groups"].items()) + f" · {P['participants']['teams']} teams", "",
         "## Venue"]
    ch = v.get("chosen")
    L.append(f"- **{ch['venue']}** — {int(ch['capacity'])} seats, {pkr(ch['price'])}" if ch else "- No feasible venue")
    L += [f"  - {o['venue']}: {'feasible' if o['feasible'] else 'rejected'} ({o['reason']})" for o in v["options"]]
    L += ["", "## Schedule", f"Duration {s.get('duration')} min, start {s.get('start')}", "",
          "| Start | End | Activity | Min |", "|---|---|---|---|"]
    L += [f"| {x['start']} | {x['end']} | {x['activity']} | {x['minutes']} |" for x in s.get("blocks", [])]
    L += [f"- _Assumption: {a}_" for a in s.get("assumptions", [])]
    fch = fd.get("chosen")
    L += ["", "## Food",
          f"- **{fch['option']}**: {fd['quantity']} meals × {pkr(fch['price_per_head'])} + delivery {pkr(fch['delivery_fee'])} = **{pkr(fd['cost'])}**"
          if fch else "- No feasible catering"]
    L += [f"  - {o['option']}: {pkr(o['price_per_head'])}/head → {pkr(o['cost'])} ({o['reason']})" for o in fd["options"]]
    L += ["", "## Judging"]
    if j.get("ok"):
        L += [f"- **{j['judges_used']} judges** (needed {j['judges_needed']}, confirmed {j.get('judges_available')}), "
              f"max {j['max_load']} teams each, {j['rounds']} rounds × {j.get('minutes_per_team')} min = {j['judging_minutes']} min, "
              f"honoraria {pkr(j['cost'])}"]
        L += [f"  - {a['judge']}: {a['teams']}" for a in j["allocation"]]
    L += ["", "## Budget", "| Item | Status | Amount |", "|---|---|---|"]
    L += [f"| {l['item']} | {l['status']} | {pkr(l['amount'])} |" for l in b["lines"]]
    L += [f"| **Total** | | **{pkr(b['total'])}** |", f"| Approved budget | | {pkr(b['budget'])} |",
          f"| **Remaining** | | **{pkr(b['remaining'])}** |"]
    for p in b["proposed"]:
        L.append(f"- Proposed, NOT approved, excluded: {p['item']} {pkr(p['amount'])} (would fit: {'yes' if p['would_fit'] else 'no'})")
    L += ["", "## Validation", "| | Type | Area | Constraint | Detail |", "|---|---|---|---|---|"]
    L += [f"| {'PASS' if c['passed'] else 'FAIL' if c['hard'] else 'WARN'} | {'hard' if c['hard'] else 'soft'} | {c['domain']} | "
          f"{c['constraint']} | {c['detail']} |" for c in V["checks"]]
    L += ["", rejected_markdown(state)]
    return "\n".join(L)


def rejected_markdown(state: dict) -> str:
    L = ["## Rejected and superseded information"]
    msgs = {m["id"]: m for m in state["messages"]}
    for c in state["claims"]:
        if c["status"] in ("rejected", "superseded"):
            m = msgs.get(c["msg"], {})
            L.append(f"- **{c['status'].upper()}** {c['id']} from {c['msg']} ({m.get('sender') or '?'}): "
                     f"{c['kind']} {c.get('subject') or ''} = {c['value']} — {c.get('resolution') or c.get('reason') or ''}")
            L.append(f"  - Original message: \"{m.get('text', '')}\"")
    for m in state["messages"]:
        if m.get("status") in ("duplicate", "irrelevant") or not m.get("relevant", True):
            L.append(f"- **{(m.get('status') or 'irrelevant').upper()}** {m['id']}: \"{m['text']}\" — {m.get('note') or ''}")
    return "\n".join(L)
