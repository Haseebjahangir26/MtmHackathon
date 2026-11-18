# CONCORD (Event Planner)

**CONCORD** turns conflicting messages into one agreed, validated plan. Constraint-aware event planner for the Mind to Machine Hackathon. It reads a pack of messy messages (emails, WhatsApp, notices; English and Roman Urdu), extracts typed claims with provenance, resolves conflicts, plans **venue, schedule, food, judging and budget**, and validates every constraint before calling a plan feasible.

## Run

```bash
pip install -r requirements.txt
cp .env.example .env        # put GEMINI_API_KEY (or ANTHROPIC_API_KEY) in .env
streamlit run app.py
```

1. **Overview → Load message pack**: upload the `.txt` pack (or paste it) and press **Run full plan**.
2. **Updates**: paste each new message and press **Process update**.
3. **Export**: download the plan (JSON/Markdown), the full trace (JSON/Markdown) and rejected messages.
   The latest `plan.md`, `trace.md` and `trace.json` are also written to `data/` after every run, and the trace is printed in the terminal running Streamlit.

No flags, no setup screens: the app never asks for an API key. It loads `GEMINI_API_KEY` (or `ANTHROPIC_API_KEY`) silently from the environment, `.env` or `.streamlit/secrets.toml`. With no key it opens in demo mode with one small banner; demo entries are labelled MOCK and carry no token counts.

## Architecture (and why each part exists)

```
.txt pack ──► Input manager ──► Reading agent (1 model call) ──► Ledger + conflict engine
                                                                       │
                     Specialist call (venue) only if a requirement     ▼
                     cannot be matched in code           Deterministic planners
                                                         judging → headcount → venue → food → schedule → budget
                                                                       │
                                                                       ▼
                                                   Validator (hard vs soft checks) ──► Version + diff + trace
```

| Part | File | Why it exists / what breaks without it |
|---|---|---|
| Input manager | `core/ingestion.py` | Splits the pack into messages verbatim (separators, numbering, paragraphs). Without it facts from different senders blur together and provenance is lost. |
| Reading agent | `agents/reader.py` | The only place language understanding is needed. One call turns all messages into typed claims (kind, subject, value, status, authority, date, supersedes). Each claim is validated with Pydantic individually, so one bad item never sinks the run. |
| Ledger + conflict engine | `core/knowledge.py` | Source of truth. Corrections supersede; a newer message from a **lower authority** cannot override an approved fact; outdated prices are superseded but kept; proposals never become approved facts or expenses. Without it the newest message would always win. |
| Planners | `agents/venue.py`, `schedule.py`, `food.py`, `judging.py`, `budget.py` | Plain Python, no model: all arithmetic (judges = ceil(teams / max per judge), headcount = students + staff + judges + others, costs, timetable) is exact and costs zero tokens. |
| Planner loop | `services/planner.py` | Runs planners in dependency order and repairs: more parallel judges if the timetable overflows, cheaper catering if over budget. |
| Dependency graph | `core/dependencies.py` | A change in attendance or judges flows into food, venue, schedule and budget even though the message was "about" one area. Also produces before/after diffs. |
| Validator | `core/validator.py` | Hard checks (capacity, meals ≥ people, judges, judge load, duration, mandatory breaks, budget, caps, coverage) and soft warnings (uncertain facts, unverifiable requirements, pending proposals). A plan is FEASIBLE only if every hard check passes. |
| Orchestrator | `core/orchestrator.py` | One pipeline for full runs and updates; snapshots, rollback, rejection of bad updates, max 5 model calls and time limits per run. |
| Trace | `core/trace.py` | Numbered model calls with model name, area tag, full input/output, provider-reported tokens (never estimated), duration, success; plus every rejection/supersession reason. |
| Provider adapter | `services/llm_provider.py` | Gemini (default `gemini-3.5-flash-lite`, small model, thinking off where configurable), Anthropic, or labelled mock. Retries on 429/503 and falls back to another small model. |

## Model calls and tokens

