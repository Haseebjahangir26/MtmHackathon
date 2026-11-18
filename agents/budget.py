"""Budget planner (deterministic): approved budget vs every committed/planned cost."""
from __future__ import annotations

from core.knowledge import Facts
from core.models import norm


def plan(f: Facts, venue_cost, food_cost, judging_cost, venue_name=None, food_name=None) -> dict:
    total_c = f.one("budget_total")
    if total_c is None:  # "ceiling of Rs X for everything" is the same thing as an approved total budget
        total_c = next((c for c in f.all("cap") if norm(c.subject) in ("total cost", "total budget", "total")), None)
    budget = total_c.num() if total_c else None
    lines = [
        {"item": f"Venue{(' – ' + str(venue_name)) if venue_name else ''}", "domain": "venue", "amount": venue_cost, "status": "planned"},
        {"item": f"Food{(' – ' + str(food_name)) if food_name else ''}", "domain": "food", "amount": food_cost, "status": "planned"},
        {"item": "Judge honoraria", "domain": "judging", "amount": judging_cost, "status": "planned"},
    ]
    committed = f.by_subject("expense_committed")
    for k, c in committed.items():
        lines.append({"item": str(c.subject), "domain": "budget", "amount": c.num() or 0, "status": "committed",
                      "claim": c.id})
    approved = f.by_subject("expense_approved")
    for k, c in approved.items():
        if k in committed:
            continue
        lines.append({"item": str(c.subject), "domain": "budget", "amount": c.num() or 0, "status": "approved",
                      "claim": c.id})
    total = sum(float(l["amount"] or 0) for l in lines)
    remaining = (budget - total) if budget is not None else None
    proposed = []
    for k, c in f.by_subject("expense_proposed").items():
        if k in approved or k in committed:
            continue
        amt = c.num() or 0
        proposed.append({"item": str(c.subject), "amount": amt, "claim": c.id, "status": "proposed – not approved",
                         "would_fit": remaining is not None and amt <= remaining})
    caps = [{"metric": norm(c.subject), "max": c.num(), "claim": c.id} for c in f.all("cap")]
    return {"ok": budget is not None and total <= budget, "budget": budget, "total": total, "remaining": remaining,
            "lines": lines, "proposed": proposed, "caps": caps,
            "warnings": [] if budget is not None else ["Approved budget not stated."],
            "evidence": [total_c.id] if total_c else []}
