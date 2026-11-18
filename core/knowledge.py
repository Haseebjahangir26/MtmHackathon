"""Knowledge ledger + conflict engine.

Deterministic rules applied to claims from the reading agent:
  * explicit corrections supersede the facts they correct;
  * newer does NOT beat more authoritative for task-defining (governing) facts;
  * a proposal never becomes an approved fact or expense by itself;
  * older values are kept as `superseded`, never deleted;
  * rejected claims keep their explanation.
"""
from __future__ import annotations

from typing import Optional

from core.models import GOVERNING, KINDS, Claim, Message, norm

OPTION_KINDS = {"venue_capacity", "venue_price", "venue_feature", "venue_unavailable", "food_price_per_head",
                "food_delivery_fee", "food_feature", "judges_available", "judge_honorarium", "judge_late_minutes",
                "expense_committed", "expense_proposed", "food_order_quantity", "note"}


PKR_KINDS = {"budget_total", "venue_price", "food_price_per_head", "food_delivery_fee", "judge_honorarium",
             "expense_committed", "expense_proposed", "expense_approved"}
MIN_KINDS = {"event_duration_minutes", "judge_minutes_per_team", "judge_late_minutes", "break_required",
             "activity_required"}


def unit_for(kind: str):
    if kind in PKR_KINDS:
        return "PKR"
    if kind in MIN_KINDS:
        return "minutes"
    if kind in ("event_start", "event_end_by"):
        return "HH:MM"
    if kind == "judge_max_teams":
        return "teams/judge"
    if kind in ("teams",):
        return "teams"
    if kind in ("students", "staff", "attendee_group", "venue_capacity", "team_size", "judges_available",
                "food_order_quantity"):
        return "people" if kind != "food_order_quantity" else "meals"
    return None


def _date_key(c: Claim):
    # undated messages count as newest in arrival order (an update arrives after the pack)
    return (c.date or "9999", c.seq)


JUDGE_RULES = {"judge_minutes_per_team", "judge_max_teams"}


def is_pending(c: Claim) -> bool:
    """A proposal for a task-defining fact is NOT applied until approved."""
    if c.kind not in GOVERNING:
        return False
    if c.authority < 2:  # informal senders cannot set task-defining facts or approve spending
        return True
    return c.status == "proposed" and not c.kind in JUDGE_RULES