* **Full run:** 1 reading call (≈2.5k tokens on the sample pack).
* **Each update:** 1 reading call (≈2k tokens) with the new message plus a compact list of known facts.
* A **venue specialist** call happens only when a stated venue requirement matches no feature token the reader produced. Hard limit: 5 calls per run; full run cut at 115 s, update at 55 s.
* **Prediction for the judging slip:** an update makes exactly one model call, tagged `reading`, unless it introduces a new venue requirement that can't be matched in code (then also `venue`). Duplicates make no call.

## How wrong messages are caught

1. **Authority:** a lower-authority sender cannot change a fact set by a higher authority (e.g. a student "reducing" judges or budget).
2. **Rule checks:** a catering order below the number of people to feed is rejected and the previous quantity is kept.
3. **Plan protection:** if an update would turn a feasible plan infeasible through a proposal or a lower-authority change, those claims are rejected, the plan is rebuilt from the previous ledger, and the failing checks are written to the trace as the reason.
4. Authoritative changes that genuinely make the event infeasible are **accepted and reported honestly** (NOT FEASIBLE with the failed check and a suggested fix), never hidden.

## UI

Overview (status, KPIs, validation table, checks-by-area chart, dependency graph), Plan (five tabs with options, decisions, evidence, checks; Gantt timetable; budget donut), Messages (original messages, claim ledger with units/validity, rejected and superseded lists, decision log), Updates (add message, version history, cost-per-version chart, before/after diff, rollback), Model trace (per-call table, token chart, full input/output), Export (plan JSON/MD, trace JSON/MD, rejected messages).

## Planner defaults (shown as assumptions in the UI)

Opening 10 min, lunch 30 min (if food is served and no lunch break is stated), results & closing 15 min, start time 10:00 if no start is stated. Catering policy: the "standard" option if it fits the budget, else the cheapest compliant option (switchable under *Planning settings* in the sidebar, no model call).

## Tests

```bash
python -m pytest -q tests
```
26 tests, synthetic data only (no official pack facts). `tests/test_scenarios.py` covers the 10 required scenarios (initial pack, newer bill, too few boxes, outdated price, unapproved expense, conflicting venue requirement, Roman Urdu, ambiguous message, multi-domain change, irrelevant message) plus missing key, retry on 503 and no estimated tokens. Other tests: figures, budget failure, malformed model output, outdated price, authority override, proposed expense, expense correction touching only budget, insufficient food order, multi-domain change, duplicates, model failure + rollback. `tests/packs/` holds two synthetic packs with different numbers, Roman Urdu and new constraint kinds (wheelchair access, vegetarian food, projector, extra attendee groups, budget ceiling).

## Judge-day runbook

1. `git status` is clean and `git log -1` matches the submitted hash.
2. `streamlit run app.py` → sidebar shows **Model: gemini-3.5-flash-lite** (key loaded silently from `.env`).
3. Overview → upload the unseen pack → **Run full plan** (≈5 s, 1 call). Check the status pill and the validation table.
4. For each released message: Updates → paste → **Process update**. The card shows changed areas, model-call areas and the rejection reason, if any.
5. Prediction slip: write **"reading only (1 call)"**. Only a message adding a brand-new venue requirement can add a `venue` call.
6. Export → **Plan + trace bundle (Markdown)** (also auto-saved as `data/plan.md`, `data/trace.md`, `data/trace.json`) → upload.

## Likely judge questions (short answers)

* **Why only one model call?** Reading messy language is the only part that needs a model. Every number in the plan is arithmetic, which code does exactly and for zero tokens.
* **How do you catch the wrong message?** Three layers: authority (who may change what), rule checks (meals ≥ people, judges ≥ needed), and plan protection (an update that breaks a valid plan through a proposal or an unentitled sender is rolled back, with the failed check written in the trace).
* **What if a real change makes the event impossible?** It is accepted and the plan is marked NOT FEASIBLE with the failed check and a suggested fix. We never fake a valid plan.
* **Why a ledger?** Corrections, outdated prices and rejected claims are kept with their source message, so every number in the plan can be traced to evidence and any change can be undone (rollback).
* **What breaks without the validator?** Nothing would stop an over-budget plan or too few meals from being shown as feasible.
* **Are tokens real?** Yes, from the provider's `usage_metadata`. A failed call or a provider without usage shows "unavailable", never an estimate.
