"""Orchestrator: full runs and incremental updates through ONE pipeline.

  messages -> reading agent (1 model call) -> ledger/conflict engine -> [specialist call only if a
  requirement cannot be matched in code] -> deterministic planners -> validator -> new version.

Updates keep the previous valid state as a snapshot; if the new message would break a
valid plan through a proposal or a lower-authority change, its claims are rejected and
the plan is restored, with the reason written to the trace.
"""
from __future__ import annotations

import copy
import time
from typing import Optional

from agents import food as food_a
from agents import reader
from agents import venue as venue_a
from core import persistence
from core.dependencies import AREAS, affected, diff, domain_summary
from core.ingestion import fingerprint, split_pack
from core.knowledge import Facts, Ledger, describe
from core.models import GOVERNING, Claim, Decision, Message, ModelCall
from core.trace import Tracer, now_iso, totals
from core.validator import validate
from services.planner import build_plan

MAX_CALLS_PER_RUN = 5


def _today() -> str:
    import datetime as _d
    return _d.date.today().isoformat()

FULL_LIMIT_S, UPDATE_LIMIT_S = 115, 55


def empty_state() -> dict:
    return {"messages": [], "claims": [], "calls": [], "decisions": [], "versions": [], "cache": {},
            "run_times": {}, "settings": {"food_policy": "standard-first", "default_start": "10:00"},
            "update_count": 0}


