"""Reading agent: the one place where language understanding is required.

One model call turns a batch of raw messages (English / Roman Urdu) into
normalised, typed claims. The output is parsed leniently and every claim is
validated individually with Pydantic, so one bad item never sinks the batch.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from pydantic import ValidationError

from core.models import KINDS, Claim, Message

KIND_DOC = """budget_total: approved total event budget (PKR)
students: number of student participants | team_size: people per team | teams: number of teams
staff: staff/volunteers on duty (count) | attendee_group s=<group>: other people attending, e.g. guests (count)
event_duration_minutes: approved event length in minutes | event_start: start time "HH:MM" 24h | event_end_by: latest allowed end "HH:MM" 24h
venue_capacity s=<venue>: seats | venue_price s=<venue>: rental PKR | venue_feature s=<venue> v=<feature token>
venue_unavailable s=<venue> v=<reason> | venue_requirement v=<feature token the venue MUST have>
food_price_per_head s=<option> | food_delivery_fee s=<option> (PKR total) | food_feature s=<option> v=<token>
food_requirement v=<token every meal must satisfy> | food_order_quantity: number of meals/boxes someone set or proposes
judges_available: judges confirmed | judge_honorarium: PKR per judge | judge_minutes_per_team | judge_max_teams: max teams one judge may cover
judge_late_minutes s=<who>: expected lateness minutes
break_required s=<name>: mandatory break minutes | activity_required s=<name>: mandatory activity minutes
expense_committed s=<item>: already ordered/paid from event budget PKR | expense_proposed s=<item>: requested/quoted, NOT approved
expense_approved s=<item>: optional expense explicitly approved by an authority
cap s=<metric> : maximum allowed; metric one of total_cost,venue_cost,food_cost,judging_cost,food_price_per_head,venue_price,judges,headcount,teams_per_judge
note s=<domain> v=<short text>: relevant constraint that fits no kind above (domain venue|schedule|food|judging|budget)"""

SYSTEM = f"""You extract facts for planning ONE physical event from messages (English or Roman Urdu). Return JSON only:
{{"messages":[{{"id","sender","channel","date","auth","relevant","why"}}],"claims":[{{"m","k","s","v","st","c","sup","why"}}]}}
messages: one entry per input message. date: YYYY-MM-DD or null if absent. auth: 3=approving authority (dean, director, organiser, finance office); 2=responsible office/coordinator for its area, or vendor stating its own prices/capacity/availability; 1=individual speaking for themselves (one judge, student, volunteer), informal, unverified, requester, rumour. relevant: false if unrelated to the event. why: <=10 words, only if irrelevant.
claims: one per fact. m=message id. k=kind (list below). s=subject (null if none). v=value: plain number for amounts (PKR as integer, no commas), else short string. c=confidence 0-1.
st: confirmed (stated fact, rule, price list, availability) | proposed (a request/suggestion/optional quote that needs approval, or a change someone wants to make) | corrected (replaces an earlier value) | uncertain (maybe/approx) | rejected (contradicts a stated rule, requirement or approved fact, or sender lacks authority to change it).
sup: id of the earlier message or fact (M#/C#) this one corrects, else null. why: <=15 words, required when st is not confirmed.
Kinds:
{KIND_DOC}
Rules: never invent or compute values; extract only what is written. Subjects keep the names as written (e.g. Hall Rose); reuse IDENTICAL subject strings and feature tokens for the same thing across messages (only feature tokens are short snake_case, e.g. power_backup, wheelchair_access; a requirement and the feature satisfying it use the same token; for each venue/food option emit a feature claim for every stated requirement its text shows it meets, e.g. veg thali -> vegetarian). Same item priced again later: emit the new price as corrected with sup. Irrelevant messages get no claims.
Output minified JSON; omit keys whose value is null or empty."""


def build_initial_prompt(msgs: list[Message], today: str) -> str:
    body = "\n".join(f"{m.id} | {m.text}" for m in msgs)
    return f"TODAY: {today} (use its year when a date has none)\nMESSAGES:\n{body}"


def build_update_prompt(msgs: list[Message], ledger_lines: list[str], vocab: dict, today: str) -> str:
    voc = "; ".join(f"{k}: {', '.join(v)}" for k, v in vocab.items() if v)
    body = "\n".join(f"{m.id} | {m.text}" for m in msgs)
    return (f"TODAY: {today}\nKNOWN FACTS (id kind subject=value [msg,auth,date,status]):\n" + "\n".join(ledger_lines) +
            f"\nKNOWN NAMES/TOKENS: {voc}\n\nNEW MESSAGE(S) - extract only from these:\n{body}")


def _loads_lenient(text: str) -> Optional[dict]:
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    for cand in (t, t[t.find("{"): t.rfind("}") + 1] if "{" in t else ""):
        if not cand:
            continue
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            try:  # trailing commas
                return json.loads(re.sub(r",\s*([}\]])", r"\1", cand))
            except json.JSONDecodeError:
                continue
    return None


def parse_reader_output(text: str, msg_ids: set[str]) -> tuple[Optional[dict], list[Claim], list[str]]:
    """Returns (message meta by id, claims, errors). meta None => unusable output."""
    data = _loads_lenient(text)
    errors: list[str] = []
    if not isinstance(data, dict):
        return None, [], ["Model output was not valid JSON"]
    meta = {}
    for m in data.get("messages") or []:
        if isinstance(m, dict) and m.get("id") in msg_ids:
            meta[m["id"]] = m
    claims: list[Claim] = []
    for raw in data.get("claims") or []:
        if not isinstance(raw, dict):
            continue
        try:
            if raw.get("m") not in msg_ids:
                raise ValueError(f"unknown message id {raw.get('m')}")
            k = str(raw.get("k", "")).strip()
            v = raw.get("v")
            if k in KINDS and KINDS[k][1] == "num":
                v = _to_num(v)
                if v is None:
                    raise ValueError(f"non-numeric value for {k}: {raw.get('v')}")
            st = str(raw.get("st") or "confirmed").lower()
            if st not in ("confirmed", "proposed", "corrected", "uncertain", "irrelevant", "rejected"):
                st = "uncertain"
            claims.append(Claim(msg=raw["m"], kind=k, subject=raw.get("s"), value=v, status=st,
                                confidence=raw.get("c", 0.8), supersedes_ref=raw.get("sup"), reason=raw.get("why")))
        except (ValidationError, ValueError, TypeError) as e:
            errors.append(f"Dropped invalid claim {json.dumps(raw)[:160]}: {str(e).splitlines()[0][:120]}")
    return meta, claims, errors


def _to_num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.lower().replace(",", "").replace("rs", "").replace("pkr", "").strip()
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        if not m:
            return None
        n = float(m.group())
        if re.search(r"\d\s*k\b", s):
            n *= 1000
        if "lakh" in s or "lac" in s:
            n *= 100000
        return int(n) if n.is_integer() else n
    return None
