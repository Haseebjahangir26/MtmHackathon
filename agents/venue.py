"""Venue planner (deterministic): cheapest venue that satisfies capacity and every requirement.

A model call is used only when a stated requirement does not match any known venue
feature token (genuine language reasoning); results are cached in state."""
from __future__ import annotations

import json

from core.knowledge import Facts
from core.models import norm


def venues(f: Facts) -> dict[str, dict]:
    vs: dict[str, dict] = {}

    def get(c):
        k = norm(c.subject)
        return vs.setdefault(k, {"name": c.subject, "capacity": None, "price": None, "features": set(),
                                 "unavailable": None, "evidence": []})

    for c in f.all("venue_capacity"):
        v = get(c); v["capacity"] = c.num(); v["evidence"].append(c.id)
    for c in f.all("venue_price"):
        v = get(c); v["price"] = c.num(); v["evidence"].append(c.id)
    for c in f.all("venue_feature"):
        v = get(c); v["features"].add(norm(c.value)); v["evidence"].append(c.id)
    for c in f.all("venue_unavailable"):
        v = get(c); v["unavailable"] = str(c.value or "unavailable"); v["evidence"].append(c.id)
    # use latest-by-subject for numeric fields
    for kind, field in (("venue_capacity", "capacity"), ("venue_price", "price")):
        for k, c in f.by_subject(kind).items():
            if k in vs:
                vs[k][field] = c.num()
    return vs


def requirements(f: Facts) -> list[str]:
    return sorted({norm(c.value) for c in f.all("venue_requirement") if c.value})


def unmatched_requirements(f: Facts, cache: dict) -> list[str]:
    vs = venues(f)
    known = set().union(*[v["features"] for v in vs.values()]) if vs else set()
    return [r for r in requirements(f) if r not in known and f"venue|{r}" not in cache]


def specialist_prompt(f: Facts, req: str, msgs: dict) -> tuple[str, str]:
    vs = venues(f)
    msg_ids = sorted({c.msg for c in f.claims if c.domain == "venue"})
    system = ('Decide which venues satisfy a requirement, using only the evidence. JSON only: '
              '{"venues":{"<venue>":true|false|null},"why":"<=20 words"}. null = evidence does not say.')
    user = (f"REQUIREMENT: {req}\nVENUES: {', '.join(v['name'] for v in vs.values())}\nEVIDENCE:\n" +
            "\n".join(f"{m} | {msgs[m].text}" for m in msg_ids if m in msgs))
    return system, user


def apply_specialist(text: str, req: str, cache: dict, f: Facts) -> str:
    from agents.reader import _loads_lenient
    d = _loads_lenient(text) or {}
    res = {norm(k): v for k, v in (d.get("venues") or {}).items()}
    cache[f"venue|{req}"] = {"result": res, "why": d.get("why", "")}
    return d.get("why", "")


def plan(f: Facts, need_seats: int, cache: dict) -> dict:
    vs = venues(f)
    reqs = requirements(f)
    cap_price = next((c.num() for c in f.all("cap") if norm(c.subject) in ("venue price", "venue cost")), None)
    def satisfies(r, k, v):
        sp = cache.get(f"venue|{r}")
        return r in v["features"] or bool(sp and sp["result"].get(k) is True)

    # A requirement no venue is known to meet or fail cannot be checked: keep it visible as a warning
    # instead of silently passing or wrongly blocking every venue.
    unverifiable = {r for r in reqs if not any(satisfies(r, k, v) for k, v in vs.items())
                    and not any((cache.get(f"venue|{r}") or {}).get("result", {}).get(k) is False for k in vs)}
    rows, notes = [], []
    for k, v in vs.items():
        reasons = []
        if v["capacity"] is None:
            reasons.append("capacity unknown")
        elif v["capacity"] < need_seats:
            reasons.append(f"seats {int(v['capacity'])} < {need_seats} needed")
        if v["price"] is None:
            reasons.append("price unknown")
        if v["unavailable"]:
            reasons.append(f"unavailable ({v['unavailable']})")
        for r in reqs:
            if satisfies(r, k, v):
                continue
            if r in unverifiable:
                notes.append(f"'{r}' not verifiable for {v['name']} from the messages")
                continue
            reasons.append(f"missing requirement '{r}'")
        if cap_price is not None and v["price"] is not None and v["price"] > cap_price:
            reasons.append(f"price above cap {int(cap_price)}")
        rows.append({"venue": v["name"], "capacity": v["capacity"], "price": v["price"],
                     "features": ", ".join(sorted(v["features"])) or "—", "feasible": not reasons,
                     "reason": "; ".join(reasons) or "meets all constraints", "evidence": v["evidence"]})
    feas = sorted([r for r in rows if r["feasible"]], key=lambda r: (r["price"], -(r["capacity"] or 0)))
    chosen = feas[0] if feas else None
    return {"ok": chosen is not None, "chosen": chosen, "options": sorted(rows, key=lambda r: (r["price"] or 0)),
            "seats_needed": need_seats, "requirements": reqs, "cost": chosen["price"] if chosen else 0,
            "warnings": ([] if chosen else ["No venue satisfies all constraints."]) +
                        [f"Requirement '{r}' could not be verified for any venue." for r in sorted(unverifiable)],
            "unverified": sorted(unverifiable),
            "evidence": chosen["evidence"] if chosen else []}


def cache_json(cache):
    return json.dumps(cache)
