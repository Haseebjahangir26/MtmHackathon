"""The 10 required scenarios plus provider/trace reliability, using synthetic data only."""
import copy

import pytest

from conftest import PACK, READ, FakeProvider, cl, msg
from core.orchestrator import Engine


def base(read=None):
    e = Engine(autosave=False)
    e.run_full(PACK, FakeProvider([read or READ]))
    return e


def upd(e, text, claims, auth=3, relevant=True):
    n = len(e.state["messages"]) + 1
    out = {"messages": [msg(n, auth=auth, date=None, relevant=relevant)],
           "claims": [dict(c, m=f"M{n}") for c in claims]}
    return e.run_update(text, FakeProvider([out])), f"M{n}"


def checks(e):
    return {c["id"]: c for c in e.current["validation"]["checks"]}


# 1
def test_s1_initial_full_pack():
    e = base()
    v = e.current
    assert v["validation"]["feasible"] and len(e.state["messages"]) == 6
    assert set(v["plan"]) >= {"venue", "food", "judging", "schedule", "budget"}
    assert [c.area for c in e.calls] == ["reading"]


# 2
def test_s2_newer_bill_replaces_older():
    e = base()
    before = e.current["plan"]["budget"]["total"]
    r, mid = upd(e, "Accounts: banners invoice is 9000, not 5000", [cl("x", "expense_committed", 9000, "banners", "corrected")])
    assert e.current["plan"]["budget"]["total"] == before + 4000
    assert r["changed"] == ["budget"]
    old = [c for c in e.ledger.claims if c.kind == "expense_committed" and c.value == 5000][0]
    assert old.status == "superseded"


# 3
def test_s3_caterer_fewer_boxes_rejected():
    e = base()
    hc = e.current["plan"]["headcount"]["total"]
    r, mid = upd(e, "Cook: rounded down to 30 boxes", [cl("x", "food_order_quantity", 30, st="proposed")], auth=2)
    assert e.current["validation"]["feasible"]
    assert e.current["plan"]["food"]["quantity"] == hc
    assert all(c.status == "rejected" for c in e.ledger.claims if c.msg == mid)
    assert any(d.kind == "rejected" and d.message_id == mid for d in e.decisions)


# 4
def test_s4_outdated_vs_newer_price():
    e = base()
    fc = e.current["plan"]["food"]
    assert fc["chosen"]["price_per_head"] == 700
    # an update carrying an OLDER date must not override the newer price
    n = len(e.state["messages"]) + 1
    out = {"messages": [msg(n, auth=2, date="2029-12-01")], "claims": [cl(f"M{n}", "food_price_per_head", 400, "standard meal")]}
    e.run_update("Cook (old quote): standard meal 400", FakeProvider([out]))
    assert e.current["plan"]["food"]["chosen"]["price_per_head"] == 700
    c = [c for c in e.ledger.claims if c.msg == f"M{n}"][0]
    assert c.status == "superseded"


# 5
def test_s5_unapproved_optional_expense_excluded():
    e = base()
    before = e.current["plan"]["budget"]["total"]
    upd(e, "Club: fireworks quote 20000?", [cl("x", "expense_proposed", 20000, "fireworks", "proposed")], auth=1)
    b = e.current["plan"]["budget"]
    assert b["total"] == before
    assert [p["item"] for p in b["proposed"]] == ["fireworks"]


# 6
def _venue_read():
    r = copy.deepcopy(READ)
    r["claims"] += [cl("M2", "venue_capacity", 100, "Mid"), cl("M2", "venue_price", 20000, "Mid"),
                    cl("M2", "venue_feature", "lift", "Big"), cl("M1", "venue_requirement", "lift")]
    return r


def test_s6_requirement_picks_pricier_compliant_venue():
    e = base(_venue_read())
    v = e.current["plan"]["venue"]
    assert v["chosen"]["venue"] == "Big"
    mid = [o for o in v["options"] if o["venue"] == "Mid"][0]
    assert not mid["feasible"] and "lift" in mid["reason"]


