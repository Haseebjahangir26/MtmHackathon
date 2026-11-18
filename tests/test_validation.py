from conftest import PACK, READ, FakeProvider
from core.orchestrator import Engine


def run():
    e = Engine(autosave=False)
    r = e.run_full(PACK, FakeProvider([READ]))
    return e, r


def test_full_run_figures():
    e, r = run()
    P = e.current["plan"]
    assert r["feasible"]
    assert P["judging"]["judges_used"] == 6            # ceil(30 / 5)
    assert P["headcount"]["total"] == 60 + 5 + 6       # students + staff + judges
    assert P["venue"]["chosen"]["venue"] == "Big"      # Small is cheaper but too small
    assert P["food"]["cost"] == 71 * 700               # latest price, not outdated 500
    assert P["budget"]["total"] == 30000 + 71 * 700 + 6 * 2000 + 5000
    s = P["schedule"]
    assert s["total_minutes"] == 180 and any(b["activity"] == "rest" for b in s["blocks"])
    assert len(e.calls) == 1                            # one reading call, planners are code


def test_never_feasible_when_budget_fails():
    import copy
    read = copy.deepcopy(READ)
    read["claims"][2]["v"] = 50000  # budget too small
    e = Engine(autosave=False)
    e.run_full(PACK, FakeProvider([read]))
    v = e.current["validation"]
    assert not v["feasible"]
    assert any(c["id"] == "budget_within" and not c["passed"] for c in v["checks"])


def test_malformed_model_output_does_not_crash():
    e = Engine(autosave=False)
    r = e.run_full(PACK, FakeProvider(["not json", "{broken"]))
    assert not r["ok"] and e.current is None
    assert len(e.calls) == 2  # one retry, both traced
