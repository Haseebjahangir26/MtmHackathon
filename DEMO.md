# CONCORD (Event Planner) — judge demo script (3 minutes)

**Setup before the judge arrives:** app open on the Overview tab with the final plan loaded. Sidebar shows `Model: gemini-3.5-flash-lite`.

1. **Hero + status (15 s).** "This is a constraint-solving planner, not a chatbot. The green "Feasible" badge means every hard check passed. We used N model calls and N tokens in total."
2. **Agent pipeline (30 s).** "Only the reading agent touches the model, once per run. It turns English and Roman Urdu messages into typed claims. The ledger resolves conflicts by authority and date. The five planners and the validator are plain Python, so every number is exact and costs no tokens. Cyan means a model call, blue means the output changed."
3. **Validation panel (20 s).** "One card per area. A plan is FEASIBLE only if every hard check passes. Warnings like uncertain facts stay visible."
4. **Plan → Venue / Food decision cards (30 s).** "Each decision shows the rule and the original messages it rests on, for example the outdated Rs 1,000 price is listed as ignored."
5. **Updates (40 s).** Point at the update cards: "This message was rejected. Here is the exact reason in the trace: too few meals for the people on site, so the plan kept the previous quantity. The printing correction made 1 call and only the budget changed." Show the side-by-side compare and Rollback.
6. **Model trace (20 s).** "Every call is numbered with model, area tag, full input and output, and the token counts the provider reported. Failed calls show unavailable, never estimates."
7. **What-if (25 s).** Drag Students up: "Zero tokens. The same deterministic planners re-plan instantly; here judges run out, and it tells you how many to confirm."

## If asked "what breaks without X?"

| Part | Without it |
|---|---|
| Reading agent | Nothing understands free text or Roman Urdu. |
| Ledger / conflict engine | The newest message would always win, so a student could override the dean, and old prices would leak in. |
| Planners in Python | The model would do arithmetic, costing tokens and making mistakes. |
| Dependency graph | An attendance change would not update judges, food, venue and budget together. |
| Validator | An over-budget or under-fed plan could be shown as feasible. |
| Snapshots / rollback | A bad update could destroy the last valid plan. |
| Trace | No proof of which model ran, on what, for how many tokens. |

## Prediction slip

Write: **"reading only (1 call)"** for any single message. Add **"venue"** only if the message introduces a venue requirement that no known venue feature matches. Exact duplicates: **no calls**.
