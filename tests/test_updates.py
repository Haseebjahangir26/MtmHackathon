from conftest import PACK, READ, FakeProvider, cl, msg
from core.orchestrator import Engine


def base():
    e = Engine(autosave=False)
    e.run_full(PACK, FakeProvider([READ]))
    return e


def test_expense_correction_only_changes_budget():
    e = base()
    upd = {"messages": [msg(7, auth=3, date=None)], "claims": [cl("M7", "expense_committed", 8000, "banners", "corrected")]}
    r = e.run_update("Accounts: banners were 8000 not 5000", FakeProvider([upd]))
    assert r["changed"] == ["budget"]
    assert [c.area for c in e.calls if c.run == r["run"]] == ["reading"]


def test_insufficient_food_order_rejected_plan_kept():
    e = base()
    upd = {"messages": [msg(7, auth=2, date=None)], "claims": [cl("M7", "food_order_quantity", 40, st="proposed")]}
    r = e.run_update("Cook: I cut your order to 40 meals", FakeProvider([upd]))
    assert e.current["validation"]["feasible"]
    assert e.current["plan"]["food"]["quantity"] == 71
    assert [c for c in e.ledger.claims if c.msg == "M7"][0].status == "rejected"


def test_multi_domain_change_and_duplicate():
    e = base()
    upd = {"messages": [msg(7, auth=3, date=None)], "claims": [cl("M7", "students", 80, st="corrected")]}
    r = e.run_update("Office: 80 students now", FakeProvider([upd]))
    assert {"food", "judging", "budget"} <= set(r["changed"])
    n = len(e.calls)
    r2 = e.run_update("Office: 80 students now", FakeProvider([]))
    assert r2.get("duplicate") and len(e.calls) == n  # no model call for duplicates


def test_model_failure_keeps_previous_plan_and_rollback():
    e = base()
    v = e.current["n"]
    r = e.run_update("anything", FakeProvider([RuntimeError("400 bad request")]))
    assert not r["ok"] and e.current["n"] == v
    upd = {"messages": [msg(8, auth=3, date=None)], "claims": [cl("M8", "students", 70, st="corrected")]}
    e.run_update("Office: 70 students", FakeProvider([upd]))
    assert e.rollback() and e.current["n"] == v
    assert e.current["plan"]["participants"]["students"] == 60
