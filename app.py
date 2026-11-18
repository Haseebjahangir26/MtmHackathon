"""MIND2MACHINE – Constraint-Aware Event Planner (Streamlit UI).
Run: streamlit run app.py
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from core import persistence
from core.calculations import pkr
from core.orchestrator import Engine
from core.report import plan_markdown, rejected_markdown
from core.trace import totals, trace_json, trace_markdown
from services.llm_provider import DEFAULT_MODELS, LLMError, make_provider

st.set_page_config(page_title="MIND2MACHINE · Event Planner", page_icon="⚡", layout="wide")


def render_table(data, **kwargs):
    """Renders a dataframe safely converting object/mixed columns to string to prevent PyArrow type conflicts."""
    df = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    if df.empty:
        st.info("No records to display.")
        return
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].map(lambda x: "" if x is None else str(x))
    kwargs.setdefault("use_container_width", True)
    kwargs.setdefault("hide_index", True)
    st.dataframe(df, **kwargs)


# Clean, crisp light theme with clear black/gray accents
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
:root {
    --bg: #ffffff;
    --panel: #f8fafc;
    --panel-hover: #f1f5f9;
    --border: #e2e8f0;
    --border-accent: #0284c7;
    --accent: #0284c7;
    --text: #0f172a;
    --text-muted: #475569;
    --dim: #64748b;
    --ok: #059669;
    --bad: #dc2626;
    --warn: #d97706;
}

html, body, [class*="css"], .stApp { font-family: 'Inter', system-ui, sans-serif; }
.stApp { background: var(--bg); color: var(--text); }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1360px; }
section[data-testid="stSidebar"] { background: #f8fafc; border-right: 1px solid var(--border); }

/* Header & Banner */
.banner-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
}
.banner-title { font-size: 24px; font-weight: 700; color: #0f172a; letter-spacing: -0.02em; }
.banner-desc { font-size: 13.5px; color: #475569; margin-top: 4px; max-width: 720px; line-height: 1.5; }
.status-pill {
    padding: 6px 14px;
    border-radius: 9999px;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.03em;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}
.status-ok { background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }
.status-bad { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
.status-idle { background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; }

/* KPI Cards */
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 22px; }
.kpi-card {
    background: #ffffff;
    border: 1px solid var(--border);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
    border-radius: 10px;
    padding: 16px;
    transition: all 0.2s ease;
}
.kpi-card:hover { border-color: #94a3b8; background: #f8fafc; }
.kpi-label { font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
.kpi-value { font-size: 22px; font-weight: 700; color: #0f172a; margin-top: 6px; font-variant-numeric: tabular-nums; }
.kpi-sub { font-size: 12px; color: #64748b; margin-top: 4px; }

/* Badges & Tables */
.pill { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; }
.pill-pass { color: #059669; background: #ecfdf5; border: 1px solid #a7f3d0; }
.pill-fail { color: #dc2626; background: #fef2f2; border: 1px solid #fecaca; }
.pill-warn { color: #d97706; background: #fffbeb; border: 1px solid #fde68a; }

/* Notice boxes */
.info-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 10px 0;
    font-size: 13.5px;
    color: #334155;
}
.reject-card {
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-left: 4px solid #ef4444;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
    font-size: 13px;
    color: #991b1b;
}
.success-card {
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    border-left: 4px solid #10b981;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
    font-size: 13px;
    color: #065f46;
}

/* Tabs & UI controls */
.stTabs [data-baseweb="tab-list"] { gap: 16px; border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] { color: #64748b; padding: 10px 14px; font-weight: 600; font-size: 14px; }
.stTabs [aria-selected="true"] { color: #0284c7 !important; border-bottom: 2px solid #0284c7 !important; }
div[data-testid="stExpander"] details { border: 1px solid var(--border); border-radius: 8px; background: #ffffff; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------- SESSION STATE
if "engine" not in st.session_state:
    st.session_state.engine = Engine(persistence.load())
eng: Engine = st.session_state.engine
S = eng.state

SAMPLE_PACKS = {
    "Select a built-in pack...": "",
    "Pack 1: Hackathon (96 Students · Wheelchair Access · PKR 480k)": "tests/packs/synthetic_pack.txt",
    "Pack 2: Build-a-thon (132 Participants · Backup Power · PKR 410k)": "tests/packs/judge_dryrun_pack.txt",
    "Pack 3: 3-Hour Event (120 Students · Vegetarian · Projector · PKR 300k)": "tests/packs/synthetic_pack2.txt",
    "Pack 4: Serena Event (72 Students · Tea Break · PKR 260k)": "tests/packs/synthetic_pack3.txt",
}

# ---------------------------------------------------------------- SIDEBAR
with st.sidebar:
    st.markdown("### ⚡ MIND2MACHINE")
    st.caption("Constraint-Aware Event Planner")

    st.markdown("---")
    st.markdown("#### 🤖 Model Provider")

    has_gemini = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))

    prov_options = ["Mock (Instant / Offline)", "Gemini (Google AI)", "Anthropic (Claude)"]
    default_idx = 1 if has_gemini else (2 if has_anthropic else 0)
    selected_prov = st.selectbox("Provider Mode", prov_options, index=default_idx)

    prov_key = "mock"
    if "Gemini" in selected_prov:
        prov_key = "gemini"
    elif "Anthropic" in selected_prov:
        prov_key = "anthropic"

    api_key = None
    model_name = None

    if prov_key == "gemini":
        default_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        api_key = st.text_input("Gemini API Key", value=default_key, type="password")
        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key
            st.success("API Key active")
        else:
            st.info("Tip: Leave blank to use Offline Mock mode")
        model_name = st.selectbox("Model", ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-3.5-flash-lite"], index=0)
    elif prov_key == "anthropic":
        default_key = os.getenv("ANTHROPIC_API_KEY") or ""
        api_key = st.text_input("Anthropic API Key", value=default_key, type="password")
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
            st.success("API Key active")
        model_name = st.selectbox("Model", ["claude-3-5-haiku-latest", "claude-haiku-4-5"], index=0)
    else:
        st.markdown('<div class="success-card">⚡ <b>Offline Mock Active</b><br>Runs instantly with 0 tokens and fully validated arithmetic.</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### ⚙️ Planner Settings")
    s = S.setdefault("settings", {"food_policy": "standard-first", "default_start": "10:00"})
    new_pol = st.selectbox("Catering Preference", ["standard-first", "cheapest"],
                           index=0 if s.get("food_policy") == "standard-first" else 1,
                           help="standard-first: standard menu if within budget; cheapest: lowest cost compliant menu.")
    new_start = st.text_input("Default Start Time", value=s.get("default_start", "10:00"))

    if (new_pol, new_start) != (s.get("food_policy"), s.get("default_start")):
        s["food_policy"], s["default_start"] = new_pol, new_start
        eng.replan()
        st.rerun()

    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("↺ Rollback", use_container_width=True, disabled=len(S["versions"]) < 2):
        eng.rollback()
        st.rerun()
    if c2.button("🗑️ Reset", use_container_width=True):
        st.session_state.engine = Engine(None)
        persistence.save(st.session_state.engine.state)
        st.rerun()


def get_active_provider():
    try:
        return make_provider(prov_key, model_name or None, api_key or None)
    except LLMError as e:
        st.error(f"Model error: {e}. Falling back to Mock.")
        return make_provider("mock", None, None)
    except Exception as e:
        st.error(f"Provider error: {e}. Falling back to Mock.")
        return make_provider("mock", None, None)


# ---------------------------------------------------------------- TOP BANNER
cur = eng.current
t_metrics = totals(eng.calls)

if not cur:
    status_html = '<span class="status-pill status-idle">⚪ No Plan Loaded</span>'
    status_msg = "Load a message pack below or choose a sample pack to generate the complete event plan."
elif cur["validation"]["feasible"]:
    status_html = f'<span class="status-pill status-ok">✅ Plan Feasible (v{cur["n"]})</span>'
    status_msg = f"All hard constraints passed! Plan v{cur['n']} is ready and within budget."
else:
    status_html = f'<span class="status-pill status-bad">⚠️ Not Feasible (v{cur["n"]})</span>'
    status_msg = "One or more constraints failed. Review the Validation tab for suggested fixes."

st.markdown(f"""
<div class="banner-card">
    <div>
        <div class="banner-title">MIND2MACHINE Event Planner</div>
        <div class="banner-desc">{status_msg}</div>
    </div>
    <div>{status_html}</div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------- KPI ROW