class Ledger:
    def __init__(self, claims: Optional[list[Claim]] = None):
        self.claims: list[Claim] = claims or []

    def by_id(self, cid: str) -> Optional[Claim]:
        return next((c for c in self.claims if c.id == cid), None)

    def active(self) -> list[Claim]:
        return [c for c in self.claims if c.active]

    def next_id(self) -> str:
        return f"C{len(self.claims) + 1}"

    # ------------------------------------------------------------------
    def integrate(self, new: list[Claim], msgs: dict[str, Message], log) -> list[Claim]:
        """Add new claims, resolving supersession/conflicts. `log(kind, text, msg, claim)`."""
        for c in new:
            m = msgs.get(c.msg)
            c.domain = (norm(c.subject) if c.kind == "note" and norm(c.subject) in
                        ("venue", "schedule", "food", "judging", "budget") else KINDS[c.kind][0])
            c.authority = m.authority if m else 1
            c.date = m.date if m else None
            c.seq = m.seq if m else 0
            c.sender = m.sender if m else None
            if not c.unit:
                c.unit = unit_for(c.kind)
        # chronological processing so "latest" is well defined
        for c in sorted(new, key=_date_key):
            c.id = self.next_id()
            self.claims.append(c)
            m = msgs.get(c.msg)
            if c.status == "irrelevant" or (m and not m.relevant):
                c.status = "irrelevant"
                continue
            if c.status == "rejected":
                c.resolution = f"Rejected by reading agent: {c.reason or 'conflicts with stated rules'}"
                log("rejected", c.resolution + f" [{describe(c)}]", c.msg, c.id)
                continue
            if c.kind in GOVERNING and c.authority < 2:
                rival = next((o for o in self.claims if o is not c and o.active and o.key() == c.key()
                              and not is_pending(o) and norm(o.value) != norm(c.value)), None)
                if rival:
                    c.status = "rejected"; c.related.append(rival.id)
                    c.resolution = (f"Rejected: tries to change an approved fact ({describe(rival)}, authority "
                                    f"{rival.authority}) from an informal/unverified source (authority {c.authority}).")
                    log("rejected", c.resolution, c.msg, c.id)
                    continue
                c.status = "proposed"
            if is_pending(c):
                c.resolution = ("Not applied: informal/unverified sender cannot set this." if c.authority < 2 else "Suggestion only: not applied to the plan until approved by an authority.")
                log("info", f"{describe(c)} kept as proposal (not applied).", c.msg, c.id)
                continue
            self._resolve(c, log)
        return new

    def _resolve(self, c: Claim, log):
        rivals = [o for o in self.claims if o is not c and o.active and o.key() == c.key()
                  and not is_pending(o)]
        # explicit reference to an earlier claim/message of the same kind but differently named subject
        if not rivals and c.supersedes_ref:
            ref = str(c.supersedes_ref).strip()
            rivals = [o for o in self.claims if o is not c and o.active and o.kind == c.kind
                      and (o.id == ref or o.msg == ref)]
        multi_valued = KINDS[c.kind][3]
        for o in rivals:
            if multi_valued:  # same fact repeated: just relate
                c.related.append(o.id); o.related.append(c.id)
                continue
            same_value = norm(o.value) == norm(c.value)
            older = bool(c.date and o.date and c.date < o.date)
            if older:
                c.status = "superseded"; c.superseded_by = o.id
                c.resolution = f"Outdated: {o.id} ({o.date}) is newer than this message ({c.date})."
                log("superseded", f"{describe(c)} is outdated; keeping {describe(o)}.", c.msg, c.id)
                return
            same_source = _same_sender(c.sender, o.sender)
            # Task-defining facts: only a higher authority, the top authority, or the original source may change them.
            governing_block = (c.kind in GOVERNING and not same_value and c.authority < 3 and not same_source
                               and c.authority <= o.authority)
            if (c.authority < o.authority or governing_block) and not same_value and not same_source:
                c.status = "rejected"
                c.resolution = (f"Rejected: tries to change an established fact ({describe(o)}, set by "
                                f"{o.sender or o.msg}, authority {o.authority}) from {c.sender or 'another sender'} "
                                f"(authority {c.authority}), who is not entitled to change it.")
                log("rejected", c.resolution, c.msg, c.id)
                c.related.append(o.id)
                return
            o.status = "superseded"; o.superseded_by = c.id
            o.resolution = f"Superseded by {c.id} ({'same value restated' if same_value else 'newer value'})."
            c.related.append(o.id)
            if not same_value:
                if c.status == "confirmed":
                    c.status = "corrected"
                log("superseded", f"{describe(o)} replaced by {describe(c)}.", c.msg, c.id)

    # ------------------------------------------------------------------
    def reject(self, claim_ids: list[str], reason: str):
        """Undo claims (used by rollback): restore what they superseded."""
        for cid in claim_ids:
            c = self.by_id(cid)
            if not c:
                continue
            c.status = "rejected"; c.resolution = reason
            for o in self.claims:
                if o.superseded_by == cid:
                    o.status = "confirmed" if o.status == "superseded" else o.status
                    o.superseded_by = None; o.resolution = f"Restored: {cid} was rejected."

    def ledger_lines(self) -> list[str]:
        out = []
        for c in self.claims:
            if c.active:
                subj = f" {c.subject}" if c.subject else ""
                out.append(f"{c.id} {c.kind}{subj}={c.value} [{c.msg},a{c.authority},{c.date or '-'},{c.status}]")
        return out

    def vocab(self) -> dict:
        v = {"venues": set(), "food options": set(), "features": set(), "expense items": set()}
        for c in self.claims:
            if c.kind.startswith("venue_") and c.subject:
                v["venues"].add(str(c.subject))
            if c.kind.startswith("food_") and c.subject:
                v["food options"].add(str(c.subject))
            if c.kind in ("venue_feature", "venue_requirement", "food_feature", "food_requirement"):
                v["features"].add(str(c.value))
            if c.kind.startswith("expense_") and c.subject:
                v["expense items"].add(str(c.subject))
        return {k: sorted(x) for k, x in v.items()}


class Facts:
    """Read-only view over active ledger claims used by the planners."""

    def __init__(self, ledger: Ledger):
        self.claims = [c for c in ledger.claims if c.active and not is_pending(c)]
        self.pending = [c for c in ledger.claims if c.active and is_pending(c)]

    def one(self, kind: str) -> Optional[Claim]:
        cs = [c for c in self.claims if c.kind == kind]
        return max(cs, key=lambda c: (c.authority, _date_key(c))) if cs else None

    def num(self, kind: str) -> Optional[float]:
        c = self.one(kind)
        return c.num() if c else None

    def all(self, kind: str) -> list[Claim]:
        return [c for c in self.claims if c.kind == kind]

    def by_subject(self, kind: str) -> dict[str, Claim]:
        out: dict[str, Claim] = {}
        for c in sorted(self.all(kind), key=_date_key):
            out[norm(c.subject)] = c
        return out


def _same_sender(a, b) -> bool:
    ta = {w for w in norm(a).replace(".", " ").replace(",", " ").split() if len(w) > 2 and w not in ("the", "here", "office", "email", "whatsapp", "team", "dept")}
    tb = {w for w in norm(b).replace(".", " ").replace(",", " ").split() if len(w) > 2 and w not in ("the", "here", "office", "email", "whatsapp", "team", "dept")}
    if not ta or not tb:
        return False
    return len(ta & tb) / min(len(ta), len(tb)) >= 0.5


def describe(c: Claim) -> str:
    s = f" '{c.subject}'" if c.subject else ""
    return f"{c.id} {c.kind}{s}={c.value} (msg {c.msg})"
