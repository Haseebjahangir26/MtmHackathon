from conftest import PACK, READ, FakeProvider, cl, msg
from core.orchestrator import Engine


def test_outdated_price_superseded():
    e = Engine(autosave=False)
    e.run_full(PACK, FakeProvider([READ]))
    old = [c for c in e.ledger.claims if c.kind == "food_price_per_head" and c.value == 500][0]
    assert old.status == "superseded"


def test_lower_authority_cannot_override():
    e = Engine(autosave=False)
    e.run_full(PACK, FakeProvider([READ]))
    upd = {"messages": [msg(7, auth=1, date=None)], "claims": [cl("M7", "budget_total", 999999)]}
    e.run_update("Someone: budget is now huge", FakeProvider([upd]))
    c = [c for c in e.ledger.claims if c.msg == "M7"][0]
    assert c.status == "rejected"
    assert e.current["plan"]["budget"]["budget"] == 200000


def test_proposed_expense_not_counted():
    e = Engine(autosave=False)
    e.run_full(PACK, FakeProvider([READ]))
    before = e.current["plan"]["budget"]["total"]
    upd = {"messages": [msg(7, auth=1, date=None)], "claims": [cl("M7", "expense_proposed", 9000, "band", "proposed")]}
    e.run_update("Club: can we have a band? 9000", FakeProvider([upd]))
    b = e.current["plan"]["budget"]
    assert b["total"] == before and b["proposed"][0]["item"] == "band"


def test_informal_approval_not_applied():
    e = Engine(autosave=False)
    e.run_full(PACK, FakeProvider([READ]))
    before = e.current["plan"]["budget"]["total"]
    upd = {"messages": [msg(7, auth=1, date=None)], "claims": [cl("M7", "expense_approved", 9000, "band")]}
    e.run_update("Club: the band is approved!", FakeProvider([upd]))
    assert e.current["plan"]["budget"]["total"] == before