if cur:
    P = cur["plan"]
    b, j, hc, v_info, f_info = P["budget"], P["judging"], P["headcount"], P["venue"], P["food"]
    ch_venue = v_info.get("chosen") or {}
    ch_food = f_info.get("chosen") or {}

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">🏢 Venue</div>
            <div class="kpi-value">{ch_venue.get('venue', '—')}</div>
            <div class="kpi-sub">{int(ch_venue.get('capacity', 0))} seats · {pkr(v_info.get('cost'))}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">👥 Headcount</div>
            <div class="kpi-value">{hc.get('total', 0)} People</div>
            <div class="kpi-sub">{hc.get('students', 0)} students · {hc.get('staff', 0)} staff · {hc.get('judges', 0)} judges</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">🍱 Catering</div>
            <div class="kpi-value">{ch_food.get('option', '—')}</div>
            <div class="kpi-sub">{f_info.get('quantity', 0)} meals · {pkr(f_info.get('cost'))}</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">⚖️ Judging</div>
            <div class="kpi-value">{j.get('judges_used', 0)} Judges</div>
            <div class="kpi-sub">{P['participants'].get('teams', 0)} teams · {j.get('judging_minutes', 0)} min total</div>
        </div>
        """, unsafe_allow_html=True)
    with c5:
        rem_str = f"{pkr(b.get('remaining'))} left" if b.get("remaining") is not None else "No limit"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">💰 Budget</div>
            <div class="kpi-value">{pkr(b.get('total'))}</div>
            <div class="kpi-sub">Limit: {pkr(b.get('budget'))} · {rem_str}</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

# ---------------------------------------------------------------- PACK INPUT EXPANDER
with st.expander("📥 " + ("Load / Change Message Pack" if cur else "Load Message Pack (Start Here)"), expanded=(cur is None)):
    sel_sample = st.selectbox("⚡ Quick Load Sample Pack", list(SAMPLE_PACKS.keys()))

    sample_content = ""
    if sel_sample and SAMPLE_PACKS[sel_sample]:
        try:
            pack_path = Path(SAMPLE_PACKS[sel_sample])
            if pack_path.exists():
                sample_content = pack_path.read_text(encoding="utf-8")
        except Exception:
            pass

    col_up, col_txt = st.columns([1, 2])
    with col_up:
        uploaded_file = st.file_uploader("Upload .txt message pack", type=["txt"])
    with col_txt:
        default_text = uploaded_file.getvalue().decode("utf-8", errors="replace") if uploaded_file else sample_content
        input_text = st.text_area("Message pack content", value=default_text, height=140, placeholder="Paste emails, WhatsApp chats, and notices here...")

    if st.button("🚀 Run Full Plan", type="primary", use_container_width=True):
        raw_to_run = input_text.strip()
        if not raw_to_run:
            st.error("Please select a sample pack, upload a file, or paste message text.")
        else:
            p = get_active_provider()
            with st.spinner("Extracting claims and solving constraints..."):
                res = eng.run_full(raw_to_run, p)
            if res.get("ok"):
                st.success(f"Plan generated successfully! Version v{res['version']}.")
            else:
                st.error(res.get("error", "Planning failed."))
            st.rerun()

if not cur:
    st.info("💡 Select a built-in pack from the dropdown above and click **Run Full Plan** to test immediately!")
    st.stop()

# ---------------------------------------------------------------- MAIN TABS
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Event Plan & Schedule",
    "⚡ Live Updates & Changelog",
    "🛡️ Constraint Validation",
    "🧪 What-If & Export"
])

LIGHT_CHART = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#1e293b", family="Inter"),
    margin=dict(l=0, r=0, t=20, b=10)
)
CHART_COLORS = ["#0284c7", "#4f46e5", "#059669", "#d97706", "#dc2626", "#64748b"]

# ================================================================ TAB 1: PLAN & SCHEDULE
with tab1:
    P = cur["plan"]
    v = P["venue"]
    s_ = P["schedule"]
    fd = P["food"]
    j = P["judging"]
    b = P["budget"]

    # 1. VENUE SECTION
    st.markdown("#### 🏢 Venue Selection")
    ch_v = v.get("chosen")
    if ch_v:
        reqs_str = ", ".join(v.get("requirements", [])) or "None specified"
        st.markdown(f"""
        <div class="info-card">
            <b>Selected: {ch_v['venue']}</b> &nbsp;·&nbsp; {int(ch_v['capacity'])} Seats &nbsp;·&nbsp; {pkr(ch_v['price'])}<br>
            <span style="color:#64748b;font-size:12.5px;">Rule: Cheapest venue seating all {v['seats_needed']} people meeting requirements: <i>{reqs_str}</i>.</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.error("No venue found that satisfies capacity and requirements.")

    v_df = pd.DataFrame([{
        "Venue": opt["venue"],
        "Seats": opt["capacity"],
        "Rental": pkr(opt["price"]),
        "Features": ", ".join(opt.get("features", [])) or "Standard",
        "Compliant": "✅ Yes" if opt["feasible"] else "❌ No",
        "Reason": opt["reason"]
    } for opt in v.get("options", [])])
    render_table(v_df)

    st.markdown("---")

    # 2. SCHEDULE SECTION
    st.markdown("#### ⏱️ Schedule & Timetable")
    if s_.get("blocks"):
        st.caption(f"Event starts at **{s_['start']}** · Total planned duration: **{s_['duration']} minutes**")

        dfb = pd.DataFrame(s_["blocks"])
        base_time = _dt.datetime(2026, 1, 1, *[int(x) for x in str(s_["start"]).split(":")[:2]])
        dfg = pd.DataFrame([{
            "Activity": r["activity"],
            "Category": r["type"],
            "Start": base_time + _dt.timedelta(minutes=r["start_min"]),
            "Finish": base_time + _dt.timedelta(minutes=r["end_min"]),
            "Duration": f"{r['minutes']} min"
        } for r in s_["blocks"]])

        color_map = {
            "hacking": "#0284c7",
            "judging": "#4f46e5",
            "break": "#d97706",
            "break (mandatory)": "#d97706",
            "activity": "#64748b",
            "activity (mandatory)": "#059669"
        }
        fig_gantt = px.timeline(
            dfg, x_start="Start", x_end="Finish", y="Activity", color="Category",
            color_discrete_map=color_map,
            hover_data={"Duration": True, "Start": "|%H:%M", "Finish": "|%H:%M"}
        )
        fig_gantt.update_yaxes(autorange="reversed", title=None)
        fig_gantt.update_xaxes(tickformat="%H:%M", gridcolor="#e2e8f0", title=None)
        fig_gantt.update_layout(**LIGHT_CHART, height=300, legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_gantt, use_container_width=True)

        sched_view = dfb[["start", "end", "activity", "minutes", "type"]].copy()
        sched_view.columns = ["Start Time", "End Time", "Activity", "Duration (min)", "Type"]
        render_table(sched_view)

    st.markdown("---")

    # 3. FOOD & JUDGING
    col_f, col_j = st.columns(2)
    with col_f:
        st.markdown("#### 🍱 Catering & Meals")
        ch_f = fd.get("chosen")
        if ch_f:
            st.markdown(f"""
            <div class="info-card">
                <b>{ch_f['option']}</b> · {pkr(ch_f['price_per_head'])} / head<br>
                Total: <b>{fd['quantity']} meals</b> = <b>{pkr(fd['cost'])}</b> (Policy: {fd['policy']})
            </div>
            """, unsafe_allow_html=True)
        else:
            st.error("No compliant catering option found.")

        f_df = pd.DataFrame([{
            "Option": opt["option"],
            "Price/Head": pkr(opt["price_per_head"]),
            "Total Cost": pkr(opt["cost"]),
            "Compliant": "✅ Yes" if opt["feasible"] else "❌ No",
            "Notes": opt["reason"]
        } for opt in fd.get("options", [])])
        render_table(f_df)

    with col_j:
        st.markdown("#### ⚖️ Judging Plan")
        if j.get("ok"):
            st.markdown(f"""
            <div class="info-card">
                <b>{j['judges_used']} Judges Assigned</b> · {j['rounds']} Round(s) · {j['judging_minutes']} min<br>
                Honorarium: <b>{pkr(j.get('honorarium'))}</b> per judge = <b>{pkr(j['cost'])}</b> total
            </div>
            """, unsafe_allow_html=True)
            if j.get("allocation"):
                alloc_df = pd.DataFrame(j["allocation"])
                render_table(alloc_df)

    st.markdown("---")

    # 4. BUDGET BREAKDOWN
    st.markdown("#### 💰 Budget Allocation")
    b_col1, b_col2 = st.columns([3, 2])
    with b_col1:
        st.markdown(f"Total Allocated: **{pkr(b['total'])}** of Approved Limit: **{pkr(b['budget'])}** (Remaining: **{pkr(b['remaining'])}**)")
        b_lines = pd.DataFrame([{
            "Expense Item": line["item"],
            "Category": line["domain"].capitalize(),
            "Status": line["status"],
            "Cost": pkr(line["amount"])
        } for line in b.get("lines", []) if line.get("amount")])
        render_table(b_lines)

        if b.get("proposed"):
            st.markdown("##### ⚠️ Proposed / Unapproved Expenses (Excluded)")
            prop_df = pd.DataFrame([{
                "Item": p["item"],
                "Amount": pkr(p["amount"]),
                "Status": p["status"],
                "Affordable if Approved": "Yes" if p["would_fit"] else "No"
            } for p in b["proposed"]])
            render_table(prop_df)

    with b_col2:
        chart_data = [{"Item": line["item"], "Cost": line["amount"]} for line in b["lines"] if line["amount"]]
        if b.get("remaining") and b["remaining"] > 0:
            chart_data.append({"Item": "Remaining Balance", "Cost": b["remaining"]})
        if chart_data:
            fig_pie = px.pie(
                pd.DataFrame(chart_data), names="Item", values="Cost",
                hole=0.6, color_discrete_sequence=CHART_COLORS
            )
            fig_pie.update_traces(textinfo="percent", hovertemplate="%{label}<br>Rs %{value:,.0f}<extra></extra>")
            fig_pie.update_layout(**LIGHT_CHART, height=280)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No budget breakdown items.")

