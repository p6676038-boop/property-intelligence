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

# COMPLETE BILLS DATA — from actual City of EC PDFs (City_2025.pdf + City_2026.pdf)
# Main account (37-0345000-01) + Office account (37-0380000-01) + Blossman Gas
# Period = billing end month
BILLS = pd.DataFrame({
    "Month":      ["Dec-24","Jan-25","Feb-25","Mar-25","Apr-25","May-25","Jun-25",
                   "Jul-25","Aug-25","Sep-25","Oct-25","Nov-25","Dec-25","Jan-26","Feb-26","Mar-26"],
    "Main_Bill":  [5474.20, 8152.34, 8889.05, 8895.28, 5095.03, 4759.04, 5190.53,
                   6415.93, 5852.34, 5550.89, 4950.70, 5384.37, 7229.77, 8550.91, 0,       7966.58],
    "Office_Bill":[348.73,  385.58,  404.14,  404.14,  343.59,  347.58,  357.72,
                   379.09,  362.43,  353.02,  342.26,  340.46,  374.40,  380.43,  386.22,  388.88],
    "Gas_Bill":   [0,       394,     0,       0,       0,       0,       0,
                   0,       0,       0,       0,       0,       0,       1000.82, 654.54,  357.86],
    # Electricity from main account bills (actual line items)
    "Elec":       [2763.08, 4134.72, 3841.44, 3841.44, 2235.17, 2131.40, 2316.39,
                   2952.58, 2641.25, 2496.87, 2140.42, 2271.27, 3042.82, 3480.48, 0,       3823.40],
    # DD3 Demand Charge — actual from bills
    "DD3":        [1061.39, 2092.01, 2707.30, 2707.30, 846.03,  646.06,  846.03,
                   1292.12, 1107.53, 984.47,  815.27,  1076.77, 1953.56, 2707.30, 0,       1784.36],
    # Water — always 99 units (estimated meter)
    "Water_Units":[99]*16,
    "Water_$":    [812.49]*16,
})
BILLS["Total_Bill"] = BILLS["Main_Bill"]+BILLS["Office_Bill"]+BILLS["Gas_Bill"]

# AUDIT REPORT DATA — EisnerAmper LLP, Year ended December 31, 2025
AUDIT = {
    "year": "December 31, 2025",
    "auditor": "EisnerAmper LLP, Birmingham AL",
    "lead_accountant": "Kelli Winter, CPA",
    "report_date": "March 26, 2026",
    "opinion": "Unmodified (clean opinion)",
    # Income Statement 2025 vs 2024
    "gross_rent_2025": 384234, "gross_rent_2024": 356994,
    "hap_subsidy_2025": 446019, "hap_subsidy_2024": 425943,
    "total_revenue_2025": 786666, "total_revenue_2024": 782747,
    "vacancies_2025": 76854, "vacancies_2024": 52393,
    "util_elec_2025": 57977, "util_elec_2024": 49132,
    "util_water_2025": 9900, "util_water_2024": 9592,
    "util_gas_2025": 8970, "util_gas_2024": 8066,
    "util_sewer_2025": 9412, "util_sewer_2024": 8638,
    "total_utilities_2025": 86259, "total_utilities_2024": 75428,
    "insurance_2025": 134382, "insurance_2024": 108976,
    "net_loss_2025": -48411, "net_loss_2024": -25317,
    # Balance Sheet Dec 31, 2025
    "cash_operations": 96403,
    "reserve_balance_dec25": 559630,
    "reserve_balance_dec24": 554656,
    "escrow_balance": 57506,
    "total_assets": 3297501,
    "mortgage_net": 3193075,
    "members_equity": 45182,
    # Reserve activity
    "reserve_deposits_2025": 20340,   # $1,695/mo (old rate - full year)
    "reserve_withdrawals_2025": 36198,
    "reserve_interest_2025": 20832,
    "reserve_deposits_2024": 20340,
    "reserve_withdrawals_2024": 114550,
    # Mortgage
    "mortgage_original": 3278000,
    "mortgage_rate": 5.36,
    "mortgage_lender": "Berkadia Commercial Mortgage LLC",
    "mortgage_date": "November 9, 2023",
    "mortgage_maturity": "December 1, 2033",
    "interest_only_until": "January 1, 2029",
    "pi_payment": 17304,
}

# RENT SCHEDULE — HUD Form 92458, effective May 1, 2025
RENT_SCHEDULE = {
    "effective_date": "May 1, 2025",
    "hap_contract": "NC19H148016",
    "contract_through": "April 30, 2026",
    "unit_mix": [
        {"type": "Efficiency",      "count": 7,  "contract_rent": 832,  "monthly": 5824},
        {"type": "1 Bedroom",       "count": 59, "contract_rent": 952,  "monthly": 56168},
        {"type": "2 Bedroom Unsub", "count": 2,  "contract_rent": 0,    "monthly": 0},
    ],
    "total_units": 68,
    "monthly_contract_potential": 61992,
    "annual_contract_potential": 743904,
    "commercial_spaces": 5,
    "commercial_monthly": 5628,
    "utilities_in_rent": ["Heating(E)","Hot Water(E)","Lights(E)","Cooling(E)","Cooking(E)","Water/Sewer"],
    "reserve_deposit_new": 1207,  # new monthly deposit from May 1, 2025
}

PROPANE = pd.DataFrame({
    "Invoice Date":["Jan-25",      "Jan-02-26",           "Jan-21-26",           "Feb-12-26",           "Mar-16-26"],
    "Invoice #":   ["N/A",         "34085586",            "34375960",            "34657363",            "35210286"],
    "Gallons":     [172,           210.60,                199.00,                None,                  145.70],
    "Rate $/Gal":  [2.099,         2.249,                 2.249,                 None,                  2.249],
    "Total Due":   [394,           514.40,                486.42,                654.54,                357.86],
    "GL Status":   ["✅ Paid",     "✅ Paid Jan-08 #1923","✅ Paid Feb-02 #1941","✅ Paid Feb-20 #1965","In Mar-26"],
})

