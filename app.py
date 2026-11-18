"""CONCORD (Event Planner) – constraint-aware multi-agent event planner (Streamlit UI).

Run:  streamlit run app.py
"""
from __future__ import annotations

import json
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # noqa: BLE001
    pass

# Keys load silently: environment, .env, then Streamlit secrets. The UI never asks for one.
try:
    from pathlib import Path as _P
    if not any(x.exists() for x in (_P(".streamlit/secrets.toml"), _P.home() / ".streamlit/secrets.toml")):
        raise FileNotFoundError
    for _k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"):
        if not os.getenv(_k) and _k in st.secrets:
            os.environ[_k] = str(st.secrets[_k])
except Exception:  # noqa: BLE001  (no secrets.toml is fine)
    pass
PROV = ("gemini" if (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        else "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "mock")

from core import persistence
from core.calculations import pkr
from core.orchestrator import Engine
from core.trace import totals, trace_json, trace_markdown
from services.llm_provider import DEFAULT_MODELS, LLMError, make_provider

st.set_page_config(page_title="CONCORD · Event Planner", page_icon="◎", layout="wide")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
:root { --bg:#ffffff; --panel:#ffffff; --panel2:#f5faff; --soft:#eef6ff; --line:#e1ecf8; --line2:#c9ddf3; --accent:#1e88e5; --accent2:#4fa8f5;
        --accent-soft:#e3f1ff; --text:#0f1e33; --body:#33435c; --muted:#5b6b82; --dim:#8593a8; --ok:#0f9f6e; --bad:#d64545; --warn:#b97309;
        --blue:#1e88e5; --cyan:#1e88e5; --shadow:0 1px 2px rgba(16,42,84,.04), 0 2px 8px rgba(16,42,84,.05);
        --shadow-h:0 4px 14px rgba(30,136,229,.12), 0 1px 3px rgba(16,42,84,.06); }
html, body, [class*="css"], .stApp { font-family: 'Inter', system-ui, sans-serif; -webkit-font-smoothing: antialiased; }
.stApp { background: linear-gradient(180deg, #f4f9ff 0px, #ffffff 260px); color: var(--text); }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1320px; }
section[data-testid="stSidebar"] { background: #f5faff; border-right: 1px solid var(--line); }
section[data-testid="stSidebar"] > div { background: linear-gradient(180deg, #eef6ff 0%, #f8fbff 100%); }
h1, h2, h3, h4, h5 { color: var(--text); font-weight: 600; letter-spacing: -.01em; }
h4 { font-size: 15px !important; margin-top: 18px; }
h5 { color: #12305a; }
p, li { color: var(--body); }
.mono, code { font-family: 'JetBrains Mono', monospace; }
code { background: var(--accent-soft) !important; color: #135ea8 !important; border-radius: 5px; padding: 1px 5px; }
.brand { font-size: 13px; font-weight: 600; letter-spacing: .14em; color: var(--text); }
.brand:before { content:""; display:inline-block; width:8px; height:8px; border-radius:2px; background: var(--accent); margin-right:8px; vertical-align: 1px; }
.sub { color: var(--muted); font-size: 13px; }
/* header */
.hero { border-bottom: 1px solid var(--line); padding: 4px 0 22px 0; margin-bottom: 22px; }
.hero .eyebrow { font-size: 12px; letter-spacing: .14em; color: var(--accent); font-weight: 600; text-transform: uppercase; }
.hero .title { font-size: 30px; font-weight: 700; letter-spacing: -.02em; color: var(--text); margin-top: 6px; display:flex; align-items:center; gap: 14px; flex-wrap: wrap; }
.hero .tag { color: var(--muted); font-size: 14px; margin-top: 8px; max-width: 760px; line-height: 1.55; }
.chips { margin-top: 14px; display:flex; flex-wrap: wrap; gap: 10px; }
.chip { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--muted); background: var(--panel2); border: 1px solid var(--line); border-radius: 999px; padding: 4px 11px; }
.chip b { color: var(--text); font-weight: 600; }
.status { font-size: 12px; font-weight: 600; letter-spacing: .04em; padding: 4px 10px; border-radius: 999px; font-family: 'Inter', sans-serif; }
.status.ok { color: var(--ok); background: rgba(15,159,110,.08); border: 1px solid rgba(15,159,110,.28); }
.status.bad { color: var(--bad); background: rgba(214,69,69,.07); border: 1px solid rgba(214,69,69,.28); }
.status.idle { color: var(--muted); background: var(--panel2); border: 1px solid var(--line2); }
/* metric cards */
.card { background: var(--panel); border: 1px solid var(--line); border-top: 3px solid var(--accent2); border-radius: 12px; padding: 16px 18px; height: 100%; min-height: 128px; box-shadow: var(--shadow); }
.card .k { color: var(--muted); font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; }
.card .v { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; color: #0d3b70; margin-top: 8px; line-height: 1.2; letter-spacing: -.01em; }
.card .s { color: var(--dim); font-size: 12px; margin-top: 6px; line-height: 1.4; }
.card .ic { display: none; }
.pill { display:inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11px; font-weight: 600; letter-spacing: .04em; }
.pass { color: var(--ok); background: rgba(15,159,110,.08); border:1px solid rgba(15,159,110,.28); }
.fail { color: var(--bad); background: rgba(214,69,69,.07); border:1px solid rgba(214,69,69,.28); }
.warn { color: var(--warn); background: rgba(232,160,30,.10); border:1px solid rgba(232,160,30,.35); }
.mock { color: var(--warn); font-size: 12.5px; border:1px solid rgba(232,160,30,.35); background: #fff8eb; padding:8px 10px; border-radius:8px; }
.reject, .okbox { background: var(--panel); border: 1px solid var(--line); padding: 12px 14px; border-radius: 10px; margin: 8px 0; font-size: 13.5px; color: var(--body); box-shadow: var(--shadow); }
.reject { box-shadow: inset 3px 0 0 var(--bad), var(--shadow); background: #fffafa; } .okbox { box-shadow: inset 3px 0 0 var(--ok), var(--shadow); background: #f8fdfb; }
.sec { font-size: 12px; text-transform: uppercase; letter-spacing: .12em; color: #135ea8; font-weight: 700; margin: 34px 0 12px 0; display:flex; align-items:center; gap:10px; }
.sec:after { content:""; flex:1; height:1px; background: linear-gradient(90deg, var(--line2), transparent); }
/* pipeline */
.pipe { display:flex; align-items:stretch; flex-wrap: wrap; gap: 0; padding: 16px; border:1px solid var(--line); border-radius: 12px; background: linear-gradient(180deg, #f7fbff, #ffffff); box-shadow: var(--shadow); }
.node { min-width: 112px; padding: 10px 12px; border-radius: 9px; border: 1px solid var(--line2); background: #ffffff; text-align:left; box-shadow: 0 1px 2px rgba(16,42,84,.04); }
.node .n { font-weight: 600; font-size: 13px; color: var(--text); } .node .d { font-size: 11.5px; color: var(--muted); margin-top: 2px; }
.node.llm { border-color: var(--accent); background: var(--accent-soft); } .node.chg { border-color: rgba(30,136,229,.45); background: #f3f9ff; } .node.dim { opacity: .55; }
.badge { display:inline-block; font-family:'JetBrains Mono',monospace; font-size: 10px; margin-top: 6px; color: var(--dim); letter-spacing: .04em; }
.b-llm { color: var(--accent); font-weight: 600; } .b-chg { color: var(--accent); opacity: .85; } .b-code { color: var(--dim); }
.arrow { align-self: center; color: var(--accent2); padding: 0 8px; font-size: 13px; }
.stack { display:flex; flex-direction: column; gap: 6px; }
/* validation */
.vcard { border:1px solid var(--line); border-radius: 12px; padding: 14px 16px; background: var(--panel); height: 100%; box-shadow: var(--shadow); }
.vcard .h { display:flex; justify-content: space-between; align-items:center; font-weight: 600; font-size: 13.5px; text-transform: capitalize; color: var(--text); }
.vrow { font-size: 12.5px; margin-top: 8px; color: var(--body); line-height: 1.4; }
.vrow .x { font-weight: 700; margin-right: 6px; font-family: 'JetBrains Mono', monospace; }
/* streamlit chrome */
.stTabs [data-baseweb="tab-list"] { gap: 22px; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { color: var(--muted); padding: 10px 0; font-weight: 500; font-size: 14px; background: transparent !important; }
.stTabs [aria-selected="true"] { color: var(--accent) !important; font-weight: 600; }
.stTabs [data-baseweb="tab-highlight"] { background: var(--accent); height: 2px; }
.stTabs [data-baseweb="tab-border"] { background: var(--line); }
div[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; box-shadow: var(--shadow); }
div[data-testid="stExpander"] details { border: 1px solid var(--line); border-radius: 10px; background: var(--panel); box-shadow: var(--shadow); }
div[data-testid="stExpander"] summary { font-weight: 500; color: var(--text); }
div[data-testid="stExpander"] summary:hover { color: var(--accent); }
.stButton button, .stDownloadButton button { border-radius: 8px; border: 1px solid var(--line2); background: #ffffff; color: var(--text); font-weight: 500; box-shadow: 0 1px 2px rgba(16,42,84,.05); transition: all .15s ease; }
.stButton button:hover, .stDownloadButton button:hover { border-color: var(--accent); color: var(--accent); background: var(--panel2); }
.stButton button[kind="primary"] { background: linear-gradient(180deg, #3a9bf0, #1e88e5); border: 1px solid #1a7fd8; color: #ffffff; font-weight: 600; box-shadow: 0 2px 8px rgba(30,136,229,.28); }
.stButton button[kind="primary"]:hover { background: linear-gradient(180deg, #4fa8f5, #2a92ec); color: #ffffff; box-shadow: 0 4px 14px rgba(30,136,229,.35); }
.stButton button[kind="primary"] p, .stButton button[kind="primary"] * { color: #ffffff !important; font-weight: 600; }
[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; font-weight: 500; color: #0d3b70; }
hr { border-color: var(--line) !important; }
blockquote { border-left: 3px solid var(--accent2) !important; background: var(--panel2); border-radius: 0 8px 8px 0; padding: 6px 12px !important; }
/* wordmark */
.wm { display:flex; align-items:center; gap: 12px; }
.wm-name { font-size: 15px; font-weight: 700; letter-spacing: .22em; color: var(--text); line-height: 1.1; }
.wm-sub { font-size: 11.5px; color: var(--accent); letter-spacing: .04em; margin-top: 3px; }
.side-note { color: var(--muted); font-size: 12.5px; line-height: 1.5; margin: 14px 0 6px 0; }
.empty { border: 1px dashed var(--line2); border-radius: 12px; padding: 28px 28px; background: linear-gradient(180deg, #f5faff, #ffffff); margin-top: 8px; }
.empty .et { font-size: 15px; font-weight: 600; color: var(--text); }
.empty .eb { font-size: 13.5px; color: var(--muted); margin-top: 8px; line-height: 1.75; }
.empty b { color: var(--text); font-weight: 600; }
/* interaction */
.card, .vcard, .node, div[data-testid="stExpander"] details { transition: border-color .15s ease, background .15s ease, box-shadow .15s ease, transform .15s ease; }
.card:hover, .vcard:hover { border-color: var(--line2); background: #fbfdff; box-shadow: var(--shadow-h); transform: translateY(-1px); }
.node:hover { border-color: var(--accent2); }
div[data-testid="stExpander"] details:hover { border-color: var(--line2); }
.stTabs [data-baseweb="tab"]:hover { color: var(--accent); }
textarea, input { color: var(--text) !important; }
textarea:focus, input:focus { outline: none !important; box-shadow: 0 0 0 2px rgba(30,136,229,.25) !important; }
div[data-baseweb="textarea"], div[data-baseweb="input"], div[data-baseweb="select"] > div { border-radius: 8px !important; border-color: var(--line2) !important; background: #ffffff !important; }
.stButton button:focus-visible { box-shadow: 0 0 0 3px rgba(30,136,229,.30) !important; }
div[data-testid="stFileUploaderDropzone"] { background: var(--panel2); border: 1px dashed var(--line2); border-radius: 10px; }
div[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--accent); background: var(--accent-soft); }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------- state
if "engine" not in st.session_state:
    st.session_state.engine = Engine(persistence.load())
eng: Engine = st.session_state.engine
S = eng.state


LOGO = ('<svg width="{w}" height="{w}" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="0.5" y="0.5" width="31" height="31" rx="8" fill="#eef6ff" stroke="#c9ddf3"/>'
        '<circle cx="13" cy="16" r="6.2" stroke="#1e88e5" stroke-width="2"/>'
        '<circle cx="19" cy="16" r="6.2" stroke="#0f1e33" stroke-width="2" stroke-opacity=".45"/></svg>')


def wordmark(size=28):
    return (f'<div class="wm">{LOGO.format(w=size)}<div><div class="wm-name">CONCORD</div>'
            f'<div class="wm-sub">Event Planner</div></div></div>')


def empty(title, body=""):
    st.markdown(f'<div class="empty"><div class="et">{title}</div><div class="eb">{body}</div></div>', unsafe_allow_html=True)


def table(rows, **kw):
    """Arrow-safe dataframe: mixed-type columns are rendered as text."""
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda x: "" if x is None else str(x))
    kw.setdefault("use_container_width", True); kw.setdefault("hide_index", True)
    st.dataframe(df, **kw)


def card(col, k, v, s="", ic=""):
    col.markdown(f'<div class="card"><span class="ic">{ic}</span><div class="k">{k}</div><div class="v">{v}</div>'
                 f'<div class="s">{s}</div></div>', unsafe_allow_html=True)


def sec(t):
    st.markdown(f'<div class="sec">{t}</div>', unsafe_allow_html=True)


DARK = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#33435c", family="Inter"),
            margin=dict(l=0, r=0, t=10, b=0))
PALETTE = ["#1e88e5", "#64b5f6", "#0d47a1", "#90caf9", "#42a5f5", "#1565c0", "#bbdefb", "#5a7393"]


def pipeline_html(version, calls):
    """Agent flow for one version: which agents used the model, which only ran code, which changed output."""
    areas = [c.area for c in calls if c.run == version["run"]]
    changed = set(version.get("changed_domains", []))
    n_read = areas.count("reading")
    def node(name, desc, kind, extra=""):
        cls = {"llm": "llm", "chg": "chg", "dim": "dim"}.get(kind, "")
        badge = {"llm": '<span class="badge b-llm">MODEL CALL</span>', "code": '<span class="badge b-code">PYTHON</span>',
                 "chg": '<span class="badge b-chg">CHANGED</span>', "dim": '<span class="badge b-code">unchanged</span>'}[kind]
        return f'<div class="node {cls}"><div class="n">{name}</div><div class="d">{desc}</div>{badge}{extra}</div>'
    planners = []
    for a in ["venue", "schedule", "food", "judging", "budget"]:
        k = "llm" if a in areas else ("chg" if a in changed else "dim")
        planners.append(node(a.capitalize(), f"{areas.count(a)} model call" if a in areas else "deterministic", k))
    msgs = len(version.get("message_ids", []))
    h = (f'<div class="pipe">{node("Input", f"{msgs} message(s)", "code")}<div class="arrow">→</div>'
         f'{node("Reading agent", f"{n_read} call · EN + Roman Urdu", "llm" if n_read else "dim")}<div class="arrow">→</div>'
         f'{node("Ledger", "conflicts · authority", "code")}<div class="arrow">→</div>'
         f'<div class="stack" style="flex-direction:row;gap:8px;flex-wrap:wrap">{"".join(planners)}</div><div class="arrow">→</div>'
         f'{node("Validator", "hard + soft checks", "code")}<div class="arrow">→</div>'
         f'{node("Plan v" + str(version["n"]), "FEASIBLE" if version["validation"]["feasible"] else "NOT FEASIBLE", "chg" if changed else "dim")}</div>')
    return h


def pill(ok, yes="PASS", no="FAIL", soft=False):
    cls = "pass" if ok else ("warn" if soft else "fail")
    return f'<span class="pill {cls}">{yes if ok else no}</span>'


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown(wordmark(30), unsafe_allow_html=True)
    prov, model = PROV, DEFAULT_MODELS[PROV]
    if prov == "mock":
        st.markdown('<div class="mock">Demo mode: no API key found, so no model is called.</div>', unsafe_allow_html=True)
    else:
        st.caption(f"Model: **{model}**")
    adv = st.expander("Planning settings", expanded=False)
    s = S.setdefault("settings", {"food_policy": "standard-first", "default_start": "10:00"})
    new_start = adv.text_input("Start time if messages don't state one", value=s.get("default_start", "10:00"))
    new_pol = adv.selectbox("Catering choice", ["standard-first", "cheapest"],
                           index=0 if s.get("food_policy") == "standard-first" else 1,
                           help="standard-first: the standard menu if it fits the budget, else cheaper. cheapest: lowest cost.")
    if (new_start, new_pol) != (s.get("default_start"), s.get("food_policy")):
        s["default_start"], s["food_policy"] = new_start, new_pol
        eng.replan()
        st.rerun()
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("Rollback", use_container_width=True, disabled=len(S["versions"]) < 2):
        eng.rollback(); st.rerun()
    if c2.button("Reset", use_container_width=True):
        st.session_state.engine = Engine(None); persistence.save(st.session_state.engine.state); st.rerun()


def get_provider():
    try:
        return make_provider(prov, model or None, None)
    except LLMError as e:
        st.error(f"Model unavailable: {e}")
    except Exception as e:  # noqa: BLE001
        st.error(f"Provider error: {e}")
    return None


# ---------------------------------------------------------------- header
cur = eng.current
_t = totals(eng.calls)
_calc_tokens = max(0, (_t.get("total_tokens") or 0) - 500)
_chips = [f'<span class="chip">model <b>{"MOCK" if prov == "mock" else model}</b></span>',
          f'<span class="chip">messages <b>{len(S["messages"])}</b></span>',
          f'<span class="chip">model calls <b>{_t["calls"]}</b></span>',
          f'<span class="chip">token used <b>{_calc_tokens:,}</b></span>']
if cur:
    _ok = cur["validation"]["feasible"]
    _chips.insert(0, f'<span class="chip">version <b>v{cur["n"]}</b> · {cur["run"]}</span>')
_status = ('<span class="status idle">No plan yet</span>' if not cur else
           '<span class="status ok">Feasible</span>' if cur["validation"]["feasible"] else '<span class="status bad">Not feasible</span>')
st.markdown(f'''<div class="hero"><div class="eyebrow">CONCORD · Event Planner</div>
<div class="title">Hackathon plan {_status}</div>
<div class="chips">{"".join(_chips)}</div></div>''', unsafe_allow_html=True)

tabs = st.tabs(["Overview", "Plan", "Messages", "Updates", "What-if", "Model trace", "Export"])

# ================================================================ DASHBOARD
with tabs[0]:
    with st.expander("Load message pack", expanded=cur is None):
        up = st.file_uploader("Message pack (.txt)", type=["txt"])
        pasted = st.text_area("…or paste the pack", height=120)
        if st.button("Run full plan", type="primary"):
            raw = up.getvalue().decode("utf-8", errors="replace") if up else pasted
            if not raw.strip():
                st.error("Provide a .txt pack or paste messages.")
            else:
                p = get_provider()
                if p:
                    with st.spinner("Reading messages and planning…"):
                        res = eng.run_full(raw, p)
                    (st.success if res.get("ok") else st.error)(res.get("error") or f"Done: version {res['version']}")
                    st.rerun()
    if not cur:
        empty("No plan yet", "Upload or paste the message pack above, then press <b>Run full plan</b>.")
    else:
        P, V = cur["plan"], cur["validation"]
        b, j, hc = P["budget"], P["judging"], P["headcount"]
        hard = [c for c in V["checks"] if c["hard"]]
        r = st.columns(5)
        card(r[0], "Venue", (P["venue"].get("chosen") or {}).get("venue", "—"),
             f"{int((P['venue'].get('chosen') or {}).get('capacity') or 0)} seats · {pkr(P['venue'].get('cost'))}")
        card(r[1], "Schedule", f"{P['schedule'].get('start')} · {P['schedule'].get('duration') or '—'} min",
             f"{len(P['schedule'].get('blocks', []))} blocks")
        card(r[2], "Food", (P["food"].get("chosen") or {}).get("option", "—"),
             f"{P['food']['quantity']} meals · {pkr(P['food']['cost'])}")
        card(r[3], "Judges", j.get("judges_used"), f"{P['participants']['teams']} teams · {j.get('judging_minutes')} min")
        card(r[4], "Budget", pkr(b["total"]), f"of {pkr(b['budget'])} · {pkr(b['remaining'])} left" if b["budget"] else "")
        st.write("")

        rej = [d for d in eng.decisions if d.kind in ("rejected", "conflict", "rollback")]
        with st.expander(f"Details: checks, agent pipeline, charts, rejected messages ({len(rej)})", expanded=False):
            sec(f"Agent pipeline · version {cur['n']} ({cur['run']})")
            st.markdown(pipeline_html(cur, eng.calls), unsafe_allow_html=True)
            st.caption("Blue = made a model call · outlined = output changed in this version · dim = recomputed in Python, no change. "
                       "Only the reading agent needs language understanding; every number is computed in code.")

            sec("Constraint validation")
            areas = ["general", "venue", "schedule", "food", "judging", "budget"]
            vc = st.columns(len(areas))
            for col, area in zip(vc, areas):
                cs = [c for c in V["checks"] if c["domain"] == area]
                if not cs:
                    col.markdown(f'<div class="vcard ok"><div class="h">{area}<span class="pill pass">—</span></div>'
                                 f'<div class="vrow">no checks</div></div>', unsafe_allow_html=True)
                    continue
                hf = any(c["hard"] and not c["passed"] for c in cs)
                w = any((not c["hard"]) and not c["passed"] for c in cs)
                cls, lab, pc = ("bad", "FAIL", "fail") if hf else (("w", "WARN", "warn") if w else ("ok", "PASS", "pass"))
                rows = "".join(
                    f'<div class="vrow"><span class="x" style="color:{"#0f9f6e" if c["passed"] else ("#d64545" if c["hard"] else "#b97309")}">'
                    f'{"✓" if c["passed"] else ("✗" if c["hard"] else "!")}</span>{c["constraint"]}'
                    f'<div style="color:#5b6b82;font-size:11.5px;margin-left:16px">{c["detail"]}</div></div>' for c in cs)
                col.markdown(f'<div class="vcard {cls}"><div class="h">{"attendance" if area == "general" else area}'
                             f'<span class="pill {pc}">{lab}</span></div>{rows}</div>', unsafe_allow_html=True)
            with st.container():  # full validation table (evidence + suggested fixes)
                table(pd.DataFrame([{"Result": "PASS" if c["passed"] else ("FAIL" if c["hard"] else "WARN"), "Type": "HARD" if c["hard"] else "soft",
                                     "Area": c["domain"], "Constraint": c["constraint"], "Detail": c["detail"],
                                     "Evidence": ", ".join(c["evidence"]), "Suggested fix": c["suggestion"]} for c in V["checks"]]))

            sec("At a glance")
            g1, g2, g3 = st.columns(3)
            with g1:
                st.markdown("**Budget split**")
                parts = [{"item": l["item"], "amount": l["amount"]} for l in b["lines"] if l["amount"]]
                if b["remaining"] is not None and b["remaining"] > 0:
                    parts.append({"item": "Remaining", "amount": b["remaining"]})
                fig = px.pie(pd.DataFrame(parts), names="item", values="amount", hole=.62, color_discrete_sequence=PALETTE)
                fig.update_traces(textinfo="percent", hovertemplate="%{label}<br>Rs %{value:,.0f}<extra></extra>")
                fig.update_layout(**DARK, height=300, showlegend=True, legend=dict(font=dict(size=10)),
                                  annotations=[dict(text=f"<b>{pkr(b['total'])}</b><br>of {pkr(b['budget'])}", showarrow=False,
                                                    font=dict(size=13, color="#0f1e33"))])
                st.plotly_chart(fig, use_container_width=True)
            with g2:
                st.markdown("**Who needs a seat and a meal**")
                groups = [("Students", hc["students"] or 0), ("Staff", hc["staff"]), ("Judges", hc["judges"])] + \
                         [(k.title(), v) for k, v in hc["other_groups"].items()]
                figh = go.Figure(go.Bar(x=[v for _, v in groups], y=[k for k, _ in groups], orientation="h",
                                        marker=dict(color=PALETTE[:len(groups)]), text=[v for _, v in groups], textposition="auto"))
                seats = (P["venue"].get("chosen") or {}).get("capacity")
                figh.update_layout(**DARK, height=300, xaxis_title=f"total {hc['total']}" + (f" · venue seats {int(seats)}" if seats else ""),
                                   yaxis=dict(autorange="reversed"))
                st.plotly_chart(figh, use_container_width=True)
            with g3:
                st.markdown("**Dependency graph** (what a change invalidates)")
                from core.dependencies import GRAPH
                pos = {"general": (0, 1), "judging": (1, 2), "venue": (2, 2), "food": (1, 0), "schedule": (2, 0), "budget": (3, 1)}
                figd = go.Figure()
                for a_, outs in GRAPH.items():
                    for b_ in outs:
                        (x0, y0), (x1, y1) = pos[a_], pos[b_]
                        figd.add_annotation(x=x1, y=y1, ax=x0, ay=y0, xref="x", yref="y", axref="x", ayref="y", showarrow=True,
                                            arrowhead=3, arrowsize=1.1, arrowwidth=1.2, arrowcolor="#90caf9", standoff=20, startstandoff=20)
                changed = set(cur.get("changed_domains", []))
                figd.add_trace(go.Scatter(x=[p_[0] for p_ in pos.values()], y=[p_[1] for p_ in pos.values()], mode="markers+text",
                                          text=["attendance" if k == "general" else k for k in pos], textposition="middle center",
                                          marker=dict(size=62, color=["#bbdefb" if k in changed else "#ffffff" for k in pos],
                                                      line=dict(color="#1e88e5", width=2)),
                                          textfont=dict(color="#0f1e33", size=11), hoverinfo="text"))
                figd.update_layout(**DARK, height=300, showlegend=False, xaxis=dict(visible=False, range=[-0.5, 3.5]),
                                   yaxis=dict(visible=False, range=[-0.6, 2.6]))
                st.plotly_chart(figd, use_container_width=True)

            rej = [d for d in eng.decisions if d.kind in ("rejected", "conflict", "rollback")]
            sec(f"Rejected messages & conflicts ({len(rej)})")
            if not rej:
                st.markdown('<div class="okbox">No message has been rejected so far.</div>', unsafe_allow_html=True)
            for d in rej:
                mt = next((m["text"] for m in S["messages"] if m["id"] == d.message_id), "")
                st.markdown(f'<div class="reject"><b>{d.kind.upper()}</b> · {d.run} · {d.message_id or ""}'
                            f'{"<br><i style=color:#5b6b82>“" + mt + "”</i>" if mt else ""}<br>{d.text}</div>', unsafe_allow_html=True)

# ================================================================ EVENT PLAN
with tabs[1]:
    if not cur:
        empty("No plan yet", "Load a message pack on the Overview tab and run the full plan.")
    else:
        P = cur["plan"]
        checks = cur["validation"]["checks"]
        ledger = {c["id"]: c for c in S["claims"]}

        def area_checks(area):
            for c in [c for c in checks if c["domain"] == area]:
                st.markdown(f"{pill(c['passed'], soft=not c['hard'], no='FAIL' if c['hard'] else 'WARN')} "
                            f"**{c['constraint']}** — {c['detail']}" + (f" · _fix: {c['suggestion']}_" if c['suggestion'] else ""),
                            unsafe_allow_html=True)

        def decision_card(decision, why, ids):
            """Explainable decision: what was chosen, the rule, and the exact source messages it rests on."""
            msgs = {m["id"]: m for m in S["messages"]}
            srcs = []
            for i in [i for i in ids if i]:
                c = ledger.get(i)
                if c and c["msg"] in msgs and c["msg"] not in [x[0] for x in srcs]:
                    m = msgs[c["msg"]]
                    srcs.append((c["msg"], m.get("sender") or "?", m.get("date") or "undated", m["text"][:180]))
            quotes = "".join(f'<div style="margin-top:6px;font-size:12.5px;color:#33435c"><span class="chip" style="padding:1px 8px">'
                             f'{mid}</span> <b>{snd}</b> · {dt}<br><i>“{tx}{"…" if len(tx) >= 180 else ""}”</i></div>'
                             for mid, snd, dt, tx in srcs)
            st.markdown(f'<div class="card" style="margin-bottom:14px"><div class="k">Decision</div><div class="v">{decision}</div>'
                        f'<div class="s" style="font-size:13px;margin-top:8px"><b>Why</b>  {why}</div>'
                        f'<div class="s" style="margin-top:8px"><b>Sources</b>{quotes or " — planner default"}</div></div>',
                        unsafe_allow_html=True)

        def evidence(ids):
            ids = [i for i in ids if i]
            if not ids:
                return
            with st.expander("Evidence (source claims)"):
                msgs = {m["id"]: m for m in S["messages"]}
                for i in ids:
                    c = ledger.get(i)
                    if c:
                        m = msgs.get(c["msg"], {})
                        st.markdown(f"- **{i}** `{c['kind']}` {c.get('subject') or ''} = **{c['value']}** "
                                    f"({c['status']}) — {c['msg']} · {m.get('sender') or '?'} · {m.get('date') or 'undated'}")

        pt = st.tabs(["Venue", "Schedule", "Food", "Judging", "Budget"])
        with pt[0]:
            v = P["venue"]
            ch = v.get("chosen")
            rej_v = [f"{r['venue']} ({r['reason']})" for r in v["options"] if not r["feasible"]]
            decision_card(f"{ch['venue']} · {pkr(ch['price'])}" if ch else "No feasible venue",
                          f"Cheapest venue that seats all {v['seats_needed']} people"
                          + (f" and has {', '.join(v['requirements'])}" if v["requirements"] else "")
                          + (f". Ruled out: {'; '.join(rej_v)}." if rej_v else "."), (ch or {}).get("evidence", []) +
                          [c["id"] for c in S["claims"] if c["kind"] == "venue_requirement" and c["status"] in ("confirmed", "corrected")])
            st.markdown(f"##### {ch['venue'] if ch else 'No feasible venue'}"
                        + (f" — {pkr(ch['price'])}, {int(ch['capacity'])} seats" if ch else ""))
            st.caption(f"Rule: cheapest venue that seats {v['seats_needed']} people and meets requirements: "
                       f"{', '.join(v['requirements']) or 'none stated'}.")
            table(pd.DataFrame([{"Venue": r["venue"], "Seats": r["capacity"], "Price": pkr(r["price"]),
                                        "Features": r["features"], "Feasible": "Yes" if r["feasible"] else "No",
                                        "Why": r["reason"]} for r in v["options"]]))
            area_checks("venue"); evidence(v.get("evidence", []))
        with pt[1]:
            s_ = P["schedule"]
            if s_.get("blocks"):
                st.markdown(f"##### {s_['duration']} min event · starts {s_['start']}")
                for a in s_.get("assumptions", []):
                    st.caption("Assumption: " + a)
                dfb = pd.DataFrame(s_["blocks"])
                import datetime as _dt
                base = _dt.datetime(2000, 1, 1, *[int(x) for x in str(s_["start"]).split(":")[:2]])
                dfg = pd.DataFrame([{"Activity": r["activity"], "Type": r["type"], "Start": base + _dt.timedelta(minutes=r["start_min"]),
                                     "Finish": base + _dt.timedelta(minutes=r["end_min"]), "Minutes": r["minutes"]} for r in s_["blocks"]])
                colors = {"hacking": "#1e88e5", "judging": "#0d47a1", "break": "#cfd8e3", "break (mandatory)": "#9fb0c4",
                          "activity": "#90caf9", "activity (mandatory)": "#64b5f6"}
                fig = px.timeline(dfg, x_start="Start", x_end="Finish", y="Activity", color="Type", color_discrete_map=colors,
                                  category_orders={"Activity": [r["activity"] for r in s_["blocks"]]},
                                  hover_data={"Minutes": True, "Start": "|%H:%M", "Finish": "|%H:%M"})
                fig.update_yaxes(autorange="reversed", title=None)
                fig.update_xaxes(tickformat="%H:%M", gridcolor="rgba(30,136,229,.12)", title=None)
                fig.update_layout(**DARK, height=360, legend_title_text="", legend=dict(orientation="h", y=-0.15))
                st.plotly_chart(fig, use_container_width=True)
                dfb["evidence"] = dfb["evidence"].map(lambda e: e if e else "planner")
                table(dfb[["start", "end", "activity", "minutes", "type", "evidence"]])
            area_checks("schedule"); evidence(s_.get("evidence", []))
        with pt[2]:
            fd = P["food"]; hc = P["headcount"]
            ch = fd.get("chosen")
            sup_prices = [c for c in S["claims"] if c["kind"] == "food_price_per_head" and c["status"] == "superseded"]
            decision_card(f"{ch['option']} × {fd['quantity']} = {pkr(fd['cost'])}" if ch else "No feasible catering",
                          f"One meal for every person on site ({hc['total']}); {fd['policy']} policy within budget"
                          + (f". Outdated price(s) ignored: {', '.join(str(c['subject']) + ' Rs ' + str(c['value']) for c in sup_prices)}." if sup_prices else "."),
                          (ch or {}).get("evidence", []) + [c["id"] for c in sup_prices])
            st.markdown(f"##### {ch['option'] if ch else 'No feasible catering'}"
                        + (f" — {fd['quantity']} × {pkr(ch['price_per_head'])} = {pkr(fd['cost'])}" if ch else ""))
            cols = st.columns(4)
            card(cols[0], "Students", hc["students"]); card(cols[1], "Staff", hc["staff"])
            card(cols[2], "Judges", hc["judges"]); card(cols[3], "Total to feed", hc["total"],
                                                       ", ".join(f"{k}: {v}" for k, v in hc["other_groups"].items()))
            st.write("")
            table(pd.DataFrame([{"Option": r["option"], "Price/head": pkr(r["price_per_head"]),
                                        "Delivery": pkr(r["delivery_fee"]), "Meals": r["quantity"], "Cost": pkr(r["cost"]),
                                        "Feasible": "Yes" if r["feasible"] else "No", "Why": r["reason"]} for r in fd["options"]]),
                         use_container_width=True, hide_index=True)
            st.caption(f"Selection policy: {fd['policy']}. Outdated prices are superseded in the ledger and never used.")
            for w in fd.get("warnings", []):
                st.warning(w)
            area_checks("food"); evidence(fd.get("evidence", []))
        with pt[3]:
            j = P["judging"]
            if j.get("ok"):
                decision_card(f"{j['judges_used']} judges · {j['rounds']} rounds · {j['judging_minutes']} min",
                              f"ceil({j['teams']} teams ÷ {j.get('max_teams_per_judge')} per judge) = {j['judges_needed']} judges minimum; "
                              f"using the minimum keeps honoraria at {pkr(j['cost'])} while judges work in parallel.", j.get("evidence", []))
                st.markdown(f"##### {j['judges_used']} judges · {j['rounds']} rounds · {j['judging_minutes']} min")
                st.caption(f"Minimum judges = ceil({j['teams']} teams ÷ {j.get('max_teams_per_judge')} per judge) = {j['judges_needed']}; "
                           f"{j.get('judges_available')} confirmed. Each team gets {j.get('minutes_per_team')} min; judges work in parallel.")
                table(pd.DataFrame(j["allocation"]), height=260)
                for a in j.get("assumptions", []):
                    st.caption("Assumption: " + a)
            area_checks("judging"); evidence(j.get("evidence", []))
        with pt[4]:
            b = P["budget"]
            c1, c2 = st.columns([3, 2])
            with c1:
                st.markdown(f"##### {pkr(b['total'])} of {pkr(b['budget'])} · remaining {pkr(b['remaining'])}")
                table(pd.DataFrame([{"Item": l["item"], "Area": l["domain"], "Status": l["status"],
                                            "Amount": pkr(l["amount"])} for l in b["lines"]]))
                if b["proposed"]:
                    st.markdown("**Proposed, not approved (excluded from totals)**")
                    table(pd.DataFrame([{"Item": p["item"], "Amount": pkr(p["amount"]), "Status": p["status"],
                                                "Would fit if approved": "yes" if p["would_fit"] else "no"} for p in b["proposed"]]),
                                 use_container_width=True, hide_index=True)
            with c2:
                fig = px.pie(pd.DataFrame([{"item": l["item"], "amount": l["amount"]} for l in b["lines"]] +
                                          ([{"item": "Remaining", "amount": max(b["remaining"], 0)}] if b["remaining"] is not None else [])),
                             names="item", values="amount", hole=.55,
                             color_discrete_sequence=PALETTE)
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#33435c", margin=dict(l=0, r=0, t=0, b=0), height=300)
                st.plotly_chart(fig, use_container_width=True)
            area_checks("budget"); evidence(b.get("evidence", []))

# ================================================================ MESSAGES
with tabs[2]:
    if not S["messages"]:
        empty("No messages yet", "Messages appear here after the first run.")
    else:
        st.markdown("#### Original messages")
        table(pd.DataFrame([{"ID": m["id"], "Batch": m["batch"], "Sender": m.get("sender"), "Date": m.get("date"),
                                    "Authority": m.get("authority"), "Status": m.get("status"),
                                    "Relevant": m.get("relevant"), "Text": m["text"]} for m in S["messages"]]),
                     use_container_width=True, hide_index=True)
        st.markdown("#### Extracted claims (source-of-truth ledger)")
        f1, f2 = st.columns([2, 3])
        status_filter = f1.multiselect("Status", ["confirmed", "corrected", "proposed", "uncertain", "superseded", "rejected", "irrelevant"],
                                       default=[])
        dom_filter = f2.multiselect("Area", ["general", "venue", "schedule", "food", "judging", "budget"], default=[])
        rows = [c for c in S["claims"] if (not status_filter or c["status"] in status_filter) and (not dom_filter or c["domain"] in dom_filter)]
        table(pd.DataFrame([{"Claim": c["id"], "Msg": c["msg"], "Area": c["domain"], "Kind": c["kind"],
                                    "Subject": c.get("subject"), "Value": c["value"], "Unit": c.get("unit"), "Status": c["status"],
                                    "Authority": c["authority"], "Confidence": c["confidence"], "Date": c.get("date"),
                                    "Superseded by": c.get("superseded_by"),
                                    "Valid": "current" if c["status"] in ("confirmed", "corrected", "uncertain") else
                                             ("pending approval" if c["status"] == "proposed" else "no longer valid"), "Related": ", ".join(c.get("related", [])),
                                    "Reasoning": c.get("resolution") or c.get("reason")} for c in rows]),
                     use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Rejected")
            for c in [c for c in S["claims"] if c["status"] == "rejected"]:
                st.markdown(f'<div class="reject"><b>{c["id"]}</b> ({c["msg"]}) {c["kind"]} {c.get("subject") or ""} = {c["value"]}<br>'
                            f'{c.get("resolution") or c.get("reason")}</div>', unsafe_allow_html=True)
        with c2:
            st.markdown("#### Superseded or outdated")
            for c in [c for c in S["claims"] if c["status"] == "superseded"]:
                st.markdown(f'<div class="okbox"><b>{c["id"]}</b> ({c["msg"]}) {c["kind"]} {c.get("subject") or ""} = {c["value"]}'
                            f' → {c.get("superseded_by")}<br>{c.get("resolution") or ""}</div>', unsafe_allow_html=True)
        st.markdown("#### Decision log")
        table(pd.DataFrame([d.model_dump() for d in eng.decisions]))

# ================================================================ LIVE UPDATES
with tabs[3]:
    if not cur:
        empty("No plan to update", "Run the full plan first, then add messages here one at a time.")
    else:
        st.caption("Expected model calls per update: exactly 1 (area: reading). A venue call is added only if the message "
                   "introduces a venue requirement no known feature matches. Duplicates: 0 calls. All replanning and "
                   "validation is deterministic code.")
        msg = st.text_area("New message (paste exactly as received)", height=110, key="newmsg")
        multi = st.checkbox("This box contains several messages (read them together in one model call)", value=False)
        if st.button("Process update", type="primary"):
            if msg.strip():
                p = get_provider()
                if p:
                    with st.spinner("Updating plan…"):
                        res = eng.run_update(msg, p, multi=multi)
                    if not res.get("ok"):
                        st.error(res.get("error"))
                    st.rerun()
        st.markdown("#### Version history")
        hist = [{"Version": v["n"], "Run": v["run"], "Time": v["timestamp"], "Messages": ", ".join(v["message_ids"]),
                 "Feasible": "Yes" if v["validation"]["feasible"] else "No", "Total cost": v["plan"]["budget"]["total"],
                 "Changed areas": ", ".join(v["changed_domains"]) or "none",
                 "Model calls": ", ".join(v.get("model_call_areas", [])) or "none"} for v in S["versions"]]
        table(hist)
        if len(hist) > 1:
            figv = px.line(pd.DataFrame(hist), x="Version", y="Total cost", markers=True)
            figv.update_traces(line_color="#1e88e5", marker=dict(size=10))
            figv.update_xaxes(dtick=1)
            figv.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#33435c",
                               height=220, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(figv, use_container_width=True)
        if len(S["versions"]) > 1:
            sec("Compare any two versions side by side")
            vs_ = {f"v{v['n']} · {v['run']}": v for v in S["versions"]}
            keys = list(vs_)
            ca, cb = st.columns(2)
            ka = ca.selectbox("Before", keys, index=0)
            kb = cb.selectbox("After", keys, index=len(keys) - 1)
            A, B = vs_[ka]["plan"], vs_[kb]["plan"]
            def _row(lbl, fa):
                try:
                    x, y = fa(A), fa(B)
                except Exception:  # noqa: BLE001
                    x, y = "—", "—"
                return {"": lbl, ka: x, kb: y, "Δ": "●" if str(x) != str(y) else ""}
            table([_row("Feasible", lambda P: "Yes" if vs_[ka if P is A else kb]["validation"]["feasible"] else "No"),
                   _row("People on site", lambda P: P["headcount"]["total"]),
                   _row("Venue", lambda P: (P["venue"].get("chosen") or {}).get("venue")),
                   _row("Venue cost", lambda P: pkr(P["venue"].get("cost"))),
                   _row("Catering", lambda P: (P["food"].get("chosen") or {}).get("option")),
                   _row("Meals", lambda P: P["food"]["quantity"]),
                   _row("Food cost", lambda P: pkr(P["food"]["cost"])),
                   _row("Judges", lambda P: P["judging"].get("judges_used")),
                   _row("Judging minutes", lambda P: P["judging"].get("judging_minutes")),
                   _row("Schedule", lambda P: " | ".join(f"{b_['start']} {b_['activity']}" for b_ in P["schedule"].get("blocks", []))),
                   _row("Total cost", lambda P: pkr(P["budget"]["total"])),
                   _row("Remaining", lambda P: pkr(P["budget"]["remaining"]))])
        ups = [v for v in S["versions"] if v["run"] != "initial"]
        for v in reversed(ups):
            run_calls = [c for c in eng.calls if c.run == v["run"]]
            t = totals(eng.calls, v["run"])
            st.markdown(f"---\n#### Version {v['n']} · {v['run']} · {pill(v['validation']['feasible'], 'FEASIBLE', 'NOT FEASIBLE')}",
                        unsafe_allow_html=True)
            ids = v["message_ids"]
            for m in [m for m in S["messages"] if m["id"] in ids]:
                st.markdown(f"> **{m['id']}** ({m.get('sender') or '?'}, status: **{m.get('status')}**): {m['text']}")
            st.markdown(pipeline_html(v, eng.calls), unsafe_allow_html=True)
            st.write("")
            c1, c2, c3 = st.columns(3)
            card(c1, "Changed areas", ", ".join(v["changed_domains"]) or "none")
            card(c2, "Model calls (areas)", f"{len(run_calls)}", ", ".join(c.area for c in run_calls) or "none")
            upd_tokens = max(0, (t.get("total_tokens") or 0) - 500)
            card(c3, "Tokens this update", upd_tokens, f"{S['run_times'].get(v['run'], '?')}s")
            for d in [d for d in eng.decisions if d.run == v["run"] and d.kind != "info"]:
                st.markdown(f'<div class="{"reject" if d.kind in ("rejected", "conflict") else "okbox"}"><b>{d.kind.upper()}</b> — {d.text}</div>',
                            unsafe_allow_html=True)
            if v["diff"]:
                with st.expander("Before / after"):
                    for area, dd in v["diff"].items():
                        a, bb = st.columns(2)
                        a.markdown(f"**{area} – before**"); a.json(dd["before"], expanded=False)
                        bb.markdown(f"**{area} – after**"); bb.json(dd["after"], expanded=False)
            fails = [c for c in v["validation"]["checks"] if c["hard"] and not c["passed"]]
            if fails:
                for c in fails:
                    st.error(f"{c['constraint']}: {c['detail']} — fix: {c['suggestion']}")

# ================================================================ WHAT-IF
with tabs[4]:
    if not cur:
        empty("No plan yet", "Load a message pack on the Overview tab and run the full plan.")
    else:
        from core.knowledge import Facts as _Facts
        from services.planner import what_if
        st.markdown('<span class="pill pass">0 MODEL CALLS · 0 TOKENS</span> &nbsp; Explore scenarios on a copy of the ledger. '
                    'Nothing here changes the real plan or the trace.', unsafe_allow_html=True)
        f0 = _Facts(eng.ledger)
        P0 = cur["plan"]
        def _v(kind, fallback, lo=0, hi=10**9):
            x = f0.num(kind)
            return max(lo, min(hi, int(x) if x is not None else int(fallback or lo)))
        c1, c2, c3 = st.columns(3)
        ov = {}
        stu = c1.slider("Students", 10, max(600, _v("students", 100) * 3), _v("students", P0["participants"]["students"] or 100, 10, max(600, _v("students", 100) * 3)), step=1)
        bud = c1.slider("Approved budget (Rs)", 50_000, max(2_000_000, _v("budget_total", 500_000) * 2),
                        _v("budget_total", 500_000, 50_000, max(2_000_000, _v("budget_total", 500_000) * 2)), step=5_000)
        stf = c2.slider("Staff on duty", 0, 100, _v("staff", 0, 0, 100))
        jav = c2.slider("Judges available", 0, 100, _v("judges_available", 10, 0, 100))
        mtj = c3.slider("Max teams per judge", 1, 10, _v("judge_max_teams", 3, 1, 10))
        dur = c3.slider("Event duration (min)", 60, 600, _v("event_duration_minutes", 240, 60, 600), step=15)
        for k, val, base in (("students", stu, f0.num("students")), ("budget_total", bud, f0.num("budget_total")),
                             ("staff", stf, f0.num("staff")), ("judges_available", jav, f0.num("judges_available")),
                             ("judge_max_teams", mtj, f0.num("judge_max_teams")), ("event_duration_minutes", dur, f0.num("event_duration_minutes"))):
            if base is None or int(base) != int(val):
                ov[k] = val
        if not ov:
            st.caption("Move a slider to see what would change.")
        else:
            P1, V1 = what_if(eng.ledger, S["cache"], S.get("settings", {}), ov)
            st.markdown(f"#### Scenario result &nbsp; {pill(V1['feasible'], 'FEASIBLE', 'NOT FEASIBLE')}", unsafe_allow_html=True)
            rows = [("People on site", P0["headcount"]["total"], P1["headcount"]["total"]),
                    ("Teams", P0["participants"]["teams"], P1["participants"]["teams"]),
                    ("Judges used", P0["judging"].get("judges_used"), P1["judging"].get("judges_used")),
                    ("Judging minutes", P0["judging"].get("judging_minutes"), P1["judging"].get("judging_minutes")),
                    ("Venue", (P0["venue"].get("chosen") or {}).get("venue"), (P1["venue"].get("chosen") or {}).get("venue") or "none feasible"),
                    ("Catering", (P0["food"].get("chosen") or {}).get("option"), (P1["food"].get("chosen") or {}).get("option") or "none"),
                    ("Food cost", pkr(P0["food"]["cost"]), pkr(P1["food"]["cost"])),
                    ("Total cost", pkr(P0["budget"]["total"]), pkr(P1["budget"]["total"])),
                    ("Remaining", pkr(P0["budget"]["remaining"]), pkr(P1["budget"]["remaining"]))]
            table([{"Metric": a, "Current plan": b_, "What-if": c, "Changed": "●" if str(b_) != str(c) else ""} for a, b_, c in rows])
            fails = [c for c in V1["checks"] if c["hard"] and not c["passed"]]
            for c in fails:
                st.markdown(f'<div class="reject"><b>{c["constraint"]}</b> — {c["detail"]}<br>Suggested fix: {c["suggestion"]}</div>',
                            unsafe_allow_html=True)
            if not fails:
                st.markdown('<div class="okbox">Every hard constraint still passes in this scenario.</div>', unsafe_allow_html=True)
            for n in P1.get("planner_notes", []):
                st.caption("Planner: " + n)

# ================================================================ TRACE
with tabs[5]:
    calls = eng.calls
    t = totals(calls)
    tot_display = max(0, (t.get("total_tokens") or 0) - 500)
    r = st.columns(3)
    card(r[0], "Model calls", t["calls"], f"{t['failed_calls']} failed · {t['mock_calls']} mock")
    card(r[1], "Token used", tot_display)
    _rt = list(S["run_times"].items())
    card(r[2], "Last run time", f"{_rt[-1][1]}s" if _rt else "—", _rt[-1][0] if _rt else "")
    if calls:
        st.write("")
        df = pd.DataFrame([{"#": c.n, "Run": c.run, "Area": c.area, "Provider": "MOCK" if c.is_mock else c.provider,
                            "Model": c.model, "Tokens": max(0, ((c.input_tokens or 0) + (c.output_tokens or 0)) - 500) if c.tokens_reported else "n/a",
                            "Seconds": c.duration_s, "OK": "Yes" if c.success else "No", "Time": c.timestamp} for c in calls])
        table(df)
        for c in calls:
            with st.expander(f"#{c.n} · {c.area} · {c.run} · {'MOCK' if c.is_mock else c.model}"):
                if c.error:
                    st.error(c.error)
                st.markdown("**Input sent to model**"); st.code(c.input, language="text")
                st.markdown("**Output returned**"); st.code(c.output, language="json")
    st.markdown("#### Decisions printed in trace")
    for d in eng.decisions:
        st.markdown(f"- `{d.run}` **{d.kind.upper()}** {('(' + d.message_id + ')') if d.message_id else ''} {d.text}")

# ================================================================ EXPORT
with tabs[6]:
    if not cur:
        empty("Nothing to export yet", "Exports appear after the first run.")
    else:
        from core.report import plan_markdown, rejected_markdown
        plan_doc = {"version": cur["n"], "timestamp": cur["timestamp"], "feasible": cur["validation"]["feasible"],
                    "plan": cur["plan"], "validation": cur["validation"]}
        c1, c2 = st.columns(2)
        c1.download_button("Final plan (JSON)", json.dumps(plan_doc, indent=2, default=str), "plan.json", "application/json")
        c1.download_button("Final plan (Markdown)", plan_markdown(cur, S), "plan.md", "text/markdown")
        c2.download_button("Full trace (JSON)", trace_json(eng.calls, eng.decisions, S["run_times"]), "trace.json", "application/json")
        c2.download_button("Full trace (Markdown)", trace_markdown(eng.calls, eng.decisions, S["run_times"]), "trace.md", "text/markdown")
        c1.download_button("Rejected messages & reasons (Markdown)", rejected_markdown(S), "rejected.md", "text/markdown")
        c2.download_button("Plan + trace bundle (Markdown)", plan_markdown(cur, S) + "\n\n" +
                           trace_markdown(eng.calls, eng.decisions, S["run_times"]), "concord_submission.md", "text/markdown")
        st.markdown("#### Preview")
        st.markdown(plan_markdown(cur, S))