# ================================================================ TAB 2: LIVE UPDATES
with tab2:
    st.markdown("#### ⚡ Process New Event Message")
    st.caption("Paste any update (e.g. updated bill, catering quote change, attendance shift, unapproved request).")

    new_update_text = st.text_area(
        "Update message content",
        height=90,
        placeholder="Example: Karachi Foods: wrap meal is now Rs 800 per person\nOr: Accounts: banners invoice is 9000, not 5000",
        key="update_box"
    )

    if st.button("⚡ Process Update", type="primary"):
        if not new_update_text.strip():
            st.error("Please enter a message to process.")
        else:
            p = get_active_provider()
            with st.spinner("Processing update and resolving conflicts..."):
                res = eng.run_update(new_update_text.strip(), p)
            if res.get("ok"):
                st.success(f"Update applied! Version is now v{eng.current['n']}.")
            else:
                st.error(res.get("error", "Update failed."))
            st.rerun()

    st.markdown("---")
    st.markdown("#### 📜 Version History & Changes")
    if len(S["versions"]) > 1:
        hist_rows = []
        for v_item in S["versions"]:
            hist_rows.append({
                "Version": f"v{v_item['n']}",
                "Run": v_item["run"],
                "Status": "✅ Feasible" if v_item["validation"]["feasible"] else "❌ Not Feasible",
                "Total Cost": pkr(v_item["plan"]["budget"]["total"]),
                "Changed Areas": ", ".join(v_item.get("changed_domains", [])) or "None",
                "Timestamp": v_item["timestamp"]
            })
        render_table(hist_rows)

    # Show decisions & rejections
    rej_decisions = [d for d in eng.decisions if d.kind in ("rejected", "conflict", "rollback")]
    if rej_decisions:
        st.markdown("##### 🚫 Rejected Messages & Rule Protections")
        for d in rej_decisions:
            st.markdown(f"""
            <div class="reject-card">
                <b>[{d.kind.upper()}] {d.run}</b>: {d.text}
            </div>
            """, unsafe_allow_html=True)

    # Latest diff
    if cur.get("diff"):
        with st.expander("🔍 View Before / After Diff for Latest Update", expanded=True):
            for area, dd in cur["diff"].items():
                c_before, c_after = st.columns(2)
                with c_before:
                    st.markdown(f"**{area.capitalize()} (Before)**")
                    st.json(dd["before"])
                with c_after:
                    st.markdown(f"**{area.capitalize()} (After)**")
                    st.json(dd["after"])