# RESERVE — actual from audit report
# Dec 2024: $554,656 | Dec 2025: $559,630
# Monthly deposit: $1,695 (Jan-Apr 2025) then $1,207 (May-Dec 2025 per HUD letter)
RESERVE_ACTUAL = pd.DataFrame({
    "Period":  ["Dec-2023","Dec-2024","Dec-2025"],
    "Balance": [617780,    554656,    559630],
    "Deposits":[20340,     20340,     None],
    "Withdrawals":[114550, 114550,    36198],
    "Interest":[31086,     31086,     20832],
})

RESERVE = pd.DataFrame({
    # SOURCE: CNA Replacement Reserve Analysis Funding Schedule (D3G, 2025-2010)
    # Initial Deposit: $700,000 | Annual Deposit: $34,000 (+2.26%/yr) | Inflation: 6.81%
    "Year":   ["Yr 1","Yr 2","Yr 3","Yr 4","Yr 5","Yr 6","Yr 7","Yr 8","Yr 9","Yr 10"],
    "Balance":[734280,769342,809824,626409,428488,236185,221978,174855,138243,112936],
    "Draw":   [0,     0,     4227,  229410,242554,235422,55896, 89523, 79348, 68527],
    "Min_Req":[59861, 63937, 65389, 66873, 68391, 69944, 71531, 73155, 74816, 76514],
})

COMPONENTS = pd.DataFrame({
    # SOURCE: D3G CNA Report, Project 2025-2010, Inspection Oct 14, 2025
    "Component": [
        "Elevators - Passenger (2x 2,000-lb)",
        "Elevator - Freight/Service (1)",
        "Elevator Cab Interior Finish (3)",
        "HVAC Heat Pumps - Units (68)",
        "HVAC Heat Pumps - Common (9)",
        "Gas Furnace - Units (68)",
        "Gas Furnace - Common (9)",
        "Rooftop Package Unit",
        "Boiler - Gas DHW (1)",
        "Hot Water Storage Tank",
        "PVC/TPO Roof Membrane",
        "Windows - Aluminum (193+20)",
        "Fire Alarm Control Panel",
        "Emergency Call System (68 units)",
        "Electric Water Heater - Common",
        "Unit Entry Doors (68)",
        "VCT Flooring - Units (66 x 1-BR)",
        "Kitchen Cabinets - Units (68)",
        "Refrigerators - Units (68)",
        "Electric Ranges - Units (68)",
    ],
    "Estimated Useful Life": [30,30,20,15,15,20,20,15,25,15,15,40,15,15,15,35,20,25,15,25],
    "Remaining Life (yrs)":  [5, 5, 4, 8, 8,10,10,10, 8, 5, 5,14, 8, 5,14,10, 8, 0, 0, 0],
    "Total Replacement $":   [369508,149498,11610,95632,12657,48158,6374,3500,9700,2000,72290,78716,3541,13158,1161,13631,44699,408000,39372,23528],
    "CNA Year Due":          ["Yr 5","Yr 5","Yr 4","Yr 8","Yr 8","Yr 10","Yr 10","Yr 10","Yr 8","Yr 5","Yr 5","Yr 14","Yr 8","Yr 5","Yr 14","Yr 10","Yr 9","Now","Now","Now"],
})
COMPONENTS["Reserve/Unit/Yr"] = (COMPONENTS["Total Replacement $"] / 68 / COMPONENTS["Estimated Useful Life"]).round(0).astype(int)
COMPONENTS["Annual Total"] = COMPONENTS["Reserve/Unit/Yr"] * UNITS
COMPONENTS["Annual Total"] = COMPONENTS["Reserve/Unit/Yr"]*UNITS
TOTAL_RES_PU  = int(COMPONENTS["Reserve/Unit/Yr"].sum())
TOTAL_RES_ANN = int(COMPONENTS["Annual Total"].sum())