class Engine:
    def __init__(self, state: Optional[dict] = None, autosave: bool = True):
        self.state = state or empty_state()
        self.autosave = autosave

    # ---------- accessors ----------
    @property
    def messages(self) -> list[Message]:
        return [Message(**m) for m in self.state["messages"]]

    @property
    def ledger(self) -> Ledger:
        return Ledger([Claim(**c) for c in self.state["claims"]])

    @property
    def calls(self) -> list[ModelCall]:
        return [ModelCall(**c) for c in self.state["calls"]]

    @property
    def decisions(self) -> list[Decision]:
        return [Decision(**d) for d in self.state["decisions"]]

    @property
    def current(self) -> Optional[dict]:
        return self.state["versions"][-1] if self.state["versions"] else None

    def _save(self):
        if self.autosave:
            persistence.save(self.state)
            try:  # always keep the latest plan + full trace on disk for submission
                from core.report import plan_markdown
                from core.trace import trace_json, trace_markdown
                d = persistence.DATA
                (d / "trace.md").write_text(trace_markdown(self.calls, self.decisions, self.state["run_times"]), encoding="utf-8")
                (d / "trace.json").write_text(trace_json(self.calls, self.decisions, self.state["run_times"]), encoding="utf-8")
                if self.current:
                    (d / "plan.md").write_text(plan_markdown(self.current, self.state), encoding="utf-8")
            except Exception as e:  # noqa: BLE001
                print("export failed:", e)

    # ---------- runs ----------
    def run_full(self, raw_text: str, provider) -> dict:
        settings = self.state.get("settings", {})
        self.state = empty_state(); self.state["settings"] = settings
        t0 = time.time(); run = "initial"
        print(f"\n######## FULL RUN started {now_iso()} ########", flush=True)
        texts = split_pack(raw_text)
        msgs, seen = [], set()
        for i, t in enumerate(texts, 1):
            fp = fingerprint(t)
            m = Message(id=f"M{i}", seq=i, text=t, batch=run)
            if fp in seen:
                m.status = "duplicate"; m.relevant = False
            seen.add(fp); msgs.append(m)
        res = self._process(msgs, provider, run, deadline=t0 + FULL_LIMIT_S, update=False)
        self.state["run_times"][run] = round(time.time() - t0, 2)
        self._save()
        return res

    def run_update(self, text: str, provider, multi: bool = False) -> dict:
        """Process new message(s). With multi=True the text is split into several messages that are read in ONE
        model call; duplicates of anything already seen are skipped without a call."""
        t0 = time.time()
        if not (text or "").strip():
            return {"ok": False, "error": "Empty message"}
        self.state["update_count"] += 1
        run = f"update-{self.state['update_count']}"
        print(f"\n######## UPDATE {run} started {now_iso()} ########", flush=True)
        existing = self.messages
        seen = {fingerprint(e.text) for e in existing}
        texts = split_pack(text) if multi else [text.strip()]
        tr = self._tracer()
        new_msgs = []
        for t in texts:
            m = Message(id=f"M{len(existing) + len(new_msgs) + 1}", seq=len(existing) + len(new_msgs) + 1,
                        text=t.strip(), batch=run)
            if fingerprint(m.text) in seen:
                m.status = "duplicate"; m.relevant = False
            seen.add(fingerprint(m.text))
            new_msgs.append(m)
        if all(m.status == "duplicate" for m in new_msgs):
            for m in new_msgs:
                tr.decide(run, "duplicate", "Identical to an earlier message; ignored (no model call).", m.id)
            self.state["messages"] += [m.model_dump() for m in new_msgs]
            self.state["run_times"][run] = round(time.time() - t0, 2)
            self._save()
            return {"ok": True, "duplicate": True, "run": run}
        res = self._process(new_msgs, provider, run, deadline=t0 + UPDATE_LIMIT_S, update=True)
        self.state["run_times"][run] = round(time.time() - t0, 2)
        self._save()
        return res

    def _tracer(self) -> Tracer:
        calls = self.state.setdefault("_calls_obj", None)
        return _StateTracer(self.state)

    # ---------- shared pipeline ----------
    def _process(self, new_msgs: list[Message], provider, run: str, deadline: float, update: bool) -> dict:
        snapshot = copy.deepcopy({k: self.state[k] for k in ("messages", "claims", "cache")})
        tr = self._tracer()
        budget = [MAX_CALLS_PER_RUN]
        ledger = self.ledger
        live = [m for m in new_msgs if m.status != "duplicate"]
        for m in new_msgs:
            if m.status == "duplicate":
                tr.decide(run, "duplicate", "Duplicate of an earlier message in the pack; ignored.", m.id)
        all_msgs = {m.id: m for m in self.messages + new_msgs}

        # 1) reading agent
        ids = {m.id for m in live}
        if update:
            user = reader.build_update_prompt(live, ledger.ledger_lines(), ledger.vocab(), _today())
        else:
            user = reader.build_initial_prompt(live, _today())
        meta, claims, errs = None, [], []
        for attempt in range(2):
            out = tr.call(provider, "reading", reader.SYSTEM, user, run, deadline, max_tokens=6000, budget=budget)
            if out is None:
                break
            meta, claims, errs = reader.parse_reader_output(out, ids)
            if meta is not None and (meta or claims or provider.is_mock):
                break
            tr.decide(run, "info", "Reading output unusable (invalid JSON); retrying once.")
        for e in errs:
            tr.decide(run, "info", e)
        if meta is None:
            self._restore(snapshot)
            if update:  # keep the message on record, but leave the plan untouched
                for m in live:
                    m.status = "not processed (model error)"
                    self.state["messages"].append(m.model_dump())
            tr.decide(run, "rollback", "Reading agent failed; previous plan kept unchanged.")
            return {"ok": False, "error": "Reading agent failed (see trace). Previous plan kept.", "run": run}

        for m in live:
            mm = meta.get(m.id) or {}
            m.sender = mm.get("sender") or m.sender
            m.channel = mm.get("channel") or m.channel
            m.date = mm.get("date") or None
            try:
                m.authority = int(mm.get("auth", 1))
            except (TypeError, ValueError):
                m.authority = 1
            # the same sender keeps the authority it already had (LLM ratings can drift between calls)
            from core.knowledge import _same_sender
            prior = [x.authority for x in self.messages if x.id != m.id and _same_sender(x.sender, m.sender)]
            if prior:
                m.authority = max(prior)
            m.relevant = bool(mm.get("relevant", True))
            m.note = mm.get("why")
            if not m.relevant:
                tr.decide(run, "info", f"Irrelevant to the event: {m.note or ''}", m.id)
        # undated update messages are newer than everything already known
        self.state["messages"] = [x.model_dump() for x in self.messages] + [m.model_dump() for m in new_msgs]
        all_msgs = {m.id: m for m in self.messages}

        def log(kind, text, mid, cid):
            tr.decide(run, kind, text, mid, cid)

        prev_plan = self.current["plan"] if self.current else None
        prev_valid = self.current["validation"]["feasible"] if self.current else False
        prev_hc = prev_plan["headcount"]["total"] if prev_plan else None

        ledger.integrate(claims, all_msgs, log)
        new_ids = [c.id for c in claims]

        # 2) rule checks on proposals that would under-supply the event
        for c in claims:
            if c.kind == "food_order_quantity" and c.active and prev_hc and (c.num() or 0) < prev_hc:
                ledger.reject([c.id], f"Rejected: {int(c.num())} meals is fewer than the {prev_hc} people who must be fed.")
                log("rejected", f"{describe(c)}: {int(c.num())} meals < {prev_hc} people to feed. "
                                f"Kept previous catering quantity.", c.msg, c.id)
        self.state["claims"] = [c.model_dump() for c in ledger.claims]

        # 3) specialist model calls ONLY for requirements code cannot match
        facts = Facts(ledger)
        cache = self.state["cache"]
        for req in venue_a.unmatched_requirements(facts, cache)[:4]:
            sysm, usr = venue_a.specialist_prompt(facts, req, all_msgs)
            out = tr.call(provider, "venue", sysm, usr, run, deadline, max_tokens=300, budget=budget)
            if out:
                why = venue_a.apply_specialist(out, req, cache, facts)
                log("info", f"Venue specialist resolved requirement '{req}': {why}", None, None)

        # 4) deterministic planning + validation
        plan, val = self._plan_validate(ledger)

        # 5) protect a valid plan from a bad update
        if update and prev_valid and not val["feasible"]:
            active_new = [ledger.by_id(i) for i in new_ids if ledger.by_id(i) and ledger.by_id(i).active]
            # Proposals and task changes from non-approving senders are rolled back. Facts a responsible party
            # reports about its own domain (a hall's capacity, a price, judge availability) are accepted and the
            # resulting infeasibility is reported honestly instead of being hidden.
            offending = [c for c in active_new if c.status == "proposed" or c.kind == "food_order_quantity"
                         or c.kind.startswith("expense_") or (c.kind in GOVERNING and c.authority < 3)
                         or c.authority < 2]
            fails = [x for x in val["checks"] if x["hard"] and not x["passed"]]
            reason = "; ".join(f"{x['constraint']} ({x['detail']})" for x in fails)
            if offending:
                ledger.reject([c.id for c in offending],
                              f"Rejected: applying it would break the plan – {reason}")
                for c in offending:
                    log("rejected", f"{describe(c)} would make the plan invalid: {reason}. Previous decision kept.",
                        c.msg, c.id)
                self.state["claims"] = [c.model_dump() for c in ledger.claims]
                plan, val = self._plan_validate(ledger)
            else:
                log("conflict", f"Authoritative change makes the plan infeasible: {reason}. Reported, not hidden.",
                    new_msgs[0].id, None)

        # message-level status
        for m in new_msgs:
            mc = [c for c in ledger.claims if c.msg == m.id]
            rej = [c for c in mc if c.status == "rejected"]
            if m.status == "duplicate":
                continue
            m.status = ("rejected" if mc and len(rej) == len(mc) else "partially rejected" if rej
                        else "irrelevant" if not m.relevant else "processed")
        msgs_by = {m.id: m for m in new_msgs}
        self.state["messages"] = [msgs_by.get(x["id"], Message(**x)).model_dump() for x in self.state["messages"]]
        self.state["claims"] = [c.model_dump() for c in ledger.claims]

        # 6) version + diff
        summ = domain_summary(plan)
        prev_summ = self.current["summary"] if self.current else None
        changed = diff(prev_summ, summ)
        touched = {c.domain for c in claims if c.status not in ("rejected", "irrelevant", "superseded")}
        run_calls = [c for c in self.calls if c.run == run]
        version = {"n": len(self.state["versions"]) + 1, "run": run, "timestamp": now_iso(),
                   "message_ids": [m.id for m in new_msgs], "plan": plan, "validation": val, "summary": summ,
                   "changed_domains": sorted(changed.keys()), "diff": changed,
                   "affected_by_dependency": sorted(affected(touched)) if update else AREAS,
                   "model_call_areas": [c.area for c in run_calls],
                   "snapshot": {"messages": self.state["messages"], "claims": self.state["claims"],
                                "cache": copy.deepcopy(self.state["cache"])}}
        self.state["versions"].append(version)
        tr.decide(run, "info", f"Version {version['n']}: plan {'FEASIBLE' if val['feasible'] else 'NOT FEASIBLE'}; "
                               f"changed areas: {', '.join(version['changed_domains']) or 'none'}; "
                               f"model calls this run: {len(run_calls)} ({', '.join(version['model_call_areas'])}).")
        t = totals(self.calls, run)
        print(f"######## {run} done: calls={t['calls']} in={t['input_tokens']} out={t['output_tokens']} "
              f"total={t['total_tokens']} | ALL RUNS total tokens={totals(self.calls)['total_tokens']} ########",
              flush=True)
        return {"ok": True, "run": run, "version": version["n"], "feasible": val["feasible"],
                "changed": version["changed_domains"]}

    def _plan_validate(self, ledger: Ledger):
        plan = build_plan(ledger, self.state["cache"], self.state.get("settings", {}))
        return plan, validate(plan, Facts(ledger))

    def _restore(self, snap):
        for k, v in snap.items():
            self.state[k] = v

    def replan(self):
        """Re-run deterministic planning after a settings change (no model call)."""
        if not self.current:
            return
        plan, val = self._plan_validate(self.ledger)
        self.current["plan"], self.current["validation"] = plan, val
        self.current["summary"] = domain_summary(plan)
        self._save()

    def rollback(self) -> bool:
        """Restore the previous version (trace entries are kept: they really happened)."""
        if len(self.state["versions"]) < 2:
            return False
        gone = self.state["versions"].pop()
        prev = self.state["versions"][-1]
        snap = prev["snapshot"]
        self.state["messages"] = copy.deepcopy(snap["messages"])
        self.state["claims"] = copy.deepcopy(snap["claims"])
        self.state["cache"] = copy.deepcopy(snap["cache"])
        _StateTracer(self.state).decide("rollback", "rollback", f"Rolled back version {gone['n']} ({gone['run']}) "
                                                                f"to version {prev['n']}.")
        self._save()
        return True


class _StateTracer(Tracer):
    """Tracer writing straight into the JSON-able state."""

    def __init__(self, state: dict):
        self.state = state

        class _L(list):
            def __init__(s, key, cls):
                super().__init__(); s.key, s.cls = key, cls

            def append(s, item):
                state[s.key].append(item.model_dump())

            def __len__(s):
                return len(state[s.key])

        self.calls = _L("calls", ModelCall)
        self.decisions = _L("decisions", Decision)