# ================================================================ TAB 3: VALIDATION
with tab3:
    st.markdown("#### 🛡️ Constraint & Rule Checklist")
    st.caption("Every hard constraint must pass for the event plan to be deemed feasible.")

    checks = cur["validation"]["checks"]
    hard_checks = [c for c in checks if c["hard"]]
    soft_checks = [c for c in checks if not c["hard"]]

    st.markdown("##### 🔒 Hard Constraints (Must Pass)")
    for c in hard_checks:
        pill_cls = "pill-pass" if c["passed"] else "pill-fail"
        icon = "✅" if c["passed"] else "❌"
        st.markdown(f"""
        <div style="padding:10px 14px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; margin-bottom:8px;">
            <span class="pill {pill_cls}">{icon} {'PASS' if c['passed'] else 'FAIL'}</span>
            <b>{c['constraint']}</b> &nbsp;·&nbsp; <span style="color:#475569;">{c['detail']}</span>
            {f'<div style="color:#dc2626;font-size:12px;margin-top:4px;"><b>Fix:</b> {c["suggestion"]}</div>' if (not c['passed'] and c.get('suggestion')) else ''}
        </div>
        """, unsafe_allow_html=True)

    if soft_checks:
        st.markdown("##### ⚠️ Soft Constraints & Advisories")
        for c in soft_checks:
            pill_cls = "pill-pass" if c["passed"] else "pill-warn"
            icon = "✅" if c["passed"] else "⚠️"
            st.markdown(f"""
            <div style="padding:8px 12px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; margin-bottom:6px;">
                <span class="pill {pill_cls}">{icon} {'OK' if c['passed'] else 'WARN'}</span>
                <b>{c['constraint']}</b> &nbsp;·&nbsp; <span style="color:#475569;">{c['detail']}</span>
            </div>
            """, unsafe_allow_html=True)

