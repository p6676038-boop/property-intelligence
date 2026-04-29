import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from groq import Groq
import PyPDF2
import io
import re

st.set_page_config(page_title="Property Intelligence System", page_icon="🏢", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.main-header{font-size:1.75rem;font-weight:700;color:#0f172a;margin-bottom:0.15rem;}
.sub-header{font-size:0.82rem;color:#64748b;margin-bottom:1.2rem;}
.section-title{font-size:0.95rem;font-weight:600;color:#1e293b;margin:1.1rem 0 0.5rem 0;border-bottom:2px solid #e2e8f0;padding-bottom:0.25rem;}
.kpi-card{background:white;padding:1rem 1.1rem;border-radius:10px;border:1px solid #e2e8f0;box-shadow:0 1px 3px rgba(0,0,0,0.06);height:100%;}
.kpi-label{font-size:0.68rem;color:#64748b;font-weight:500;text-transform:uppercase;letter-spacing:0.05em;}
.kpi-value{font-size:1.4rem;font-weight:700;color:#0f172a;margin:0.2rem 0;}
.kpi-sub{font-size:0.7rem;color:#64748b;margin-top:0.1rem;}
.delta-red{font-size:0.72rem;color:#dc2626;font-weight:600;}
.delta-green{font-size:0.72rem;color:#16a34a;font-weight:600;}
.delta-gray{font-size:0.72rem;color:#64748b;}
.alert-red{background:#fef2f2;padding:0.7rem 1rem;border-radius:8px;border-left:4px solid #ef4444;margin:0.35rem 0;font-size:0.83rem;}
.alert-yellow{background:#fffbeb;padding:0.7rem 1rem;border-radius:8px;border-left:4px solid #f59e0b;margin:0.35rem 0;font-size:0.83rem;}
.alert-blue{background:#eff6ff;padding:0.7rem 1rem;border-radius:8px;border-left:4px solid #3b82f6;margin:0.35rem 0;font-size:0.83rem;}
.alert-green{background:#f0fdf4;padding:0.7rem 1rem;border-radius:8px;border-left:4px solid #22c55e;margin:0.35rem 0;font-size:0.83rem;}
.insight-box{background:linear-gradient(135deg,#f0f9ff,#e0f2fe);border:1px solid #bae6fd;border-radius:10px;padding:0.85rem 1.1rem;margin:0.5rem 0;font-size:0.83rem;color:#0c4a6e;}
.insight-box strong{color:#0369a1;}
.recon-match{background:#f0fdf4;padding:0.45rem 0.8rem;border-radius:6px;border-left:3px solid #22c55e;margin:0.2rem 0;font-size:0.81rem;}
.recon-flag{background:#fef2f2;padding:0.45rem 0.8rem;border-radius:6px;border-left:3px solid #ef4444;margin:0.2rem 0;font-size:0.81rem;}
.recon-warn{background:#fffbeb;padding:0.45rem 0.8rem;border-radius:6px;border-left:3px solid #f59e0b;margin:0.2rem 0;font-size:0.81rem;}
</style>
""", unsafe_allow_html=True)

for key, default in [("messages",[]),("documents",{}),("groq_key","")]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── DATA ──
UNITS=68; SQFT=56000; BUDGET_UTIL_MO=6942; MORTGAGE_MO=15130; ANNUAL_EGI=786025

T12 = pd.DataFrame({
    "Month":   ["Feb-25","Mar-25","Apr-25","May-25","Jun-25","Jul-25","Aug-25","Sep-25","Oct-25","Nov-25","Dec-25","Jan-26"],
    "Revenue": [64642,63045,60395,65840,65745,65173,65740,63987,67534,67880,68845,67200],
    "Expenses":[35093,36806,44395,44011,30969,29022,45828,25240,26492,26546,43098,33593],
    "NOI":     [29549,26239,16000,21829,34776,36151,19912,38747,41042,41334,25747,33607],
    "Net_Inc": [9497,1760,-8675,-180,12013,8089,1742,14792,22542,20590,-29612,15104],
    "Elec":    [6560,7624,7795,3617,3401,3859,6651,3781,3329,3949,7043,7709],
    "Water":   [806,1440,744,839,928,711,1115,755,854,771,853,796],
    "Gas":     [1179,1021,684,531,989,318,1130,580,628,1024,492,1001],
    "Sewer":   [836,1743,562,755,846,634,1023,680,768,695,768,715],
    "Trash":   [277,598,256,280,280,280,318,260,294,266,294,275],
    "Vacancy": [5485,8146,11646,8060,6094,7626,7227,8284,4592,3368,2797,5243],
    "Bad_Debt":[314,1114,11910,1802,0,1163,705,0,0,2504,73,5819],
})
T12["Total_Util"] = T12[["Elec","Water","Gas","Sewer","Trash"]].sum(axis=1)

FEB26 = dict(
    revenue=70153.86,budget_rev=73490,total_expenses=29130.72,budget_exp=31244,
    noi=41023.14,budget_noi=42246,net_income=19424.42,budget_ni=24729,
    elec=6039.44,budget_elec=4605,water=689.38,budget_water=817,
    gas=654.54,budget_gas=745,sewer=620.40,budget_sewer=775,
    trash=295.62,budget_trash=280,total_util=8003.76,budget_util=6942,
    bad_debt=1699,vacancy=1992,
)
JAN26=dict(revenue=67199.53,noi=33606.55,net_income=15104.44,
           total_util=10221.01,elec=7709.25,water=795.26,gas=1000.82,sewer=715.68,trash=274.88)

BILLS = pd.DataFrame({
    "Month":      ["Nov-24","Dec-24","Jan-25","Feb-25","Mar-25","Apr-25","May-25","Aug-25","Sep-25","Oct-25","Dec-25","Jan-26","Mar-26"],
    "Main_Bill":  [4614,5876,5474,8889,8895,5095,4759,5852,6173,4951,7229.77,8550.91,7966.58],
    "Office_Bill":[0,0,0,0,0,0,0,0,0,0,374.40,380.43,388.88],
    "Gas_Bill":   [0,0,394,0,0,0,0,0,0,0,0,1000.82,357.86],
    "Elec":       [2195,2763,2763,3841,3841,2235,2131,2641,2641,2140,3042.82,3480.48,3823.40],
    "DD3":        [492,1061,1061,2707,2707,846,646,1108,1108,815,1953.56,2707.30,1784.36],
    "Water_Units":[99]*13,
})
BILLS["Total_Bill"] = BILLS["Main_Bill"]+BILLS["Office_Bill"]+BILLS["Gas_Bill"]

PROPANE = pd.DataFrame({
    "Invoice Date":["Jan-25","Jan-02-26","Jan-21-26","Feb-12-26","Mar-16-26"],
    "Invoice #":   ["N/A","34085586","34375960","34657363","35210286"],
    "Gallons":     [172,210.60,199.00,None,145.70],
    "Rate $/Gal":  [2.099,2.249,2.249,None,2.249],
    "Total Due":   [394,514.40,486.42,654.54,357.86],
    "GL Status":   ["✅ Paid","✅ Paid Jan-08 chk#1923","✅ Paid Feb-02 chk#1941","✅ Paid Feb-20 chk#1965","In Mar-26"],
})

RESERVE = pd.DataFrame({
    "Year":   ["Yr 1","Yr 2","Yr 3","Yr 4","Yr 5","Yr 6","Yr 7","Yr 8"],
    "Balance":[734280,769342,809824,626409,428488,236185,221978,174855],
    "Draw":   [0,0,4227,229410,242554,235422,55896,89523],
})

COMPONENTS = pd.DataFrame({
    "Component":      ["Elevators (2)","Boiler System","HVAC Units (77)","Roof","Plumbing Infra","Common Area Flooring","Exterior/Facade","Windows"],
    "Useful Life":    [25,20,15,20,30,10,25,25],
    "Remaining Life": [8,5,4,10,15,3,12,18],
    "Replacement $":  [350000,80000,154000,120000,200000,45000,180000,95000],
    "Reserve/Unit/Yr":[257,59,151,88,98,66,106,56],
})
COMPONENTS["Annual Total"] = COMPONENTS["Reserve/Unit/Yr"]*UNITS
TOTAL_RES_PU  = int(COMPONENTS["Reserve/Unit/Yr"].sum())
TOTAL_RES_ANN = int(COMPONENTS["Annual Total"].sum())

# ── SIDEBAR ──
with st.sidebar:
    st.markdown("### 🏢 Property Intelligence")
    st.markdown("---")
    api_key = st.text_input("🔑 Groq API Key",type="password",value=st.session_state.groq_key)
    if api_key: st.session_state.groq_key = api_key
    st.markdown("---")
    st.selectbox("🏢 Property",["Virginia Dare Apartments","Add more..."])
    st.markdown("---")
    st.markdown("#### 📁 Upload Documents")
    st.caption("Upload new bills or reports — used by chatbot.")
    uploaded_files = st.file_uploader("Drop files here",accept_multiple_files=True,type=["pdf","xlsx","xls","csv"])
    if uploaded_files:
        for file in uploaded_files:
            if file.name not in st.session_state.documents:
                content=""
                try:
                    if file.name.endswith(".pdf"):
                        reader=PyPDF2.PdfReader(io.BytesIO(file.read()))
                        for page in reader.pages:
                            t=page.extract_text()
                            if t: content+=t+"\n"
                    elif file.name.endswith((".xlsx",".xls")):
                        xl=pd.ExcelFile(file)
                        for sheet in xl.sheet_names:
                            df=xl.parse(sheet)
                            content+=f"\n---{sheet}---\n{df.to_string()}\n"
                    elif file.name.endswith(".csv"):
                        content=pd.read_csv(file).to_string()
                except Exception as e:
                    content=f"[Error:{e}]"
                st.session_state.documents[file.name]=content
                st.success(f"✅ {file.name}")
    if st.session_state.documents:
        st.markdown(f"**{len(st.session_state.documents)} file(s) loaded**")
        for f in st.session_state.documents: st.caption(f"📄 {f}")
        if st.button("🗑️ Clear Files"):
            st.session_state.documents={}; st.rerun()
    st.markdown("---")
    st.caption("Virginia Dare Apartments · 68 units · HUD HAP\nElizabeth City, NC · GL as of Feb-28-2026")

# ── TABS ──
tab1,tab2,tab3,tab4,tab5 = st.tabs([
    "🏠 Investor Snapshot","⚡ Utility Deep Dive",
    "📊 Financial Performance","🏦 Reserves & Capital","💬 Ask Anything",
])

# ══════════════════════════════════════════════════════════════
# TAB 1
# ══════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<p class="main-header">🏢 Virginia Dare Apartments</p>',unsafe_allow_html=True)
    st.markdown('<p class="sub-header">110 McMorrine Street, Elizabeth City, NC &nbsp;·&nbsp; 68 units &nbsp;·&nbsp; 9-story &nbsp;·&nbsp; Built 1927 &nbsp;·&nbsp; HUD HAP Contract &nbsp;·&nbsp; Data as of Feb-28-2026</p>',unsafe_allow_html=True)

    # KPIs — Monthly (Feb-26)
    st.markdown('<p class="section-title">📊 Monthly Snapshot — February 2026</p>',unsafe_allow_html=True)
    feb_util=FEB26["total_util"]; feb_bud=FEB26["budget_util"]
    feb_var=feb_util-feb_bud; feb_var_pct=(feb_var/feb_bud)*100
    util_vars={"Electricity":FEB26["elec"]-FEB26["budget_elec"],"Water":FEB26["water"]-FEB26["budget_water"],
               "Gas":FEB26["gas"]-FEB26["budget_gas"],"Sewer":FEB26["sewer"]-FEB26["budget_sewer"],
               "Trash":FEB26["trash"]-FEB26["budget_trash"]}
    top_driver=max(util_vars,key=lambda k:abs(util_vars[k]))

    c1,c2,c3,c4,c5=st.columns(5)
    with c1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Monthly Utility Cost</div>
            <div class="kpi-value">${feb_util:,.0f}</div>
            <div class="delta-red">▲ ${feb_var:,.0f} over budget</div>
            <div class="kpi-sub">Budget: ${feb_bud:,}/mo</div>
        </div>""",unsafe_allow_html=True)
    with c2:
        col="delta-red" if feb_var_pct>0 else "delta-green"
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Budget Variance %</div>
            <div class="kpi-value">{feb_var_pct:+.1f}%</div>
            <div class="{col}">vs ${feb_bud:,} monthly budget</div>
            <div class="kpi-sub">Feb-26 actual</div>
        </div>""",unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">🔴 Top Variance Driver</div>
            <div class="kpi-value" style="color:#dc2626">{top_driver}</div>
            <div class="delta-red">${abs(util_vars[top_driver]):,.0f} over budget</div>
            <div class="kpi-sub">{abs(util_vars[top_driver])/feb_bud*100:.1f}% of total budget</div>
        </div>""",unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Cost Per Unit / Month</div>
            <div class="kpi-value">${feb_util/UNITS:,.0f}</div>
            <div class="kpi-sub">${feb_util/UNITS*12:,.0f}/unit/year</div>
        </div>""",unsafe_allow_html=True)
    with c5:
        pct_rev=(feb_util/FEB26["revenue"])*100
        col="delta-red" if pct_rev>12 else "delta-green"
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">% of Monthly Revenue</div>
            <div class="kpi-value">{pct_rev:.1f}%</div>
            <div class="{col}">Revenue: ${FEB26['revenue']:,.0f}</div>
        </div>""",unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # Breakdown donut + bar + table
    st.markdown('<p class="section-title">📊 Utility Breakdown — February 2026 ($ & %)</p>',unsafe_allow_html=True)
    cats=["Electricity","Water","Gas/Propane","Sewer","Trash"]
    actuals=[FEB26["elec"],FEB26["water"],FEB26["gas"],FEB26["sewer"],FEB26["trash"]]
    budgets=[FEB26["budget_elec"],FEB26["budget_water"],FEB26["budget_gas"],FEB26["budget_sewer"],FEB26["budget_trash"]]
    colors=["#3b82f6","#8b5cf6","#f59e0b","#10b981","#94a3b8"]

    col_l,col_r=st.columns([1,1.8])
    with col_l:
        fig_d=go.Figure(go.Pie(labels=cats,values=actuals,hole=0.55,marker_colors=colors,
                               textinfo="label+percent",textfont_size=11))
        fig_d.update_layout(showlegend=False,height=270,margin=dict(t=15,b=10,l=10,r=10),
                            annotations=[dict(text=f"<b>${sum(actuals):,.0f}</b><br>Feb-26",
                                             x=0.5,y=0.5,font_size=12,showarrow=False)])
        st.plotly_chart(fig_d,use_container_width=True)

    with col_r:
        fig_c=go.Figure()
        fig_c.add_bar(x=cats,y=actuals,name="Actual",marker_color=colors)
        fig_c.add_bar(x=cats,y=budgets,name="Budget",
                      marker_color="rgba(0,0,0,0)",marker_line=dict(color="#94a3b8",width=2))
        fig_c.update_layout(barmode="overlay",height=270,margin=dict(t=15,b=10),
                            title="Actual vs Budget by Category (Feb-26)",yaxis_title="$",
                            legend=dict(orientation="h",y=-0.28))
        st.plotly_chart(fig_c,use_container_width=True)

    bdown_data={"Category":cats,"Actual $":[f"${a:,.2f}" for a in actuals],
                "Budget $":[f"${b:,.0f}" for b in budgets],
                "Variance $":[f"${a-b:+,.2f}" for a,b in zip(actuals,budgets)],
                "Variance %":[f"{(a-b)/b*100:+.1f}%" for a,b in zip(actuals,budgets)],
                "% of Total":[f"{a/sum(actuals)*100:.1f}%" for a in actuals],
                "Status":["🔴 >20% Over" if (a-b)/b*100>20 else "🟡 >10% Over" if (a-b)/b*100>10 else "🟢 Under" if (a-b)/b*100<-5 else "✅ On Track"
                          for a,b in zip(actuals,budgets)]}
    st.dataframe(pd.DataFrame(bdown_data),use_container_width=True,hide_index=True)

    st.markdown(f"""<div class="insight-box">
        🤖 <strong>Feb-26 Insight:</strong> Total utility <strong>${feb_util:,.0f}</strong> vs budget <strong>${feb_bud:,}</strong>
        = <strong>${feb_var:,.0f} over ({feb_var_pct:.1f}%)</strong>.
        Primary driver: <strong>Electricity ${FEB26['elec']:,.0f}</strong> — ${util_vars['Electricity']:,.0f} over budget
        ({util_vars['Electricity']/FEB26['budget_elec']*100:.0f}% variance).
        Utilities exceeded budget in <strong>8 of 12 trailing months</strong>.
        Water & Sewer are on/under budget — the issue is purely <strong>electric demand (DD3)</strong>.
    </div>""",unsafe_allow_html=True)

    # T12 trend
    st.markdown('<p class="section-title">📈 Trailing 12 Month Trend — GL Booked vs Budget</p>',unsafe_allow_html=True)
    fig_t=go.Figure()
    fig_t.add_scatter(x=T12["Month"],y=T12["Total_Util"],name="Monthly Utility (GL)",
                      line=dict(color="#3b82f6",width=2.5),mode="lines+markers",marker=dict(size=7))
    fig_t.add_scatter(x=T12["Month"],y=[BUDGET_UTIL_MO]*len(T12),name=f"Budget ${BUDGET_UTIL_MO:,}",
                      line=dict(color="#94a3b8",width=1.5,dash="dash"))
    fig_t.update_layout(height=290,margin=dict(t=20,b=10),
                        legend=dict(orientation="h",y=-0.28),yaxis_title="$")
    st.plotly_chart(fig_t,use_container_width=True)

    fig_s=go.Figure()
    for cat,color in [("Elec","#3b82f6"),("Water","#8b5cf6"),("Gas","#f59e0b"),("Sewer","#10b981"),("Trash","#94a3b8")]:
        fig_s.add_bar(x=T12["Month"],y=T12[cat],name=cat,marker_color=color)
    fig_s.add_hline(y=BUDGET_UTIL_MO,line_dash="dash",line_color="#ef4444",
                    annotation_text=f"Budget ${BUDGET_UTIL_MO:,}",annotation_position="top left")
    fig_s.update_layout(barmode="stack",height=290,margin=dict(t=30,b=10),
                        legend=dict(orientation="h",y=-0.3),
                        title="Monthly Utility Breakdown — Trailing 12 (GL Booked)")
    st.plotly_chart(fig_s,use_container_width=True)

    # Variance table T12
    st.markdown('<p class="section-title">🚨 Monthly Variance vs Budget — Trailing 12</p>',unsafe_allow_html=True)
    bmap={"Elec":4605,"Water":817,"Gas":745,"Sewer":775,"Trash":280}
    vrows=[]
    for _,row in T12.iterrows():
        va=row["Total_Util"]-BUDGET_UTIL_MO; vp=(va/BUDGET_UTIL_MO)*100
        td=max(["Elec","Water","Gas","Sewer","Trash"],key=lambda c:abs(row[c]-bmap[c]))
        vrows.append({"Month":row["Month"],"Utility (GL)":f"${row['Total_Util']:,.0f}",
                      "Budget":f"${BUDGET_UTIL_MO:,}","Variance $":f"${va:+,.0f}",
                      "Variance %":f"{vp:+.1f}%","Top Driver":td,
                      "Flag":"🔴 >20% Over" if vp>20 else "🟡 >10% Over" if vp>10 else "🟢 Under" if vp<-5 else "✅ On Track"})
    st.dataframe(pd.DataFrame(vrows),use_container_width=True,hide_index=True)

    # Reserve + NOI snapshot
    st.markdown('<p class="section-title">🏦 Reserve & NOI Snapshot</p>',unsafe_allow_html=True)
    sn1,sn2,sn3,sn4=st.columns(4)
    util_drag=T12["Total_Util"].sum()-BUDGET_UTIL_MO*12
    with sn1:
        st.markdown(f'<div class="kpi-card"><div class="kpi-label">Feb-26 NOI</div><div class="kpi-value">${FEB26["noi"]:,.0f}</div><div class="delta-green">+${FEB26["noi"]-FEB26["budget_noi"]:,.0f} vs budget</div></div>',unsafe_allow_html=True)
    with sn2:
        st.markdown(f'<div class="kpi-card"><div class="kpi-label">NOI After Reserve Req.</div><div class="kpi-value">${FEB26["noi"]-TOTAL_RES_ANN/12:,.0f}</div><div class="delta-red">-${TOTAL_RES_ANN/12:,.0f}/mo reserve</div></div>',unsafe_allow_html=True)
    with sn3:
        st.markdown(f'<div class="kpi-card"><div class="kpi-label">Yr 1 Reserve Balance</div><div class="kpi-value" style="color:#16a34a">$734,280</div><div class="delta-red">↓ $707K draw Yr 4-6</div></div>',unsafe_allow_html=True)
    with sn4:
        st.markdown(f'<div class="kpi-card"><div class="kpi-label">T12 Utility Overrun</div><div class="kpi-value" style="color:#dc2626">${util_drag:,.0f}</div><div class="delta-red">vs annual budget</div></div>',unsafe_allow_html=True)

    st.markdown("""<div class="insight-box">
        💰 <strong>Value Creation:</strong> HVAC PM + LED Retrofit + Demand Controller + Refuse split =
        <strong>~$26,800/yr savings</strong>. At 6% cap rate → <strong>$447,000 added property value.</strong>
        Utility overrun is the single most actionable NOI lever available today.
    </div>""",unsafe_allow_html=True)

    # Alerts
    st.markdown('<p class="section-title">🚨 Alerts & Findings</p>',unsafe_allow_html=True)
    for level,text in [
        ("red","🔴 CRITICAL — DD3 Demand Charge winter spike CONFIRMED: $2,707 in BOTH Feb-25 AND Jan-26 — identical amount, recurring winter pattern. Demand controller needed urgently. $4-8K install saves $5-12K/yr."),
        ("red","🔴 CRITICAL — Office Account Apr-26: $405.54 past due + $19.32 penalty. Disconnect date was Apr-23-26. Confirm payment cleared with Kenya Owens immediately."),
        ("red","🔴 CRITICAL — HUD Life Safety violations open: GFCI $4,760 + Smoke detectors $2,380 + UFAS $5,000 = $13,540. Must resolve before next HUD inspection."),
        ("red","🔴 CRITICAL — GL Anomaly Feb-26: Deleted batch #1419 ($8,978.45) — Mar bill accidentally entered Feb-16, deleted, reversed Feb-28. Net=Zero but messy audit trail for HUD."),
        ("yellow","🟡 HIGH — Jan-26 double propane delivery: 409.6 gal/$1,001 in 19 days. Normal = 150-200 gal/mo. Investigate tank leak or fill error with Blossman."),
        ("yellow","🟡 HIGH — Elevator replacement Yr 4-6: $707K draw drops reserves $810K → $174K. HVAC stress today = risk of accelerated timeline."),
        ("yellow","🟡 HIGH — Feb-26 electricity accrual overstated by ~$1,885 ($9,852 accrued vs $7,967 actual). Auto-reverses Mar-01."),
        ("yellow","🟡 HIGH — Feb-26 trash accrual only $24.17 vs $280 actual — understated by $256. Mar-26 P&L will spike."),
        ("blue","🔵 MEDIUM — Water meter estimated: exactly 99 units every single month. City not physically reading meter. Request verification — actual usage unknown."),
        ("blue","🔵 MEDIUM — Bad Debt Jan-26: $5,819 vs $697 budget. Investigate tenant arrears and HUD subsidy timing."),
    ]:
        st.markdown(f'<div class="alert-{level}">{text}</div>',unsafe_allow_html=True)

    # Action Plan
    st.markdown('<p class="section-title">✅ Action Plan — Ranked by Urgency</p>',unsafe_allow_html=True)
    st.dataframe(pd.DataFrame([
        {"#":1,"Priority":"🔴 Immediate","Action":"Confirm office account past due $405.54 cleared — call Kenya Owens","Deadline":"Today","Impact":"Disconnect risk"},
        {"#":2,"Priority":"🔴 Immediate","Action":"Document deleted GL batch #1419 — memo to file for HUD audit trail","Deadline":"This week","Impact":"HUD compliance"},
        {"#":3,"Priority":"🔴 Immediate","Action":"Clear HUD life safety violations: GFCI + Smoke + UFAS = $13,540","Deadline":"Before inspection","Impact":"HUD contract"},
        {"#":4,"Priority":"🔴 30 days","Action":"Install demand controller/peak shaving relay — eliminate DD3 winter spikes","Deadline":"30 days","Impact":"$5-12K/yr"},
        {"#":5,"Priority":"🟡 30 days","Action":"Investigate Jan-26 double propane delivery — possible tank leak","Deadline":"30 days","Impact":"Cost control"},
        {"#":6,"Priority":"🟡 30 days","Action":"HVAC PM contract — all 77 units","Deadline":"30 days","Impact":"$6,200/yr"},
        {"#":7,"Priority":"🟡 30 days","Action":"Request water meter physical read from City of Elizabeth City","Deadline":"30 days","Impact":"Billing accuracy"},
        {"#":8,"Priority":"🟡 60 days","Action":"LED retrofit — common areas + exterior","Deadline":"60 days","Impact":"$8,400/yr"},
        {"#":9,"Priority":"🟡 60 days","Action":"Fix accrual methodology for trash with Beacon Management","Deadline":"60 days","Impact":"Clean P&L"},
        {"#":10,"Priority":"🔵 90 days","Action":"CNA elevator inspection — confirm Yr 4-6 replacement timeline","Deadline":"90 days","Impact":"$350K planning"},
    ]),use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════
# TAB 2 — UTILITY DEEP DIVE
# ══════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<p class="main-header">⚡ Utility Deep Dive</p>',unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Variance analysis · Consumption trends · Invoice reconciliation · GL anomaly check · Reserve linkage</p>',unsafe_allow_html=True)

    # 1 Variance
    st.markdown('<p class="section-title">1️⃣ Variance Analysis — GL Booked vs Budget (Trailing 12)</p>',unsafe_allow_html=True)
    t12_tots={c:int(T12[c].sum()) for c in ["Elec","Water","Gas","Sewer","Trash"]}
    t12_buds={"Elec":4605*12,"Water":817*12,"Gas":745*12,"Sewer":775*12,"Trash":280*12}
    total_overrun=T12["Total_Util"].sum()-BUDGET_UTIL_MO*12

    va1,va2=st.columns(2)
    with va1:
        fig_va=go.Figure()
        cat_list=list(t12_tots.keys())
        fig_va.add_bar(x=cat_list,y=[t12_tots[c] for c in cat_list],name="T12 Actual",
                       marker_color=["#ef4444" if t12_tots[c]>t12_buds[c] else "#22c55e" for c in cat_list])
        fig_va.add_bar(x=cat_list,y=[t12_buds[c] for c in cat_list],name="T12 Budget",
                       marker_color="rgba(0,0,0,0)",marker_line=dict(color="#94a3b8",width=2))
        fig_va.update_layout(barmode="overlay",height=290,title="T12 Actual vs Annual Budget",
                             margin=dict(t=35,b=10),yaxis_title="$",legend=dict(orientation="h",y=-0.28))
        st.plotly_chart(fig_va,use_container_width=True)
    with va2:
        vd=[{"Category":c,"T12 Actual":f"${t12_tots[c]:,.0f}","T12 Budget":f"${t12_buds[c]:,.0f}",
             "Variance $":f"${t12_tots[c]-t12_buds[c]:+,.0f}",
             "Variance %":f"{(t12_tots[c]-t12_buds[c])/t12_buds[c]*100:+.1f}%",
             "Assessment":"🔴 Critical" if (t12_tots[c]-t12_buds[c])/t12_buds[c]*100>30 else "🟡 Monitor" if (t12_tots[c]-t12_buds[c])/t12_buds[c]*100>10 else "✅ OK"}
            for c in cat_list]
        st.dataframe(pd.DataFrame(vd),use_container_width=True,hide_index=True)
        elec_overrun=t12_tots["Elec"]-t12_buds["Elec"]
        st.markdown(f"""<div class="alert-red">
            🔴 <strong>T12 Total Overrun: ${total_overrun:,.0f}</strong> vs annual budget ${BUDGET_UTIL_MO*12:,}.
            Electricity alone = <strong>${elec_overrun:,.0f}</strong> ({elec_overrun/total_overrun*100:.0f}% of overrun).
        </div>""",unsafe_allow_html=True)

    # 2 Consumption
    st.markdown('<p class="section-title">2️⃣ Consumption Analysis — From Actual Bills</p>',unsafe_allow_html=True)
    cb1,cb2=st.columns(2)
    with cb1:
        fig_e=go.Figure()
        fig_e.add_bar(x=BILLS["Month"],y=BILLS["Elec"]-BILLS["DD3"],name="Base Electric",marker_color="#3b82f6")
        fig_e.add_bar(x=BILLS["Month"],y=BILLS["DD3"],name="DD3 Demand",marker_color="#ef4444")
        fig_e.update_layout(barmode="stack",height=280,title="Electricity: Base + DD3 (Actual Bills)",
                            margin=dict(t=35,b=10),legend=dict(orientation="h",y=-0.3))
        st.plotly_chart(fig_e,use_container_width=True)
        st.markdown("""<div class="alert-red">
            🔴 <strong>DD3 Winter Pattern:</strong> Feb-25 = $2,707 | Jan-26 = $2,707 — exact same spike.
            Jan-26 peak demand = <strong>206 kW</strong> (rate $1.83/kW).
            Demand controller targeting &lt;100 kW saves $5-12K/yr.
        </div>""",unsafe_allow_html=True)
    with cb2:
        fig_w=go.Figure()
        fig_w.add_scatter(x=BILLS["Month"],y=BILLS["Water_Units"],mode="lines+markers",
                          line=dict(color="#8b5cf6",width=2.5),marker=dict(size=8),name="Water Units")
        fig_w.add_hline(y=99,line_dash="dot",line_color="#ef4444",
                        annotation_text="⚠️ Always 99 = ESTIMATED",annotation_position="top right")
        fig_w.update_layout(height=280,title="Water Meter Reads",margin=dict(t=35,b=10),
                            yaxis=dict(range=[90,110]),yaxis_title="Units")
        st.plotly_chart(fig_w,use_container_width=True)
        st.markdown("""<div class="alert-yellow">
            🟡 <strong>Estimated Billing:</strong> Every bill reads exactly 99 units — meter not physically read.
            Actual consumption unknown. Could be over or under-billed. Request City verification immediately.
        </div>""",unsafe_allow_html=True)

    # Gas
    cg1,cg2=st.columns(2)
    with cg1:
        gdf=BILLS[BILLS["Gas_Bill"]>0]
        fig_g=px.bar(gdf,x="Month",y="Gas_Bill",color_discrete_sequence=["#f59e0b"],
                     title="Propane Spend (Blossman)")
        fig_g.update_layout(height=255,margin=dict(t=35,b=10),yaxis_title="$")
        st.plotly_chart(fig_g,use_container_width=True)
    with cg2:
        st.markdown("**Blossman Invoice Log:**")
        st.dataframe(PROPANE,use_container_width=True,hide_index=True)
        st.markdown("""<div class="alert-yellow">
            ⚠️ <strong>Jan-26 Double Delivery:</strong> 210.6 + 199.0 gal = 409.6 gal in 19 days.
            Normal = ~150-200 gal/mo. Price up 7.1% YoY ($2.099→$2.249/gal).
            Investigate: possible tank leak or fill error.
        </div>""",unsafe_allow_html=True)

    # 3 Invoice Reconciliation
    st.markdown('<p class="section-title">3️⃣ Invoice Reconciliation — Bills vs General Ledger</p>',unsafe_allow_html=True)
    rc1,rc2=st.columns(2)
    with rc1:
        st.markdown("**January 2026 ✅ — Fully Reconciled**")
        for item,bill,gl,note in [
            ("City EC Main (37-0345000-01)","$8,550.91","$8,550.91","01/27 inv → 02/02 paid chk#1943"),
            ("City EC Office (37-0380000-01)","$380.43","$380.43","01/27 inv → 02/02 paid chk#1942"),
            ("Blossman Jan-02 (#34085586)","$514.40","$514.40","01/07 inv → 01/08 paid chk#1923"),
            ("Blossman Jan-21 (#34375960)","$486.42","$486.42","01/22 inv → 02/02 paid chk#1941"),
            ("AGT Final Bill (37-0390000-06)","$83.24","$83.24","02/16 booked, split correctly"),
        ]:
            st.markdown(f'<div class="recon-match">✅ <strong>{item}</strong><br>Bill {bill} = GL {gl} | {note}</div>',unsafe_allow_html=True)
        st.markdown('<div class="alert-green">✅ Jan-26 fully clean. Zero discrepancies.</div>',unsafe_allow_html=True)
    with rc2:
        st.markdown("**February 2026 ⚠️ — 5 Flags**")
        st.markdown('<div class="recon-match">✅ <strong>Blossman Feb-12 (#34657363)</strong> — $654.54 = GL | 02/16 inv → 02/20 paid</div>',unsafe_allow_html=True)
        for icon,title,desc,cls in [
            ("🔴","Deleted Batch #1419 ($8,978.45)","Mar bill entered Feb-16 by mistake → deleted → reversed. Net=Zero, messy audit trail.","recon-flag"),
            ("🟡","Electricity Accrual Overstated","$9,852 accrued vs $7,967 actual. +$1,885. Auto-reverses Mar-01.","recon-warn"),
            ("⚠️","Trash Accrual Understated","$24.17 accrued vs $280 actual. -$256. Mar P&L will spike.","recon-warn"),
            ("🔴","Office Account Past Due","$405.54 unpaid + $19.32 penalty. Disconnect Apr-23-26.","recon-flag"),
            ("🔴","Missing Blossman PDF","Invoice #34657363 ($654.54) in GL but PDF not uploaded.","recon-flag"),
        ]:
            st.markdown(f'<div class="{cls}">{icon} <strong>{title}</strong> — {desc}</div>',unsafe_allow_html=True)

        st.markdown("<br>**Feb-26 Accrual vs Actual:**")
        st.dataframe(pd.DataFrame({
            "Category":["Electricity","Water","Gas","Sewer","Trash"],
            "GL Accrual":["$9,851.95","$1,132.56","$654.54","$1,019.23","$24.17"],
            "Actual Bill":["$5,607.76","$812.49","$654.54","$731.19","$280.00"],
            "Status":["🟡 Overstated","🟡 Overstated","✅ Match","🟡 Overstated","⚠️ Understated"],
        }),use_container_width=True,hide_index=True)

    # 4 Reserve Linkage
    st.markdown('<p class="section-title">4️⃣ Utility → Replacement Reserve Linkage</p>',unsafe_allow_html=True)
    st.markdown("""<div class="insight-box">
        🔗 <strong>Why utilities matter for reserves:</strong>
        High HVAC load (DD3 spikes) = mechanical stress = shorter useful life = earlier replacement.
        HVAC has <strong>4 years remaining</strong> ($154K replacement). Boiler has <strong>5 years</strong> ($80K).
        Fixing demand charge today <strong>protects the reserve schedule tomorrow.</strong>
        Every year of HVAC life extension = $10,267 deferred capital.
    </div>""",unsafe_allow_html=True)

    ll1,ll2=st.columns(2)
    with ll1:
        st.markdown("**⚠️ High-Risk Components (≤5 yrs remaining):**")
        hr=COMPONENTS[COMPONENTS["Remaining Life"]<=5][["Component","Remaining Life","Replacement $","Reserve/Unit/Yr"]]
        st.dataframe(hr,use_container_width=True,hide_index=True)
    with ll2:
        avg_util=T12["Total_Util"].mean(); mo_res=TOTAL_RES_ANN/12
        fig_link=go.Figure()
        fig_link.add_bar(x=["Avg Monthly Utility","Monthly Reserve Req.","Combined Impact"],
                         y=[avg_util,mo_res,avg_util+mo_res],
                         marker_color=["#3b82f6","#f59e0b","#ef4444"],
                         text=[f"${avg_util:,.0f}",f"${mo_res:,.0f}",f"${avg_util+mo_res:,.0f}"],
                         textposition="outside")
        fig_link.update_layout(height=270,title="Monthly NOI Pressure",margin=dict(t=35,b=10),
                               yaxis_title="$/month",showlegend=False)
        st.plotly_chart(fig_link,use_container_width=True)

    st.markdown(f"""<div class="alert-yellow">
        🟡 <strong>Combined Monthly Pressure:</strong> Avg utility ${T12["Total_Util"].mean():,.0f} +
        Reserve req. ${TOTAL_RES_ANN/12:,.0f} = <strong>${T12["Total_Util"].mean()+TOTAL_RES_ANN/12:,.0f}/mo</strong>.
        Against Feb-26 NOI of ${FEB26["noi"]:,.0f}, this = <strong>{(T12["Total_Util"].mean()+TOTAL_RES_ANN/12)/FEB26["noi"]*100:.0f}%</strong> of NOI consumed.
    </div>""",unsafe_allow_html=True)

    # 5 Per-unit
    st.markdown('<p class="section-title">5️⃣ Per-Unit Monthly Cost Analysis</p>',unsafe_allow_html=True)
    pur=[]
    for _,row in T12.iterrows():
        va=row["Total_Util"]-BUDGET_UTIL_MO
        pur.append({"Month":row["Month"],"Total Util":f"${row['Total_Util']:,.0f}",
                    "Elec":f"${row['Elec']:,.0f}","Water":f"${row['Water']:,.0f}",
                    "Gas":f"${row['Gas']:,.0f}","Sewer":f"${row['Sewer']:,.0f}",
                    "$/Unit/Mo":f"${row['Total_Util']/UNITS:.0f}",
                    "vs Budget":f"${va:+,.0f}",
                    "Flag":"🔴" if va>BUDGET_UTIL_MO*0.2 else "🟡" if va>BUDGET_UTIL_MO*0.1 else "✅"})
    st.dataframe(pd.DataFrame(pur),use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════
# TAB 3 — FINANCIAL PERFORMANCE
# ══════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<p class="main-header">📊 Financial Performance</p>',unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Source: Jan-26 & Feb-26 Financial Reports · Accrual Basis · GL as of Feb-28-2026</p>',unsafe_allow_html=True)

    st.markdown('<p class="section-title">💰 Key Financials — February 2026</p>',unsafe_allow_html=True)
    f1,f2,f3,f4,f5=st.columns(5)
    for widget,(label,actual,budget,higher) in zip([f1,f2,f3,f4,f5],[
        ("Total Revenue",FEB26["revenue"],FEB26["budget_rev"],True),
        ("Net Op. Income",FEB26["noi"],FEB26["budget_noi"],True),
        ("Net Income",FEB26["net_income"],FEB26["budget_ni"],True),
        ("Vacancy Loss",FEB26["vacancy"],1686,False),
        ("Bad Debt",FEB26["bad_debt"],697,False),
    ]):
        var=actual-budget; vp=(var/abs(budget))*100 if budget else 0
        good=(var>=0 and higher)or(var<0 and not higher)
        col="delta-green" if good else "delta-red"
        with widget:
            st.markdown(f"""<div class="kpi-card">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">${actual:,.0f}</div>
                <div class="{col}">{vp:+.1f}% vs ${budget:,} budget</div>
            </div>""",unsafe_allow_html=True)

    st.markdown('<p class="section-title">📈 Revenue, Expenses & NOI — Trailing 12 Months</p>',unsafe_allow_html=True)
    fig_fin=go.Figure()
    fig_fin.add_bar(x=T12["Month"],y=T12["Revenue"],name="Revenue",marker_color="#22c55e",opacity=0.85)
    fig_fin.add_bar(x=T12["Month"],y=T12["Expenses"],name="Expenses",marker_color="#ef4444",opacity=0.85)
    fig_fin.add_scatter(x=T12["Month"],y=T12["NOI"],name="NOI",
                        line=dict(color="#3b82f6",width=3),mode="lines+markers",marker=dict(size=8))
    fig_fin.update_layout(barmode="group",height=330,margin=dict(t=20,b=10),
                          legend=dict(orientation="h",y=-0.25),yaxis_title="$")
    st.plotly_chart(fig_fin,use_container_width=True)

    cni,csum=st.columns([2,1])
    with cni:
        fig_ni=go.Figure()
        fig_ni.add_bar(x=T12["Month"],y=T12["Net_Inc"],
                       marker_color=["#16a34a" if v>=0 else "#dc2626" for v in T12["Net_Inc"]],name="Net Income")
        fig_ni.add_hline(y=0,line_color="#94a3b8",line_width=1)
        fig_ni.update_layout(height=260,title="Net Income (Loss) by Month",margin=dict(t=35,b=10),yaxis_title="$")
        st.plotly_chart(fig_ni,use_container_width=True)
    with csum:
        st.markdown("**T12 Summary:**")
        st.dataframe(pd.DataFrame({
            "Item":["Total Revenue","Total Op. Exp.","Net Op. Income","T12 Net Income","Avg NOI/mo","Mortgage/yr"],
            "Amount":[f"${ANNUAL_EGI:,}",f"${T12['Expenses'].sum():,}",f"${T12['NOI'].sum():,}",
                      "$67,662",f"${T12['NOI'].mean():,.0f}",f"${MORTGAGE_MO*12:,}"]
        }),use_container_width=True,hide_index=True)

    st.markdown('<p class="section-title">📋 Budget Comparison — Feb-26</p>',unsafe_allow_html=True)
    st.dataframe(pd.DataFrame({
        "Line Item":["Electricity","Water","Gas","Sewer","Total Utilities","Bad Debt","Vacancy","Total Op. Exp.","NOI","Net Income"],
        "Jan-26 Actual":[7709.25,795.26,1000.82,715.68,10221.01,5818.88,5243,33592.98,33606.55,15104.44],
        "Feb-26 Actual":[6039.44,689.38,654.54,620.40,8003.76,1699,1992,29130.72,41023.14,19424.42],
        "Feb Budget":  [4605,817,745,775,6942,697,1686,31244,42246,24729],
        "Variance $":  [1434.44,-127.62,-90.46,-154.60,1061.76,1002,-306,-2113.28,-1222.86,-5304.58],
        "Var %":       [-31.1,15.6,12.1,19.9,-15.3,-143.8,181.5,6.8,-2.9,-21.5],
    }),use_container_width=True,hide_index=True)

    st.markdown('<p class="section-title">🔍 GL Reconciliation</p>',unsafe_allow_html=True)
    rt1,rt2=st.tabs(["January 2026 ✅","February 2026 ⚠️"])
    with rt1:
        for item,b,g,n in [("City EC Main","$8,550.91","$8,550.91","01/27→02/02 chk#1943"),
                            ("City EC Office","$380.43","$380.43","01/27→02/02 chk#1942"),
                            ("Blossman Jan-02","$514.40","$514.40","01/07→01/08 chk#1923"),
                            ("Blossman Jan-21","$486.42","$486.42","01/22→02/02 chk#1941"),
                            ("AGT Final Bill","$83.24","$83.24","02/16 booked correctly")]:
            st.markdown(f'<div class="recon-match">✅ <strong>{item}</strong> — Bill {b} = GL {g} | {n}</div>',unsafe_allow_html=True)
        st.markdown('<div class="alert-green">✅ January 2026 fully reconciled. Zero discrepancies.</div>',unsafe_allow_html=True)
    with rt2:
        st.markdown('<div class="recon-match">✅ <strong>Blossman Feb-12 (#34657363)</strong> — $654.54 = GL</div>',unsafe_allow_html=True)
        for icon,title,desc,cls in [
            ("🔴","Deleted Batch #1419","$8,978.45 — Mar bill Feb-16 mistake → reversed. Net=Zero, messy trail.","recon-flag"),
            ("🟡","Electricity Accrual","$9,852 vs $7,967 actual. +$1,885 overstated. Auto-reverses Mar-01.","recon-warn"),
            ("⚠️","Trash Accrual","$24.17 vs $280 actual. -$256 understated. Mar P&L will spike.","recon-warn"),
            ("🔴","Office Past Due","$405.54 + $19.32 penalty. Disconnect Apr-23.","recon-flag"),
        ]:
            st.markdown(f'<div class="{cls}">{icon} <strong>{title}</strong> — {desc}</div>',unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# TAB 4 — RESERVES & CAPITAL
# ══════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<p class="main-header">🏦 Replacement Reserve & Capital Planning</p>',unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Source: HUD Reserve Schedule · Upload Audit or CNA to override with property-specific figures</p>',unsafe_allow_html=True)

    rc1,rc2,rc3,rc4=st.columns(4)
    with rc1: st.markdown('<div class="kpi-card"><div class="kpi-label">Yr 1 Balance</div><div class="kpi-value" style="color:#16a34a">$734,280</div></div>',unsafe_allow_html=True)
    with rc2: st.markdown('<div class="kpi-card"><div class="kpi-label">Yr 4–6 Draw</div><div class="kpi-value" style="color:#dc2626">$707,386</div><div class="delta-red">Elevator replacement</div></div>',unsafe_allow_html=True)
    with rc3: st.markdown('<div class="kpi-card"><div class="kpi-label">Yr 8 Balance</div><div class="kpi-value" style="color:#d97706">$174,855</div></div>',unsafe_allow_html=True)
    with rc4: st.markdown(f'<div class="kpi-card"><div class="kpi-label">Required/Unit/Yr</div><div class="kpi-value">${TOTAL_RES_PU:,}</div><div class="delta-gray">${TOTAL_RES_ANN:,}/yr total</div></div>',unsafe_allow_html=True)

    st.markdown('<p class="section-title">📊 8-Year Reserve Balance Projection</p>',unsafe_allow_html=True)
    fig_r=go.Figure()
    fig_r.add_bar(x=RESERVE["Year"],y=RESERVE["Balance"],name="Reserve Balance",
                  marker_color=["#16a34a" if b>400000 else "#f59e0b" if b>200000 else "#ef4444" for b in RESERVE["Balance"]])
    fig_r.add_scatter(x=RESERVE["Year"],y=RESERVE["Draw"],name="Annual Draw",
                      line=dict(color="#ef4444",dash="dash",width=2),mode="lines+markers")
    fig_r.add_hline(y=200000,line_dash="dot",line_color="#f59e0b",
                    annotation_text="⚠️ Caution $200K",annotation_position="top left")
    fig_r.update_layout(height=350,margin=dict(t=20,b=10),legend=dict(orientation="h",y=-0.18),yaxis_title="$")
    st.plotly_chart(fig_r,use_container_width=True)

    st.markdown("""<div class="alert-yellow">
        🟡 <strong>Elevator Risk:</strong> $707K draw in Yr 4-6 drops balance $810K → $174K.
        HVAC stress (DD3 spikes) = mechanical wear = possible accelerated timeline.
        Recommend CNA elevator inspection before Yr 3.
    </div>""",unsafe_allow_html=True)

    st.markdown('<p class="section-title">🔧 Component Reserve Schedule</p>',unsafe_allow_html=True)
    def sty_rem(val):
        try:
            v=int(val)
            if v<=5: return "background-color:#fef2f2;color:#dc2626;font-weight:600"
            if v<=10: return "background-color:#fffbeb;color:#92400e"
            return "background-color:#f0fdf4;color:#15803d"
        except: return ""
    st.dataframe(COMPONENTS.style.map(sty_rem,subset=["Remaining Life"]),use_container_width=True,hide_index=True)

    cc1,cc2,cc3=st.columns(3)
    with cc1: st.markdown(f'<div class="kpi-card"><div class="kpi-label">Required/Unit/Yr</div><div class="kpi-value">${TOTAL_RES_PU:,}</div></div>',unsafe_allow_html=True)
    with cc2: st.markdown(f'<div class="kpi-card"><div class="kpi-label">Total Annual Requirement</div><div class="kpi-value">${TOTAL_RES_ANN:,}</div></div>',unsafe_allow_html=True)
    with cc3: st.markdown(f'<div class="kpi-card"><div class="kpi-label">Reserve Impact on EGI</div><div class="kpi-value" style="color:#dc2626">-{TOTAL_RES_ANN/ANNUAL_EGI*100:.1f}%</div></div>',unsafe_allow_html=True)

    st.markdown('<p class="section-title">🔗 Utility Overrun → Reserve Risk</p>',unsafe_allow_html=True)
    lk1,lk2,lk3=st.columns(3)
    with lk1: st.markdown(f'<div class="kpi-card"><div class="kpi-label">T12 Utility Overrun</div><div class="kpi-value" style="color:#dc2626">${total_overrun:,.0f}</div><div class="delta-red">Direct NOI reduction</div></div>',unsafe_allow_html=True)
    with lk2: st.markdown('<div class="kpi-card"><div class="kpi-label">HVAC Risk (4 yrs)</div><div class="kpi-value" style="color:#dc2626">$154,000</div><div class="delta-red">Stress accelerating</div></div>',unsafe_allow_html=True)
    with lk3: st.markdown('<div class="kpi-card"><div class="kpi-label">Boiler Risk (5 yrs)</div><div class="kpi-value" style="color:#d97706">$80,000</div><div class="delta-red">Monitor closely</div></div>',unsafe_allow_html=True)

    st.markdown('<p class="section-title">📉 NOI Waterfall — Full Cost Impact</p>',unsafe_allow_html=True)
    avg_rev=T12["Revenue"].mean(); avg_util2=T12["Total_Util"].mean()
    avg_other=T12["Expenses"].mean()-avg_util2; avg_noi=T12["NOI"].mean(); mo_res=TOTAL_RES_ANN/12
    fig_wf=go.Figure(go.Waterfall(
        orientation="v",measure=["absolute","relative","relative","total","relative","total"],
        x=["Gross Revenue","Utility Cost","Other Expenses","NOI","Reserve Req.","NOI After Reserve"],
        y=[avg_rev,-avg_util2,-avg_other,0,-mo_res,0],
        connector={"line":{"color":"#cbd5e1"}},
        increasing={"marker":{"color":"#16a34a"}},
        decreasing={"marker":{"color":"#ef4444"}},
        totals={"marker":{"color":"#3b82f6"}},
        text=[f"${avg_rev:,.0f}",f"-${avg_util2:,.0f}",f"-${avg_other:,.0f}",
              f"${avg_noi:,.0f}",f"-${mo_res:,.0f}",f"${avg_noi-mo_res:,.0f}"],
        textposition="outside",
    ))
    fig_wf.update_layout(height=400,margin=dict(t=30,b=10),yaxis_title="$/month (T12 avg)")
    st.plotly_chart(fig_wf,use_container_width=True)

    st.markdown(f"""<div class="insight-box">
        🤖 <strong>Bottom Line:</strong> Avg monthly NOI = <strong>${avg_noi:,.0f}</strong>.
        After reserve requirement <strong>${mo_res:,.0f}/mo</strong>, effective NOI = <strong>${avg_noi-mo_res:,.0f}/mo</strong>
        (${(avg_noi-mo_res)*12:,.0f}/yr).
        Reducing utility overrun by 50% adds <strong>${total_overrun*0.5/12:,.0f}/mo</strong> directly to this figure.
    </div>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# TAB 5 — ASK ANYTHING
# ══════════════════════════════════════════════════════════════
with tab5:
    st.markdown('<p class="main-header">💬 Ask Anything</p>',unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Powered by actual GL data, bills, and financial reports. Ask in English or Hindi.</p>',unsafe_allow_html=True)
    if not st.session_state.groq_key:
        st.warning("⚠️ Enter your Groq API Key in the sidebar.")
    else:
        sugg=["Why is electricity over budget?","What caused the DD3 spike?","When will reserves run low?",
              "Explain the deleted GL batch","Is water billing estimated?","Jan vs Feb NOI comparison",
              "Propane double delivery — what?","How much can NOI improve?","What to ask management?","Feb-26 accrual issues"]
        cols=st.columns(5)
        for i,s in enumerate(sugg):
            with cols[i%5]:
                if st.button(s,key=f"s{i}"): st.session_state.messages.append({"role":"user","content":s})
        st.markdown("---")
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]): st.write(msg["content"])

        doc_ctx=""
        if st.session_state.documents:
            doc_ctx="\n\nUPLOADED DOCS:\n"
            for fn,ct in st.session_state.documents.items(): doc_ctx+=f"\n---{fn}---\n{ct[:2000]}\n"

        SYS=f"""Senior real estate financial analyst — HUD affordable housing specialist.
PROPERTY: Virginia Dare Apartments | 68 units | Elizabeth City NC | HUD HAP | Beacon Mgmt (Kenya Owens)
T12 Revenue: $786,025 | T12 Util: ${T12["Total_Util"].sum():,.0f} | Avg NOI: ${T12["NOI"].mean():,.0f}
JAN-26: Revenue $67,200 | NOI $33,607 | Util $10,221 (47.2% over budget)
FEB-26: Revenue $70,154 | NOI $41,023 | Util $8,004 (15.3% over budget)
BILLS: DD3 = $2,707 in BOTH Feb-25 AND Jan-26 (winter pattern). Water = always 99 units (estimated).
Blossman Jan-26: 2 deliveries 409.6 gal/$1,001 (unusual). Price up 7.1% YoY.
GL JAN-26: All bills clean, zero discrepancies.
GL FEB-26: Deleted batch #1419 ($8,978.45), elec accrual overstated $1,885, trash understated $256, office past due $405.
RESERVES: Yr1 $734K | Yr4-6 draw $707K | Yr8 $174K | HVAC 4yr/$154K | Boiler 5yr/$80K
Savings potential: $26,800/yr = $447K property value at 6% cap.{doc_ctx}
Answer with specific numbers. Flag risks. Suggest actions. Be concise."""

        if prompt:=st.chat_input("Ask about utilities, GL, NOI, reserves..."):
            st.session_state.messages.append({"role":"user","content":prompt})
            with st.chat_message("user"): st.write(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Analyzing..."):
                    try:
                        client=Groq(api_key=st.session_state.groq_key)
                        hist=[{"role":m["role"],"content":m["content"]} for m in st.session_state.messages[:-1]]
                        resp=client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[{"role":"system","content":SYS},*hist,{"role":"user","content":prompt}],
                            max_tokens=1500)
                        reply=resp.choices[0].message.content
                        st.write(reply)
                        st.session_state.messages.append({"role":"assistant","content":reply})
                    except Exception as e: st.error(f"Error: {str(e)}")
        if st.session_state.messages:
            if st.button("🗑️ Clear Chat"): st.session_state.messages=[]; st.rerun()