# COMPLETE LINE-ITEM BUDGET COMPARISON — from actual GL reports Jan-26 & Feb-26
BUDGET_LINES = pd.DataFrame([
    {"Category":"Income","Account":"5120","Line Item":"Gross Tenant Rent Potential","Jan_Act":31659,"Jan_Bud":69702,"Feb_Act":31659,"Feb_Bud":69702,"Type":"income"},
    {"Category":"Income","Account":"5121","Line Item":"Tenant Assistance (HAP)","Jan_Act":36570,"Jan_Bud":0,"Feb_Act":38334,"Feb_Bud":0,"Type":"income"},
    {"Category":"Income","Account":"5220","Line Item":"Vacancies - Apartments","Jan_Act":-5243,"Jan_Bud":-1686,"Feb_Act":-1992,"Feb_Bud":-1686,"Type":"income"},
    {"Category":"Income","Account":"5410","Line Item":"Financial Revenue - Operations","Jan_Act":20.48,"Jan_Bud":29,"Feb_Act":9.87,"Feb_Bud":29,"Type":"income"},
    {"Category":"Income","Account":"5440","Line Item":"Revenue - Replacement Reserve","Jan_Act":1489.48,"Jan_Bud":0,"Feb_Act":1314.47,"Feb_Bud":0,"Type":"income"},
    {"Category":"Income","Account":"5910","Line Item":"Laundry & Vending","Jan_Act":307.44,"Jan_Bud":303,"Feb_Act":187.52,"Feb_Bud":303,"Type":"income"},
    {"Category":"Income","Account":"5920","Line Item":"Tenant Charges","Jan_Act":486,"Jan_Bud":1242,"Feb_Act":641,"Feb_Bud":0,"Type":"income"},
    {"Category":"Payroll","Account":"6510","Line Item":"Maintenance Payroll","Jan_Act":3865,"Jan_Bud":3840,"Feb_Act":3664.08,"Feb_Bud":3840,"Type":"expense"},
    {"Category":"Administrative","Account":"6250","Line Item":"Other Renting Expenses","Jan_Act":-2792.70,"Jan_Bud":85,"Feb_Act":125,"Feb_Bud":85,"Type":"expense"},
    {"Category":"Administrative","Account":"6311","Line Item":"Office Expenses","Jan_Act":648.63,"Jan_Bud":1028,"Feb_Act":1159.54,"Feb_Bud":1028,"Type":"expense"},
    {"Category":"Administrative","Account":"6320","Line Item":"Management Fees","Jan_Act":2621.60,"Jan_Bud":2721,"Feb_Act":2510.44,"Feb_Bud":2721,"Type":"expense"},
    {"Category":"Administrative","Account":"6330","Line Item":"Manager Salaries","Jan_Act":2757.04,"Jan_Bud":3200,"Feb_Act":3000,"Feb_Bud":3200,"Type":"expense"},
    {"Category":"Administrative","Account":"6340","Line Item":"Legal","Jan_Act":96.25,"Jan_Bud":0,"Feb_Act":0,"Feb_Bud":0,"Type":"expense"},
    {"Category":"Administrative","Account":"6370","Line Item":"Bad Debt","Jan_Act":5818.88,"Jan_Bud":697,"Feb_Act":1699,"Feb_Bud":697,"Type":"expense"},
    {"Category":"Administrative","Account":"6390","Line Item":"Misc Administrative","Jan_Act":-20,"Jan_Bud":0,"Feb_Act":0,"Feb_Bud":0,"Type":"expense"},
    {"Category":"Utilities","Account":"6450","Line Item":"Electricity","Jan_Act":7709.25,"Jan_Bud":4605,"Feb_Act":6039.44,"Feb_Bud":4605,"Type":"expense"},
    {"Category":"Utilities","Account":"6451","Line Item":"Water","Jan_Act":795.26,"Jan_Bud":817,"Feb_Act":689.38,"Feb_Bud":817,"Type":"expense"},
    {"Category":"Utilities","Account":"6452","Line Item":"Gas","Jan_Act":1000.82,"Jan_Bud":745,"Feb_Act":654.54,"Feb_Bud":745,"Type":"expense"},
    {"Category":"Utilities","Account":"6453","Line Item":"Sewer","Jan_Act":715.68,"Jan_Bud":775,"Feb_Act":620.40,"Feb_Bud":775,"Type":"expense"},
    {"Category":"Operating & Maint.","Account":"6515","Line Item":"Supplies","Jan_Act":53.16,"Jan_Bud":732,"Feb_Act":-182.51,"Feb_Bud":732,"Type":"expense"},
    {"Category":"Operating & Maint.","Account":"6520","Line Item":"Contracts","Jan_Act":3667.70,"Jan_Bud":3843,"Feb_Act":1325,"Feb_Bud":3843,"Type":"expense"},
    {"Category":"Operating & Maint.","Account":"6525","Line Item":"Garbage & Trash Removal","Jan_Act":274.88,"Jan_Bud":280,"Feb_Act":295.62,"Feb_Bud":280,"Type":"expense"},
    {"Category":"Operating & Maint.","Account":"6530","Line Item":"Security Payroll/Contracts","Jan_Act":0,"Jan_Bud":106,"Feb_Act":519.03,"Feb_Bud":106,"Type":"expense"},
    {"Category":"Taxes & Insurance","Account":"6711","Line Item":"Payroll Taxes","Jan_Act":528.62,"Jan_Bud":607,"Feb_Act":532.29,"Feb_Bud":607,"Type":"expense"},
    {"Category":"Taxes & Insurance","Account":"6720","Line Item":"Property & Liability Insurance","Jan_Act":4553.02,"Jan_Bud":4553,"Feb_Act":4553.02,"Feb_Bud":4553,"Type":"expense"},
    {"Category":"Taxes & Insurance","Account":"6722","Line Item":"Workmens Compensation","Jan_Act":80.67,"Jan_Bud":78,"Feb_Act":80.67,"Feb_Bud":78,"Type":"expense"},
    {"Category":"Taxes & Insurance","Account":"6723","Line Item":"Health Insurance & Benefits","Jan_Act":1219.22,"Jan_Bud":1795,"Feb_Act":1845.78,"Feb_Bud":1795,"Type":"expense"},
    {"Category":"Taxes & Insurance","Account":"6790","Line Item":"Misc Taxes, Licenses & Permits","Jan_Act":0,"Jan_Bud":237,"Feb_Act":0,"Feb_Bud":237,"Type":"expense"},
    {"Category":"Non-Operating","Account":"6820","Line Item":"Interest - First Mortgage","Jan_Act":15129.79,"Jan_Bud":15130,"Feb_Act":15129.79,"Feb_Bud":15130,"Type":"expense"},
    {"Category":"Non-Operating","Account":"7100","Line Item":"Other/Non-Recurring Expenses","Jan_Act":2376.92,"Jan_Bud":1707,"Feb_Act":5841.32,"Feb_Bud":1707,"Type":"expense"},
    {"Category":"Non-Operating","Account":"7140","Line Item":"Partnership Management Fee","Jan_Act":340,"Jan_Bud":0,"Feb_Act":0,"Feb_Bud":0,"Type":"expense"},
    {"Category":"Non-Operating","Account":"7190","Line Item":"Incentive Performance Mgmt Fee","Jan_Act":655.40,"Jan_Bud":680,"Feb_Act":627.61,"Feb_Bud":680,"Type":"expense"},
])
BUDGET_LINES["Jan_Var"]     = BUDGET_LINES["Jan_Act"] - BUDGET_LINES["Jan_Bud"]
BUDGET_LINES["Feb_Var"]     = BUDGET_LINES["Feb_Act"] - BUDGET_LINES["Feb_Bud"]
BUDGET_LINES["Jan_Var_Pct"] = ((BUDGET_LINES["Jan_Var"] / BUDGET_LINES["Jan_Bud"].replace(0,1)) * 100).round(1)
BUDGET_LINES["Feb_Var_Pct"] = ((BUDGET_LINES["Feb_Var"] / BUDGET_LINES["Feb_Bud"].replace(0,1)) * 100).round(1)