# ================================================================ TAB 4: WHAT-IF & EXPORT
with tab4:
    col_sim, col_exp = st.columns([3, 2])

    with col_sim:
        st.markdown("#### 🧪 Instant What-If Simulator")
        st.caption("Simulate variations in participants, budget, or judges. Re-plans in 0 model calls / 0 tokens.")

        from core.knowledge import Facts as _Facts
        from services.planner import what_if

        f0 = _Facts(eng.ledger)
        P0 = cur["plan"]

        def _val(kind, fallback, lo=0, hi=10**9):
            x = f0.num(kind)
            return max(lo, min(hi, int(x) if x is not None else int(fallback or lo)))

        w_c1, w_c2 = st.columns(2)
        with w_c1:
            stu_sim = st.slider("Students Count", 10, 400, _val("students", P0["participants"]["students"] or 96, 10, 400))
            bud_sim = st.slider("Budget Limit (PKR)", 50_000, 1_500_000, _val("budget_total", 480_000, 50_000, 1_500_000), step=10_000)
        with w_c2:
            stf_sim = st.slider("Staff On Duty", 0, 50, _val("staff", 10, 0, 50))
            jdg_sim = st.slider("Available Judges", 1, 30, _val("judges_available", 10, 1, 30))

        sim_overrides = {}
        if stu_sim != f0.num("students"):
            sim_overrides["students"] = stu_sim
        if bud_sim != f0.num("budget_total"):
            sim_overrides["budget_total"] = bud_sim
        if stf_sim != f0.num("staff"):
            sim_overrides["staff"] = stf_sim
        if jdg_sim != f0.num("judges_available"):
            sim_overrides["judges_available"] = jdg_sim

        if sim_overrides:
            P_sim, V_sim = what_if(eng.ledger, S.get("cache", {}), S.get("settings", {}), sim_overrides)
            status_text = "✅ FEASIBLE" if V_sim["feasible"] else "❌ NOT FEASIBLE"
            st.markdown(f"**Simulation Result: {status_text}**")

            sim_comp = [
                {"Metric": "Total People", "Current": str(P0["headcount"]["total"]), "What-If": str(P_sim["headcount"]["total"])},
                {"Metric": "Venue", "Current": str((P0["venue"].get("chosen") or {}).get("venue", "—")), "What-If": str((P_sim["venue"].get("chosen") or {}).get("venue", "None"))},
                {"Metric": "Catering", "Current": str((P0["food"].get("chosen") or {}).get("option", "—")), "What-If": str((P_sim["food"].get("chosen") or {}).get("option", "None"))},
                {"Metric": "Judges Used", "Current": str(P0["judging"].get("judges_used")), "What-If": str(P_sim["judging"].get("judges_used"))},
                {"Metric": "Total Cost", "Current": str(pkr(P0["budget"]["total"])), "What-If": str(pkr(P_sim["budget"]["total"]))},
                {"Metric": "Remaining", "Current": str(pkr(P0["budget"]["remaining"])), "What-If": str(pkr(P_sim["budget"]["remaining"]))},
            ]
            render_table(sim_comp)

    with col_exp:
        st.markdown("#### 📥 One-Click Export")
        st.caption("Download the plan, provenance ledger, and trace logs.")

        plan_doc = {
            "version": cur["n"],
            "timestamp": cur["timestamp"],
            "feasible": cur["validation"]["feasible"],
            "plan": cur["plan"],
            "validation": cur["validation"]
        }

        st.download_button(
            "📄 Download Final Plan (Markdown)",
            plan_markdown(cur, S),
            file_name="event_plan.md",
            mime="text/markdown",
            use_container_width=True
        )
        st.download_button(
            "💾 Download Final Plan (JSON)",
            json.dumps(plan_doc, indent=2, default=str),
            file_name="event_plan.json",
            mime="application/json",
            use_container_width=True
        )
        st.download_button(
            "🔍 Download Full Trace Log (Markdown)",
            trace_markdown(eng.calls, eng.decisions, S["run_times"]),
            file_name="execution_trace.md",
            mime="text/markdown",
            use_container_width=True
        )
        st.download_button(
            "📦 Download Complete Submission Bundle",
            plan_markdown(cur, S) + "\n\n---\n\n" + trace_markdown(eng.calls, eng.decisions, S["run_times"]),
            file_name="concord_complete_submission.md",
            mime="text/markdown",
            use_container_width=True
        )
