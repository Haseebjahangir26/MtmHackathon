"""Food planner (deterministic): headcount-based quantity, latest valid prices, requirement checks."""
from __future__ import annotations

from typing import Optional

from core.knowledge import Facts
from core.models import norm

PREFERRED_WORDS = ("standard", "regular", "normal", "default")


def options(f: Facts) -> list[dict]:
    fees = f.by_subject("food_delivery_fee")
    generic_fee = fees.get("")
    feats: dict[str, set] = {}
    for c in f.all("food_feature"):
        feats.setdefault(norm(c.subject), set()).add(norm(c.value))
    out = []
    for k, c in f.by_subject("food_price_per_head").items():
        fee_c = fees.get(k) or generic_fee
        out.append({"option": c.subject or "meal", "key": k, "price_per_head": c.num(),
                    "delivery_fee": fee_c.num() if fee_c else 0, "features": feats.get(k, set()),
                    "first_seen": c.seq, "evidence": [c.id] + ([fee_c.id] if fee_c else [])})
    return out


def requirements(f: Facts) -> list[str]:
    return sorted({norm(c.value) for c in f.all("food_requirement") if c.value})


def plan(f: Facts, headcount: int, cache: dict, policy: str = "standard-first",
         max_cost: Optional[float] = None) -> dict:
    opts = options(f)
    reqs = requirements(f)
    order_c = f.one("food_order_quantity")
    order_q = int(order_c.num()) if order_c and order_c.num() is not None else None
    qty = max(headcount, order_q or 0)
    cap_pp = next((c.num() for c in f.all("cap") if norm(c.subject) == "food price per head"), None)
    cap_cost = next((c.num() for c in f.all("cap") if norm(c.subject) == "food cost"), None)
    unverifiable = {r for r in reqs if not any(r in o["features"] for o in opts)}
    rows = []
    for o in opts:
        reasons = []
        for r in reqs:
            if r not in o["features"] and r not in unverifiable:
                reasons.append(f"does not meet '{r}'")
        cost = qty * (o["price_per_head"] or 0) + (o["delivery_fee"] or 0)
        if cap_pp is not None and (o["price_per_head"] or 0) > cap_pp:
            reasons.append(f"price per head above cap {int(cap_pp)}")
        if cap_cost is not None and cost > cap_cost:
            reasons.append(f"cost above food cap {int(cap_cost)}")
        rows.append({**o, "features": ", ".join(sorted(o["features"])) or "—", "quantity": qty, "cost": cost,
                     "feasible": not reasons, "reason": "; ".join(reasons) or "ok"})
    feas = [r for r in rows if r["feasible"]]

    def pref(r):
        is_std = any(w in norm(r["option"]) for w in PREFERRED_WORDS)
        return (0 if (policy == "standard-first" and is_std) else 1, r["cost"])

    chosen = None
    if feas:
        ranked = sorted(feas, key=pref)
        if max_cost is not None:
            within = [r for r in ranked if r["cost"] <= max_cost]
            chosen = within[0] if within else sorted(feas, key=lambda r: r["cost"])[0]
        else:
            chosen = ranked[0]
    warnings = []
    if not opts:
        warnings.append("No catering prices stated.")
    for r in sorted(unverifiable):
        warnings.append(f"Food requirement '{r}' not confirmed by any caterer message – confirm with caterer.")
    if order_q is not None and order_q < headcount:
        warnings.append(f"Order quantity {order_q} is below the {headcount} people to feed.")
    return {"ok": chosen is not None, "chosen": chosen, "options": rows, "headcount": headcount, "quantity": qty,
            "order_quantity_claim": order_c.id if order_c else None, "requirements": reqs, "unverified": sorted(unverifiable),
            "cost": chosen["cost"] if chosen else 0, "policy": policy, "warnings": warnings,
            "evidence": chosen["evidence"] if chosen else []}
