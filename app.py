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
/* Executive summary table styling */
.exec-row-ok{background:#f0fdf4;padding:0.55rem 0.9rem;border-radius:7px;border-left:3px solid #22c55e;margin:0.2rem 0;font-size:0.84rem;display:flex;justify-content:space-between;align-items:center;}
.exec-row-warn{background:#fffbeb;padding:0.55rem 0.9rem;border-radius:7px;border-left:3px solid #f59e0b;margin:0.2rem 0;font-size:0.84rem;display:flex;justify-content:space-between;align-items:center;}
.exec-row-flag{background:#fef2f2;padding:0.55rem 0.9rem;border-radius:7px;border-left:3px solid #ef4444;margin:0.2rem 0;font-size:0.84rem;display:flex;justify-content:space-between;align-items:center;}
</style>
""", unsafe_allow_html=True)

for key, default in [("messages",[]),("documents",{}),("groq_key","")]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── CONSTANTS ──
UNITS=68; SQFT=56000; BUDGET_UTIL_MO=6942; MORTGAGE_MO=15130; ANNUAL_EGI=786025

# ── T12 — updated to drop Feb-25, add Mar-26 ──
T12 = pd.DataFrame({
    "Month":   ["Mar-25","Apr-25","May-25","Jun-25","Jul-25","Aug-25","Sep-25","Oct-25","Nov-25","Dec-25","Jan-26","Feb-26","Mar-26"],
    "Revenue": [63045,60395,65840,65745,65173,65740,63987,67534,67880,68845,67200,70154,70693],
    "Expenses":[36806,44395,44011,30969,29022,45828,25240,26492,26546,43098,33593,29131,34179],
    "NOI":     [26239,16000,21829,34776,36151,19912,38747,41042,41334,25747,33607,41023,36514],
    "Net_Inc": [1760,-8675,-180,12013,8089,1742,14792,22542,20590,-29612,15104,19424,13116],
    "Elec":    [7624,7795,3617,3401,3859,6651,3781,3329,3949,7043,7709,6039,9035],
    "Water":   [1440,744,839,928,711,1115,755,854,771,853,796,689,1181],
    "Gas":     [1021,684,531,989,318,1130,580,628,1024,492,1001,655,917],
    "Sewer":   [1743,562,755,846,634,1023,680,768,695,768,715,620,1078],
    "Trash":   [598,256,280,280,280,318,260,294,266,294,275,296,286],
    "Vacancy": [8146,11646,8060,6094,7626,7227,8284,4592,3368,2797,5243,1992,1379],
    "Bad_Debt":[1114,11910,1802,0,1163,705,0,0,2504,73,5819,1699,0],
})
T12["Total_Util"] = T12[["Elec","Water","Gas","Sewer","Trash"]].sum(axis=1)

# ── MARCH 2026 actuals vs budget ──
MAR26 = dict(
    revenue=70692.72, budget_rev=73490,
    noi=36514.06, budget_noi=42983,
    net_income=13116.46, budget_ni=26930,
    total_expenses=34178.66, budget_exp=30507,
    elec=9034.66, budget_elec=4605,
    water=1180.86, budget_water=817,
    gas=917.12, budget_gas=745,
    sewer=1078.33, budget_sewer=775,
    trash=285.85, budget_trash=280,
    total_util=12210.97, budget_util=6942,
    bad_debt=0, budget_bad_debt=697,
    vacancy=1379, budget_vacancy=1686,
    mgmt_fee=2686.52, budget_mgmt=2721,
    payroll=3840, budget_payroll=3840,
    insurance=4668.76, budget_insurance=4553,
    other_nonop=9060.35, budget_other_nonop=1707,
    interest=13665.62, budget_interest=13666,
    cash_in_bank=135102.27,
    reserve_1320=45765, reserve_1322=-31930.93,  # 1322 went negative - consolidation artifact
    reserve_operating=518950,
    ar_tenant=13896.96, ar_hud=3269,
)

# ── FEB26 (previous month, kept for reference) ──
FEB26 = dict(
    revenue=70153.86,budget_rev=73490,total_expenses=29130.72,budget_exp=31244,
    noi=41023.14,budget_noi=42246,net_income=19424.42,budget_ni=24729,
    elec=6039.44,budget_elec=4605,water=689.38,budget_water=817,
    gas=654.54,budget_gas=745,sewer=620.40,budget_sewer=775,
    trash=295.62,budget_trash=280,total_util=8003.76,budget_util=6942,
    bad_debt=1699,vacancy=1992,
)

BILLS = pd.DataFrame({
    "Month":      ["Dec-24","Jan-25","Feb-25","Mar-25","Apr-25","May-25","Jun-25",
                   "Jul-25","Aug-25","Sep-25","Oct-25","Nov-25","Dec-25","Jan-26","Feb-26","Mar-26"],
    "Main_Bill":  [5474.20,8152.34,8889.05,8895.28,5095.03,4759.04,5190.53,
                   6415.93,5852.34,5550.89,4950.70,5384.37,7229.77,8550.91,0,7966.58],
    "Office_Bill":[348.73,385.58,404.14,404.14,343.59,347.58,357.72,
                   379.09,362.43,353.02,342.26,340.46,374.40,380.43,386.22,388.88],
    "Gas_Bill":   [0,394,0,0,0,0,0,0,0,0,0,0,0,1000.82,654.54,357.86],
    "Elec":       [2763.08,4134.72,3841.44,3841.44,2235.17,2131.40,2316.39,
                   2952.58,2641.25,2496.87,2140.42,2271.27,3042.82,3480.48,0,3823.40],
    "DD3":        [1061.39,2092.01,2707.30,2707.30,846.03,646.06,846.03,
                   1292.12,1107.53,984.47,815.27,1076.77,1953.56,2707.30,0,1784.36],
    "Water_Units":[99]*16,
    "Water_$":    [812.49]*16,
})
BILLS["Total_Bill"] = BILLS["Main_Bill"]+BILLS["Office_Bill"]+BILLS["Gas_Bill"]

PROPANE = pd.DataFrame({
    "Invoice Date":["Jan-25","Jan-02-26","Jan-21-26","Feb-12-26","Mar-16-26"],
    "Invoice #":["N/A","34085586","34375960","34657363","35210286"],
    "Gallons":[172,210.60,199.00,None,145.70],
    "Rate $/Gal":[2.099,2.249,2.249,None,2.249],
    "Total Due":[394,514.40,486.42,654.54,357.86],
    "GL Status":["Paid","Paid Jan-08 #1923","Paid Feb-02 #1941","Paid Feb-20 #1965","In Mar-26"],
})

RESERVE = pd.DataFrame({
    "Year":["Yr 1","Yr 2","Yr 3","Yr 4","Yr 5","Yr 6","Yr 7","Yr 8","Yr 9","Yr 10"],
    "Balance":[734280,769342,809824,626409,428488,236185,221978,174855,138243,112936],
    "Draw":[0,0,4227,229410,242554,235422,55896,89523,79348,68527],
    "Min_Req":[59861,63937,65389,66873,68391,69944,71531,73155,74816,76514],
})

COMPONENTS = pd.DataFrame({
    "Component":["Elevators - Passenger (2x 2,000-lb)","Elevator - Freight/Service (1)",
        "Elevator Cab Interior Finish (3)","HVAC Heat Pumps - Units (68)","HVAC Heat Pumps - Common (9)",
        "Gas Furnace - Units (68)","Gas Furnace - Common (9)","Rooftop Package Unit",
        "Boiler - Gas DHW (1)","Hot Water Storage Tank","PVC/TPO Roof Membrane",
        "Windows - Aluminum (193+20)","Fire Alarm Control Panel","Emergency Call System (68 units)",
        "Electric Water Heater - Common","Unit Entry Doors (68)","VCT Flooring - Units (66 x 1-BR)",
        "Kitchen Cabinets - Units (68)","Refrigerators - Units (68)","Electric Ranges - Units (68)",],
    "Estimated Useful Life":[30,30,20,15,15,20,20,15,25,15,15,40,15,15,15,35,20,25,15,25],
    "Remaining Life (yrs)":[5,5,4,8,8,10,10,10,8,5,5,14,8,5,14,10,8,0,0,0],
    "Total Replacement $":[369508,149498,11610,95632,12657,48158,6374,3500,9700,2000,72290,78716,3541,13158,1161,13631,44699,408000,39372,23528],
    "CNA Year Due":["Yr 5","Yr 5","Yr 4","Yr 8","Yr 8","Yr 10","Yr 10","Yr 10","Yr 8","Yr 5","Yr 5","Yr 14","Yr 8","Yr 5","Yr 14","Yr 10","Yr 9","Now","Now","Now"],
})
COMPONENTS["Reserve/Unit/Yr"] = (COMPONENTS["Total Replacement $"]/68/COMPONENTS["Estimated Useful Life"]).round(0).astype(int)
COMPONENTS["Annual Total"] = COMPONENTS["Reserve/Unit/Yr"]*UNITS
TOTAL_RES_PU  = int(COMPONENTS["Reserve/Unit/Yr"].sum())
TOTAL_RES_ANN = int(COMPONENTS["Annual Total"].sum())

# ── BUDGET_LINES — Jan, Feb, Mar 2026 ──
BUDGET_LINES = pd.DataFrame([
    {"Category":"Income","Account":"5120","Line Item":"Gross Tenant Rent Potential","Jan_Act":31659,"Jan_Bud":69702,"Feb_Act":31659,"Feb_Bud":69702,"Mar_Act":31371,"Mar_Bud":69702,"Type":"income"},
    {"Category":"Income","Account":"5121","Line Item":"Tenant Assistance (HAP)","Jan_Act":36570,"Jan_Bud":0,"Feb_Act":38334,"Feb_Bud":0,"Mar_Act":38622,"Mar_Bud":0,"Type":"income"},
    {"Category":"Income","Account":"5220","Line Item":"Vacancies - Apartments","Jan_Act":-5243,"Jan_Bud":-1686,"Feb_Act":-1992,"Feb_Bud":-1686,"Mar_Act":-1379,"Mar_Bud":-1686,"Type":"income"},
    {"Category":"Income","Account":"5410","Line Item":"Financial Revenue - Operations","Jan_Act":20.48,"Jan_Bud":29,"Feb_Act":9.87,"Feb_Bud":29,"Mar_Act":10.93,"Mar_Bud":29,"Type":"income"},
    {"Category":"Income","Account":"5440","Line Item":"Revenue - Replacement Reserve","Jan_Act":1489.48,"Jan_Bud":0,"Feb_Act":1314.47,"Feb_Bud":0,"Mar_Act":1463.34,"Mar_Bud":0,"Type":"income"},
    {"Category":"Income","Account":"5910","Line Item":"Laundry & Vending","Jan_Act":307.44,"Jan_Bud":303,"Feb_Act":187.52,"Feb_Bud":303,"Mar_Act":619.45,"Mar_Bud":303,"Type":"income"},
    {"Category":"Income","Account":"5920","Line Item":"Tenant Charges","Jan_Act":486,"Jan_Bud":1242,"Feb_Act":641,"Feb_Bud":0,"Mar_Act":-15,"Mar_Bud":0,"Type":"income"},
    {"Category":"Payroll","Account":"6510","Line Item":"Maintenance Payroll","Jan_Act":3865,"Jan_Bud":3840,"Feb_Act":3664.08,"Feb_Bud":3840,"Mar_Act":3840,"Mar_Bud":3840,"Type":"expense"},
    {"Category":"Administrative","Account":"6250","Line Item":"Other Renting Expenses","Jan_Act":-2792.70,"Jan_Bud":85,"Feb_Act":125,"Feb_Bud":85,"Mar_Act":125,"Mar_Bud":85,"Type":"expense"},
    {"Category":"Administrative","Account":"6311","Line Item":"Office Expenses","Jan_Act":648.63,"Jan_Bud":1028,"Feb_Act":1159.54,"Feb_Bud":1028,"Mar_Act":1277.42,"Mar_Bud":1028,"Type":"expense"},
    {"Category":"Administrative","Account":"6320","Line Item":"Management Fees","Jan_Act":2621.60,"Jan_Bud":2721,"Feb_Act":2510.44,"Feb_Bud":2721,"Mar_Act":2686.52,"Mar_Bud":2721,"Type":"expense"},
    {"Category":"Administrative","Account":"6330","Line Item":"Manager Salaries","Jan_Act":2757.04,"Jan_Bud":3200,"Feb_Act":3000,"Feb_Bud":3200,"Mar_Act":3000,"Mar_Bud":3200,"Type":"expense"},
    {"Category":"Administrative","Account":"6340","Line Item":"Legal","Jan_Act":96.25,"Jan_Bud":0,"Feb_Act":0,"Feb_Bud":0,"Mar_Act":0,"Mar_Bud":0,"Type":"expense"},
    {"Category":"Administrative","Account":"6370","Line Item":"Bad Debt","Jan_Act":5818.88,"Jan_Bud":697,"Feb_Act":1699,"Feb_Bud":697,"Mar_Act":0,"Mar_Bud":697,"Type":"expense"},
    {"Category":"Administrative","Account":"6390","Line Item":"Misc Administrative","Jan_Act":-20,"Jan_Bud":0,"Feb_Act":0,"Feb_Bud":0,"Mar_Act":0,"Mar_Bud":0,"Type":"expense"},
    {"Category":"Utilities","Account":"6450","Line Item":"Electricity","Jan_Act":7709.25,"Jan_Bud":4605,"Feb_Act":6039.44,"Feb_Bud":4605,"Mar_Act":9034.66,"Mar_Bud":4605,"Type":"expense"},
    {"Category":"Utilities","Account":"6451","Line Item":"Water","Jan_Act":795.26,"Jan_Bud":817,"Feb_Act":689.38,"Feb_Bud":817,"Mar_Act":1180.86,"Mar_Bud":817,"Type":"expense"},
    {"Category":"Utilities","Account":"6452","Line Item":"Gas","Jan_Act":1000.82,"Jan_Bud":745,"Feb_Act":654.54,"Feb_Bud":745,"Mar_Act":917.12,"Mar_Bud":745,"Type":"expense"},
    {"Category":"Utilities","Account":"6453","Line Item":"Sewer","Jan_Act":715.68,"Jan_Bud":775,"Feb_Act":620.40,"Feb_Bud":775,"Mar_Act":1078.33,"Mar_Bud":775,"Type":"expense"},
    {"Category":"Operating & Maint.","Account":"6515","Line Item":"Supplies","Jan_Act":53.16,"Jan_Bud":732,"Feb_Act":-182.51,"Feb_Bud":732,"Mar_Act":649.85,"Mar_Bud":732,"Type":"expense"},
    {"Category":"Operating & Maint.","Account":"6520","Line Item":"Contracts","Jan_Act":3667.70,"Jan_Bud":3843,"Feb_Act":1325,"Feb_Bud":3843,"Mar_Act":2942.70,"Mar_Bud":3843,"Type":"expense"},
    {"Category":"Operating & Maint.","Account":"6525","Line Item":"Garbage & Trash Removal","Jan_Act":274.88,"Jan_Bud":280,"Feb_Act":295.62,"Feb_Bud":280,"Mar_Act":285.85,"Mar_Bud":280,"Type":"expense"},
    {"Category":"Operating & Maint.","Account":"6530","Line Item":"Security Payroll/Contracts","Jan_Act":0,"Jan_Bud":106,"Feb_Act":519.03,"Feb_Bud":106,"Mar_Act":99.80,"Mar_Bud":106,"Type":"expense"},
    {"Category":"Taxes & Insurance","Account":"6711","Line Item":"Payroll Taxes","Jan_Act":528.62,"Jan_Bud":607,"Feb_Act":532.29,"Feb_Bud":607,"Mar_Act":520.97,"Mar_Bud":607,"Type":"expense"},
    {"Category":"Taxes & Insurance","Account":"6720","Line Item":"Property & Liability Insurance","Jan_Act":4553.02,"Jan_Bud":4553,"Feb_Act":4553.02,"Feb_Bud":4553,"Mar_Act":4668.76,"Mar_Bud":4553,"Type":"expense"},
    {"Category":"Taxes & Insurance","Account":"6722","Line Item":"Workmens Compensation","Jan_Act":80.67,"Jan_Bud":78,"Feb_Act":80.67,"Feb_Bud":78,"Mar_Act":55.84,"Mar_Bud":78,"Type":"expense"},
    {"Category":"Taxes & Insurance","Account":"6723","Line Item":"Health Insurance & Benefits","Jan_Act":1219.22,"Jan_Bud":1795,"Feb_Act":1845.78,"Feb_Bud":1795,"Mar_Act":1814.98,"Mar_Bud":1795,"Type":"expense"},
    {"Category":"Taxes & Insurance","Account":"6790","Line Item":"Misc Taxes, Licenses & Permits","Jan_Act":0,"Jan_Bud":237,"Feb_Act":0,"Feb_Bud":237,"Mar_Act":0,"Mar_Bud":237,"Type":"expense"},
    {"Category":"Non-Operating","Account":"6820","Line Item":"Interest - First Mortgage","Jan_Act":15129.79,"Jan_Bud":15130,"Feb_Act":15129.79,"Feb_Bud":15130,"Mar_Act":13665.62,"Mar_Bud":13666,"Type":"expense"},
    {"Category":"Non-Operating","Account":"7100","Line Item":"Other/Non-Recurring Expenses","Jan_Act":2376.92,"Jan_Bud":1707,"Feb_Act":5841.32,"Feb_Bud":1707,"Mar_Act":9060.35,"Mar_Bud":1707,"Type":"expense"},
    {"Category":"Non-Operating","Account":"7140","Line Item":"Partnership Management Fee","Jan_Act":340,"Jan_Bud":0,"Feb_Act":0,"Feb_Bud":0,"Mar_Act":0,"Mar_Bud":0,"Type":"expense"},
    {"Category":"Non-Operating","Account":"7190","Line Item":"Incentive Performance Mgmt Fee","Jan_Act":655.40,"Jan_Bud":680,"Feb_Act":627.61,"Feb_Bud":680,"Mar_Act":671.63,"Mar_Bud":680,"Type":"expense"},
])
for mo in ["Jan","Feb","Mar"]:
    BUDGET_LINES[f"{mo}_Var"]     = BUDGET_LINES[f"{mo}_Act"] - BUDGET_LINES[f"{mo}_Bud"]
    BUDGET_LINES[f"{mo}_Var_Pct"] = ((BUDGET_LINES[f"{mo}_Var"] / BUDGET_LINES[f"{mo}_Bud"].replace(0,1)) * 100).round(1)

def flag_line(row, month="Mar"):
    act=row[f"{month}_Act"]; bud=row[f"{month}_Bud"]
    var=row[f"{month}_Var"]; var_pct=row[f"{month}_Var_Pct"]
    is_expense = row["Type"]=="expense"
    if is_expense:
        if row["Account"]=="6525":
            if var>100: return "\U0001f534 Over $100"
            elif var>0: return "\U0001f7e1 Slightly Over"
            else: return "\u2705 Under"
        if var_pct>50 or var>2000: return "\U0001f534 Critical"
        if var_pct>20 or var>500:  return "\U0001f7e1 Over Budget"
        if var_pct<-20:            return "\U0001f7e2 Under Budget"
        return "\u2705 On Track"
    else:
        if var_pct<-20 and bud>0: return "\U0001f534 Under Budget"
        if var_pct<-10 and bud>0: return "\U0001f7e1 Watch"
        return "\u2705 OK"

for mo in ["Jan","Feb","Mar"]:
    BUDGET_LINES[f"{mo}_Flag"] = BUDGET_LINES.apply(lambda r: flag_line(r, mo), axis=1)

# ── GL DRILL-DOWN ──
GL_DRILLDOWN = {
    "6370 \u2014 Bad Debt ($1,699 vs $697 budget)": {
        "verdict": "\U0001f534 REAL EXPENSE \u2014 Not accrual timing",
        "explanation": "Two actual tenant write-offs processed Feb-16. LOSTRENT $1,178 + LOSTOTHER $521 = $1,699. These are genuine bad debt entries. Jan-26 also had $5,819 bad debt. YTD bad debt = $7,518 vs $1,394 budget \u2014 439% over. Investigate which units and whether HUD subsidy adjustments are current.",
        "transactions": [
            {"Date":"02/16/2026","Description":"LOSTRENT \u2014 Lost To Uncollectible (Rent)","Amount":"$1,178.00","Type":"Real write-off"},
            {"Date":"02/16/2026","Description":"LOSTOTHER \u2014 Lost To Uncollectible (Other)","Amount":"$521.00","Type":"Real write-off"},
        ]
    },
    "6450 \u2014 Electricity ($6,039 vs $4,605 budget)": {
        "verdict": "\U0001f7e1 ACCRUAL TIMING \u2014 Not a real Feb overspend",
        "explanation": "Feb-26 electricity = $9,851.95 accrual MINUS $3,877.20 prior month reversal + $64.69 AGT = net $6,039. Actual Mar-26 bill = $7,967. Accrual overstated by ~$1,885. Deleted batch #1419 created noise but was fully reversed Feb-28.",
        "transactions": [
            {"Date":"02/01/2026","Description":"Reversed prior accrual (Dec-25)","Amount":"-$3,877.20","Type":"Accrual reversal"},
            {"Date":"02/16/2026","Description":"Deleted Batch #1419 \u2014 entered then reversed","Amount":"$7,149.75 \u2192 $0","Type":"\u26a0\ufe0f Error entry (net zero)"},
            {"Date":"02/16/2026","Description":"City of EC \u2014 AGT account final bill","Amount":"$64.69","Type":"Actual bill"},
            {"Date":"02/28/2026","Description":"Feb-26 utility accrual (estimated)","Amount":"$9,851.95","Type":"Accrual (overestimated)"},
        ]
    },
    "6530 \u2014 Security ($519 vs $106 budget)": {
        "verdict": "\U0001f534 REAL EXPENSE \u2014 Capital equipment replacement",
        "explanation": "Three invoices from Down East Protection Systems. $49.90 + $49.90 normal recurring. $419.23 for Replace Hard Drive is one-time, possibly miscoded. Should be in 7100 or capitalized.",
        "transactions": [
            {"Date":"02/16/2026","Description":"Down East Protection: Security Service Jan","Amount":"$49.90","Type":"Normal recurring"},
            {"Date":"02/16/2026","Description":"Down East Protection: Monitoring Service Feb","Amount":"$49.90","Type":"Normal recurring"},
            {"Date":"02/16/2026","Description":"Down East Protection: Replace Hard Drive","Amount":"$419.23","Type":"\u26a0\ufe0f One-time \u2014 possible miscoding"},
        ]
    },
    "7100 \u2014 Other/Non-Recurring ($5,841 vs $1,707 budget) [Feb]": {
        "verdict": "\U0001f534 REAL EXPENSES \u2014 Multiple unit repairs + large plumbing job",
        "explanation": "13 transactions totaling $5,841. Major: Dickson Plumbing toilet Apt 3-1 $2,178 (unusually expensive \u2014 verify scope), VSC Fire pump $897, HD Supply range $868, Rick's wall repair $470, deep clean $500.",
        "transactions": [
            {"Date":"02/16/2026","Description":"Dickson Plumbing \u2014 Replace toilet Apt 3-1","Amount":"$2,178.23","Type":"\U0001f534 High \u2014 verify scope"},
            {"Date":"02/16/2026","Description":"VSC Fire & Security \u2014 Repair fire pump leak","Amount":"$896.54","Type":"Safety item"},
            {"Date":"02/16/2026","Description":"HD Supply \u2014 Range replacement","Amount":"$868.33","Type":"Unit appliance"},
            {"Date":"02/05/2026","Description":"Rick's Home Service \u2014 Wall repair Apt 5-2","Amount":"$470.00","Type":"Unit repair"},
            {"Date":"02/01/2026","Description":"Rick's Home Service \u2014 Deep clean Apt 7-6","Amount":"$500.00","Type":"Turnover cost"},
            {"Date":"02/04/2026","Description":"Rick's Home Service \u2014 HVAC repair Apt M-1","Amount":"$305.00","Type":"HVAC repair"},
            {"Date":"02/04/2026","Description":"Lowe's Pro Supply \u2014 Refrigerator Apt 7-6","Amount":"$357.76","Type":"Unit appliance"},
            {"Date":"02/11/2026","Description":"Dickson Plumbing \u2014 Unclog toilet Apt 3-4","Amount":"$165.00","Type":"Normal repair"},
            {"Date":"02/23/2026","Description":"Mr Snowden's Pest Control \u2014 Roach clean out","Amount":"$45.00","Type":"Normal recurring"},
            {"Date":"02/23/2026","Description":"Rick's Home Service \u2014 Bulk trash removal Apt 3-2","Amount":"$400.00","Type":"Turnover cost"},
        ]
    },
    "7100 \u2014 Other/Non-Recurring ($9,060 vs $1,707 budget) [Mar]": {
        "verdict": "\U0001f534 REAL EXPENSES \u2014 Reason unknown, needs management clarification",
        "explanation": "March 7100 = $9,060 vs $1,707 budget (430% over). GL: $9,405 debit, $345 credit = $9,060 net. Specific invoices unknown \u2014 management (Kenya Owens / Beacon) must provide backup. Must clarify before investor reporting.",
        "transactions": [
            {"Date":"03/2026","Description":"Multiple transactions totaling $9,404.89 debit","Amount":"$9,060.35 net","Type":"\u26a0\ufe0f Details unknown \u2014 request invoice backup from Beacon"},
        ]
    },
    "6311 \u2014 Office Expenses ($1,160 vs $1,028 budget)": {
        "verdict": "\U0001f7e1 REAL EXPENSE \u2014 Brightspeed late fee driving overage",
        "explanation": "Brightspeed internet $390.97 + $42 late fee + $110 adjustments = $543 total. $42 late fee avoidable. Realpage $140, ODP supplies $138, copier $103 all normal.",
        "transactions": [
            {"Date":"02/11/2026","Description":"Brightspeed \u2014 Internet service Jan-Feb","Amount":"$390.97","Type":"Normal"},
            {"Date":"02/11/2026","Description":"Brightspeed \u2014 Late fee","Amount":"$42.00","Type":"\u26a0\ufe0f Avoidable \u2014 late payment"},
            {"Date":"02/13/2026","Description":"Brightspeed \u2014 Manual adjustments (x2)","Amount":"$110.00","Type":"\u26a0\ufe0f Billing dispute"},
            {"Date":"02/16/2026","Description":"Toshiba \u2014 Copier lease","Amount":"$103.38","Type":"Normal"},
            {"Date":"02/03/2026","Description":"Realpage \u2014 Monthly software service","Amount":"$139.86","Type":"Normal"},
        ]
    },
    "6525 \u2014 Garbage & Trash ($296 vs $280 budget)": {
        "verdict": "\U0001f7e1 ACCRUAL ISSUE \u2014 Actual charge correct, accrual understated",
        "explanation": "Feb actual $295.62 (only $15.62 over \u2014 fine). BUT Feb accrual was only $24.17 vs actual $280 office refuse. Accrual methodology broken for this account. Mar-26 spiked as expected.",
        "transactions": [
            {"Date":"02/01/2026","Description":"Reversed prior accrual","Amount":"-$153.55","Type":"Accrual reversal"},
            {"Date":"02/16/2026","Description":"City of EC \u2014 Office refuse charge","Amount":"$18.55","Type":"Actual bill (AGT)"},
            {"Date":"02/28/2026","Description":"Feb-26 garbage accrual (understated)","Amount":"$24.17","Type":"\u26a0\ufe0f Accrual too low"},
            {"Date":"02/28/2026","Description":"Manual entry \u2014 GARBAGE AND TRASH","Amount":"$406.45","Type":"\u26a0\ufe0f Verify not duplicate"},
        ]
    },
}


# ── RENT ROLL — March 31, 2026 (72/73 occupied, only C6 vacant) ──
RR_COLS = ["Unit","Floorplan","SQFT","Status","Tenant","Move_In","Lease_Start","Lease_End",
           "Market_Rent","Tenant_Rent","Subsidy","Total_Billing","Balance","Type"]
RENT_ROLL_DATA = [
    ("C1","C1",1300,"Occupied","Heard, Casey","01/21/2026","01/21/2026","01/20/2027",1800,2370,0,2370,4011,"Market"),
    ("C3","C3",1300,"Occupied","Trotman, Gerald","01/21/2026","01/21/2026","01/20/2027",1195,1195,0,1195,2859,"Market"),
    ("C4","C4",1300,"Occupied","Warden, Danielle","09/10/2024","09/10/2024","09/09/2025",1197,1197,0,1197,5034,"Market"),
    ("C5","C5",1300,"Occupied","Whidbee, Valerie","07/07/2025","07/07/2025","07/06/2026",790,790,0,790,-425,"Market"),
    ("C6","C6",900,"Vacant","VACANT",None,None,None,650,0,0,0,0,""),
    ("M1","M-1",1000,"Occupied","Williams, Margaret","05/09/2025","05/09/2025","05/08/2026",1000,916,0,916,-1160,"Market"),
    ("M2","1B",600,"Occupied","BARKER, EDDA","10/31/2022","10/01/2025","09/30/2026",952,426,526,952,0,"HUD"),
    ("M3","1B",600,"Occupied","BENGE, PEGGY","02/07/2011","02/01/2026","01/31/2027",952,286,666,952,0,"HUD"),
    ("M4","1B",600,"Occupied","McCrey, Carmelia","05/21/2025","05/21/2025","05/20/2026",952,252,700,952,-1,"HUD"),
    ("M5","1B",600,"Occupied","MCMURRIN SR., JOHNNY","09/30/2024","12/01/2025","11/30/2026",952,294,658,952,18,"HUD"),
    ("M6","1B",600,"Occupied","ELMORE, KIT","01/07/2019","01/01/2026","12/31/2026",952,492,460,952,0,"HUD"),
    ("M7","1B",600,"Occupied","Whidbee Walker, Theresa","12/20/2024","12/20/2024","12/19/2025",952,301,651,952,-105,"HUD"),
    ("M8","1B",600,"Occupied","BRADLEY, YVONNE","08/30/2024","08/30/2024","08/29/2025",952,286,666,952,-108,"HUD"),
    ("M9","1B",600,"Occupied","NELSON, JOANNE","11/18/2024","11/18/2024","11/17/2025",952,372,580,952,-318,"HUD"),
    ("M10","1B",600,"Occupied","BRACALE, CELESTINE","10/30/2009","11/01/2025","10/31/2026",952,462,490,952,-72,"HUD"),
    ("2-1","1B",600,"Occupied","WHIDBEE, ANNIE","10/13/2020","10/01/2025","09/30/2026",952,295,657,952,-14,"HUD"),
    ("2-2","1B",600,"Occupied","BEST, MARTHA","11/09/2016","11/01/2025","10/31/2026",952,507,445,952,0,"HUD"),
    ("2-3","1B",600,"Occupied","Lamb, Deborah","03/20/2025","03/20/2025","03/19/2026",916,363,589,952,-3,"HUD"),
    ("2-4","1B",600,"Occupied","Wilson, Ronald","09/11/2024","09/11/2024","09/10/2025",952,438,514,952,-60,"HUD"),
    ("2-5","1B",600,"Occupied","WILSON, CALVIN","08/25/2020","08/01/2025","07/31/2026",952,286,666,952,0,"HUD"),
    ("2-6","1B",600,"Occupied","CULLUM, JR., ALVIN","03/01/2022","03/01/2026","02/28/2027",952,312,640,952,0,"HUD"),
    ("2-7","1A",500,"Occupied","EVANS, ELMER","06/13/2017","06/01/2025","05/31/2026",832,301,531,832,381,"HUD"),
    ("2-8","1B",600,"Occupied","PERRY, DANFAR","11/02/2011","11/01/2025","10/31/2026",952,385,567,952,-14,"HUD"),
    ("2-9","1B",600,"Occupied","Lewis, Robin","09/18/2024","09/18/2024","09/17/2025",952,171,781,952,0,"HUD"),
    ("2-10","M-1",1000,"Occupied","De La Cruz, Miguel","01/01/2023","01/01/2023","12/31/2023",1000,883,0,883,0,"Market"),
    ("3-1","1B",600,"Occupied","JAMES, LEDELL","01/28/2016","01/01/2026","12/31/2026",952,309,643,952,0,"HUD"),
    ("3-2","1B",600,"Occupied","Ferebee, Jean","03/09/2026","03/09/2026","03/08/2027",952,417,535,952,0,"HUD"),
    ("3-3","1B",600,"Occupied","TIMPSON, PALESTINE","10/03/2019","10/01/2025","09/30/2026",952,286,666,952,0,"HUD"),
    ("3-4","1B",600,"Occupied","Williams, Carolyn","05/20/2024","05/20/2024","05/19/2025",952,284,668,952,0,"HUD"),
    ("3-5","1B",600,"Occupied","Moore, Juliet","01/29/2026","01/29/2026","01/28/2027",952,243,709,952,0,"HUD"),
    ("3-6","1B",600,"Occupied","Green, Cleveland","04/23/2025","04/23/2025","04/22/2026",952,337,615,952,0,"HUD"),
    ("3-7","1A",500,"Occupied","PHILLIPS, WILLIE","10/18/2004","10/01/2025","09/30/2026",832,280,552,832,0,"HUD"),
    ("3-8","1B",600,"Occupied","TARKINGTON, MARVIN","03/30/2023","03/01/2026","02/28/2027",952,318,634,952,-332,"HUD"),
    ("4-1","1B",600,"Occupied","Christofferson, David","01/30/2026","01/30/2026","01/29/2027",952,511,441,952,0,"HUD"),
    ("4-2","1B",600,"Occupied","Rouldhac, Zelene","12/10/2024","12/10/2024","12/09/2025",952,438,514,952,-145,"HUD"),
    ("4-3","1B",600,"Occupied","Kinnaman, Kathy","11/21/2023","11/01/2025","10/31/2026",952,609,343,952,-287,"HUD"),
    ("4-4","1B",600,"Occupied","WILLIAMS, ALICE","08/16/2016","08/01/2025","07/31/2026",952,355,597,952,-9,"HUD"),
    ("4-5","1B",600,"Occupied","Lassiter, Donnie","01/13/2025","01/12/2026","12/31/2026",952,212,740,952,0,"HUD"),
    ("4-6","1B",600,"Occupied","BROOKS, BEULAH","07/30/2019","07/01/2025","06/30/2026",952,279,673,952,0,"HUD"),
    ("4-7","1A",500,"Occupied","Chamblee, Charlie","10/10/2024","10/10/2024","10/09/2025",832,358,474,832,0,"HUD"),
    ("4-8","1B",600,"Occupied","MONDT, MARY","07/11/2018","07/01/2025","06/30/2026",952,345,607,952,0,"HUD"),
    ("5-1","1B",600,"Occupied","Ferebee, Jonathan","09/25/2025","09/25/2025","09/24/2026",952,559,393,952,556,"HUD"),
    ("5-2","1B",600,"Occupied","Conery, Robert","04/22/2024","04/25/2025","04/01/2026",952,288,664,952,0,"HUD"),
    ("5-3","1B",600,"Occupied","DOZIER, CENDIA","09/28/2022","09/01/2025","08/31/2026",952,251,701,952,0,"HUD"),
    ("5-4","1B",600,"Occupied","COWELL, CARROLL","05/11/2023","05/01/2025","04/30/2026",952,493,459,952,0,"HUD"),
    ("5-5","1B",600,"Occupied","Jackson, Robert","08/04/2025","08/04/2025","08/03/2026",952,591,361,952,-57,"HUD"),
    ("5-6","1B",600,"Occupied","Midyette, John","06/04/2025","06/04/2025","06/03/2026",952,441,511,952,-44,"HUD"),
    ("5-7","1A",500,"Occupied","Harris, April","03/19/2026","03/19/2026","03/18/2027",832,255,577,832,0,"HUD"),
    ("5-8","1B",600,"Occupied","HUNTER, DIANNE","05/21/2015","05/01/2025","04/30/2026",952,283,669,952,-8,"HUD"),
    ("6-1","1B",600,"Occupied","Price, Bruce","11/27/2024","11/27/2024","11/26/2025",952,286,666,952,-2,"HUD"),
    ("6-2","1B",600,"Occupied","Perkins, Tommy","09/19/2025","09/19/2025","09/18/2026",952,373,579,952,-7,"HUD"),
    ("6-3","1B",600,"Occupied","Castelanno, Janet","08/26/2024","08/26/2024","08/25/2025",952,257,695,952,-47,"HUD"),
    ("6-4","1B",600,"Occupied","Sawyer, William","04/26/2024","05/01/2025","03/31/2026",952,280,672,952,0,"HUD"),
    ("6-5","1B",600,"Occupied","Thomas, Robert","05/16/2024","05/16/2024","05/15/2025",952,286,666,952,-33,"HUD"),
    ("6-6","1B",600,"Occupied","BUTLER, ALTON","03/30/2023","03/01/2026","02/28/2027",952,443,509,952,-4,"HUD"),
    ("6-7","1A",500,"Occupied","Palmer, Jack","11/17/2025","11/17/2025","11/16/2026",832,260,572,832,0,"HUD"),
    ("6-8","1B",600,"Occupied","Barcliff, Martha","10/16/2025","10/16/2025","10/15/2026",952,148,804,952,0,"HUD"),
    ("7-1","1B",600,"Occupied","ZURAWICKI, GRACE","02/16/2007","02/01/2026","01/31/2027",952,443,509,952,31,"HUD"),
    ("7-2","1B",600,"Occupied","BURTON, VICKIE","06/16/2022","06/01/2025","05/31/2026",952,454,498,952,0,"HUD"),
    ("7-3","1B",600,"Occupied","WHITE, DONALD","11/17/2022","11/01/2025","10/31/2026",952,320,632,952,0,"HUD"),
    ("7-4","1B",600,"Occupied","GREGORY, MARY","10/27/2008","10/01/2025","09/30/2026",952,286,666,952,-9,"HUD"),
    ("7-5","1B",600,"Occupied","CURTIS JR., WILLIAM","05/22/2023","05/01/2025","04/30/2026",952,283,669,952,-275,"HUD"),
    ("7-6","1B",600,"Occupied","Christian, Sonia","01/30/2026","01/30/2026","01/29/2027",952,164,788,952,-1,"HUD"),
    ("7-7","1A",500,"Occupied","Parker, Caleb","11/01/2024","11/01/2025","10/31/2026",832,607,225,832,0,"HUD"),
    ("7-8","1B",600,"Occupied","EDWARDS, FRANCIS","03/02/2015","03/01/2026","02/28/2027",952,294,658,952,0,"HUD"),
    ("8-1","1B",600,"Occupied","Tillett, Yvonne","11/12/2025","11/12/2025","11/11/2026",952,384,568,952,-64,"HUD"),
    ("8-2","1B",600,"Occupied","Robinson, Evelyn","10/06/2025","10/06/2025","10/05/2026",952,328,624,952,0,"HUD"),
    ("8-3","1B",600,"Occupied","MOORE, CHARLIE","05/04/2023","05/01/2025","04/30/2026",952,376,576,952,371,"HUD"),
    ("8-4","1B",600,"Occupied","KINNEY, ERNEST","04/21/2021","04/01/2025","03/31/2026",952,290,662,952,0,"HUD"),
    ("8-5","1B",600,"Occupied","HARRIS, JR., DANIEL","12/21/2021","12/01/2025","11/30/2026",952,506,446,952,566,"HUD"),
    ("8-6","1B",600,"Occupied","JONES, LINDA","11/14/2017","11/01/2025","10/31/2026",952,286,666,952,0,"HUD"),
    ("8-7","1A",500,"Occupied","JONES, TROY","07/28/2020","07/01/2025","06/30/2026",832,286,546,832,0,"HUD"),
    ("8-8","1B",600,"Occupied","PETTAWAY, KENNY","02/08/2017","02/01/2026","01/31/2027",952,286,666,952,0,"HUD"),
]
df_rr = pd.DataFrame(RENT_ROLL_DATA, columns=RR_COLS)

OCC_TREND = pd.DataFrame({
    "Month":         ["Nov-25","Dec-25","Jan-26","Feb-26","Mar-26"],
    "Occupied":      [67,68,68,70,72],
    "Total":         [73,73,73,73,73],
    "Occ_Pct":       [91.8,93.2,93.2,95.9,98.6],
    "Resident_Share":[29179,30778,32973,29542,30248],
    "Subsidy_Share": [38333,38645,36911,38017,39095],
    "Total_Billing": [67512,69423,69884,67559,69343],
})

# ── SIDEBAR ──
with st.sidebar:
    st.markdown("### Property Intelligence")
    st.markdown("---")
    api_key = st.text_input("Groq API Key",type="password",value=st.session_state.groq_key)
    if api_key: st.session_state.groq_key = api_key
    st.markdown("---")
    st.selectbox("Property",["Virginia Dare Apartments","Add more..."])
    st.markdown("---")
    st.markdown("#### Upload Documents")
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
                st.success(f"Loaded: {file.name}")
    if st.session_state.documents:
        st.markdown(f"**{len(st.session_state.documents)} file(s) loaded**")
        for f in st.session_state.documents: st.caption(f"📄 {f}")
        if st.button("Clear Files"):
            st.session_state.documents={}; st.rerun()
    st.markdown("---")
    st.caption("Virginia Dare Apartments · 73 units · HUD HAP\nElizabeth City, NC · Data as of Mar 31, 2026")

# ── TABS ──
tab1,tab2,tab3,tab4,tab5,tab6 = st.tabs([
    "🏠 Investor Snapshot","🏘️ Rent Roll & Occupancy","⚡ Utility Deep Dive",
    "📊 Financial Performance","🏦 Reserves & Capital","💬 Ask Anything",
])

# ════════════════════════════════════════════════════════════════
# TAB 1 — INVESTOR SNAPSHOT (clean executive summary)
# ════════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<p class="main-header">🏢 Virginia Dare Apartments</p>',unsafe_allow_html=True)
    st.markdown('<p class="sub-header">110 McMorrine Street, Elizabeth City, NC &nbsp;·&nbsp; 73 units &nbsp;·&nbsp; HUD HAP NC19H148016 &nbsp;·&nbsp; March 2026</p>',unsafe_allow_html=True)

    # ── Top KPIs: 5 headline numbers ──
    k1,k2,k3,k4,k5 = st.columns(5)
    occ_pct_mar = 98.6
    noi_var = MAR26["noi"]-MAR26["budget_noi"]
    with k1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Occupancy</div>
            <div class="kpi-value" style="color:#16a34a">{occ_pct_mar}%</div>
            <div class="delta-green">72 of 73 units — best ever</div></div>""",unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Net Rental Income</div>
            <div class="kpi-value">${MAR26['revenue']:,.0f}</div>
            <div class="delta-gray">vs ${MAR26['budget_rev']:,} budget</div></div>""",unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Net Operating Income</div>
            <div class="kpi-value">${MAR26['noi']:,.0f}</div>
            <div class="delta-red">${noi_var:,.0f} vs budget</div></div>""",unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Net Income</div>
            <div class="kpi-value">${MAR26['net_income']:,.0f}</div>
            <div class="delta-red">${MAR26['net_income']-MAR26['budget_ni']:,.0f} vs budget</div></div>""",unsafe_allow_html=True)
    with k5:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Cash in Bank</div>
            <div class="kpi-value">${MAR26['cash_in_bank']:,.0f}</div>
            <div class="delta-green">↑ from $129K last month</div></div>""",unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # ── Executive Summary: Utilities ──
    st.markdown('<p class="section-title">⚡ Utility Summary — March 2026</p>',unsafe_allow_html=True)

    util_lines = [
        ("Electricity","$9,035","$4,605","+$4,430","96% over","🔴",
         "March bill confirmed at $7,967 (main) + $389 (office) = $8,356 from City EC. GL shows $9,035 due to February over-accrual reversal adding ~$679. The actual bill itself is a genuine spike — DD3 demand charge hit $1,784 in March (winter pattern fading but still elevated). Not a GL error; real cost."),
        ("Water","$1,181","$817","+$364","45% over","🟡",
         "GL shows $1,181 vs typical $812/mo bill. Water is estimated at exactly 99 units every month — city has not physically read this meter. The $1,181 includes a Feb accrual reversal in the GL; actual bill is still the standard ~$812. Flag: meter estimation continues — request physical read."),
        ("Gas / Propane","$917","$745","+$172","23% over","🟡",
         "March Blossman invoice was $357.86 (145.7 gal @ $2.249). GL shows $917 — difference is the Jan double-delivery anomaly still working through the books. No new anomaly in March. Gas spend is normalizing as winter ends."),
        ("Sewer","$1,078","$775","+$303","39% over","🟡",
         "GL shows $1,078 vs $775 budget. Similar to water, sewer billing runs on the estimated 99-unit meter. The GL figure includes prior-month accrual timing. Actual sewer cost tracks with water — both will normalize once city installs smart meters. Not an operational issue."),
        ("Trash","$286","$280","+$6","2% over","✅",
         "Essentially on budget. Standard pickup schedule, no changes."),
    ]

    for util, actual, budget, var, pct, flag, explanation in util_lines:
        color = "exec-row-flag" if flag=="🔴" else ("exec-row-warn" if flag=="🟡" else "exec-row-ok")
        with st.expander(f"{flag} {util} — {actual} vs {budget} budget &nbsp;({pct})", expanded=(flag=="🔴")):
            st.markdown(f"**Variance:** {var} &nbsp;|&nbsp; **Actual:** {actual} &nbsp;|&nbsp; **Budget:** {budget}")
            st.markdown(explanation)

    total_util_var = MAR26["total_util"]-MAR26["budget_util"]
    st.markdown(f"""<div class="insight-box">
        <strong>Total Utilities Mar-26: ${MAR26['total_util']:,.0f}</strong> vs budget ${MAR26['budget_util']:,}
        = <strong>+${total_util_var:,.0f} over (76%).</strong>
        Electricity is the primary driver — it alone accounts for 84% of the overrun.
        The DD3 demand charge remains the single most actionable cost to fix.
        All other utility variances are either accrual timing or meter estimation, not operational problems.
    </div>""",unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # ── Executive Summary: Other Line Items ──
    st.markdown('<p class="section-title">📋 Other Expense Summary — March 2026</p>',unsafe_allow_html=True)

    other_lines = [
        ("Maintenance Payroll","$3,840","$3,840","$0","On budget","✅",
         "Exactly on budget. No variance."),
        ("Management Fees","$2,687","$2,721","+$34 under","1% under","✅",
         "Essentially on budget. Standard 3.5% of collections fee applied correctly."),
        ("Manager Salaries","$3,000","$3,200","+$200 under","6% under","✅",
         "Slightly under budget — no concern."),
        ("Bad Debt","$0","$697","$697 under","Zero this month","✅",
         "No bad debt written off in March. January had a spike ($5,819) — that appears to have been addressed. YTD bad debt $7,518 vs $2,091 budget is still elevated, but March itself is clean."),
        ("Vacancy Loss","$1,379","$1,686","$307 under","Good — under budget","✅",
         "Vacancy loss improved significantly. 98.6% occupancy — only C6 vacant. Rent roll confirms this: 72 of 73 units occupied as of March 31."),
        ("Other Non-Recurring (7100)","$9,060","$1,707","-$7,353","430% over — investigate","🔴",
         "This is the biggest flag in March outside utilities. GL shows $9,404 debit, $345 credit = $9,060 net. Budget was only $1,707. This line typically covers one-time repairs, legal costs, or unusual expenses. The GL detail does not specify the nature — management (Kenya Owens / Beacon) should be asked what this covers. Could be a major repair, emergency service, or administrative cost. Needs clarification before next investor report."),
        ("Interest Expense","$13,666","$13,666","$0","Exact","✅",
         "Berkadia mortgage interest, exactly as scheduled. Interest-only until Jan 2029."),
        ("Insurance","$4,669","$4,553","-$116","2.5% over","✅",
         "Marginally over — normal annual insurance payment timing. Not a concern."),
    ]

    for item, actual, budget, var, label, flag, explanation in other_lines:
        if flag == "🔴":
            with st.expander(f"🔴 {item} — {actual} vs {budget} budget &nbsp;({label})", expanded=True):
                st.markdown(f"**Variance:** {var}")
                st.markdown(explanation)
        elif flag == "🟡":
            with st.expander(f"🟡 {item} — {actual} vs {budget} budget &nbsp;({label})"):
                st.markdown(f"**Variance:** {var}")
                st.markdown(explanation)
        # ✅ items shown as a clean table row
    
    # Show all green items as a compact table
    green_items = [(item,actual,budget,var,label) for item,actual,budget,var,label,flag,_ in other_lines if flag=="✅"]
    if green_items:
        st.markdown("**✅ All other line items on track:**")
        green_df = pd.DataFrame(green_items, columns=["Line Item","Actual","Budget","Variance","Status"])
        st.dataframe(green_df, use_container_width=True, hide_index=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # ── Bottom line ──
    st.markdown('<p class="section-title">📌 Bottom Line — March 2026</p>',unsafe_allow_html=True)
    st.markdown(f"""<div class="insight-box">
        <strong>NOI: ${MAR26['noi']:,.0f}</strong> (budget ${MAR26['budget_noi']:,}, gap of ${abs(noi_var):,.0f}).
        The shortfall comes from two sources: <strong>utilities over by $5,269</strong> (electricity/DD3)
        and <strong>Other Non-Recurring expenses at $9,060</strong> vs $1,707 budgeted — reason unknown, needs clarification.
        Everything else — payroll, management, vacancy, bad debt, insurance — is on or under budget.
        <strong>Occupancy at 98.6% is the strongest it has been.</strong>
        Cash position healthy at $135K.
    </div>""",unsafe_allow_html=True)

    st.markdown('<p class="section-title">🚨 Action Items</p>',unsafe_allow_html=True)
    for level,text in [
        ("red","🔴 INVESTIGATE — Other Non-Recurring (7100): $9,060 vs $1,707 budget (430% over). Ask Beacon Management what this covers before investor reporting."),
        ("red","🔴 ELECTRICITY — DD3 demand charge still elevated ($1,784 in March). Install demand controller — $4-8K one-time cost saves $5-12K/yr. This is the #1 NOI lever."),
        ("yellow","🟡 WATER METER — City has not physically read the meter in 16+ months. Always 99 units estimated. Request physical read from City of Elizabeth City."),
        ("yellow","🟡 Unit C4 (Warden) — lease expired Sep 2025, balance now $5,034. Holdover tenant. Cure notice / action needed."),
        ("yellow","🟡 Unit M1 (Williams, Margaret) — lease expired May 2026, balance -$1,160 delinquent. Follow up."),
    ]:
        st.markdown(f'<div class="alert-{level}">{text}</div>',unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════
# TAB 2 — RENT ROLL & OCCUPANCY
# ════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<p class="main-header">🏘️ Rent Roll & Occupancy</p>',unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Source: OneSite Rents · As of 03/31/2026 · 73 Total Units · 72 Occupied · 1 Vacant (C6)</p>',unsafe_allow_html=True)

    df_occ = df_rr[df_rr["Status"]=="Occupied"]
    df_vac = df_rr[df_rr["Status"]=="Vacant"]
    total_units_rr = len(df_rr)
    occ_count = len(df_occ)
    occ_pct = occ_count/total_units_rr*100
    total_billing_rr = df_occ["Total_Billing"].sum()
    resident_total = df_occ["Tenant_Rent"].sum()
    subsidy_total  = df_occ["Subsidy"].sum()
    delinquent_df  = df_occ[df_occ["Balance"]<0]
    delinquent_amt = abs(delinquent_df["Balance"].sum())

    k1,k2,k3,k4,k5=st.columns(5)
    with k1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Occupancy Rate</div>
            <div class="kpi-value" style="color:#16a34a">{occ_pct:.1f}%</div>
            <div class="delta-green">{occ_count} of {total_units_rr} — best ever</div>
            <div class="kpi-sub">Only C6 vacant</div></div>""",unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Total Monthly Billing</div>
            <div class="kpi-value">${total_billing_rr:,.0f}</div>
            <div class="kpi-sub">Resident + HAP combined</div></div>""",unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Resident Rent</div>
            <div class="kpi-value">${resident_total:,.0f}</div>
            <div class="delta-gray">{resident_total/total_billing_rr*100:.1f}% of billing</div></div>""",unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">HAP Subsidy</div>
            <div class="kpi-value" style="color:#3b82f6">${subsidy_total:,.0f}</div>
            <div class="delta-gray">{subsidy_total/total_billing_rr*100:.1f}% of billing</div></div>""",unsafe_allow_html=True)
    with k5:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Delinquent Accounts</div>
            <div class="kpi-value" style="color:#dc2626">{len(delinquent_df)} units</div>
            <div class="delta-red">${delinquent_amt:,.0f} total owed</div></div>""",unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    col_trend,col_donut=st.columns([2,1])
    with col_trend:
        st.markdown('<p class="section-title">📈 Occupancy & Billing Trend — Nov 2025 to Mar 2026</p>',unsafe_allow_html=True)
        fig_occ=go.Figure()
        fig_occ.add_bar(x=OCC_TREND["Month"],y=OCC_TREND["Subsidy_Share"],name="HAP Subsidy",marker_color="#3b82f6",opacity=0.85)
        fig_occ.add_bar(x=OCC_TREND["Month"],y=OCC_TREND["Resident_Share"],name="Resident Rent",marker_color="#22c55e",opacity=0.85)
        for i,row in OCC_TREND.iterrows():
            fig_occ.add_annotation(x=row["Month"],y=row["Total_Billing"]+700,
                text=f"<b>{row['Occ_Pct']}%</b>",showarrow=False,font=dict(size=11,color="#0f172a"),yanchor="bottom")
        fig_occ.update_layout(barmode="stack",height=280,margin=dict(t=30,b=10),
                              legend=dict(orientation="h",y=-0.28),yaxis_title="$ Monthly Billing")
        st.plotly_chart(fig_occ,use_container_width=True)
    with col_donut:
        st.markdown('<p class="section-title">Mar-26 Billing Split</p>',unsafe_allow_html=True)
        fig_pie=go.Figure(go.Pie(
            labels=["HAP Subsidy","Resident Rent"],values=[subsidy_total,resident_total],
            hole=0.55,marker_colors=["#3b82f6","#22c55e"],textinfo="label+percent",textfont_size=11))
        fig_pie.update_layout(showlegend=False,height=230,margin=dict(t=10,b=10,l=10,r=10),
                              annotations=[dict(text=f"<b>${total_billing_rr:,.0f}</b>",x=0.5,y=0.5,font_size=13,showarrow=False)])
        st.plotly_chart(fig_pie,use_container_width=True)

    st.markdown('<p class="section-title">🏗️ Floorplan Breakdown</p>',unsafe_allow_html=True)
    fp_grp=df_rr.groupby("Floorplan").agg(
        Units=("Unit","count"),Occupied=("Status",lambda x:(x=="Occupied").sum()),
        Avg_SQFT=("SQFT","mean"),Avg_Market=("Market_Rent","mean"),
        Total_Billing=("Total_Billing","sum")).reset_index()
    fp_grp["Occ_%"]=(fp_grp["Occupied"]/fp_grp["Units"]*100).round(1).astype(str)+"%"
    fp_grp["Avg_Market"]=fp_grp["Avg_Market"].map(lambda x:f"${x:,.0f}")
    fp_grp["Total_Billing"]=fp_grp["Total_Billing"].map(lambda x:f"${x:,.0f}")
    fp_grp["Avg_SQFT"]=fp_grp["Avg_SQFT"].map(lambda x:f"{x:,.0f} sf")
    st.dataframe(fp_grp,use_container_width=True,hide_index=True)

    st.markdown('<p class="section-title">📅 Lease Expiration Schedule</p>',unsafe_allow_html=True)
    df_leases=df_occ.dropna(subset=["Lease_End"]).copy()
    df_leases["Lease_End_dt"]=pd.to_datetime(df_leases["Lease_End"],errors="coerce")
    df_leases["Exp_Month"]=df_leases["Lease_End_dt"].dt.to_period("M").astype(str)
    exp_counts=df_leases.groupby("Exp_Month")["Unit"].count().reset_index()
    exp_counts.columns=["Month","Leases_Expiring"]
    exp_counts=exp_counts[exp_counts["Month"]>="2026-03"].sort_values("Month").head(14)

    col_exp,col_hold=st.columns([2,1])
    with col_exp:
        fig_exp=px.bar(exp_counts,x="Month",y="Leases_Expiring",color="Leases_Expiring",
                       color_continuous_scale=["#22c55e","#f59e0b","#ef4444"],
                       text="Leases_Expiring",title="Upcoming Lease Expirations by Month")
        fig_exp.update_traces(textposition="outside")
        fig_exp.update_layout(height=270,margin=dict(t=35,b=10),showlegend=False,
                              coloraxis_showscale=False,xaxis=dict(tickangle=-45))
        st.plotly_chart(fig_exp,use_container_width=True)
    with col_hold:
        st.markdown("**⚠️ Holdover / Expired Leases:**")
        holdovers=df_leases[df_leases["Lease_End_dt"]<pd.Timestamp("2026-03-31")][["Unit","Tenant","Lease_End","Balance"]].copy()
        holdovers["Balance"]=holdovers["Balance"].map(lambda x:f"(${abs(x):,.0f})" if x<0 else f"${x:,.0f}")
        if len(holdovers):
            st.dataframe(holdovers,use_container_width=True,hide_index=True)

    st.markdown('<p class="section-title">💸 Account Balance Analysis</p>',unsafe_allow_html=True)
    col_del,col_cred=st.columns(2)
    with col_del:
        st.markdown(f"**🔴 Delinquent — {len(delinquent_df)} units, ${delinquent_amt:,.0f} total:**")
        del_disp=delinquent_df.sort_values("Balance")[["Unit","Tenant","Tenant_Rent","Subsidy","Balance","Lease_End"]].copy()
        del_disp["Tenant_Rent"]=del_disp["Tenant_Rent"].map(lambda x:f"${x:,.0f}")
        del_disp["Subsidy"]=del_disp["Subsidy"].map(lambda x:f"${x:,.0f}")
        del_disp["Balance"]=del_disp["Balance"].map(lambda x:f"(${abs(x):,.2f})")
        st.dataframe(del_disp,use_container_width=True,hide_index=True)
    with col_cred:
        st.markdown("**✅ Credit / Prepaid Balances:**")
        cred_disp=df_occ[df_occ["Balance"]>0].sort_values("Balance",ascending=False)[["Unit","Tenant","Balance"]].copy()
        cred_disp["Balance"]=cred_disp["Balance"].map(lambda x:f"${x:,.2f}")
        st.dataframe(cred_disp,use_container_width=True,hide_index=True)
        st.caption(f"{len(df_occ[df_occ['Balance']==0])} units with zero balance (fully current)")

    st.markdown('<p class="section-title">📋 Full Rent Roll Detail — Mar 31, 2026</p>',unsafe_allow_html=True)
    fc1,fc2,fc3=st.columns(3)
    with fc1:
        status_filter=st.multiselect("Status",df_rr["Status"].unique().tolist(),default=df_rr["Status"].unique().tolist(),key="rr_status")
    with fc2:
        fp_filter=st.multiselect("Floorplan",sorted(df_rr["Floorplan"].unique().tolist()),default=sorted(df_rr["Floorplan"].unique().tolist()),key="rr_fp")
    with fc3:
        bal_filter=st.selectbox("Balance Filter",["All","Delinquent Only","Credit Only","Zero Balance"],key="rr_bal")

    df_disp=df_rr[df_rr["Status"].isin(status_filter)&df_rr["Floorplan"].isin(fp_filter)].copy()
    if bal_filter=="Delinquent Only": df_disp=df_disp[df_disp["Balance"]<0]
    elif bal_filter=="Credit Only":   df_disp=df_disp[df_disp["Balance"]>0]
    elif bal_filter=="Zero Balance":  df_disp=df_disp[df_disp["Balance"]==0]
    df_disp_fmt=df_disp.copy()
    df_disp_fmt["Market_Rent"]=df_disp_fmt["Market_Rent"].map(lambda x:f"${x:,.0f}" if x else "—")
    df_disp_fmt["Tenant_Rent"]=df_disp_fmt["Tenant_Rent"].map(lambda x:f"${x:,.0f}" if x else "—")
    df_disp_fmt["Subsidy"]=df_disp_fmt["Subsidy"].map(lambda x:f"${x:,.0f}" if x else "—")
    df_disp_fmt["Total_Billing"]=df_disp_fmt["Total_Billing"].map(lambda x:f"${x:,.0f}")
    df_disp_fmt["Balance"]=df_disp_fmt["Balance"].map(lambda x:f"(${abs(x):,.2f})" if x<0 else f"${x:,.2f}" if x>0 else "—")
    st.dataframe(df_disp_fmt,use_container_width=True,hide_index=True,height=420)
    st.caption(f"Showing {len(df_disp)} of {total_units_rr} units · Source: OneSite Rents, As of 03/31/2026")

# ════════════════════════════════════════════════════════════════
# TAB 3 — UTILITY DEEP DIVE (unchanged logic)
# ════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<p class="main-header">⚡ Utility Deep Dive</p>',unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Variance analysis · Consumption trends · Invoice reconciliation · GL anomaly check</p>',unsafe_allow_html=True)

    st.markdown('<p class="section-title">1️⃣ Variance Analysis — GL Booked vs Budget (Trailing 13 Months)</p>',unsafe_allow_html=True)
    t12_tots={c:int(T12[c].sum()) for c in ["Elec","Water","Gas","Sewer","Trash"]}
    t12_buds={"Elec":4605*13,"Water":817*13,"Gas":745*13,"Sewer":775*13,"Trash":280*13}
    total_overrun=T12["Total_Util"].sum()-BUDGET_UTIL_MO*13

    va1,va2=st.columns(2)
    with va1:
        fig_va=go.Figure()
        cat_list=list(t12_tots.keys())
        fig_va.add_bar(x=cat_list,y=[t12_tots[c] for c in cat_list],name="Actual",
                       marker_color=["#ef4444" if t12_tots[c]>t12_buds[c] else "#22c55e" for c in cat_list],
                       marker_line=dict(color="white",width=1))
        fig_va.add_bar(x=cat_list,y=[t12_buds[c] for c in cat_list],name="Budget",
                       marker_color="#334155",opacity=0.8,marker_line=dict(color="white",width=1))
        for c in cat_list:
            var=t12_tots[c]-t12_buds[c]
            fig_va.add_annotation(x=c,y=max(t12_tots[c],t12_buds[c])+300,
                text=f"<b>${var:+,.0f}</b>",showarrow=False,
                font=dict(size=10,color="#dc2626" if var>0 else "#16a34a"),yanchor="bottom")
        fig_va.update_layout(barmode="group",height=310,title="Actual vs Budget by Category",
                             margin=dict(t=35,b=10),yaxis_title="$",
                             legend=dict(orientation="h",y=-0.28),bargap=0.2,bargroupgap=0.05)
        st.plotly_chart(fig_va,use_container_width=True)
    with va2:
        vd=[{"Category":c,"Actual":f"${t12_tots[c]:,.0f}","Budget":f"${t12_buds[c]:,.0f}",
             "Variance $":f"${t12_tots[c]-t12_buds[c]:+,.0f}",
             "Variance %":f"{(t12_tots[c]-t12_buds[c])/t12_buds[c]*100:+.1f}%",
             "Assessment":"🔴 Critical" if (t12_tots[c]-t12_buds[c])/t12_buds[c]*100>30 else "🟡 Monitor" if (t12_tots[c]-t12_buds[c])/t12_buds[c]*100>10 else "✅ OK"}
            for c in cat_list]
        st.dataframe(pd.DataFrame(vd),use_container_width=True,hide_index=True)
        elec_overrun=t12_tots["Elec"]-t12_buds["Elec"]
        st.markdown(f"""<div class="alert-red">🔴 <strong>Total Overrun: ${total_overrun:,.0f}</strong> vs budget.
            Electricity alone = <strong>${elec_overrun:,.0f}</strong> ({elec_overrun/total_overrun*100:.0f}% of overrun).</div>""",unsafe_allow_html=True)

    st.markdown('<p class="section-title">2️⃣ Monthly Trend</p>',unsafe_allow_html=True)
    fig_s=go.Figure()
    for cat,color in [("Elec","#3b82f6"),("Water","#8b5cf6"),("Gas","#f59e0b"),("Sewer","#10b981"),("Trash","#94a3b8")]:
        fig_s.add_bar(x=T12["Month"],y=T12[cat],name=cat,marker_color=color)
    fig_s.add_hline(y=BUDGET_UTIL_MO,line_dash="dash",line_color="#ef4444",
                    annotation_text=f"Budget ${BUDGET_UTIL_MO:,}",annotation_position="top left")
    fig_s.update_layout(barmode="stack",height=310,margin=dict(t=30,b=10),
                        legend=dict(orientation="h",y=-0.3),title="Monthly Utility Breakdown (GL Booked)")
    st.plotly_chart(fig_s,use_container_width=True)

    st.markdown('<p class="section-title">3️⃣ DD3 Demand Charge — Seasonal Pattern</p>',unsafe_allow_html=True)
    cb1,cb2=st.columns(2)
    with cb1:
        fig_e=go.Figure()
        fig_e.add_bar(x=BILLS["Month"],y=BILLS["Elec"]-BILLS["DD3"],name="Base Electric",marker_color="#3b82f6")
        fig_e.add_bar(x=BILLS["Month"],y=BILLS["DD3"],name="DD3 Demand",marker_color="#ef4444")
        fig_e.update_layout(barmode="stack",height=280,title="Electricity: Base + DD3 (Actual Bills)",
                            margin=dict(t=35,b=10),legend=dict(orientation="h",y=-0.3))
        st.plotly_chart(fig_e,use_container_width=True)
        st.markdown("""<div class="alert-red">🔴 <strong>DD3 Pattern:</strong> Feb-25=$2,707 | Jan-26=$2,707 | Mar-26=$1,784 (fading).
            Winter peaks cost ~$5-8K/yr above summer baseline. Demand controller = $4-8K install, $5-12K/yr savings.</div>""",unsafe_allow_html=True)
    with cb2:
        fig_w=go.Figure()
        fig_w.add_scatter(x=BILLS["Month"],y=BILLS["Water_Units"],mode="lines+markers",
                          line=dict(color="#8b5cf6",width=2.5),marker=dict(size=8))
        fig_w.add_hline(y=99,line_dash="dot",line_color="#ef4444",
                        annotation_text="Always 99 = ESTIMATED",annotation_position="top right")
        fig_w.update_layout(height=280,title="Water Meter Reads — Never Physically Read",
                            margin=dict(t=35,b=10),yaxis=dict(range=[90,110]))
        st.plotly_chart(fig_w,use_container_width=True)
        st.markdown("""<div class="alert-yellow">🟡 City has not read this meter in 16+ months.
            Billing always exactly 99 units. Request physical read — actual consumption unknown.</div>""",unsafe_allow_html=True)

    st.markdown('<p class="section-title">4️⃣ Propane (Blossman)</p>',unsafe_allow_html=True)
    st.dataframe(PROPANE,use_container_width=True,hide_index=True)
    st.markdown("""<div class="alert-yellow">🟡 <strong>Jan-26 Double Delivery resolved:</strong> Two invoices (210.6+199 gal) in 19 days.
        March-26 back to normal (145.7 gal). Monitor going forward.</div>""",unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════
# TAB 4 — FINANCIAL PERFORMANCE
# ════════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<p class="main-header">📊 Financial Performance</p>',unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Source: March 2026 Financial Reports · Accrual Basis · GL as of 03/31/2026</p>',unsafe_allow_html=True)

    st.markdown('<p class="section-title">💰 Key Financials — March 2026</p>',unsafe_allow_html=True)
    f1,f2,f3,f4,f5=st.columns(5)
    for widget,(label,actual,budget,higher) in zip([f1,f2,f3,f4,f5],[
        ("Total Revenue",MAR26["revenue"],MAR26["budget_rev"],True),
        ("Net Op. Income",MAR26["noi"],MAR26["budget_noi"],True),
        ("Net Income",MAR26["net_income"],MAR26["budget_ni"],True),
        ("Vacancy Loss",MAR26["vacancy"],MAR26["budget_vacancy"],False),
        ("Bad Debt",MAR26["bad_debt"],MAR26["budget_bad_debt"],False),
    ]):
        var=actual-budget; vp=(var/abs(budget))*100 if budget else 0
        good=(var>=0 and higher)or(var<0 and not higher)
        col="delta-green" if good else "delta-red"
        with widget:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">{label}</div>
                <div class="kpi-value">${actual:,.0f}</div>
                <div class="{col}">{vp:+.1f}% vs ${budget:,} budget</div></div>""",unsafe_allow_html=True)

    st.markdown('<p class="section-title">📈 Revenue, Expenses & NOI — Trailing Months</p>',unsafe_allow_html=True)
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
        st.markdown("**Recent Months:**")
        st.dataframe(pd.DataFrame({
            "Month":["Jan-26","Feb-26","Mar-26"],
            "NOI":["$33,607","$41,023","$36,514"],
            "Net Inc":["$15,104","$19,424","$13,116"],
            "Utilities":["$10,221","$8,004","$12,211"],
            "Vacancy":["$5,243","$1,992","$1,379"],
        }),use_container_width=True,hide_index=True)

    st.markdown('<p class="section-title">📋 Full Line-Item Budget Analysis — Jan, Feb & Mar 2026</p>',unsafe_allow_html=True)
    fc1,fc2,fc3 = st.columns(3)
    with fc1:
        month_sel = st.selectbox("Month",["March 2026","February 2026","January 2026"],key="bud_month")
    with fc2:
        cat_sel = st.selectbox("Category",["All Categories","Income","Payroll","Administrative",
                                            "Utilities","Operating & Maint.","Taxes & Insurance","Non-Operating"],key="bud_cat")
    with fc3:
        flag_sel = st.selectbox("Show",["All","Flagged Only (\U0001f534\U0001f7e1)","Over Budget Only"],key="bud_flag")

    mo = "Mar" if "March" in month_sel else ("Feb" if "February" in month_sel else "Jan")
    df_show = BUDGET_LINES.copy()
    if cat_sel != "All Categories":
        df_show = df_show[df_show["Category"]==cat_sel]
    if "Flagged" in flag_sel:
        df_show = df_show[df_show[f"{mo}_Flag"].str.contains("\U0001f534|\U0001f7e1")]
    elif flag_sel == "Over Budget Only":
        df_show = df_show[(df_show[f"{mo}_Var"]>0) & (df_show["Type"]=="expense")]

    display_rows = []
    for _, row in df_show.iterrows():
        act = row[f"{mo}_Act"]; bud = row[f"{mo}_Bud"]
        var = row[f"{mo}_Var"]; var_pct = row[f"{mo}_Var_Pct"]
        flag = row[f"{mo}_Flag"]
        display_rows.append({
            "Cat": row["Category"], "Account": row["Account"],
            "Line Item": row["Line Item"],
            "Actual": f"${act:,.2f}",
            "Budget": f"${bud:,.2f}" if bud != 0 else "\u2014",
            "Variance $": f"${var:+,.2f}",
            "Var %": f"{var_pct:+.1f}%" if bud != 0 else "N/A",
            "Flag": flag,
        })
    df_disp2 = pd.DataFrame(display_rows)

    def color_flag_cell(val):
        if "\U0001f534" in str(val): return "background-color:#fef2f2;color:#dc2626;font-weight:600"
        if "\U0001f7e1" in str(val): return "background-color:#fffbeb;color:#92400e"
        if "\U0001f7e2" in str(val): return "background-color:#f0fdf4;color:#15803d"
        return ""
    def color_var(val):
        try:
            if "+" in str(val) and "$" in str(val):
                v = float(str(val).replace("$","").replace(",","").replace("+",""))
                return "color:#dc2626;font-weight:600" if v>100 else "color:#dc2626"
        except: pass
        return ""

    st.dataframe(df_disp2.style.map(color_flag_cell,subset=["Flag"]).map(color_var,subset=["Variance $"]),
                 use_container_width=True, hide_index=True, height=420)

    critical = BUDGET_LINES[BUDGET_LINES[f"{mo}_Flag"].str.contains("\U0001f534")]
    warning  = BUDGET_LINES[BUDGET_LINES[f"{mo}_Flag"].str.contains("\U0001f7e1")]
    if not critical.empty or not warning.empty:
        st.markdown(f"**{month_sel} \u2014 {len(critical)} Critical Flags, {len(warning)} Warnings:**")
        for _, row in critical.iterrows():
            var = row[f"{mo}_Var"]; var_pct = row[f"{mo}_Var_Pct"]
            st.markdown(f'<div class="alert-red">\U0001f534 <strong>{row["Account"]} \u2014 {row["Line Item"]}</strong>: ${row[f"{mo}_Act"]:,.2f} vs ${row[f"{mo}_Bud"]:,.2f} = <strong>${var:+,.2f} ({var_pct:+.1f}%)</strong></div>',unsafe_allow_html=True)
        for _, row in warning.iterrows():
            var = row[f"{mo}_Var"]; var_pct = row[f"{mo}_Var_Pct"]
            st.markdown(f'<div class="alert-yellow">\U0001f7e1 <strong>{row["Account"]} \u2014 {row["Line Item"]}</strong>: ${row[f"{mo}_Act"]:,.2f} vs ${row[f"{mo}_Bud"]:,.2f} = <strong>${var:+,.2f} ({var_pct:+.1f}%)</strong></div>',unsafe_allow_html=True)

    st.markdown('<p class="section-title">\U0001f4ca Variance Waterfall \u2014 Top Over-Budget Items</p>',unsafe_allow_html=True)
    expense_over = BUDGET_LINES[(BUDGET_LINES["Type"]=="expense") & (BUDGET_LINES[f"{mo}_Var"]>50)].copy()
    expense_over = expense_over.nlargest(8, f"{mo}_Var")
    if not expense_over.empty:
        fig_wfall = go.Figure(go.Bar(
            x=expense_over["Line Item"], y=expense_over[f"{mo}_Var"],
            marker_color=["#ef4444" if v>500 else "#f59e0b" if v>100 else "#fbbf24" for v in expense_over[f"{mo}_Var"]],
            text=[f"${v:+,.0f}" for v in expense_over[f"{mo}_Var"]],
            textposition="outside",
        ))
        fig_wfall.add_hline(y=100,line_dash="dot",line_color="#94a3b8",
                            annotation_text="$100 threshold",annotation_position="top right")
        fig_wfall.update_layout(height=320,margin=dict(t=30,b=80),yaxis_title="$ Over Budget",
                                xaxis_tickangle=-30,title=f"Over-Budget Expenses \u2014 {month_sel}")
        st.plotly_chart(fig_wfall,use_container_width=True)

    st.markdown('<p class="section-title">\U0001f52c GL Drill-Down \u2014 What\'s Behind Each Over-Budget Line</p>',unsafe_allow_html=True)
    st.caption("Source: Feb-26 & Mar-26 General Ledger | Actual transactions extracted from GL reports")
    selected_acct = st.selectbox("Select flagged account to drill down:",list(GL_DRILLDOWN.keys()),key="gl_drill")
    if selected_acct in GL_DRILLDOWN:
        drill = GL_DRILLDOWN[selected_acct]
        verdict_color = "alert-red" if "\U0001f534" in drill["verdict"] else "alert-yellow"
        st.markdown(f'<div class="{verdict_color}"><strong>{drill["verdict"]}</strong><br>{drill["explanation"]}</div>',unsafe_allow_html=True)
        st.markdown("**GL Transactions:**")
        st.dataframe(pd.DataFrame(drill["transactions"]),use_container_width=True,hide_index=True)

# ════════════════════════════════════════════════════════════════
# TAB 5 — RESERVES & CAPITAL
# ════════════════════════════════════════════════════════════════
with tab5:
    st.markdown('<p class="main-header">🏦 Replacement Reserve & Capital Planning</p>',unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Source: CNA Report D3G Oct 2025 · HUD Reserve Schedule · Trial Balance Mar 31 2026</p>',unsafe_allow_html=True)

    rc1,rc2,rc3,rc4=st.columns(4)
    with rc1: st.markdown(f'<div class="kpi-card"><div class="kpi-label">Reserve 1320 (Mar-26)</div><div class="kpi-value" style="color:#16a34a">${MAR26["reserve_1320"]:,.0f}</div><div class="kpi-sub">+$1,695/mo deposits</div></div>',unsafe_allow_html=True)
    with rc2: st.markdown(f'<div class="kpi-card"><div class="kpi-label">Operating Reserve</div><div class="kpi-value">${MAR26["reserve_operating"]:,.0f}</div><div class="kpi-sub">Long-term reserve (1332)</div></div>',unsafe_allow_html=True)
    with rc3: st.markdown('<div class="kpi-card"><div class="kpi-label">CNA Yr 4-6 Draw</div><div class="kpi-value" style="color:#dc2626">$707K</div><div class="delta-red">Elevator replacement</div></div>',unsafe_allow_html=True)
    with rc4: st.markdown(f'<div class="kpi-card"><div class="kpi-label">Required/Unit/Yr (CNA)</div><div class="kpi-value">${TOTAL_RES_PU:,}</div><div class="delta-gray">${TOTAL_RES_ANN:,}/yr total</div></div>',unsafe_allow_html=True)

    st.markdown('<p class="section-title">📊 10-Year Reserve Balance Projection (CNA D3G 2025)</p>',unsafe_allow_html=True)
    fig_r=go.Figure()
    fig_r.add_bar(x=RESERVE["Year"],y=RESERVE["Balance"],name="Reserve Balance",
                  marker_color=["#16a34a" if b>400000 else "#f59e0b" if b>200000 else "#ef4444" for b in RESERVE["Balance"]])
    fig_r.add_scatter(x=RESERVE["Year"],y=RESERVE["Draw"],name="Annual Draw",
                      line=dict(color="#ef4444",dash="dash",width=2),mode="lines+markers")
    fig_r.add_scatter(x=RESERVE["Year"],y=RESERVE["Min_Req"],name="HUD Minimum",
                      line=dict(color="#f59e0b",dash="dot",width=2),mode="lines+markers",marker=dict(size=5))
    fig_r.update_layout(height=350,margin=dict(t=20,b=10),legend=dict(orientation="h",y=-0.22),
                        yaxis_title="$",title="Reserve Balance vs Draws vs HUD Minimum")
    st.plotly_chart(fig_r,use_container_width=True)

    st.markdown("""<div class="insight-box">
        <strong>Reserve Status:</strong> HUD minimum balance maintained throughout all 10 years per CNA model.
        The Yr 4-6 elevator draw ($519K combined passenger + freight) is the dominant event.
        Current reserve 1320 at $45,765 + operating reserve $518,950 = approximately $565K total — on track.
        No immediate reserve concern. The HVAC utility stress (DD3 overruns) could accelerate mechanical wear,
        which is why fixing the demand charge also protects future capital timing.
    </div>""",unsafe_allow_html=True)

    st.markdown('<p class="section-title">🔧 Component Schedule</p>',unsafe_allow_html=True)
    def sty_rem(val):
        try:
            v=int(val)
            if v<=5: return "background-color:#fef2f2;color:#dc2626;font-weight:600"
            if v<=10: return "background-color:#fffbeb;color:#92400e"
            return "background-color:#f0fdf4;color:#15803d"
        except: return ""
    st.dataframe(COMPONENTS.style.map(sty_rem,subset=["Remaining Life (yrs)"]),use_container_width=True,hide_index=True)

# ════════════════════════════════════════════════════════════════
# TAB 6 — ASK ANYTHING
# ════════════════════════════════════════════════════════════════
with tab6:
    st.markdown('<p class="main-header">💬 Ask Anything</p>',unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Powered by actual GL data, bills, rent roll, and financial reports through March 2026.</p>',unsafe_allow_html=True)
    if not st.session_state.groq_key:
        st.warning("Enter your Groq API Key in the sidebar to use the chatbot.")
    else:
        sugg=["Why is electricity over budget?","What is DD3?","What is the Other Non-Recurring $9,060 in March?",
              "Which tenants are delinquent?","How is occupancy trending?","NOI vs budget explanation",
              "What is the HAP subsidy ratio?","Which leases expire soon?","How much can NOI improve?","Reserve status"]
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

        SYS=f"""You are a senior real estate analyst specializing in HUD affordable housing.
You have full access to Virginia Dare Apartments financial data through March 2026.

PROPERTY: 110 McMorrine St, Elizabeth City NC | 73 units | 9-story | Built 1927 | HUD HAP NC19H148016
Owner: Virginia Dare NC Preservation LLC | Management: Beacon Management (Kenya Owens)
Mortgage: Berkadia $3,278,000 @ 5.36%, interest-only until Jan 2029, matures Dec 2033

MARCH 2026 FINANCIALS:
- Revenue: $70,693 (budget $73,490)
- NOI: $36,514 (budget $42,983 — gap driven by utilities + other non-op)
- Net Income: $13,116 (budget $26,930)
- Total Utilities: $12,211 vs $6,942 budget (76% over — electricity is 84% of overrun)
  * Electricity: $9,035 vs $4,605 budget. GL shows Feb accrual reversal in debits.
    Actual Mar bill: $7,967 (main) + $389 (office) = $8,356. DD3 demand charge = $1,784.
  * Water: $1,181 vs $817 — includes Feb accrual reversal; actual bill ~$812 (estimated meter)
  * Gas: $917 vs $745 — Blossman Mar invoice $357.86, 145.7 gal, normal
  * Sewer: $1,078 vs $775 — accrual timing, tracks with water
- Other Non-Recurring (7100): $9,060 vs $1,707 budget — REASON UNKNOWN, needs management clarification
- Bad Debt: $0 (budget $697) — clean month
- Vacancy Loss: $1,379 (budget $1,686) — UNDER budget, good
- Cash in Bank: $135,102
- Reserve 1320: $45,765 | Operating Reserve: $518,950

RENT ROLL MARCH 2026:
- Occupancy: 98.6% (72/73) — only C6 vacant
- NEW move-ins: Unit 5-7 (Harris, April, Mar-19) and Unit 3-2 (Ferebee, Jean, Mar-09)
- Total billing: $69,343 — Resident: $30,248 | Subsidy: $39,095
- HAP ratio: 56.4%
- Unit C4 (Warden): lease expired Sep-25, balance now $5,034 — holdover, action needed
- Unit M9 (Nelson): -$318 delinquent | Unit 3-8 (Tarkington): -$332 | Unit 7-5 (Curtis): -$275

AUDIT (EisnerAmper, Dec 31 2025 — Clean Opinion):
- 2025 Revenue: $786,666 | Net Loss: -$48,411 | Utilities: $86,259 | Reserve: $559,630

DD3 DEMAND CHARGE: Winter pattern — Feb-25=$2,707, Jan-26=$2,707, Mar-26=$1,784.
Water meter: Always 99 units estimated — not physically read in 16+ months.
{doc_ctx}
Answer with specific numbers. Be direct and concise."""

        if prompt:=st.chat_input("Ask about utilities, GL, rent roll, NOI, reserves..."):
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
            if st.button("Clear Chat"): st.session_state.messages=[]; st.rerun()
