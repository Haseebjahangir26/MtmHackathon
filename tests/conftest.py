import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.llm_provider import LLMResult, Provider


class FakeProvider(Provider):
    """Test double: returns scripted reader JSON. Synthetic data only (not the official pack)."""
    name = "fake"

    def __init__(self, outputs):
        super().__init__("fake-model")
        self.outputs = list(outputs)

    def complete(self, system, user, max_tokens=4000):
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return LLMResult(out if isinstance(out, str) else json.dumps(out), 100, 50, None, True, 0.01)


def msg(i, auth=3, date="2030-01-10", relevant=True):
    return {"id": f"M{i}", "sender": "x", "date": date, "auth": auth, "relevant": relevant}


def cl(m, k, v, s=None, st="confirmed", sup=None):
    d = {"m": m, "k": k, "v": v, "st": st}
    if s: d["s"] = s
    if sup: d["sup"] = sup
    return d


# synthetic pack: 60 students, teams of 2 -> 30 teams; 5 staff; max 5 teams/judge -> 6 judges; 71 people
PACK = "1. Office: approved\n2. Venue co: rooms\n3. Cook: menu old\n4. Cook: menu new\n5. Judges lead\n6. Accounts"
READ = {"messages": [msg(1), msg(2, 2, "2030-01-05"), msg(3, 2, "2030-01-01"), msg(4, 2, "2030-01-12"),
                     msg(5, 2, "2030-01-08"), msg(6, 3, "2030-01-09")],
        "claims": [cl("M1", "students", 60), cl("M1", "team_size", 2), cl("M1", "budget_total", 200000),
                   cl("M1", "staff", 5), cl("M1", "event_duration_minutes", 180), cl("M1", "break_required", 10, "rest"),
                   cl("M2", "venue_capacity", 50, "Small"), cl("M2", "venue_price", 10000, "Small"),
                   cl("M2", "venue_capacity", 100, "Big"), cl("M2", "venue_price", 30000, "Big"),
                   cl("M3", "food_price_per_head", 500, "standard meal"),
                   cl("M4", "food_price_per_head", 700, "standard meal", "corrected", "M3"),
                   cl("M5", "judges_available", 8), cl("M5", "judge_honorarium", 2000),
                   cl("M5", "judge_minutes_per_team", 10), cl("M5", "judge_max_teams", 5),
                   cl("M6", "expense_committed", 5000, "banners")]}