def test_s6_lower_authority_cannot_change_venue_rules():
    e = base(_venue_read())
    r, mid = upd(e, "Student: we also need a pool", [cl("x", "venue_requirement", "pool")], auth=1)
    assert e.current["plan"]["venue"]["chosen"]["venue"] == "Big"
    assert e.current["plan"]["venue"]["requirements"] == ["lift"]
    r2, mid2 = upd(e, "Student: actually 200 students", [cl("x", "students", 200)], auth=1)
    assert e.current["plan"]["participants"]["students"] == 60
    assert [c for c in e.ledger.claims if c.msg == mid2][0].status == "rejected"


# 7
def test_s7_roman_urdu_text_preserved():
    e = base()
    text = "Salam! Khana ab 800 rupay per banda hoga, delivery muft hai."
    upd(e, text, [cl("x", "food_price_per_head", 800, "standard meal", "corrected")], auth=2)
    m = e.state["messages"][-1]
    assert m["text"] == text
    assert e.current["plan"]["food"]["chosen"]["price_per_head"] == 800


# 8
def test_s8_ambiguous_message_soft_warning_only():
    e = base()
    upd(e, "Office: maybe a few guests will come, around 5", [cl("x", "attendee_group", 5, "guests", "uncertain")])
    ch = [c for c in e.current["validation"]["checks"] if c["id"].startswith("uncertain_")]
    assert ch and not ch[0]["hard"] and not ch[0]["passed"]
    assert e.current["validation"]["feasible"]


# 9
def test_s9_multi_domain_attendance_change():
    e = base()
    before = e.current["summary"]
    r, _ = upd(e, "Office: 70 students now", [cl("x", "students", 70, st="corrected")])
    assert {"judging", "food", "budget"} <= set(r["changed"])
    after = e.current["summary"]
    assert after["judging"]["judges"] == 7  # ceil(35 teams / 5)
    assert after["headcount"]["total"] == 70 + 5 + 7
    assert e.current["validation"]["feasible"]
    assert after["venue"]["seats_needed"] != before["venue"]["seats_needed"]
    assert [c.area for c in e.calls if c.run == r["run"]] == ["reading"]


# 10
def test_s10_irrelevant_message():
    e = base()
    before = e.current["summary"]
    r, mid = upd(e, "Cricket practice moved to Sunday", [], auth=1, relevant=False)
    m = [m for m in e.state["messages"] if m["id"] == mid][0]
    assert m["status"] == "irrelevant"
    assert not [c for c in e.ledger.claims if c.msg == mid]
    assert e.current["summary"] == before and r["changed"] == []


# reliability
def test_missing_gemini_key_raises(monkeypatch):
    from services.llm_provider import LLMError, make_provider
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(LLMError):
        make_provider("gemini", "some-model", None)


def test_retry_on_transient_error_and_both_traced():
    e = Engine(autosave=False)
    r = e.run_full(PACK, FakeProvider([Exception("503 UNAVAILABLE"), READ]))
    assert r["ok"] and r["feasible"]
    calls = e.calls
    assert len(calls) == 2 and not calls[0].success and calls[1].success
    assert [c.n for c in calls] == [1, 2]


def test_failed_call_has_no_estimated_tokens():
    e = Engine(autosave=False)
    e.run_full(PACK, FakeProvider([Exception("503 UNAVAILABLE"), READ]))
    bad = e.calls[0]
    assert bad.tokens_reported is False and bad.input_tokens is None and bad.output_tokens is None
    from core.trace import totals
    t = totals(e.calls)
    assert t["input_tokens"] == 100 and t["output_tokens"] == 50  # only provider-reported numbers


def test_what_if_is_pure_and_zero_calls():
    from conftest import PACK, READ, FakeProvider
    from core.orchestrator import Engine
    from services.planner import what_if
    e = Engine(autosave=False)
    e.run_full(PACK, FakeProvider([READ]))
    n_calls, before = len(e.calls), e.current["plan"]["headcount"]["total"]
    plan, val = what_if(e.ledger, e.state["cache"], e.state["settings"], {"students": 90})
    assert plan["participants"]["students"] == 90 and plan["headcount"]["total"] > before
    assert len(e.calls) == n_calls and e.current["plan"]["headcount"]["total"] == before
    plan2, val2 = what_if(e.ledger, e.state["cache"], e.state["settings"], {"budget_total": 1000})
    assert not val2["feasible"]