def flag_line(row, month="Feb"):
    act=row[f"{month}_Act"]; bud=row[f"{month}_Bud"]
    var=row[f"{month}_Var"]; var_pct=row[f"{month}_Var_Pct"]
    is_expense = row["Type"]=="expense"
    if is_expense:
        if row["Account"]=="6525":  # Trash — flag >$100
            if var>100: return "🔴 Over $100"
            elif var>0: return "🟡 Slightly Over"
            else: return "✅ Under"
        if var_pct>50 or var>2000: return "🔴 Critical"
        if var_pct>20 or var>500:  return "🟡 Over Budget"
        if var_pct<-20:            return "🟢 Under Budget"
        return "✅ On Track"
    else:
        if var_pct<-20 and bud>0: return "🔴 Under Budget"
        if var_pct<-10 and bud>0: return "🟡 Watch"
        return "✅ OK"

BUDGET_LINES["Feb_Flag"] = BUDGET_LINES.apply(lambda r: flag_line(r,"Feb"), axis=1)
BUDGET_LINES["Jan_Flag"] = BUDGET_LINES.apply(lambda r: flag_line(r,"Jan"), axis=1)

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
        # Actual bars — colored per category
        fig_c.add_bar(x=cats, y=actuals, name="Actual",
                      marker_color=colors,
                      marker_line=dict(color="white", width=1))
        # Budget bars — always dark slate, clearly visible
        fig_c.add_bar(x=cats, y=budgets, name="Budget",
                      marker_color="#334155",
                      marker_line=dict(color="white", width=1),
                      opacity=0.75)
        # Variance annotations on top
        for i,(cat,a,b) in enumerate(zip(cats,actuals,budgets)):
            var=a-b
            fig_c.add_annotation(
                x=cat, y=max(a,b)+50,
                text=f"<b>${var:+,.0f}</b>",
                showarrow=False,
                font=dict(size=10, color="#dc2626" if var>0 else "#16a34a"),
                yanchor="bottom"
            )
        fig_c.update_layout(
            barmode="group", height=290, margin=dict(t=35,b=10),
            title="Actual vs Budget by Category (Feb-26)",
            yaxis_title="$",
            legend=dict(orientation="h", y=-0.25),
            bargap=0.2, bargroupgap=0.05,
        )
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
        ("red","🔴 CRITICAL — CNA Critical Repairs (D3G, Oct 14 2025): GFCI outlets 136 units ($4,760) + Smoke detectors 68 units ($2,380) + UFAS accessibility 4 units ($5,000) + Code violation-pallets ($250) + Audio/visual alarms ($400) + UFAS common areas ($1,320) = TOTAL $14,110. Must resolve before next HUD inspection."),
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
                       marker_color=["#ef4444" if t12_tots[c]>t12_buds[c] else "#22c55e" for c in cat_list],
                       marker_line=dict(color="white",width=1))
        fig_va.add_bar(x=cat_list,y=[t12_buds[c] for c in cat_list],name="T12 Budget",
                       marker_color="#334155",opacity=0.8,marker_line=dict(color="white",width=1))
        for c in cat_list:
            var=t12_tots[c]-t12_buds[c]
            fig_va.add_annotation(x=c,y=max(t12_tots[c],t12_buds[c])+300,
                text=f"<b>${var:+,.0f}</b>",showarrow=False,
                font=dict(size=10,color="#dc2626" if var>0 else "#16a34a"),yanchor="bottom")
        fig_va.update_layout(barmode="group",height=310,title="T12 Actual vs Annual Budget",
                             margin=dict(t=35,b=10),yaxis_title="$",
                             legend=dict(orientation="h",y=-0.28),bargap=0.2,bargroupgap=0.05)
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
        hr=COMPONENTS[COMPONENTS["Remaining Life (yrs)"]<=5][["Component","Remaining Life (yrs)","Total Replacement $","Reserve/Unit/Yr"]]
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

    st.markdown('<p class="section-title">📋 Full Line-Item Budget Analysis — Jan & Feb 2026</p>',unsafe_allow_html=True)

    # Filter controls
    fc1,fc2,fc3 = st.columns(3)
    with fc1:
        month_sel = st.selectbox("Month",["February 2026","January 2026"],key="bud_month")
    with fc2:
        cat_sel = st.selectbox("Category",["All Categories","Income","Payroll","Administrative",
                                            "Utilities","Operating & Maint.","Taxes & Insurance","Non-Operating"],key="bud_cat")
    with fc3:
        flag_sel = st.selectbox("Show",["All","Flagged Only (🔴🟡)","Over Budget Only"],key="bud_flag")

    mo = "Feb" if "February" in month_sel else "Jan"
    df_show = BUDGET_LINES.copy()
    if cat_sel != "All Categories":
        df_show = df_show[df_show["Category"]==cat_sel]
    if flag_sel == "Flagged Only (🔴🟡)":
        df_show = df_show[df_show[f"{mo}_Flag"].str.contains("🔴|🟡")]
    elif flag_sel == "Over Budget Only":
        df_show = df_show[(df_show[f"{mo}_Var"]>0) & (df_show["Type"]=="expense")]

    # Build display table
    display_rows = []
    for _, row in df_show.iterrows():
        act = row[f"{mo}_Act"]; bud = row[f"{mo}_Bud"]
        var = row[f"{mo}_Var"]; var_pct = row[f"{mo}_Var_Pct"]
        flag = row[f"{mo}_Flag"]
        display_rows.append({
            "Cat": row["Category"],
            "Account": row["Account"],
            "Line Item": row["Line Item"],
            "Actual": f"${act:,.2f}",
            "Budget": f"${bud:,.2f}" if bud != 0 else "—",
            "Variance $": f"${var:+,.2f}",
            "Var %": f"{var_pct:+.1f}%" if bud != 0 else "N/A",
            "Flag": flag,
        })
    df_disp = pd.DataFrame(display_rows)

    def color_flag_cell(val):
        if "🔴" in str(val): return "background-color:#fef2f2;color:#dc2626;font-weight:600"
        if "🟡" in str(val): return "background-color:#fffbeb;color:#92400e"
        if "🟢" in str(val): return "background-color:#f0fdf4;color:#15803d"
        return ""
    def color_var(val):
        try:
            v = float(str(val).replace("$","").replace(",","").replace("%","").replace("+",""))
            if "+" in str(val) and "$" in str(val):
                return "color:#dc2626;font-weight:600" if v>100 else "color:#dc2626"
        except: pass
        return ""

    st.dataframe(df_disp.style
                 .map(color_flag_cell, subset=["Flag"])
                 .map(color_var, subset=["Variance $"]),
                 use_container_width=True, hide_index=True, height=420)

    # Summary flags box
    critical = BUDGET_LINES[BUDGET_LINES[f"{mo}_Flag"].str.contains("🔴")]
    warning  = BUDGET_LINES[BUDGET_LINES[f"{mo}_Flag"].str.contains("🟡")]

    if not critical.empty or not warning.empty:
        st.markdown(f"**{month_sel} — {len(critical)} Critical Flags, {len(warning)} Warnings:**")
        for _, row in critical.iterrows():
            var = row[f"{mo}_Var"]; var_pct = row[f"{mo}_Var_Pct"]
            st.markdown(f'<div class="alert-red">🔴 <strong>{row["Account"]} — {row["Line Item"]}</strong>: Actual ${row[f"{mo}_Act"]:,.2f} vs Budget ${row[f"{mo}_Bud"]:,.2f} = <strong>${var:+,.2f} ({var_pct:+.1f}%)</strong></div>',unsafe_allow_html=True)
        for _, row in warning.iterrows():
            var = row[f"{mo}_Var"]; var_pct = row[f"{mo}_Var_Pct"]
            st.markdown(f'<div class="alert-yellow">🟡 <strong>{row["Account"]} — {row["Line Item"]}</strong>: Actual ${row[f"{mo}_Act"]:,.2f} vs Budget ${row[f"{mo}_Bud"]:,.2f} = <strong>${var:+,.2f} ({var_pct:+.1f}%)</strong></div>',unsafe_allow_html=True)

    st.markdown('<p class="section-title">📊 Variance Waterfall — Top Over-Budget Items</p>',unsafe_allow_html=True)
    expense_over = BUDGET_LINES[(BUDGET_LINES["Type"]=="expense") & (BUDGET_LINES[f"{mo}_Var"]>50)].copy()
    expense_over = expense_over.nlargest(8, f"{mo}_Var")
    if not expense_over.empty:
        fig_wfall = go.Figure(go.Bar(
            x=expense_over["Line Item"],
            y=expense_over[f"{mo}_Var"],
            marker_color=["#ef4444" if v>500 else "#f59e0b" if v>100 else "#fbbf24"
                          for v in expense_over[f"{mo}_Var"]],
            text=[f"${v:+,.0f}" for v in expense_over[f"{mo}_Var"]],
            textposition="outside",
        ))
        fig_wfall.add_hline(y=100, line_dash="dot", line_color="#94a3b8",
                             annotation_text="$100 threshold", annotation_position="top right")
        fig_wfall.update_layout(height=320, margin=dict(t=30,b=80),
                                 yaxis_title="$ Over Budget",
                                 xaxis_tickangle=-30,
                                 title=f"Over-Budget Expenses — {month_sel}")
        st.plotly_chart(fig_wfall, use_container_width=True)

    # GL DRILL-DOWN for flagged expenses
    st.markdown('<p class="section-title">🔬 GL Drill-Down — What\'s Behind Each Over-Budget Line</p>',unsafe_allow_html=True)
    st.caption("Source: February 2026 General Ledger | Actual transactions extracted from GL report")

    # GL transactions data — extracted from actual Feb-26 GL report
    GL_DRILLDOWN = {
        "6370 — Bad Debt ($1,699 vs $697 budget)": {
            "verdict": "🔴 REAL EXPENSE — Not accrual timing",
            "explanation": "Two actual tenant write-offs processed Feb-16. LOSTRENT $1,178 + LOSTOTHER $521 = $1,699. These are genuine bad debt entries — tenants who could not pay. Jan-26 also had $5,819 bad debt (4 write-offs). YTD bad debt = $7,518 vs $1,394 budget — 439% over. Investigate which units and whether HUD subsidy adjustments are current.",
            "transactions": [
                {"Date":"02/16/2026","Description":"LOSTRENT — Lost To Uncollectible (Rent)","Amount":"$1,178.00","Type":"Real write-off"},
                {"Date":"02/16/2026","Description":"LOSTOTHER — Lost To Uncollectible (Other)","Amount":"$521.00","Type":"Real write-off"},
            ]
        },
        "6450 — Electricity ($6,039 vs $4,605 budget)": {
            "verdict": "🟡 ACCRUAL TIMING — Not a real Feb overspend",
            "explanation": "Feb-26 electricity = $9,851.95 accrual MINUS $3,877.20 prior month reversal + $64.69 AGT account = net $6,039. The accrual ($9,852) was based on Jan-26 high bill. Actual Mar-26 bill = $7,967 — so accrual overstated by ~$1,885. Real electricity spend is tracking to Mar bill. Deleted batch #1419 ($7,149.75) also created noise but was fully reversed Feb-28.",
            "transactions": [
                {"Date":"02/01/2026","Description":"Reversed prior accrual (Dec-25)","Amount":"-$3,877.20","Type":"Accrual reversal"},
                {"Date":"02/16/2026","Description":"Deleted Batch #1419 — entered then reversed","Amount":"$7,149.75 → $0","Type":"⚠️ Error entry (net zero)"},
                {"Date":"02/16/2026","Description":"City of EC — AGT account final bill","Amount":"$64.69","Type":"Actual bill"},
                {"Date":"02/28/2026","Description":"Feb-26 utility accrual (estimated)","Amount":"$9,851.95","Type":"Accrual (overestimated)"},
            ]
        },
        "6530 — Security ($519 vs $106 budget)": {
            "verdict": "🔴 REAL EXPENSE — Capital equipment replacement",
            "explanation": "Three invoices from Down East Protection Systems. $49.90 security service + $49.90 monitoring — these are normal recurring. But $419.23 for 'Replace Hard Drive' is a one-time capital item incorrectly coded to operating security expense. Should be in 7100 (Other/Non-Recurring) or capitalized. Flag to management for reclassification.",
            "transactions": [
                {"Date":"02/16/2026","Description":"Down East Protection: Security Service Jan","Amount":"$49.90","Type":"Normal recurring"},
                {"Date":"02/16/2026","Description":"Down East Protection: Monitoring Service Feb","Amount":"$49.90","Type":"Normal recurring"},
                {"Date":"02/16/2026","Description":"Down East Protection: Replace Hard Drive","Amount":"$419.23","Type":"⚠️ One-time — possible miscoding"},
            ]
        },
        "7100 — Other/Non-Recurring ($5,841 vs $1,707 budget)": {
            "verdict": "🔴 REAL EXPENSES — Multiple unit repairs + one large plumbing job",
            "explanation": "13 transactions totaling $5,841. Major items: Dickson Plumbing replace toilet Apt 3-1 ($2,178), VSC Fire & Security repair fire pump leak ($897), HD Supply range replacement ($868), Rick's Home Service wall repair Apt 5-2 ($470) + deep clean Apt 7-6 ($500). These are all legitimate repair costs but significantly above budget. The $2,178 toilet replacement in particular is unusually expensive — verify scope.",
            "transactions": [
                {"Date":"02/16/2026","Description":"Dickson Plumbing — Replace toilet Apt 3-1","Amount":"$2,178.23","Type":"🔴 High — verify scope"},
                {"Date":"02/16/2026","Description":"VSC Fire & Security — Repair fire pump leak","Amount":"$896.54","Type":"Safety item"},
                {"Date":"02/16/2026","Description":"HD Supply — Range replacement","Amount":"$868.33","Type":"Unit appliance"},
                {"Date":"02/05/2026","Description":"Rick's Home Service — Wall repair Apt 5-2","Amount":"$470.00","Type":"Unit repair"},
                {"Date":"02/01/2026","Description":"Rick's Home Service — Deep clean Apt 7-6","Amount":"$500.00","Type":"Turnover cost"},
                {"Date":"02/04/2026","Description":"Rick's Home Service — HVAC repair Apt M-1","Amount":"$305.00","Type":"HVAC repair"},
                {"Date":"02/04/2026","Description":"Lowe's Pro Supply — Refrigerator Apt 7-6","Amount":"$357.76","Type":"Unit appliance"},
                {"Date":"02/11/2026","Description":"Dickson Plumbing — Unclog toilet Apt 3-4","Amount":"$165.00","Type":"Normal repair"},
                {"Date":"02/23/2026","Description":"Mr Snowden's Pest Control — Roach clean out","Amount":"$45.00","Type":"Normal recurring"},
                {"Date":"02/23/2026","Description":"Rick's Home Service — Bulk trash removal Apt 3-2","Amount":"$400.00","Type":"Turnover cost"},
            ]
        },
        "6311 — Office Expenses ($1,160 vs $1,028 budget)": {
            "verdict": "🟡 REAL EXPENSE — Brightspeed late fee driving overage",
            "explanation": "Most items normal: Realpage software $140, ODP supplies $138, copier lease $103. Issue: Brightspeed internet $390.97 + $42 late fee + two $55 manual adjustments = $543 total for internet. $42 late fee is avoidable — management should ensure timely payment. Also note the 'S/B DISCOUNT' adjustments suggest a billing dispute was not resolved properly.",
            "transactions": [
                {"Date":"02/11/2026","Description":"Brightspeed — Internet service Jan-Feb","Amount":"$390.97","Type":"Normal"},
                {"Date":"02/11/2026","Description":"Brightspeed — Late fee","Amount":"$42.00","Type":"⚠️ Avoidable — late payment"},
                {"Date":"02/13/2026","Description":"Brightspeed — Manual adjustments (x2)","Amount":"$110.00","Type":"⚠️ Billing dispute"},
                {"Date":"02/16/2026","Description":"Toshiba — Copier lease","Amount":"$103.38","Type":"Normal"},
                {"Date":"02/03/2026","Description":"Realpage — Monthly software service","Amount":"$139.86","Type":"Normal"},
            ]
        },
        "6525 — Garbage & Trash ($296 vs $280 budget)": {
            "verdict": "🟡 ACCRUAL ISSUE — Actual charge correct, accrual understated",
            "explanation": "Feb-26 actual = $295.62 (only $15.62 over budget — fine). BUT the Feb accrual was only $24.17 vs actual $280 office refuse charge. This means the accrual methodology is broken for this account. Mar-26 will show a spike when the real bill is booked. Also note $406.45 manual entry 'GARBAGE AND TRASH' on Feb-28 — verify this is not a duplicate.",
            "transactions": [
                {"Date":"02/01/2026","Description":"Reversed prior accrual","Amount":"-$153.55","Type":"Accrual reversal"},
                {"Date":"02/16/2026","Description":"City of EC — Office refuse charge","Amount":"$18.55","Type":"Actual bill (AGT)"},
                {"Date":"02/28/2026","Description":"Feb-26 garbage accrual (understated)","Amount":"$24.17","Type":"⚠️ Accrual too low"},
                {"Date":"02/28/2026","Description":"Manual entry — GARBAGE AND TRASH","Amount":"$406.45","Type":"⚠️ Verify not duplicate"},
            ]
        },
    }

    selected_acct = st.selectbox(
        "Select flagged account to drill down:",
        list(GL_DRILLDOWN.keys()),
        key="gl_drill"
    )

    if selected_acct in GL_DRILLDOWN:
        drill = GL_DRILLDOWN[selected_acct]
        verdict_color = "alert-red" if "🔴" in drill["verdict"] else "alert-yellow"
        st.markdown(f'<div class="{verdict_color}"><strong>{drill["verdict"]}</strong><br>{drill["explanation"]}</div>', unsafe_allow_html=True)

        st.markdown("**GL Transactions:**")
        txn_df = pd.DataFrame(drill["transactions"])
        st.dataframe(txn_df, use_container_width=True, hide_index=True)


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
    fig_r.add_scatter(x=RESERVE["Year"],y=RESERVE["Draw"],name="Annual Draw (Inflated)",
                      line=dict(color="#ef4444",dash="dash",width=2),mode="lines+markers")
    fig_r.add_scatter(x=RESERVE["Year"],y=RESERVE["Min_Req"],name="HUD Min Balance Required",
                      line=dict(color="#f59e0b",dash="dot",width=2),mode="lines+markers",marker=dict(size=5))
    fig_r.update_layout(height=370,margin=dict(t=20,b=10),legend=dict(orientation="h",y=-0.22),yaxis_title="$",
                        title="10-Year Reserve Balance — CNA Funding Schedule (D3G 2025)")
    st.plotly_chart(fig_r,use_container_width=True)

    st.markdown("""<div class="alert-yellow">
        🟡 <strong>CNA Finding (D3G, Oct 2025):</strong> Elevator replacement (Yr 4-6) = $519K draw (2 passenger + 1 freight).
        Balance drops from $810K → $112K by Yr 10. However HUD minimum balance maintained throughout all 10 years.
        Initial deposit $700K | Annual deposit $34,000 (+2.26%/yr) | Inflation assumption: 6.81%.
        Recommend physical elevator inspection before Yr 3 given current HVAC stress.
    </div>""",unsafe_allow_html=True)

    st.markdown('<p class="section-title">🔧 Component Reserve Schedule</p>',unsafe_allow_html=True)
    def sty_rem(val):
        try:
            v=int(val)
            if v<=5: return "background-color:#fef2f2;color:#dc2626;font-weight:600"
            if v<=10: return "background-color:#fffbeb;color:#92400e"
            return "background-color:#f0fdf4;color:#15803d"
        except: return ""
    st.dataframe(COMPONENTS.style.map(sty_rem,subset=["Remaining Life (yrs)"]),use_container_width=True,hide_index=True)

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

        SYS=f"""You are a senior real estate financial analyst specializing in HUD affordable housing.
You have full access to all Virginia Dare Apartments documents including audit, rent schedule, and utility bills.

PROPERTY: Virginia Dare Apartments | 110 McMorrine St, Elizabeth City NC 27909
68 units | 9-story | Built 1927 | HUD HAP Contract NC19H148016
Owner: Virginia Dare NC Preservation LLC | Management: Beacon Management Corp (Kenya Owens)

AUDIT REPORT (EisnerAmper LLP — CLEAN UNMODIFIED OPINION):
Period: Year ended December 31, 2025 | Auditor: Kelli Winter CPA | Report date: March 26, 2026
INCOME STATEMENT 2025 vs 2024:
- Gross Rent: $384,234 (2025) vs $356,994 (2024) — +7.6% due to OCAF increase
- HAP Subsidy: $446,019 (2025) vs $425,943 (2024)
- Total Revenue: $786,666 (2025) vs $782,747 (2024)
- Vacancies: -$76,854 (2025) vs -$52,393 (2024) — vacancy INCREASED
- Utilities 2025: Electricity $57,977 | Water $9,900 | Gas $8,970 | Sewer $9,412 | TOTAL $86,259
- Utilities 2024: Electricity $49,132 | Water $9,592 | Gas $8,066 | Sewer $8,638 | TOTAL $75,428
- Utility YoY increase: +$10,831 (+14.4%) — electricity up $8,845 alone
- Insurance: $134,382 | O&M: $191,134 | Mortgage Interest: $188,757 | Depreciation: $117,299
- Net Loss 2025: -$48,411 | Net Loss 2024: -$25,317

BALANCE SHEET Dec 31, 2025:
- Cash operations: $96,403 | Reserve for Replacements: $559,630 | Escrow: $57,506
- Total Assets: $3,297,501 | Mortgage net: $3,193,075 | Members Equity: $45,182

RESERVE FOR REPLACEMENTS (Audit confirmed):
- Dec 2023: $617,780 | Dec 2024: $554,656 | Dec 2025: $559,630
- 2024: -$114,550 withdrawn | 2025: -$36,198 withdrawn (much less)
- Monthly deposit: $1,695/mo old → $1,207/mo from May 1, 2025 (HUD OCAF adjustment)
- Lender (Berkadia) + HUD consent required for withdrawals

MORTGAGE: Berkadia Commercial Mortgage | $3,278,000 at 5.36% | Originated Nov 9, 2023
Interest-only until Jan 1, 2029 | Then $17,304/mo P+I | Matures Dec 1, 2033

RENT SCHEDULE (HUD Form 92458 — Effective May 1, 2025):
- 7 Efficiency units @ $832/mo = $5,824
- 59 One-Bedroom units @ $952/mo = $56,168
- 2 Two-Bedroom Unsubsidized @ $0 contract rent
- TOTAL: 68 units | $61,992/mo contract potential | $743,904/yr
- 5 Commercial spaces = $5,628/mo additional
- ALL utilities included in rent (tenant pays nothing separately)
- HAP contract through April 30, 2026

MONTHLY FINANCIALS (from GL reports):
JAN-26: Revenue $67,200 | NOI $33,607 | Net Income $15,104 | Utilities $10,221 (47% over budget)
FEB-26: Revenue $70,154 | NOI $41,023 | Net Income $19,424 | Utilities $8,004 (15% over budget)

COMPLETE UTILITY BILLS — DD3 HISTORY (all from actual bills):
Dec-24: $5,474 (DD3=$1,061) | Jan-25: $8,152 (DD3=$2,092) | Feb-25: $8,889 (DD3=$2,707 ⚠️)
Mar-25: $8,895 (DD3=$2,707) | Apr-25: $5,095 (DD3=$846) | May-25: $4,759 (DD3=$646)
Jun-25: $5,191 (DD3=$846) | Jul-25: $6,416 (DD3=$1,292) | Aug-25: $5,852 (DD3=$1,108)
Sep-25: $5,551 (DD3=$984) | Oct-25: $4,951 (DD3=$815) | Nov-25: $5,384 (DD3=$1,077)
Dec-25: $7,230 (DD3=$1,954) | Jan-26: $8,551 (DD3=$2,707 ⚠️ SAME SPIKE) | Mar-26: $7,967 (DD3=$1,784)
DD3 PATTERN: Winter (Dec-Feb) = $1,900-$2,707. Summer (May-Jun) = $646-$846. CLEAR SEASONAL PATTERN.
Water: ALWAYS 99 units estimated billing. City upgrading to smart meters Apr-Oct 2025.
Blossman: Jan-26 two deliveries 409.6 gal/$1,001 unusual. Price $2.099→$2.249 (+7.1% YoY).
Office Apr-26: Past due $405.54 + $19.32 penalty. Disconnect date was Apr-23-26.

GL RECONCILIATION:
Jan-26: ALL 5 bills clean. Zero discrepancies. ✅
Feb-26: Deleted batch #1419 ($8,978.45), elec accrual overstated $1,885, trash understated $256.

SAVINGS POTENTIAL ($26,800/yr → $447,000 added value at 6% cap rate):
- HVAC PM contract (77 units): $6,200/yr savings
- LED retrofit common areas + exterior: $8,400/yr savings
- Demand controller (cut DD3 winter spikes): ~$8,200/yr
- Refuse split with 5 commercial tenants: ~$2,000/yr

FULL LINE-ITEM BUDGET ANALYSIS (Jan-26 & Feb-26 from actual GL):
FORMAT: Line Item | Jan Actual vs Budget (Variance) | Feb Actual vs Budget (Variance) | Flag

INCOME:
- Gross Rent: Jan $31,659 vs $69,702 | Feb $31,659 vs $69,702 [Note: HAP subsidy separate in 5121]
- Tenant Assistance HAP: Jan $36,570 | Feb $38,334 [not budgeted separately]
- Vacancies: Jan -$5,243 vs -$1,686 (HIGH) | Feb -$1,992 vs -$1,686 ✅
- Laundry: Jan $307 vs $303 ✅ | Feb $188 vs $303 🟡

PAYROLL:
- Maintenance Payroll (6510): Jan $3,865 vs $3,840 (+$25) ✅ | Feb $3,664 vs $3,840 ✅

ADMINISTRATIVE:
- Other Renting (6250): Jan -$2,793 vs $85 (credit/reversal) | Feb $125 vs $85 (+$40) ✅
- Office Expenses (6311): Jan $649 vs $1,028 ✅ | Feb $1,160 vs $1,028 (+$132 🟡) — Brightspeed late fee $42 avoidable
- Management Fees (6320): Jan $2,622 vs $2,721 ✅ | Feb $2,510 vs $2,721 ✅
- Manager Salaries (6330): Jan $2,757 vs $3,200 ✅ | Feb $3,000 vs $3,200 ✅
- Bad Debt (6370): Jan $5,819 vs $697 (+$5,122 🔴) | Feb $1,699 vs $697 (+$1,002 🔴) — REAL write-offs, not accrual

UTILITIES:
- Electricity (6450): Jan $7,709 vs $4,605 (+$3,104 🔴 -67%) | Feb $6,039 vs $4,605 (+$1,434 🔴 -31%) — ACCRUAL TIMING mostly
- Water (6451): Jan $795 vs $817 ✅ | Feb $689 vs $817 ✅
- Gas (6452): Jan $1,001 vs $745 (+$256 🟡) | Feb $655 vs $745 ✅
- Sewer (6453): Jan $716 vs $775 ✅ | Feb $620 vs $775 ✅

OPERATING & MAINTENANCE:
- Supplies (6515): Jan $53 vs $732 (under) | Feb -$183 vs $732 (credit/reversal)
- Contracts (6520): Jan $3,668 vs $3,843 ✅ | Feb $1,325 vs $3,843 (under — timing)
- Trash/Garbage (6525): Jan $275 vs $280 ✅ | Feb $296 vs $280 (+$16 🟡) — small over; accrual only $24 (understated!)
- Security (6530): Jan $0 vs $106 | Feb $519 vs $106 (+$413 🔴) — Down East: $419 hard drive replacement possibly miscoded

TAXES & INSURANCE:
- Payroll Taxes (6711): Jan $529 vs $607 ✅ | Feb $532 vs $607 ✅
- Insurance (6720): Jan $4,553 vs $4,553 ✅ | Feb $4,553 vs $4,553 ✅ — exactly on budget
- Health Benefits (6723): Jan $1,219 vs $1,795 ✅ | Feb $1,846 vs $1,795 (+$51) ✅

NON-OPERATING:
- Mortgage Interest (6820): Jan $15,130 vs $15,130 ✅ | Feb $15,130 vs $15,130 ✅ — perfectly on budget
- Other/Non-Recurring (7100): Jan $2,377 vs $1,707 (+$670 🔴) | Feb $5,841 vs $1,707 (+$4,134 🔴) — REAL REPAIRS:
  Feb breakdown: Dickson Plumbing toilet Apt 3-1 $2,178 + VSC fire pump $897 + HD Supply range $868 + Rick's wall repair $470 + deep clean $500 + HVAC repair $305 + Lowe's fridge $358 + plumbing $165 + pest control $45 + bulk trash $400
- Partnership Mgmt Fee (7140): Jan $340 vs $0 (unbudgeted) | Feb $0
- Incentive Mgmt Fee (7190): Jan $655 vs $680 ✅ | Feb $628 vs $680 ✅

KEY INSIGHT FOR CHATBOT: When asked which expenses are over budget:
TOP 3 OVER-BUDGET (Feb-26): 1) Bad Debt $1,699 (+144% REAL write-offs) 2) Electricity $6,039 (+31% ACCRUAL) 3) Other/Non-Recurring $5,841 (+242% REAL repairs)
TOP 3 OVER-BUDGET (Jan-26): 1) Bad Debt $5,819 (+735% REAL) 2) Electricity $7,709 (+67% ACCRUAL) 3) Other/Non-Recurring $2,377 (+39% REAL)
{doc_ctx}
Answer with specific numbers from the documents above. Flag risks. Suggest concrete actions. Be concise."""

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
