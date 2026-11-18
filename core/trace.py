"""Model-call trace. Every real (or mock-labelled) call goes through `Tracer.call`.

The trace is printed to the terminal as calls happen, persisted as JSON, and
rendered as Markdown. Token counts come only from provider usage metadata.
"""
from __future__ import annotations

import datetime as dt
import json
import time
from typing import Optional

from core.models import Decision, ModelCall
from services.llm_provider import LLMError, Provider, is_retryable


import sys

for _stream in (sys.stdout, sys.stderr):  # Windows consoles (cp1252) must never crash on Roman Urdu / symbols
    try:
        _stream.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


class Tracer:
    def __init__(self, calls: list[ModelCall], decisions: list[Decision]):
        self.calls = calls
        self.decisions = decisions

    # ---- model calls -------------------------------------------------
    def call(self, provider: Provider, area: str, system: str, user: str, run: str,
             deadline: float, max_tokens: int = 4000, budget: Optional[list] = None) -> Optional[str]:
        """Make one model call (with limited retries for transient errors).
        `budget` is a 1-element list holding remaining allowed calls for this run."""
        attempts = 0
        while True:
            if budget is not None and budget[0] <= 0:
                self.decide(run, "info", f"Model-call budget exhausted; skipped {area} call.")
                return None
            remaining = deadline - time.time()
            if remaining < 3:
                self.decide(run, "info", f"Time limit reached; skipped {area} call.")
                return None
            provider.timeout_s = max(3, min(provider.timeout_s, remaining - 1))
            attempts += 1
            if budget is not None:
                budget[0] -= 1
            n = len(self.calls) + 1
            ts = now_iso()
            t0 = time.time()
            try:
                r = provider.complete(system, user, max_tokens)
                mc = ModelCall(n=n, timestamp=ts, provider=provider.name, model=provider.model, area=area,
                               input=f"[SYSTEM]\n{system}\n\n[USER]\n{user}", output=r.text,
                               input_tokens=r.input_tokens, output_tokens=r.output_tokens,
                               thinking_tokens=r.thinking_tokens, tokens_reported=r.tokens_reported,
                               duration_s=round(r.duration_s or (time.time() - t0), 2), success=True,
                               run=run, is_mock=provider.is_mock)
                self.calls.append(mc)
                print_call(mc)
                return r.text
            except Exception as e:  # noqa: BLE001
                mc = ModelCall(n=n, timestamp=ts, provider=provider.name, model=provider.model, area=area,
                               input=f"[SYSTEM]\n{system}\n\n[USER]\n{user}", output="",
                               input_tokens=None, output_tokens=None, tokens_reported=False,
                               duration_s=round(time.time() - t0, 2), success=False,
                               error=f"{type(e).__name__}: {str(e)[:300]}", run=run, is_mock=provider.is_mock)
                self.calls.append(mc)
                print_call(mc)
                if attempts < 3 and is_retryable(e) and deadline - time.time() > 8:
                    fb = [m for m in getattr(provider, "fallbacks", []) if m != provider.model]
                    if attempts >= 2 and fb:  # primary still failing: switch to the fallback small model
                        self.decide(run, "info", f"{provider.model} unavailable; retrying with {fb[0]}.")
                        provider.model = fb[0]
                    time.sleep(min(2 ** attempts, 4))
                    continue
                return None

    # ---- decisions ---------------------------------------------------
    def decide(self, run: str, kind: str, text: str, message_id: str | None = None, claim_id: str | None = None):
        d = Decision(timestamp=now_iso(), run=run, kind=kind, text=text, message_id=message_id, claim_id=claim_id)
        self.decisions.append(d)
        print(f"  [{kind.upper()}] {('(' + message_id + ') ') if message_id else ''}{text}", flush=True)


def totals(calls: list[ModelCall], run: Optional[str] = None) -> dict:
    cs = [c for c in calls if run is None or c.run == run]
    real = [c for c in cs if not c.is_mock]
    inp = [c.input_tokens for c in real if c.input_tokens is not None]
    out = [(c.output_tokens or 0) + (c.thinking_tokens or 0) for c in real if c.output_tokens is not None]
    missing = sum(1 for c in real if not c.tokens_reported)
    return {
        "calls": len(cs),
        "real_calls": len(real),
        "mock_calls": len(cs) - len(real),
        "failed_calls": sum(1 for c in cs if not c.success),
        "input_tokens": sum(inp),
        "output_tokens": sum(out),
        "total_tokens": sum(inp) + sum(out),
        "calls_without_token_counts": missing,
        "model_time_s": round(sum(c.duration_s for c in cs), 2),
    }


def print_call(c: ModelCall):
    tag = "MOCK (no model)" if c.is_mock else f"{c.provider}/{c.model}"
    toks = (f"in={c.input_tokens} out={c.output_tokens}" + (f" thinking={c.thinking_tokens}" if c.thinking_tokens else "")
            if c.tokens_reported else "tokens=UNAVAILABLE")
    print(f"\n=== MODEL CALL #{c.n} [{c.area}] {tag} run={c.run} {c.duration_s}s "
          f"{'OK' if c.success else 'FAILED: ' + str(c.error)} {toks}", flush=True)
    print("--- INPUT ---\n" + c.input[-3000:], flush=True)
    print("--- OUTPUT ---\n" + c.output, flush=True)


def trace_markdown(calls: list[ModelCall], decisions: list[Decision], run_times: dict) -> str:
    lines = ["# CONCORD (Event Planner) — model trace", ""]
    for c in calls:
        tag = "MOCK — not a model call" if c.is_mock else f"{c.provider} / `{c.model}`"
        toks = (f"input {c.input_tokens}, output {c.output_tokens}" + (f", thinking {c.thinking_tokens}" if c.thinking_tokens else "")
                if c.tokens_reported else "token counts unavailable from provider")
        lines += [f"## Call #{c.n} — area: **{c.area}** — run: {c.run}",
                  f"- Time: {c.timestamp}  |  Model: {tag}  |  Duration: {c.duration_s}s  |  "
                  f"{'Success' if c.success else 'FAILED: ' + str(c.error)}",
                  f"- Tokens (provider-reported): {toks}", "", "**Input**", "```", c.input, "```",
                  "**Output**", "```", c.output, "```", ""]
    lines += ["## Decisions and rejections", ""]
    for d in decisions:
        lines.append(f"- [{d.run}] **{d.kind.upper()}** {('(' + d.message_id + ') ') if d.message_id else ''}{d.text}")
    t = totals(calls)
    lines += ["", "## Totals", f"- Model calls: {t['calls']} (real {t['real_calls']}, mock {t['mock_calls']}, failed {t['failed_calls']})",
              f"- Input tokens: {t['input_tokens']}", f"- Output tokens: {t['output_tokens']}",
              f"- **Total tokens: {t['total_tokens']}**",
              f"- Calls without provider token counts: {t['calls_without_token_counts']}"]
    for run, secs in run_times.items():
        lines.append(f"- Wall time {run}: {secs}s")
    return "\n".join(lines)


def trace_json(calls: list[ModelCall], decisions: list[Decision], run_times: dict) -> str:
    return json.dumps({"calls": [c.model_dump() for c in calls], "decisions": [d.model_dump() for d in decisions],
                       "totals": totals(calls), "run_times_s": run_times}, indent=2, ensure_ascii=False)
