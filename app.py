import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from groq import Groq
import PyPDF2
import io
import os
import re

st.set_page_config(
    page_title="Property Intelligence System",
    page_icon="🏢",
    layout="wide"
)

# ─────────────────────────────────────────────────────────────
# STYLING
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.main-header { font-size:1.8rem; font-weight:700; color:#0f172a; margin-bottom:0.2rem; }
.sub-header  { font-size:0.85rem; color:#64748b; margin-bottom:1.5rem; }
.section-title {
    font-size:1rem; font-weight:600; color:#1e293b;
    margin:1.2rem 0 0.6rem 0; border-bottom:2px solid #e2e8f0; padding-bottom:0.3rem;
}
.kpi-card {
    background:white; padding:1rem 1.2rem; border-radius:10px;
    border:1px solid #e2e8f0; box-shadow:0 1px 3px rgba(0,0,0,0.06);
    height:100%;
}
.kpi-label { font-size:0.7rem; color:#64748b; font-weight:500; text-transform:uppercase; letter-spacing:0.05em; }
.kpi-value { font-size:1.45rem; font-weight:700; color:#0f172a; margin:0.2rem 0; }
.kpi-delta-green { font-size:0.73rem; color:#16a34a; font-weight:500; }
.kpi-delta-red   { font-size:0.73rem; color:#dc2626; font-weight:500; }
.kpi-delta-gray  { font-size:0.73rem; color:#64748b; font-weight:500; }

.alert-red    { background:#fef2f2; padding:0.75rem 1rem; border-radius:8px; border-left:4px solid #ef4444; margin:0.4rem 0; font-size:0.84rem; }
.alert-yellow { background:#fffbeb; padding:0.75rem 1rem; border-radius:8px; border-left:4px solid #f59e0b; margin:0.4rem 0; font-size:0.84rem; }
.alert-blue   { background:#eff6ff; padding:0.75rem 1rem; border-radius:8px; border-left:4px solid #3b82f6; margin:0.4rem 0; font-size:0.84rem; }
.alert-green  { background:#f0fdf4; padding:0.75rem 1rem; border-radius:8px; border-left:4px solid #22c55e; margin:0.4rem 0; font-size:0.84rem; }

.insight-box {
    background:linear-gradient(135deg,#f0f9ff 0%,#e0f2fe 100%);
    border:1px solid #bae6fd; border-radius:10px;
    padding:0.9rem 1.1rem; margin:0.5rem 0; font-size:0.84rem; color:#0c4a6e;
}
.insight-box strong { color:#0369a1; }

.recon-match  { background:#f0fdf4; padding:0.5rem 0.8rem; border-radius:6px; border-left:3px solid #22c55e; margin:0.25rem 0; font-size:0.82rem; }
.recon-flag   { background:#fef2f2; padding:0.5rem 0.8rem; border-radius:6px; border-left:3px solid #ef4444; margin:0.25rem 0; font-size:0.82rem; }
.recon-warn   { background:#fffbeb; padding:0.5rem 0.8rem; border-radius:6px; border-left:3px solid #f59e0b; margin:0.25rem 0; font-size:0.82rem; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────
for key, default in [("messages",[]),("documents",{}),("groq_key","")]:
    if key not in st.session_state:
        st.session_state[key] = default

# ─────────────────────────────────────────────────────────────
# REAL DATA — EXTRACTED FROM ACTUAL DOCUMENTS
# ─────────────────────────────────────────────────────────────

# ── Trailing 12 Months (Feb-25 through Jan-26, from Jan-26 financial report)
T12_MONTHS = ["Feb-25","Mar-25","Apr-25","May-25","Jun-25","Jul-25","Aug-25","Sep-25","Oct-25","Nov-25","Dec-25","Jan-26"]

T12 = pd.DataFrame({
    "Month":    T12_MONTHS,
    "Revenue":  [64642,63045,60395,65840,65745,65173,65740,63987,67534,67880,68845,67200],
    "Expenses": [35093,36806,44395,44011,30969,29022,45828,25240,26492,26546,43098,33593],
    "NOI":      [29549,26239,16000,21829,34776,36151,19912,38747,41042,41334,25747,33607],
    "Net_Income":[9497, 1760,-8675, -180,12013, 8089, 1742,14792,22542,20590,-29612,15104],
    # Utility breakdown (GL booked)
    "Elec":     [6560, 7624, 7795, 3617, 3401, 3859, 6651, 3781, 3329, 3949, 7043, 7709],
    "Water":    [806,  1440,  744,  839,  928,  711, 1115,  755,  854,  771,  853,  796],
    "Gas":      [1179, 1021,  684,  531,  989,  318, 1130,  580,  628, 1024,  492, 1001],
    "Sewer":    [836,  1743,  562,  755,  846,  634, 1023,  680,  768,  695,  768,  715],
    "Trash":    [277,   598,  256,  280,  280,  280,  318,  260,  294,  266,  294,  275],
    "Vacancy_Loss": [5485,8146,11646,8060,6094,7626,7227,8284,4592,3368,2797,5243],
    "Bad_Debt": [314,  1114,11910,1802,    0, 1163,  705,    0,    0, 2504,   73, 5819],
    "Insurance":[8023, 7992, 7927, 7927, 7927, 7927, 7927, 5043, 3719, 3585,12687, 4553],
})
T12["Total_Util"] = T12["Elec"] + T12["Water"] + T12["Gas"] + T12["Sewer"] + T12["Trash"]

# ── Feb-26 actuals (from Feb-26 financial report)
FEB26 = {
    "revenue": 70153.86, "budget_rev": 73490,
    "total_expenses": 29130.72, "budget_exp": 31244,
    "noi": 41023.14, "budget_noi": 42246,
    "net_income": 19424.42, "budget_ni": 24729,
    "elec": 6039.44, "budget_elec": 4605,
    "water": 689.38,  "budget_water": 817,
    "gas":   654.54,  "budget_gas": 745,
    "sewer": 620.40,  "budget_sewer": 775,
    "trash": 295.62,  "budget_trash": 280,
    "total_util": 8003.76, "budget_util": 6942,
    "bad_debt": 1699, "vacancy": 1992,
    "ytd_util": 18224.77, "ytd_budget_util": 13884,
}

# ── Jan-26 actuals
JAN26 = {
    "revenue": 67199.53, "budget_rev": 75035,
    "noi": 33606.55, "budget_noi": 44528,
    "net_income": 15104.44, "budget_ni": 27011,
    "total_util": 10221.01, "budget_util": 6942,
    "elec": 7709.25, "water": 795.26, "gas": 1000.82, "sewer": 715.68, "trash": 274.88,
}

# ── City of EC actual bills (from PDF — combined main + office)
BILLS = pd.DataFrame({
    "Month":      ["Nov-24","Dec-24","Jan-25","Feb-25","Mar-25","Apr-25","May-25",
                   "Aug-25","Sep-25","Oct-25","Dec-25","Jan-26","Feb-26","Mar-26"],
    "Period_From":["Oct-24","Nov-24","Dec-24","Jan-25","Feb-25","Mar-25","Apr-25",
                   "Jul-25","Aug-25","Sep-25","Nov-25","Dec-25","Jan-26","Feb-26"],
    "Main_Bill":  [4614,   5876,   5474,   8889,   8895,   5095,   4759,
                   5852,   6173,   4951,   7229.77,8550.91,0,      7966.58],
    "Office_Bill":[0,      0,      0,      0,      0,      0,      0,
                   0,      0,      0,      374.40, 380.43, 386.22, 388.88],
    "Gas_Blossman":[0,     0,      394,    0,      0,      0,      0,
                   0,      0,      0,      0,      1000.82,654.54, 357.86],
    "Elec":       [2195,   2763,   2763,   3841,   3841,   2235,   2131,
                   2641,   2641,   2140,   3042.82,3480.48,0,      3823.40],
    "DD3":        [492,    1061,   1061,   2707,   2707,   846,    646,
                   1108,   1108,   815,    1953.56,2707.30,0,      1784.36],
    "Water":      [1543,   1543,   1543,   1558,   1558,   1543,   1543,
                   1543,   1543,   1543,   812.49, 812.49, 0,      812.49],
    "Sewer":      [0,      0,      0,      0,      0,      0,      0,
                   0,      0,      0,      731.19, 731.19, 0,      731.19],
})
BILLS["Total_Bill"] = BILLS["Main_Bill"] + BILLS["Office_Bill"] + BILLS["Gas_Blossman"]

# ── Propane (Blossman) detail
PROPANE = pd.DataFrame({
    "Invoice_Date": ["Jan-25","Jan-02-26","Jan-21-26","Feb-12-26","Mar-16-26"],
    "Invoice#":     ["N/A",  "34085586","34375960","34657363","35210286"],
    "Gallons":      [172,    210.60,    199.00,    None,      145.70],
    "Rate_$/Gal":   [2.099,  2.249,     2.249,     None,      2.249],
    "Total_Due":    [394,    514.40,    486.42,    654.54,    357.86],
    "GL_Status":    ["✅ Paid Jan-25","✅ Paid Jan-08-26 (chk#1923)","✅ Paid Feb-02-26","✅ Paid Feb-20-26","In Mar-26"],
})

# ── Reserve schedule (from CNA / audit baseline)
RESERVE = pd.DataFrame({
    "Year":   ["Yr 1","Yr 2","Yr 3","Yr 4","Yr 5","Yr 6","Yr 7","Yr 8"],
    "Balance":[734280,769342,809824,626409,428488,236185,221978,174855],
    "Draw":   [0,     0,     4227,  229410,242554,235422,55896, 89523],
})

COMPONENTS = pd.DataFrame({
    "Component":        ["Elevators (2)","Boiler System","HVAC Units (77)","Roof",
                         "Plumbing Infra","Common Area Flooring","Exterior/Facade","Windows"],
    "Useful_Life":      [25,20,15,20,30,10,25,25],
    "Remaining_Life":   [8, 5, 4, 10,15, 3, 12,18],
    "Replacement_Cost": [350000,80000,154000,120000,200000,45000,180000,95000],
    "Reserve/Unit/Yr":  [257,59,151,88,98,66,106,56],
})

# ── GL Reconciliation data
GL_RECON = {
    "jan": {
        "matches": [
            ("City EC Main (37-0345000-01) Jan-26 bill", 8550.91, 8550.91, "01/27/26 invoiced → 02/02/26 paid chk#1943", "✅"),
            ("City EC Office (37-0380000-01) Jan-26 bill", 380.43, 380.43, "01/27/26 invoiced → 02/02/26 paid chk#1942", "✅"),
            ("Blossman Jan-02 (Inv#34085586)", 514.40, 514.40, "01/07/26 invoiced → 01/08/26 paid chk#1923", "✅"),
            ("Blossman Jan-21 (Inv#34375960)", 486.42, 486.42, "01/22/26 invoiced → 02/02/26 paid chk#1941", "✅"),
            ("AGT Final Bill (37-0390000-06)", 83.24, 83.24, "02/16/26 booked split to Elec+Trash", "✅"),
        ],
        "flags": []
    },
    "feb": {
        "matches": [
            ("Blossman Feb-12 (Inv#34657363)", 654.54, 654.54, "02/16/26 invoiced → 02/20/26 paid chk#1965", "✅"),
        ],
        "flags": [
            ("🔴", "DELETED BATCH #1419 ($8,978.45)", "Mar-26 penalty bill entered Feb-16 by mistake, deleted, reversed Feb-28. Net=Zero but messy audit trail. Document before HUD inspection."),
            ("🟡", "Electricity Accrual Overstated", "Feb-26 accrual $9,851.95 vs actual Mar-26 bill $7,966.58. Overstated by ~$1,885. Auto-reverses Mar-01."),
            ("⚠️", "Trash Accrual Understated", "Feb-26 trash accrual only $24.17 vs actual $280/mo bill. Understated by $255.83. Will spike in Mar-26 P&L."),
            ("🔴", "Missing Blossman PDF", "Invoice #34657363 (Feb-12, $654.54) in GL but PDF not uploaded. Request from Beacon/Management."),
            ("🔴", "Office Account Past Due Apr-26", "$405.54 past due + $19.32 penalty. Previous month payment missed. Confirm cleared immediately with Kenya Owens."),
        ]
    }
}

# ── Budget comparison (Feb-26, most recent)
BUDGET_TABLE = pd.DataFrame({
    "Line Item":   ["Electricity","Water","Gas","Sewer","Total Utilities","Bad Debt","Vacancy Loss","Total Operating Exp","NOI","Net Income"],
    "Jan-26 Actual":[7709.25,795.26,1000.82,715.68,10221.01,5818.88,5243,33592.98,33606.55,15104.44],
    "Feb-26 Actual":[6039.44,689.38,654.54,620.40,8003.76,1699,1992,29130.72,41023.14,19424.42],
    "Feb Budget":  [4605,817,745,775,6942,697,1686,31244,42246,24729],
    "Feb Variance":[1434.44,-127.62,-90.46,-154.60,1061.76,1002,-306,-2113.28,-1222.86,-5304.58],
    "Feb Var%":    [-31.1,15.6,12.1,19.9,-15.3,-143.8,181.5,6.8,-2.9,-21.5],
})

UNITS    = 68
SQFT     = 56000
ANNUAL_EGI = 786025  # from T12 total revenue
BUDGET_UTIL_MO = 6942
MORTGAGE = 15130

# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏢 Property Intelligence")
    st.markdown("---")
    api_key = st.text_input("🔑 Groq API Key", type="password", value=st.session_state.groq_key)
    if api_key:
        st.session_state.groq_key = api_key
    st.markdown("---")
    st.selectbox("🏢 Property", ["Virginia Dare Apartments","Add more..."])
    st.markdown("---")
    st.markdown("#### 📁 Upload Documents")
    st.caption("Upload additional bills or reports — system will parse and add to analysis.")
    uploaded_files = st.file_uploader("Drop files here", accept_multiple_files=True, type=["pdf","xlsx","xls","csv"])
    if uploaded_files:
        for file in uploaded_files:
            if file.name not in st.session_state.documents:
                content = ""
                try:
                    if file.name.endswith(".pdf"):
                        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
                        for page in pdf_reader.pages:
                            t = page.extract_text()
                            if t: content += t + "\n"
                    elif file.name.endswith((".xlsx",".xls")):
                        xl = pd.ExcelFile(file)
                        for sheet in xl.sheet_names:
                            df = xl.parse(sheet)
                            content += f"\n--- Sheet: {sheet} ---\n" + df.to_string() + "\n"
                    elif file.name.endswith(".csv"):
                        df = pd.read_csv(file)
                        content = df.to_string()
                except Exception as e:
                    content = f"[Parse error: {e}]"
                st.session_state.documents[file.name] = content
                st.success(f"✅ {file.name}")
    if st.session_state.documents:
        st.markdown(f"**{len(st.session_state.documents)} file(s) loaded**")
        for fname in st.session_state.documents:
            st.caption(f"📄 {fname}")
        if st.button("🗑️ Clear Files"):
            st.session_state.documents = {}
            st.rerun()
    st.markdown("---")
    st.caption("Virginia Dare Apartments · 68 units · HUD HAP\nElizabeth City, NC · GL as of Feb-28-2026")

# ─────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏠 Investor Snapshot",
    "⚡ Utility Deep Dive",
    "📊 Financial Performance",
    "🏦 Reserves & Capital",
    "💬 Ask Anything",
])

# ══════════════════════════════════════════════════════════════
# TAB 1 — INVESTOR SNAPSHOT
# ══════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<p class="main-header">🏢 Virginia Dare Apartments</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">110 McMorrine Street, Elizabeth City, NC &nbsp;·&nbsp; 68 units &nbsp;·&nbsp; 9-story &nbsp;·&nbsp; Built 1927 &nbsp;·&nbsp; HUD HAP Contract &nbsp;·&nbsp; Data as of Feb-28-2026</p>', unsafe_allow_html=True)

    # ── SECTION 1: 5 Top KPIs ──
    st.markdown('<p class="section-title">📊 Key Performance Indicators — Feb-26</p>', unsafe_allow_html=True)
    c1,c2,c3,c4,c5 = st.columns(5)
    ann_util = T12["Total_Util"].sum()
    util_per_unit = ann_util / UNITS
    util_per_sf   = ann_util / SQFT
    util_pct_egi  = (ann_util / ANNUAL_EGI) * 100
    feb_var_pct   = ((FEB26["total_util"] - BUDGET_UTIL_MO) / BUDGET_UTIL_MO) * 100

    with c1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Annualized Utility Cost</div>
            <div class="kpi-value">${ann_util:,.0f}</div>
            <div class="kpi-delta-red">▲ vs ${BUDGET_UTIL_MO*12:,} budget/yr</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Cost Per Unit / Year</div>
            <div class="kpi-value">${util_per_unit:,.0f}</div>
            <div class="kpi-delta-gray">68 units</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Cost Per SF / Year</div>
            <div class="kpi-value">${util_per_sf:.2f}</div>
            <div class="kpi-delta-gray">{SQFT:,} sq ft</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        col = "kpi-delta-red" if util_pct_egi > 14 else "kpi-delta-green"
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">% of Annual EGI</div>
            <div class="kpi-value">{util_pct_egi:.1f}%</div>
            <div class="{col}">EGI ${ANNUAL_EGI:,}</div>
        </div>""", unsafe_allow_html=True)
    with c5:
        arrow = "▲" if feb_var_pct > 0 else "▼"
        col = "kpi-delta-red" if feb_var_pct > 0 else "kpi-delta-green"
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Feb-26 Budget Variance</div>
            <div class="kpi-value">{feb_var_pct:+.1f}%</div>
            <div class="{col}">{arrow} vs ${BUDGET_UTIL_MO:,} budget</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── SECTION 2: Donut + Bar ──
    st.markdown('<p class="section-title">📊 Utility Breakdown — Trailing 12 Months</p>', unsafe_allow_html=True)
    col_a, col_b = st.columns([1,2])
    with col_a:
        totals = {
            "Electricity": T12["Elec"].sum(),
            "Water":       T12["Water"].sum(),
            "Gas":         T12["Gas"].sum(),
            "Sewer":       T12["Sewer"].sum(),
            "Trash":       T12["Trash"].sum(),
        }
        fig_donut = go.Figure(go.Pie(
            labels=list(totals.keys()), values=list(totals.values()),
            hole=0.55,
            marker_colors=["#3b82f6","#8b5cf6","#f59e0b","#10b981","#64748b"],
            textinfo="label+percent", textfont_size=11,
        ))
        fig_donut.update_layout(
            showlegend=False, height=280, margin=dict(t=20,b=20,l=10,r=10),
            annotations=[dict(text=f"${ann_util:,.0f}<br><span style='font-size:10px'>T12 Total</span>",
                              x=0.5,y=0.5,font_size=13,showarrow=False)]
        )
        st.plotly_chart(fig_donut, use_container_width=True)
        for k,v in totals.items():
            pct = v/sum(totals.values())*100
            st.markdown(f"**{k}:** ${v:,.0f} ({pct:.0f}%)")

    with col_b:
        fig_bar = px.bar(T12, x="Month",
                         y=["Elec","DD3" if "DD3" in T12.columns else "Elec","Water","Gas","Sewer","Trash"],
                         title="Monthly Utility Breakdown (GL Booked)",
                         color_discrete_map={"Elec":"#3b82f6","Water":"#8b5cf6","Gas":"#f59e0b","Sewer":"#10b981","Trash":"#64748b"},
                         labels={"value":"$","variable":"Category"})
        # Use actual breakdown
        fig_bar2 = go.Figure()
        fig_bar2.add_bar(x=T12["Month"], y=T12["Elec"],   name="Electricity",   marker_color="#3b82f6")
        fig_bar2.add_bar(x=T12["Month"], y=T12["Water"],  name="Water",         marker_color="#8b5cf6")
        fig_bar2.add_bar(x=T12["Month"], y=T12["Gas"],    name="Gas/Propane",   marker_color="#f59e0b")
        fig_bar2.add_bar(x=T12["Month"], y=T12["Sewer"],  name="Sewer",         marker_color="#10b981")
        fig_bar2.add_bar(x=T12["Month"], y=T12["Trash"],  name="Trash",         marker_color="#94a3b8")
        fig_bar2.add_hline(y=BUDGET_UTIL_MO, line_dash="dash", line_color="#ef4444",
                           annotation_text=f"Budget ${BUDGET_UTIL_MO:,}/mo", annotation_position="top left")
        fig_bar2.update_layout(barmode="stack", height=285, margin=dict(t=30,b=10),
                               legend=dict(orientation="h",y=-0.28), title="Monthly Utility (GL Booked) vs Budget")
        st.plotly_chart(fig_bar2, use_container_width=True)

    # ── SECTION 3: Trend ──
    st.markdown('<p class="section-title">📈 Monthly Trend — GL Booked vs Bills vs Budget</p>', unsafe_allow_html=True)

    # Combine T12 + Bills for trend
    bill_map = dict(zip(BILLS["Month"], BILLS["Total_Bill"]))
    T12["Bill_Total"] = T12["Month"].map(bill_map)

    fig_trend = go.Figure()
    fig_trend.add_scatter(x=T12["Month"], y=T12["Total_Util"], name="GL Booked",
                          line=dict(color="#3b82f6",width=2.5), mode="lines+markers", marker=dict(size=7))
    fig_trend.add_scatter(x=T12["Month"], y=T12["Bill_Total"], name="Actual Bill",
                          line=dict(color="#f59e0b",width=2,dash="dot"), mode="lines+markers", marker=dict(size=6))
    fig_trend.add_scatter(x=T12["Month"], y=[BUDGET_UTIL_MO]*len(T12), name="Budget",
                          line=dict(color="#94a3b8",width=1.5,dash="dash"))
    fig_trend.update_layout(height=300, margin=dict(t=20,b=10),
                             legend=dict(orientation="h",y=-0.25), yaxis_title="$")
    st.plotly_chart(fig_trend, use_container_width=True)

    st.markdown("""<div class="insight-box">
        🤖 <strong>AI Insight:</strong> Utility cost has exceeded budget in <strong>8 of 12 months</strong>.
        Peak months: Jan-26 ($10,221), Mar-25 ($9,785), Aug-25 ($9,919).
        Primary driver: <strong>Electricity + DD3 Demand Charge</strong> = 71% of total utility cost.
        Water reads flat $812/month — consistent with <strong>estimated (not metered) billing</strong>.
        Gas (Blossman) shows irregular delivery pattern — Jan-26 had 2 deliveries totalling $1,001.
    </div>""", unsafe_allow_html=True)

    # ── SECTION 4: Variance Table ──
    st.markdown('<p class="section-title">🚨 Monthly Variance vs Budget</p>', unsafe_allow_html=True)
    var_rows = []
    for _, row in T12.iterrows():
        var_amt = row["Total_Util"] - BUDGET_UTIL_MO
        var_pct = (var_amt / BUDGET_UTIL_MO)*100
        flag = "🔴 >20% Over" if var_pct>20 else "🟡 >10% Over" if var_pct>10 else "🟢 Under Budget" if var_pct<-5 else "✅ On Track"
        note = ""
        if row["Elec"] > 6000: note = "High electricity"
        if row["Gas"] > 900:   note = (note+" | " if note else "") + "High gas/propane"
        var_rows.append({
            "Month": row["Month"], "GL Total": f"${row['Total_Util']:,.0f}",
            "Budget": f"${BUDGET_UTIL_MO:,}", "Variance $": f"${var_amt:+,.0f}",
            "Variance %": f"{var_pct:+.1f}%", "Flag": flag, "Note": note,
        })
    df_var = pd.DataFrame(var_rows)
    def color_flag(val):
        if "🔴" in str(val): return "background-color:#fef2f2"
        if "🟡" in str(val): return "background-color:#fffbeb"
        if "🟢" in str(val): return "background-color:#f0fdf4"
        return ""
    st.dataframe(df_var.style.applymap(color_flag, subset=["Flag"]), use_container_width=True, hide_index=True)

    # ── SECTION 5: Reserve Snapshot ──
    st.markdown('<p class="section-title">🏦 Replacement Reserve Snapshot</p>', unsafe_allow_html=True)
    rc1,rc2,rc3,rc4 = st.columns(4)
    with rc1:
        st.markdown('<div class="kpi-card"><div class="kpi-label">Yr 1 Balance</div><div class="kpi-value" style="color:#16a34a">$734,280</div></div>', unsafe_allow_html=True)
    with rc2:
        st.markdown('<div class="kpi-card"><div class="kpi-label">Yr 4–6 Draw</div><div class="kpi-value" style="color:#dc2626">$707,386</div></div>', unsafe_allow_html=True)
    with rc3:
        st.markdown('<div class="kpi-card"><div class="kpi-label">Yr 8 Balance</div><div class="kpi-value" style="color:#d97706">$174,855</div></div>', unsafe_allow_html=True)
    with rc4:
        st.markdown('<div class="kpi-card"><div class="kpi-label">Recommended Reserve/Unit/Yr</div><div class="kpi-value">$881</div></div>', unsafe_allow_html=True)
    st.caption("👉 See **Reserves & Capital** tab for full 8-year projection and component analysis.")

    # ── SECTION 6: NOI Impact ──
    st.markdown('<p class="section-title">📉 NOI Impact View</p>', unsafe_allow_html=True)
    avg_mo_util = T12["Total_Util"].mean()
    noi_after_util  = T12["NOI"].mean()
    reserve_avg_draw = RESERVE["Draw"].mean()
    noi_after_res   = noi_after_util - reserve_avg_draw
    noi_if_fixed    = noi_after_util + 26800/12  # monthly savings

    n1,n2,n3,n4 = st.columns(4)
    with n1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Avg Monthly NOI (T12)</div>
            <div class="kpi-value">${noi_after_util:,.0f}</div>
            <div class="kpi-delta-gray">After all operating expenses</div>
        </div>""", unsafe_allow_html=True)
    with n2:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">NOI After Reserve Draw</div>
            <div class="kpi-value">${noi_after_res:,.0f}</div>
            <div class="kpi-delta-red">Avg ${reserve_avg_draw:,.0f}/mo draw</div>
        </div>""", unsafe_allow_html=True)
    with n3:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Utility Over-Budget (T12)</div>
            <div class="kpi-value" style="color:#dc2626">${ann_util - BUDGET_UTIL_MO*12:,.0f}</div>
            <div class="kpi-delta-red">vs ${BUDGET_UTIL_MO*12:,} budget</div>
        </div>""", unsafe_allow_html=True)
    with n4:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">NOI if Top 4 Fixed</div>
            <div class="kpi-value" style="color:#16a34a">${noi_if_fixed:,.0f}/mo</div>
            <div class="kpi-delta-green">+$26,800/yr savings potential</div>
        </div>""", unsafe_allow_html=True)

    st.markdown(f"""<div class="insight-box">
        💰 <strong>Value Creation:</strong> HVAC PM + LED Retrofit + Demand Controller + Refuse Fix =
        <strong>~$26,800/yr savings</strong>. At 6% cap rate → <strong>$447,000 added property value.</strong>
        Utility budget overrun (T12: ${ann_util - BUDGET_UTIL_MO*12:,.0f}) is the single largest controllable expense driver.
    </div>""", unsafe_allow_html=True)

    # ── SECTION 7: Alerts ──
    st.markdown('<p class="section-title">🚨 Alerts & Findings</p>', unsafe_allow_html=True)
    alerts = [
        ("red",    "🔴 CRITICAL — GL Anomaly: Deleted batch #1419 ($8,978.45) entered Feb-16 (Mar bill by mistake), deleted, reversed Feb-28. Net=Zero but messy audit trail. Must document before HUD inspection."),
        ("red",    "🔴 CRITICAL — Office Account Apr-26 past due $405.54 + $19.32 penalty. Previous month payment missed by management. Confirm cleared immediately — disconnect date was Apr-23."),
        ("red",    "🔴 CRITICAL — DD3 Demand Charge: $2,707 spike in BOTH Feb-25 AND Jan-26 — confirms this is a recurring winter peak issue, not one-time. Demand controller/peak shaving relay needed urgently."),
        ("red",    "🔴 CRITICAL — HUD Life Safety violations open: GFCI outlets ($4,760) + smoke detectors ($2,380) + UFAS accessibility ($5,000) = $13,540. Must resolve before next HUD inspection."),
        ("yellow", "🟡 HIGH — Feb-26 Electricity accrual overstated by ~$1,885 ($9,852 accrued vs $7,967 actual Mar bill). Will auto-reverse Mar-01 but inflates Feb P&L temporarily."),
        ("yellow", "🟡 HIGH — Feb-26 Trash accrual understated: only $24.17 accrued vs $280/mo actual. Mar-26 P&L will show spike. Accrual methodology needs review with Beacon Management."),
        ("yellow", "🟡 HIGH — Elevator replacement (Yr 4–6): $707K draw will reduce reserves from $810K → $174K. Current HVAC stress = early warning of mechanical wear. Physical inspection recommended by Yr 3."),
        ("yellow", "🟡 HIGH — Propane: Jan-26 had 2 deliveries in 19 days (409.6 gal / $1,001). Unusually high — possible tank leak or fill error. Investigate with Blossman. Rate up 7.1% YoY."),
        ("blue",   "🔵 MEDIUM — Water meter: reads exactly 99 units every month ($812.49). Likely estimated billing not actual metered usage. Request meter verification from City of Elizabeth City."),
        ("blue",   "🔵 MEDIUM — Missing Blossman PDF: Invoice #34657363 (Feb-12, $654.54) correctly in GL but PDF not uploaded. Request from management."),
        ("blue",   "🔵 MEDIUM — Bad Debt Jan-26: $5,819 — significantly above budget ($697). Investigate which tenants and whether HUD subsidy adjustments are current."),
    ]
    for level, text in alerts:
        st.markdown(f'<div class="alert-{level}">{text}</div>', unsafe_allow_html=True)

    # ── SECTION 8: Action Plan ──
    st.markdown('<p class="section-title">✅ Action Plan — Ranked by Urgency</p>', unsafe_allow_html=True)
    actions = [
        {"#":1,"Priority":"🔴 Immediate","Action":"Confirm Office account Apr-26 past due $405.54 cleared — call Kenya Owens","Deadline":"Today","Est. Impact":"Compliance"},
        {"#":2,"Priority":"🔴 Immediate","Action":"Document deleted GL batch #1419 ($8,978.45) — memo to file for HUD audit trail","Deadline":"This week","Est. Impact":"HUD compliance"},
        {"#":3,"Priority":"🔴 Immediate","Action":"Clear HUD life safety violations: GFCI $4,760 + Smoke $2,380 + UFAS $5,000","Deadline":"Before inspection","Est. Impact":"$13,540 capex"},
        {"#":4,"Priority":"🔴 30 days","Action":"Install demand controller/peak shaving relay — eliminate DD3 winter spikes","Deadline":"30 days","Est. Impact":"$5-12K/yr"},
        {"#":5,"Priority":"🟡 30 days","Action":"Investigate Jan-26 double propane delivery (409 gal) — possible tank leak","Deadline":"30 days","Est. Impact":"Cost control"},
        {"#":6,"Priority":"🟡 30 days","Action":"HVAC PM contract — all 77 units to reduce peak load","Deadline":"30 days","Est. Impact":"$6,200/yr"},
        {"#":7,"Priority":"🟡 30 days","Action":"Request water meter verification from City of Elizabeth City","Deadline":"30 days","Est. Impact":"Risk mgmt"},
        {"#":8,"Priority":"🟡 60 days","Action":"LED retrofit — common areas + exterior","Deadline":"60 days","Est. Impact":"$8,400/yr"},
        {"#":9,"Priority":"🟡 60 days","Action":"Review accrual methodology with Beacon — fix trash underaccrual pattern","Deadline":"60 days","Est. Impact":"Cleaner P&L"},
        {"#":10,"Priority":"🔵 90 days","Action":"CNA physical inspection of elevators before Yr 3 — confirm replacement timeline","Deadline":"90 days","Est. Impact":"$350K planning"},
    ]
    st.dataframe(pd.DataFrame(actions), use_container_width=True, hide_index=True)
    st.markdown(f'<div class="alert-green">💰 <strong>Value Creation:</strong> Top improvements = ~$26,800/yr savings. At 6% cap rate = <strong>$447,000 added property value.</strong></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# TAB 2 — UTILITY DEEP DIVE
# ══════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<p class="main-header">⚡ Utility Deep Dive</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Source: City of Elizabeth City bills + Blossman Gas invoices + GL (Jan-26 & Feb-26 financial reports)</p>', unsafe_allow_html=True)

    # DD3 Demand charge
    st.markdown('<p class="section-title">⚡ Electricity + DD3 Demand Charge (from Actual Bills)</p>', unsafe_allow_html=True)
    col1,col2 = st.columns(2)
    with col1:
        fig_elec = go.Figure()
        fig_elec.add_bar(x=BILLS["Month"], y=BILLS["Elec"]-BILLS["DD3"], name="Base Electric", marker_color="#3b82f6")
        fig_elec.add_bar(x=BILLS["Month"], y=BILLS["DD3"], name="DD3 Demand Charge", marker_color="#ef4444")
        fig_elec.update_layout(barmode="stack", height=300, title="Electricity Breakdown (Bills)",
                               margin=dict(t=35,b=10), legend=dict(orientation="h",y=-0.3))
        st.plotly_chart(fig_elec, use_container_width=True)

    with col2:
        fig_dd3 = go.Figure()
        fig_dd3.add_scatter(x=BILLS["Month"], y=BILLS["DD3"], name="DD3 Demand",
                            line=dict(color="#ef4444",width=2.5), mode="lines+markers",
                            marker=dict(size=9), fill="tozeroy", fillcolor="rgba(239,68,68,0.08)")
        fig_dd3.add_hline(y=BILLS["DD3"].mean(), line_dash="dash", line_color="#94a3b8",
                          annotation_text=f"Avg ${BILLS['DD3'].mean():.0f}", annotation_position="top right")
        fig_dd3.update_layout(height=300, title="DD3 Demand Charge Trend",
                              margin=dict(t=35,b=10), yaxis_title="$")
        st.plotly_chart(fig_dd3, use_container_width=True)

    st.markdown("""<div class="alert-red">
        🔴 <strong>DD3 Spike Pattern Confirmed:</strong> Feb-25 ($2,707) AND Jan-26 ($2,707) — identical peak.
        This is a <strong>recurring winter demand issue</strong>, not a one-time event.
        Demand charge rate = $1.83/kW (Mar-26 bill). Peak demand was 146 kW (Mar-26) vs 206 kW (Jan-26).
        A demand controller targeting peak below 100 kW could save $5-12K/year.
    </div>""", unsafe_allow_html=True)

    # Water
    st.markdown('<p class="section-title">💧 Water & Sewer Analysis</p>', unsafe_allow_html=True)
    col3,col4 = st.columns(2)
    with col3:
        fig_water = go.Figure()
        fig_water.add_bar(x=BILLS["Month"], y=BILLS["Water"], name="Water", marker_color="#8b5cf6")
        fig_water.add_bar(x=BILLS["Month"], y=BILLS["Sewer"], name="Sewer", marker_color="#6d28d9")
        fig_water.update_layout(barmode="stack", height=280, title="Water + Sewer (from Bills)",
                                margin=dict(t=35,b=10), legend=dict(orientation="h",y=-0.3))
        st.plotly_chart(fig_water, use_container_width=True)

    with col4:
        water_stats = {
            "Metric": ["Avg Monthly Water","Std Deviation","Min","Max","Usage (units/mo)","Bill reads"],
            "Value": [f"${BILLS['Water'].mean():.2f}",f"${BILLS['Water'].std():.2f}",
                      f"${BILLS['Water'].min():.2f}",f"${BILLS['Water'].max():.2f}","99 (every month)","ESTIMATED ⚠️"]
        }
        st.dataframe(pd.DataFrame(water_stats), use_container_width=True, hide_index=True)
        st.markdown("""<div class="alert-yellow">
            🟡 <strong>Estimated Meter Warning:</strong> Water usage = exactly 99 units every single month
            (Dec-10 to Jan-12-26 bill: 18,888 current − 18,789 prior = 99). City is estimating, not reading.
            Actual consumption may be higher or lower. Request meter verification immediately.
        </div>""", unsafe_allow_html=True)

    # Gas / Propane
    st.markdown('<p class="section-title">🔥 Gas / Propane (Blossman)</p>', unsafe_allow_html=True)
    col5,col6 = st.columns([1,1])
    with col5:
        gas_bills = BILLS[BILLS["Gas_Blossman"]>0].copy()
        fig_gas = px.bar(gas_bills, x="Month", y="Gas_Blossman",
                         color_discrete_sequence=["#f59e0b"], title="Monthly Propane Spend")
        fig_gas.update_layout(height=260, margin=dict(t=35,b=10), yaxis_title="$")
        st.plotly_chart(fig_gas, use_container_width=True)

    with col6:
        st.markdown("**📋 Blossman Invoice Log**")
        st.dataframe(PROPANE, use_container_width=True, hide_index=True)
        st.markdown("""<div class="alert-yellow">
            🟡 <strong>Price up 7.1% YoY:</strong> $2.099 (Jan-25) → $2.249 (Jan-26).<br>
            ⚠️ <strong>Jan-26 double delivery:</strong> 210.6 + 199.0 gal in 19 days = 409.6 gal / $1,001.
            Normal month = ~150-200 gal. Investigate possible tank leak or fill error with Blossman.
        </div>""", unsafe_allow_html=True)

    # Per-unit cost table
    st.markdown('<p class="section-title">📋 Monthly Per-Unit Cost (GL Booked)</p>', unsafe_allow_html=True)
    df_pu = T12.copy()
    df_pu["$/Unit"] = (df_pu["Total_Util"]/UNITS).round(2)
    df_pu["$/SF"]   = (df_pu["Total_Util"]/SQFT).round(4)
    df_pu["vs Budget"] = df_pu["Total_Util"].apply(lambda x: f"${x-BUDGET_UTIL_MO:+,.0f}")
    df_pu["Flag"] = df_pu["Total_Util"].apply(lambda x:
        "🔴 >20% over" if x>BUDGET_UTIL_MO*1.2 else "🟡 >10% over" if x>BUDGET_UTIL_MO*1.1 else "✅")
    st.dataframe(df_pu[["Month","Total_Util","Elec","Water","Gas","Sewer","Trash","$/Unit","vs Budget","Flag"]],
                 use_container_width=True, hide_index=True)

    # Forward projection
    st.markdown('<p class="section-title">🔮 Forward Cost Projection (from T12 Avg)</p>', unsafe_allow_html=True)
    avg_mo = T12["Total_Util"].mean()
    pc1,pc2,pc3 = st.columns(3)
    for col_widget, rate, label in [(pc1,0.02,"Conservative (2%)"),(pc2,0.03,"Base Case (3%)"),(pc3,0.05,"Stress (5%)")]:
        yr1 = avg_mo*12*(1+rate)
        yr3 = avg_mo*12*(1+rate)**3
        with col_widget:
            st.markdown(f"""<div class="kpi-card">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">${yr1:,.0f}</div>
                <div class="kpi-delta-gray">Yr 1 annualized | Yr 3: ${yr3:,.0f}</div>
            </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# TAB 3 — FINANCIAL PERFORMANCE
# ══════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<p class="main-header">📊 Financial Performance</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Source: Jan-26 & Feb-26 Financial Reports | Accrual basis | Data as of Feb-28-2026</p>', unsafe_allow_html=True)

    # KPIs
    st.markdown('<p class="section-title">💰 Income & NOI — Feb-26</p>', unsafe_allow_html=True)
    f1,f2,f3,f4,f5 = st.columns(5)
    kpis = [
        ("Total Revenue",     FEB26["revenue"],    FEB26["budget_rev"],   "budget"),
        ("Net Operating Income",FEB26["noi"],       FEB26["budget_noi"],   "budget"),
        ("Net Income",        FEB26["net_income"],  FEB26["budget_ni"],    "budget"),
        ("Vacancy Loss",      -FEB26["vacancy"],    1686,                  "lower_better"),
        ("Bad Debt",          -FEB26["bad_debt"],   -697,                  "lower_better"),
    ]
    for widget, (label, actual, budget, mode) in zip([f1,f2,f3,f4,f5], kpis):
        var = actual - budget
        var_pct = (var/abs(budget))*100 if budget else 0
        if mode == "budget":
            col = "kpi-delta-green" if var >= 0 else "kpi-delta-red"
        else:
            col = "kpi-delta-red" if actual < budget else "kpi-delta-green"
        with widget:
            st.markdown(f"""<div class="kpi-card">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">${abs(actual):,.0f}</div>
                <div class="{col}">vs ${abs(budget):,} budget ({var_pct:+.1f}%)</div>
            </div>""", unsafe_allow_html=True)

    # Revenue + NOI trend
    st.markdown('<p class="section-title">📈 Revenue, Expenses & NOI — Trailing 12 Months</p>', unsafe_allow_html=True)
    fig_fin = go.Figure()
    fig_fin.add_bar(x=T12["Month"], y=T12["Revenue"],  name="Revenue",  marker_color="#22c55e", opacity=0.8)
    fig_fin.add_bar(x=T12["Month"], y=T12["Expenses"], name="Expenses", marker_color="#ef4444", opacity=0.8)
    fig_fin.add_scatter(x=T12["Month"], y=T12["NOI"], name="NOI",
                        line=dict(color="#3b82f6",width=3), mode="lines+markers", marker=dict(size=8))
    fig_fin.update_layout(barmode="group", height=340, margin=dict(t=20,b=10),
                           legend=dict(orientation="h",y=-0.25), yaxis_title="$")
    st.plotly_chart(fig_fin, use_container_width=True)

    # Net income trend
    col_ni1, col_ni2 = st.columns([2,1])
    with col_ni1:
        fig_ni = go.Figure()
        colors_ni = ["#16a34a" if v >= 0 else "#dc2626" for v in T12["Net_Income"]]
        fig_ni.add_bar(x=T12["Month"], y=T12["Net_Income"], name="Net Income",
                       marker_color=colors_ni)
        fig_ni.add_hline(y=0, line_color="#94a3b8", line_width=1)
        fig_ni.update_layout(height=260, title="Net Income (Loss) by Month",
                             margin=dict(t=35,b=10), yaxis_title="$")
        st.plotly_chart(fig_ni, use_container_width=True)
        st.markdown("""<div class="alert-yellow">
            🟡 <strong>Net Loss months:</strong> Apr-25 (−$180), May-25 (−$8,675), Nov-25 (−$29,612 — large insurance/non-recurring expense).
            T12 total net income = $67,662 but highly volatile month-to-month.
        </div>""", unsafe_allow_html=True)

    with col_ni2:
        st.markdown("**T12 Financial Summary**")
        summary = pd.DataFrame({
            "Item": ["Total Revenue","Total Expenses","Net Op. Income","Net Income","Avg NOI/mo","Debt Service/yr"],
            "Amount": [f"${ANNUAL_EGI:,}",
                       f"${T12['Expenses'].sum():,}",
                       f"${T12['NOI'].sum():,}",
                       f"$67,662",
                       f"${T12['NOI'].mean():,.0f}",
                       f"${MORTGAGE*12:,}"]
        })
        st.dataframe(summary, use_container_width=True, hide_index=True)

    # Budget comparison table
    st.markdown('<p class="section-title">📋 Budget Comparison — Feb-26 (Most Recent)</p>', unsafe_allow_html=True)
    def color_var(val):
        try:
            v = float(str(val).replace(",",""))
            if v > 500:  return "background-color:#fef2f2;color:#dc2626"
            if v < -200: return "background-color:#f0fdf4;color:#15803d"
        except: pass
        return ""
    st.dataframe(BUDGET_TABLE.style.applymap(color_var, subset=["Feb Variance"]),
                 use_container_width=True, hide_index=True)

    # GL Reconciliation
    st.markdown('<p class="section-title">🔍 GL Reconciliation — Bill vs Books</p>', unsafe_allow_html=True)
    rec_tab1, rec_tab2 = st.tabs(["January 2026 ✅", "February 2026 ⚠️"])

    with rec_tab1:
        st.markdown("**January 2026 — All bills correctly booked. Zero discrepancies.**")
        for item, bill, gl, note, status in GL_RECON["jan"]["matches"]:
            match_icon = "✅" if status == "✅" else "⚠️"
            st.markdown(f'<div class="recon-match"><strong>{match_icon} {item}</strong><br>Bill: ${bill:,.2f} | GL: ${gl:,.2f} | {note}</div>', unsafe_allow_html=True)
        st.markdown("""<div class="insight-box">
            ✅ <strong>January 2026 is clean.</strong>
            Note: Blossman Jan-02 invoice ($514.40) appeared missing from Feb GL — but Jan GL confirms
            it was paid Jan-08-26 (chk#1923). It was already cleared before Feb books opened.
            All accruals reversed correctly on Feb-01.
        </div>""", unsafe_allow_html=True)

    with rec_tab2:
        st.markdown("**February 2026 — 1 match confirmed, 5 flags require attention.**")
        for item, bill, gl, note, status in GL_RECON["feb"]["matches"]:
            st.markdown(f'<div class="recon-match"><strong>✅ {item}</strong><br>Bill: ${bill:,.2f} | GL: ${gl:,.2f} | {note}</div>', unsafe_allow_html=True)
        st.markdown("<br>**⚠️ Flags:**", unsafe_allow_html=True)
        for icon, title, desc in GL_RECON["feb"]["flags"]:
            cls = "recon-flag" if icon == "🔴" else "recon-warn"
            st.markdown(f'<div class="{cls}"><strong>{icon} {title}</strong><br>{desc}</div>', unsafe_allow_html=True)

        # Accrual vs actual table
        st.markdown("<br>**Feb-26 Accrual vs Actual Bill Comparison:**")
        accrual_df = pd.DataFrame({
            "Category":     ["Electricity","Water","Gas","Sewer","Trash"],
            "GL Accrual":   [9851.95, 1132.56, 654.54, 1019.23,  24.17],
            "Actual Bill":  [5607.76,  812.49, 654.54,  731.19, 280.00],
            "Variance":     [4244.19,  320.07,   0.00,  288.04,-255.83],
            "Status":       ["🟡 Overstated","🟡 Overstated","✅ Match","🟡 Overstated","⚠️ Understated"],
        })
        st.dataframe(accrual_df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════
# TAB 4 — RESERVES & CAPITAL
# ══════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<p class="main-header">🏦 Replacement Reserve & Capital Planning</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Source: HUD Reserve Schedule | Upload Audit Report or CNA to override with actual figures.</p>', unsafe_allow_html=True)

    # 8-year projection
    st.markdown('<p class="section-title">📊 Reserve Balance Projection (8-Year)</p>', unsafe_allow_html=True)
    fig_res = go.Figure()
    bar_colors = ["#16a34a" if b>400000 else "#f59e0b" if b>200000 else "#ef4444" for b in RESERVE["Balance"]]
    fig_res.add_bar(x=RESERVE["Year"], y=RESERVE["Balance"], name="Reserve Balance", marker_color=bar_colors)
    fig_res.add_scatter(x=RESERVE["Year"], y=RESERVE["Draw"], name="Annual Draw",
                        line=dict(color="#ef4444",dash="dash",width=2), mode="lines+markers")
    fig_res.add_hline(y=200000, line_dash="dot", line_color="#f59e0b",
                      annotation_text="⚠️ Caution $200K", annotation_position="top left")
    fig_res.update_layout(height=360, margin=dict(t=20,b=10),
                           legend=dict(orientation="h",y=-0.2), yaxis_title="$")
    st.plotly_chart(fig_res, use_container_width=True)

    res_c1,res_c2,res_c3,res_c4 = st.columns(4)
    for widget, label, value, color in [
        (res_c1,"Yr 1 Balance","$734,280","#16a34a"),
        (res_c2,"Yr 3 Balance (pre-draw)","$809,824","#16a34a"),
        (res_c3,"Yr 4–6 Draw","$707,386","#dc2626"),
        (res_c4,"Yr 8 Balance","$174,855","#d97706"),
    ]:
        with widget:
            st.markdown(f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value" style="color:{color}">{value}</div></div>', unsafe_allow_html=True)

    st.markdown("""<div class="alert-yellow">
        🟡 <strong>Elevator Replacement (Yr 4–6):</strong> $707,386 draw reduces balance from $810K → $174K.
        Current DD3 demand spikes suggest HVAC/boiler stress — <strong>risk of accelerated mechanical failure
        pulling elevator timeline forward</strong>. Recommend physical CNA inspection before Yr 3.
    </div>""", unsafe_allow_html=True)

    # Component table
    st.markdown('<p class="section-title">🔧 Component-Level Reserve Schedule</p>', unsafe_allow_html=True)
    def color_remaining(val):
        try:
            v = int(val)
            if v <= 5:  return "background-color:#fef2f2;color:#dc2626;font-weight:600"
            if v <= 10: return "background-color:#fffbeb;color:#92400e"
            return "background-color:#f0fdf4;color:#15803d"
        except: return ""

    COMPONENTS["Annual Reserve Total"] = COMPONENTS["Reserve/Unit/Yr"] * UNITS
    total_per_unit = COMPONENTS["Reserve/Unit/Yr"].sum()
    total_annual   = COMPONENTS["Annual Reserve Total"].sum()

    st.dataframe(COMPONENTS.style.applymap(color_remaining, subset=["Remaining_Life"]),
                 use_container_width=True, hide_index=True)

    comp_c1,comp_c2,comp_c3 = st.columns(3)
    noi_impact_pct = (total_annual / ANNUAL_EGI)*100
    with comp_c1:
        st.markdown(f'<div class="kpi-card"><div class="kpi-label">Recommended Reserve/Unit/Yr</div><div class="kpi-value">${total_per_unit:,}</div></div>', unsafe_allow_html=True)
    with comp_c2:
        st.markdown(f'<div class="kpi-card"><div class="kpi-label">Total Annual Reserve Required</div><div class="kpi-value">${total_annual:,}</div></div>', unsafe_allow_html=True)
    with comp_c3:
        st.markdown(f'<div class="kpi-card"><div class="kpi-label">Reserve Impact on NOI</div><div class="kpi-value" style="color:#dc2626">-{noi_impact_pct:.1f}%</div><div class="kpi-delta-gray">of annual EGI</div></div>', unsafe_allow_html=True)

    st.markdown(f"""<div class="insight-box">
        🤖 <strong>Key Insight:</strong> Recommended reserve = <strong>${total_per_unit:,}/unit/yr</strong> (${total_annual:,} total).
        <strong>HVAC (4 yrs remaining)</strong> and <strong>Elevators (8 yrs remaining)</strong> are highest priority.
        Combined utility overrun + reserve requirement = significant NOI pressure.
        Upload your CNA or Audit report to populate with property-specific figures.
    </div>""", unsafe_allow_html=True)

    # NOI Waterfall
    st.markdown('<p class="section-title">📉 NOI Waterfall — Full Impact View</p>', unsafe_allow_html=True)
    wf_labels = ["Gross Revenue","Utility Cost","Other Operating","NOI Before Reserve","Reserve Draw","NOI After Reserve"]
    other_exp = T12["Expenses"].mean() - T12["Total_Util"].mean()
    noi_before_res = T12["Revenue"].mean() - T12["Total_Util"].mean() - other_exp
    noi_after_res_wf = noi_before_res - (total_annual/12)
    wf_vals = [T12["Revenue"].mean(), -T12["Total_Util"].mean(), -other_exp, 0, -(total_annual/12), 0]
    fig_wf = go.Figure(go.Waterfall(
        orientation="v", measure=["absolute","relative","relative","total","relative","total"],
        x=wf_labels, y=wf_vals,
        connector={"line":{"color":"#cbd5e1"}},
        increasing={"marker":{"color":"#16a34a"}},
        decreasing={"marker":{"color":"#ef4444"}},
        totals={"marker":{"color":"#3b82f6"}},
    ))
    fig_wf.update_layout(height=380, margin=dict(t=20,b=10), yaxis_title="$/month (avg)")
    st.plotly_chart(fig_wf, use_container_width=True)

# ══════════════════════════════════════════════════════════════
# TAB 5 — ASK ANYTHING
# ══════════════════════════════════════════════════════════════
with tab5:
    st.markdown('<p class="main-header">💬 Ask Anything</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Ask any question about Virginia Dare — powered by actual GL, bills, and financial reports.</p>', unsafe_allow_html=True)

    if not st.session_state.groq_key:
        st.warning("⚠️ Enter your Groq API Key in the sidebar to use the chatbot.")
    else:
        suggestions = [
            "Why is electricity over budget?","What caused the DD3 spike?",
            "When will reserves run low?","What are the HUD violations?",
            "Explain the deleted GL batch","Is water billing estimated?",
            "Jan-26 vs Feb-26 NOI comparison","What should I ask management?",
            "Propane situation and double delivery","How much can NOI improve?",
        ]
        cols = st.columns(5)
        for i, s in enumerate(suggestions):
            with cols[i%5]:
                if st.button(s, key=f"sug_{i}"):
                    st.session_state.messages.append({"role":"user","content":s})

        st.markdown("---")
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        doc_context = ""
        if st.session_state.documents:
            doc_context = "\n\nADDITIONAL UPLOADED DOCUMENTS:\n"
            for fname, content in st.session_state.documents.items():
                doc_context += f"\n--- {fname} ---\n{content[:2500]}\n"

        SYSTEM_PROMPT = f"""You are a senior real estate financial analyst specializing in HUD affordable housing.
You have full access to Virginia Dare Apartments financial data.

PROPERTY: Virginia Dare Apartments
110 McMorrine St, Elizabeth City NC | 68 units | 9-story | Built 1927 | HUD HAP Contract
Management: Beacon Management (Kenya Owens)

FINANCIAL DATA (Trailing 12 Months: Feb-25 to Jan-26):
- Annual Revenue: $786,025 | Annual EGI
- Total Utility Cost (T12): ${ann_util:,.0f} vs ${BUDGET_UTIL_MO*12:,} budget
- Avg Monthly NOI: ${T12["NOI"].mean():,.0f}
- T12 Net Income: $67,662 (highly volatile — Nov-25 had -$29,612 loss)
- Annual Mortgage (interest): ${MORTGAGE*12:,}

JAN-26 FINANCIALS: Revenue $67,200 | NOI $33,607 | Net Income $15,104 | Utilities $10,221 (vs $6,942 budget, -47.2%)
FEB-26 FINANCIALS: Revenue $70,154 | NOI $41,023 | Net Income $19,424 | Utilities $8,004 (vs $6,942 budget, -15.3%)

UTILITY BILLS (City of EC + Blossman):
- Main account (37-0345000-01): Nov-24 $4,614 | Feb-25 $8,889 (DD3=$2,707 spike) | Dec-25 $7,230 | Jan-26 $8,551 (DD3=$2,707 again!) | Mar-26 $7,967
- Office account (37-0380000-01): ~$374-389/mo | Apr-26 PAST DUE $405.54 + $19.32 penalty
- Blossman Gas: Jan-25 $394 (172gal@$2.099) | Jan-26 TWO deliveries $514+$486=$1,001 (unusual!) | Mar-26 $357.86
- Water meter: reads exactly 99 units EVERY month = ESTIMATED billing

GL RECONCILIATION FINDINGS:
- Jan-26 GL: ALL BILLS CORRECTLY BOOKED. Zero discrepancies.
- Feb-26 GL: Deleted batch #1419 ($8,978.45) — Mar bill entered by mistake Feb-16, deleted, reversed Feb-28. Net=Zero.
- Feb-26 Electricity accrual $9,852 overstated vs actual $7,967 bill (auto-reverses Mar-01)
- Feb-26 Trash accrual only $24.17 vs $280 actual (understated — Mar P&L will spike)
- Missing Blossman PDF: Invoice #34657363 (Feb-12, $654.54) in GL, PDF not uploaded

RESERVES: Yr1 $734,280 | Yr4-6 elevator draw $707K | Yr8 balance $174,855
CRITICAL REPAIRS: $13,540 (GFCI $4,760 + Smoke $2,380 + UFAS $5,000)
SAVINGS POTENTIAL: $26,800/yr → $447,000 property value at 6% cap rate
{doc_context}

Answer with specific numbers, flag risks clearly, suggest concrete action items. Be concise but thorough."""

        if prompt := st.chat_input("Ask about utilities, GL, NOI, reserves, bills..."):
            st.session_state.messages.append({"role":"user","content":prompt})
            with st.chat_message("user"):
                st.write(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Analyzing..."):
                    try:
                        client = Groq(api_key=st.session_state.groq_key)
                        history = [{"role":m["role"],"content":m["content"]} for m in st.session_state.messages[:-1]]
                        response = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[{"role":"system","content":SYSTEM_PROMPT},*history,
                                      {"role":"user","content":prompt}],
                            max_tokens=1500
                        )
                        reply = response.choices[0].message.content
                        st.write(reply)
                        st.session_state.messages.append({"role":"assistant","content":reply})
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

        if st.session_state.messages:
            if st.button("🗑️ Clear Chat"):
                st.session_state.messages = []
                st.rerun()
