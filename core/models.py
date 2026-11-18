"""Pydantic data models shared across the system."""
from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

Status = Literal["confirmed", "proposed", "corrected", "uncertain", "irrelevant", "rejected", "superseded"]
Domain = Literal["venue", "schedule", "food", "judging", "budget", "general"]

# kind -> (domain, value type, keyed by subject?, keyed by value?)
KINDS: dict[str, tuple[str, str, bool, bool]] = {
    "budget_total": ("budget", "num", False, False),
    "students": ("general", "num", False, False),
    "team_size": ("general", "num", False, False),
    "teams": ("general", "num", False, False),
    "staff": ("general", "num", False, False),
    "attendee_group": ("general", "num", True, False),
    "event_duration_minutes": ("schedule", "num", False, False),
    "event_start": ("schedule", "str", False, False),
    "event_end_by": ("schedule", "str", False, False),
    "venue_capacity": ("venue", "num", True, False),
    "venue_price": ("venue", "num", True, False),
    "venue_feature": ("venue", "str", True, True),
    "venue_unavailable": ("venue", "str", True, False),
    "venue_requirement": ("venue", "str", False, True),
    "food_price_per_head": ("food", "num", True, False),
    "food_delivery_fee": ("food", "num", True, False),
    "food_feature": ("food", "str", True, True),
    "food_requirement": ("food", "str", False, True),
    "food_order_quantity": ("food", "num", False, False),
    "judges_available": ("judging", "num", False, False),
    "judge_honorarium": ("judging", "num", False, False),
    "judge_minutes_per_team": ("judging", "num", False, False),
    "judge_max_teams": ("judging", "num", False, False),
    "judge_late_minutes": ("judging", "num", True, False),
    "break_required": ("schedule", "num", True, False),
    "activity_required": ("schedule", "num", True, False),
    "expense_committed": ("budget", "num", True, False),
    "expense_proposed": ("budget", "num", True, False),
    "expense_approved": ("budget", "num", True, False),
    "cap": ("budget", "num", True, False),
    "note": ("general", "str", True, True),
}

# Kinds that set the task itself: only equal/higher authority may change them.
GOVERNING = {
    "budget_total", "students", "team_size", "teams", "staff", "event_duration_minutes",
    "break_required", "venue_requirement", "food_requirement", "cap", "expense_approved",
    "judge_max_teams", "judge_minutes_per_team", "activity_required", "attendee_group", "event_end_by",
}

CAP_METRICS = ["total_cost", "venue_cost", "food_cost", "judging_cost", "food_price_per_head",
               "venue_price", "judges", "headcount", "teams_per_judge"]


def norm(s: Any) -> str:
    if s is None:
        return ""
    return " ".join(str(s).lower().replace("_", " ").replace("-", " ").split())


class Message(BaseModel):
    id: str
    seq: int
    text: str
    sender: Optional[str] = None
    channel: Optional[str] = None
    date: Optional[str] = None
    authority: int = 1
    relevant: bool = True
    note: Optional[str] = None
    batch: str = "initial"  # initial | update-N
    status: str = "processed"  # processed | duplicate | rejected | partially rejected


class Claim(BaseModel):
    id: str = ""
    msg: str
    kind: str
    subject: Optional[str] = None
    value: Union[float, int, str, bool, None] = None
    unit: Optional[str] = None
    status: Status = "confirmed"
    confidence: float = 0.8
    supersedes_ref: Optional[str] = None
    reason: Optional[str] = None
    # filled by knowledge engine
    domain: str = "general"
    authority: int = 1
    date: Optional[str] = None
    sender: Optional[str] = None
    seq: int = 0
    superseded_by: Optional[str] = None
    related: list[str] = Field(default_factory=list)
    resolution: Optional[str] = None  # explanation of ledger decision

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        v = v.strip()
        if v not in KINDS:
            raise ValueError(f"unknown kind {v}")
        return v

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        try:
            return max(0.0, min(1.0, float(v)))
        except Exception:
            return 0.5

    def key(self) -> tuple:
        dom, _, by_subj, by_val = KINDS[self.kind]
        return (self.kind, norm(self.subject) if by_subj else "", norm(self.value) if by_val else "")

    @property
    def active(self) -> bool:
        return self.status in ("confirmed", "corrected", "uncertain", "proposed")

    def num(self) -> Optional[float]:
        try:
            return float(self.value)
        except (TypeError, ValueError):
            return None


class ModelCall(BaseModel):
    n: int
    timestamp: str
    provider: str
    model: str
    area: str
    input: str
    output: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    thinking_tokens: Optional[int] = None
    tokens_reported: bool = True
    duration_s: float = 0.0
    success: bool = True
    error: Optional[str] = None
    run: str = "initial"
    is_mock: bool = False


class Decision(BaseModel):
    timestamp: str
    run: str
    kind: str  # rejected | superseded | conflict | duplicate | info | rollback
    message_id: Optional[str] = None
    claim_id: Optional[str] = None
    text: str
