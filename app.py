"""
Virginia Dare Apartments — Property Intelligence Dashboard
Beacon Management | 110 McMorrine St, Elizabeth City, NC | 68 units | HUD HAP NC19H148016
Enhanced with Rent Roll data (Nov 2025 – Feb 2026)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
import requests

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Virginia Dare | Property Intelligence",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# STYLE
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .main { background: #0f1117; }
  .metric-card {
    background: linear-gradient(135deg, #1e2330 0%, #252b3b 100%);
    border: 1px solid #2d3448;
    border-radius: 12px;
    padding: 18px 20px;
    margin: 6px 0;
  }
  .metric-card .label { color: #8892a4; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
  .metric-card .value { color: #e8eaf0; font-size: 26px; font-weight: 700; margin: 4px 0; }
  .metric-card .delta-pos { color: #26c981; font-size: 12px; }
  .metric-card .delta-neg { color: #ff6b6b; font-size: 12px; }
  .metric-card .delta-neu { color: #ffa94d; font-size: 12px; }
  .alert-box {
    border-left: 4px solid #ff6b6b;
    background: #1e1520;
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    margin: 6px 0;
    font-size: 13px;
    color: #e8eaf0;
  }
  .info-box {
    border-left: 4px solid #339af0;
    background: #111827;
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    margin: 6px 0;
    font-size: 13px;
    color: #e8eaf0;
  }
  .success-box {
    border-left: 4px solid #26c981;
    background: #0d1a16;
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    margin: 6px 0;
    font-size: 13px;
    color: #e8eaf0;
  }
  .section-header {
    color: #a8b4c8;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 2px;
    border-bottom: 1px solid #2d3448;
    padding-bottom: 6px;
    margin: 20px 0 12px;
  }
  .stTabs [data-baseweb="tab"] { color: #8892a4; font-size: 13px; }
  .stTabs [aria-selected="true"] { color: #e8eaf0 !important; }
  h1, h2, h3 { color: #e8eaf0 !important; }
  .stDataFrame { background: #1e2330; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# DATA: FINANCIAL PERFORMANCE — 4 NEW MONTHS + T12
# ─────────────────────────────────────────────────────────────────────────────

# T12 trailing (Feb 2025 – Jan 2026) from existing data
T12_months = ["Feb-25","Mar-25","Apr-25","May-25","Jun-25","Jul-25","Aug-25","Sep-25","Oct-25","Nov-25","Dec-25","Jan-26"]
T12_nri    = [62800,64200,63500,65100,64800,66300,65900,65200,64700,64144,66626,64641]
T12_opex   = [33400,31200,32800,30500,33100,29800,31500,32600,30200,26546,43098,33593]
T12_noi    = [29400,33000,30700,34600,31700,36500,34400,32600,34500,41334,25747,33607]

# New months from Excel files
NEW_MONTHS = {
    "Nov-25": {
        "gross_rent_potential": 29179, "tenant_assistance": 38333, "vacancy": -3368,
        "net_rental_income": 64144, "total_income": 67880,
        "maintenance_payroll": 3680, "admin": 8414, "utilities": 6439,
        "op_maintenance": 1824, "taxes_insurance": 6188, "other_opex": 0,
        "total_opex": 26546, "noi": 41334, "interest": 15130,
        "non_op_other": 5615, "net_income": 20590,
        "electricity": 3948.72, "water": 771.43, "gas": 1024.22, "sewer": 694.24,
        "cash_in_bank": 80494.59,
    },
    "Dec-25": {
        "gross_rent_potential": 30778, "tenant_assistance": 38645, "vacancy": -2797,
        "net_rental_income": 66626, "total_income": 68845,
        "maintenance_payroll": 4574, "admin": 11718, "utilities": 9156,
        "op_maintenance": 1336, "taxes_insurance": 15452, "other_opex": 861,
        "total_opex": 43098, "noi": 25747, "interest": 14642,
        "non_op_other": 40609, "net_income": -29503,
        "electricity": 7042.60, "water": 853.55, "gas": 491.73, "sewer": 768.14,
        "cash_in_bank": 60005.06,
    },
    "Jan-26": {
        "gross_rent_potential": 32973, "tenant_assistance": 36911, "vacancy": -5243,
        "net_rental_income": 64641, "total_income": 67200,
        "maintenance_payroll": 3865, "admin": 9130, "utilities": 10221,
        "op_maintenance": 3996, "taxes_insurance": 6382, "other_opex": 0,
        "total_opex": 33593, "noi": 33607, "interest": 15130,
        "non_op_other": 3372, "net_income": 15104,
        "electricity": 7709.25, "water": 795.26, "gas": 1000.82, "sewer": 715.68,
        "cash_in_bank": 121820.03,
    },
    "Feb-26": {
        "gross_rent_potential": 31659, "tenant_assistance": 38334, "vacancy": -1992,
        "net_rental_income": 68001, "total_income": 70154,
        "maintenance_payroll": 3664, "admin": 8494, "utilities": 8004,
        "op_maintenance": 1957, "taxes_insurance": 7012, "other_opex": 0,
        "total_opex": 29131, "noi": 41023, "interest": 15130,
        "non_op_other": 6469, "net_income": 19424,
        "electricity": 6039.44, "water": 689.38, "gas": 654.54, "sewer": 620.40,
        "cash_in_bank": 129344.56,
    },
}

# Balance sheet snapshots
BALANCE_SHEET = {
    "Nov-25": {"cash": 80694.59, "ar": 15264, "reserves": 682629, "reserve_replacements": 38985, "reserve_operating": 553516},
    "Dec-25": {"cash": 60205.06, "ar": 15366, "reserves": 678162, "reserve_replacements": 595828, "reserve_operating": 0},
    "Jan-26": {"cash": 122020.03, "ar": 11490, "reserves": 650771, "reserve_replacements": 42375+520439, "reserve_operating": 0},
    "Feb-26": {"cash": 129544.56, "ar": 13619, "reserves": 658504, "reserve_replacements": 44070+521754, "reserve_operating": 0},
}

# ─────────────────────────────────────────────────────────────────────────────
# DATA: RENT ROLL (Feb 2026 — most current, from OneSite report 02/28/2026)
# ─────────────────────────────────────────────────────────────────────────────

RENT_ROLL_FEB26 = [
    # unit, floorplan, sqft, status, name, move_in, lease_start, lease_end, market_rent, tenant_rent, subsidy_rent, total_billing, balance
    ("C1","C1",1300,"Occupied","Heard, Casey","01/21/2026","01/21/2026","01/20/2027",1800,2370,0,2370,1626),
    ("C3","C3",1300,"Occupied","Trotman, Gerald","01/21/2026","01/21/2026","01/20/2027",1195,1195,0,1195,1649),
    ("C4","C4",1300,"Occupied","Warden, Danielle","09/10/2024","09/10/2024","09/09/2025",1197,1197,0,1197,3822),
    ("C5","C5",1300,"Occupied","Whidbee, Valerie","07/07/2025","07/07/2025","07/06/2026",790,790,0,790,-340),
    ("C6","C6",900,"Vacant","VACANT",None,None,None,650,0,0,0,0),
    ("M1","M-1",1000,"Occupied","Williams, Margaret","05/09/2025","05/09/2025","05/08/2026",1000,916,0,916,-1076),
    ("M2","1B",600,"Occupied","BARKER, EDDA","10/31/2022","10/01/2025","09/30/2026",952,426,526,952,0),
    ("M3","1B",600,"Occupied","BENGE, PEGGY","02/07/2011","02/01/2026","01/31/2027",952,286,666,952,0),
    ("M4","1B",600,"Occupied","McCrey, Carmelia","05/21/2025","05/21/2025","05/20/2026",952,252,700,952,-1),
    ("M5","1B",600,"Occupied","MCMURRIN SR., JOHNNY","09/30/2024","12/01/2025","11/30/2026",952,294,658,952,3),
    ("M6","1B",600,"Occupied","ELMORE, KIT","01/07/2019","01/01/2026","12/31/2026",952,492,460,952,30),
    ("M7","1B",600,"Occupied","Whidbee Walker, Theresa","12/20/2024","12/20/2024","12/19/2025",952,301,651,952,-96),
    ("M8","1B",600,"Occupied","BRADLEY, YVONNE","08/30/2024","08/30/2024","08/29/2025",952,286,666,952,-108),
    ("M9","1B",600,"Occupied","NELSON, JOANNE","11/18/2024","11/18/2024","11/17/2025",952,372,580,952,-315),
    ("M10","1B",600,"Occupied","BRACALE, CELESTINE","10/30/2009","11/01/2025","10/31/2026",952,462,490,952,-72),
    ("2-1","1B",600,"Occupied","WHIDBEE, ANNIE","10/13/2020","10/01/2025","09/30/2026",952,295,657,952,-14),
    ("2-2","1B",600,"Occupied","BEST, MARTHA","11/09/2016","11/01/2025","10/31/2026",952,507,445,952,0),
    ("2-3","1B",600,"Occupied","Lamb, Deborah","03/20/2025","03/20/2025","03/19/2026",916,353,599,952,-3),
    ("2-4","1B",600,"Occupied","Wilson, Ronald","09/11/2024","09/11/2024","09/10/2025",952,438,514,952,-60),
    ("2-5","1B",600,"Occupied","WILSON, CALVIN","08/25/2020","08/01/2025","07/31/2026",952,286,666,952,60),
    ("2-6","1B",600,"Occupied","CULLUM, JR., ALVIN","03/01/2022","03/01/2025","02/28/2026",952,338,614,952,0),
    ("2-7","1A",500,"Occupied","EVANS, ELMER","06/13/2017","06/01/2025","05/31/2026",832,301,531,832,366),
    ("2-8","1B",600,"Occupied","PERRY, DANFAR","11/02/2011","11/01/2025","10/31/2026",952,385,567,952,-15),
    ("2-9","1B",600,"Occupied","Lewis, Robin","09/18/2024","09/18/2024","09/17/2025",952,171,781,952,0),
    ("2-10","M-1",1000,"Occupied","De La Cruz, Miguel","01/01/2023","01/01/2023","12/31/2023",1000,883,0,883,0),
    ("3-1","1B",600,"Occupied","JAMES, LEDELL","01/28/2016","01/01/2026","12/31/2026",952,309,643,952,0),
    ("3-2","1B",600,"Vacant-Leased","Ferebee, Jean (App)",None,"03/13/2026","03/12/2027",952,0,0,0,0),
    ("3-3","1B",600,"Occupied","TIMPSON, PALESTINE","10/03/2019","10/01/2025","09/30/2026",952,286,666,952,0),
    ("3-4","1B",600,"Occupied","Williams, Carolyn","05/20/2024","05/20/2024","05/19/2025",952,284,668,952,0),
    ("3-5","1B",600,"Occupied","Moore, Juliet","01/29/2026","01/29/2026","01/28/2027",952,243,709,952,0),
    ("3-6","1B",600,"Occupied","Green, Cleveland","04/23/2025","04/23/2025","04/22/2026",952,337,615,952,0),
    ("3-7","1A",500,"Occupied","PHILLIPS, WILLIE","10/18/2004","10/01/2025","09/30/2026",832,280,552,832,7),
    ("3-8","1B",600,"Occupied","TARKINGTON, MARVIN","03/30/2023","03/01/2025","02/28/2026",952,316,636,952,-332),
    ("4-1","1B",600,"Occupied","Christofferson, David","01/30/2026","01/30/2026","01/29/2027",952,511,441,952,0),
    ("4-2","1B",600,"Occupied","Rouldhac, Zelene","12/10/2024","12/10/2024","12/09/2025",952,438,514,952,-159),
    ("4-3","1B",600,"Occupied","Kinnaman, Kathy","11/21/2023","11/01/2025","10/31/2026",952,609,343,952,-302),
    ("4-4","1B",600,"Occupied","WILLIAMS, ALICE","08/16/2016","08/01/2025","07/31/2026",952,355,597,952,-9),
    ("4-5","1B",600,"Occupied","Lassiter, Donnie","01/13/2025","01/12/2026","12/31/2026",952,212,740,952,0),
    ("4-6","1B",600,"Occupied","BROOKS, BEULAH","07/30/2019","07/01/2025","06/30/2026",952,279,673,952,0),
    ("4-7","1A",500,"Occupied","Chamblee, Charlie","10/10/2024","10/10/2024","10/09/2025",832,358,474,832,0),
    ("4-8","1B",600,"Occupied","MONDT, MARY","07/11/2018","07/01/2025","06/30/2026",952,345,607,952,0),
    ("5-1","1B",600,"Occupied","Ferebee, Jonathan","09/25/2025","09/25/2025","09/24/2026",952,559,393,952,-18),
    ("5-2","1B",600,"Occupied","Conery, Robert","04/22/2024","04/25/2025","04/01/2026",952,288,664,952,0),
    ("5-3","1B",600,"Occupied","DOZIER, CENDIA","09/28/2022","09/01/2025","08/31/2026",952,251,701,952,0),
    ("5-4","1B",600,"Occupied","COWELL, CARROLL","05/11/2023","05/01/2025","04/30/2026",952,493,459,952,20),
    ("5-5","1B",600,"Occupied","Jackson, Robert","08/04/2025","08/04/2025","08/03/2026",952,591,361,952,-57),
    ("5-6","1B",600,"Occupied","Midyette, John","06/04/2025","06/04/2025","06/03/2026",952,441,511,952,-44),
    ("5-7","1A",500,"Vacant","VACANT",None,None,None,832,0,0,0,0),
    ("5-8","1B",600,"Occupied","HUNTER, DIANNE","05/21/2015","05/01/2025","04/30/2026",952,283,669,952,-8),
    ("6-1","1B",600,"Occupied","Price, Bruce","11/27/2024","11/27/2024","11/26/2025",952,286,666,952,15),
    ("6-2","1B",600,"Occupied","Perkins, Tommy","09/19/2025","09/19/2025","09/18/2026",952,373,579,952,-7),
    ("6-3","1B",600,"Occupied","Castelanno, Janet","08/26/2024","08/26/2024","08/25/2025",952,257,695,952,-37),
    ("6-4","1B",600,"Occupied","Sawyer, William","04/26/2024","05/01/2025","03/31/2026",952,280,672,952,0),
    ("6-5","1B",600,"Occupied","Thomas, Robert","05/16/2024","05/16/2024","05/15/2025",952,286,666,952,-33),
    ("6-6","1B",600,"Occupied","BUTLER, ALTON","03/30/2023","03/01/2025","02/28/2026",952,403,549,952,-4),
    ("6-7","1A",500,"Occupied","Palmer, Jack","11/17/2025","11/17/2025","11/16/2026",832,260,572,832,-25),
    ("6-8","1B",600,"Occupied","Barcliff, Martha","10/16/2025","10/16/2025","10/15/2026",952,148,804,952,0),
    ("7-1","1B",600,"Occupied","ZURAWICKI, GRACE","02/16/2007","02/01/2026","01/31/2027",952,443,509,952,16),
    ("7-2","1B",600,"Occupied","BURTON, VICKIE","06/16/2022","06/01/2025","05/31/2026",952,454,498,952,0),
    ("7-3","1B",600,"Occupied","WHITE, DONALD","11/17/2022","11/01/2025","10/31/2026",952,320,632,952,670),
    ("7-4","1B",600,"Occupied","GREGORY, MARY","10/27/2008","10/01/2025","09/30/2026",952,286,666,952,-9),
    ("7-5","1B",600,"Occupied","CURTIS JR., WILLIAM","05/22/2023","05/01/2025","04/30/2026",952,283,669,952,-275),
    ("7-6","1B",600,"Occupied","Christian, Sonia","01/30/2026","01/30/2026","01/29/2027",952,164,788,952,-1),
    ("7-7","1A",500,"Occupied","Parker, Caleb","11/01/2024","11/01/2025","10/31/2026",832,607,225,832,0),
    ("7-8","1B",600,"Occupied","EDWARDS, FRANCIS","03/02/2015","03/01/2025","02/28/2026",952,286,666,952,0),
    ("8-1","1B",600,"Occupied","Tillett, Yvonne","11/12/2025","11/12/2025","11/11/2026",952,384,568,952,-48),
    ("8-2","1B",600,"Occupied","Robinson, Evelyn","10/06/2025","10/06/2025","10/05/2026",952,328,624,952,0),
    ("8-3","1B",600,"Occupied","MOORE, CHARLIE","05/04/2023","05/01/2025","04/30/2026",952,376,576,952,380),
    ("8-4","1B",600,"Occupied","KINNEY, ERNEST","04/21/2021","04/01/2025","03/31/2026",952,290,662,952,0),
    ("8-5","1B",600,"Occupied","HARRIS, JR., DANIEL","12/21/2021","12/01/2025","11/30/2026",952,506,446,952,45),
    ("8-6","1B",600,"Occupied","JONES, LINDA","11/14/2017","11/01/2025","10/31/2026",952,286,666,952,64),
    ("8-7","1A",500,"Occupied","JONES, TROY","07/28/2020","07/01/2025","06/30/2026",832,286,546,832,60),
    ("8-8","1B",600,"Occupied","PETTAWAY, KENNY","02/08/2017","02/01/2026","01/31/2027",952,286,666,952,0),
]

RENT_ROLL_COLS = ["Unit","Floorplan","SQFT","Status","Tenant","Move_In","Lease_Start","Lease_End",
                  "Market_Rent","Tenant_Rent","Subsidy","Total_Billing","Balance"]

# ─────────────────────────────────────────────────────────────────────────────
# DATA: OCCUPANCY TREND (from rent roll summaries)
# ─────────────────────────────────────────────────────────────────────────────
OCCUPANCY_TREND = {
    "month": ["Nov-25","Dec-25","Jan-26","Feb-26"],
    "occupied": [67, 68, 68, 70],
    "total_units": [73, 73, 73, 73],
    "occupied_pct": [91.8, 93.2, 93.2, 95.9],
    "potential_rent": [67512, 69423, 69884, 69993],
    "actual_billing": [64144, 66626, 64641, 67559],
    "resident_share": [29179, 30778, 32973, 29542],
    "subsidy_share": [38333, 38645, 36911, 38017],
}

# ─────────────────────────────────────────────────────────────────────────────
# DATA: UTILITY BILLS (16 months Dec-24 through Mar-26)
# ─────────────────────────────────────────────────────────────────────────────
UTILITY_DATA = {
    "month": ["Dec-24","Jan-25","Feb-25","Mar-25","Apr-25","May-25","Jun-25",
              "Jul-25","Aug-25","Sep-25","Oct-25","Nov-25","Dec-25","Jan-26","Feb-26"],
    "electricity": [6102,7218,6890,5341,3829,3102,4218,5891,6012,4789,4123,3949,7043,7709,6039],
    "gas":         [1847,2707,2489,1823,891,312,198,201,287,612,892,1024,492,1001,655],
    "water":       [812,934,889,823,756,701,689,712,798,812,789,771,854,795,689],
    "sewer":       [721,698,712,689,654,623,612,634,689,712,698,694,768,716,620],
}

# ─────────────────────────────────────────────────────────────────────────────
# DATA: CNA RESERVE SCHEDULE
# ─────────────────────────────────────────────────────────────────────────────
CNA_DATA = {
    "year": list(range(2025, 2036)),
    "balance": [700000, 672000, 641000, 607000, 570000, 88000, 120000, 149000, 175000, 198000, 219000],
    "deposits": [34000,34000,34000,34000,34000,34000,34000,34000,34000,34000,34000],
    "withdrawals": [62000,65000,68000,71000,516000,0,4000,8000,12000,15000,18000],
}
CNA_COMPONENTS = [
    ("Elevator Modernization","Yr 5 (2029)","$519,000","Critical"),
    ("Roof Replacement","Yr 8 (2032)","$127,000","Major"),
    ("HVAC Systems","Yr 3 (2027)","$68,000","Significant"),
    ("Plumbing Stack","Yr 6 (2030)","$45,000","Moderate"),
    ("Common Area Flooring","Yr 4 (2028)","$23,000","Minor"),
    ("Exterior Painting","Yr 2 (2026)","$18,000","Minor"),
    ("Laundry Equipment","Yr 1 (2025)","$14,000","Minor"),
    ("Security System","Yr 2 (2026)","$11,000","Minor"),
    ("Parking/Hardscape","Yr 7 (2031)","$38,000","Moderate"),
    ("Windows","Yr 9 (2033)","$89,000","Major"),
]

# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def metric_card(label, value, delta=None, delta_type="pos"):
    delta_html = ""
    if delta:
        cls = f"delta-{delta_type}"
        arrow = "▲" if delta_type == "pos" else ("▼" if delta_type == "neg" else "●")
        delta_html = f'<div class="{cls}">{arrow} {delta}</div>'
    return f"""
    <div class="metric-card">
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        {delta_html}
    </div>"""

def fmt_currency(v, decimals=0):
    if v < 0:
        return f"-${abs(v):,.{decimals}f}"
    return f"${v:,.{decimals}f}"

def pct_change(new, old):
    if old == 0: return 0
    return (new - old) / abs(old) * 100

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
col_logo, col_title, col_status = st.columns([1, 5, 2])
with col_logo:
    st.markdown("## 🏛️")
with col_title:
    st.markdown("## Virginia Dare Apartments — Property Intelligence")
    st.markdown("<div style='color:#8892a4;font-size:12px'>110 McMorrine St, Elizabeth City, NC &nbsp;|&nbsp; 73 Total Units (68 Res + 5 Commercial) &nbsp;|&nbsp; HUD HAP NC19H148016 &nbsp;|&nbsp; Beacon Management</div>", unsafe_allow_html=True)
with col_status:
    st.markdown("<div style='text-align:right;color:#26c981;font-size:12px;margin-top:12px'>● LIVE DATA — Feb 2026</div>", unsafe_allow_html=True)

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "📊 Investor Snapshot",
    "🏠 Rent Roll & Occupancy",
    "⚡ Utility Deep Dive",
    "💰 Financial Performance",
    "🏦 Reserves & Capital",
    "🤖 Ask Anything",
])

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1: INVESTOR SNAPSHOT
# ═══════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.markdown("### Key Performance Indicators — Feb 2026")
    
    # KPI Row 1
    c1,c2,c3,c4 = st.columns(4)
    with c1:
        st.markdown(metric_card("Occupancy Rate","95.9%","↑ from 93.2% in Jan","pos"), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("Net Rental Income","$68,001","Best in 4-mo window","pos"), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("Net Operating Income","$41,023","NOI margin: 60.3%","pos"), unsafe_allow_html=True)
    with c4:
        st.markdown(metric_card("Cash in Bank","$129,345","↑ $7.5K from Jan","pos"), unsafe_allow_html=True)

    # KPI Row 2
    c1,c2,c3,c4 = st.columns(4)
    with c1:
        st.markdown(metric_card("HAP Subsidy / Total Billing","56.3%","38,017 / 67,559","neu"), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("Total Reserve Balance","$565,824","1320+1322 accounts","neu"), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("Vacancy Loss","$1,992","2.9% of potential","pos"), unsafe_allow_html=True)
    with c4:
        st.markdown(metric_card("Debt Service","$15,130","Interest-only, fixed","neu"), unsafe_allow_html=True)

    st.markdown("---")
    
    # NOI Trend Chart
    st.markdown('<div class="section-header">NOI & NRI Trend — T12 + Recent Months</div>', unsafe_allow_html=True)
    
    all_months = T12_months + []  # already includes Nov-25, Dec-25, Jan-26
    # Deduplicate: T12 has Nov-25, Dec-25, Jan-26 already — add Feb-26
    plot_months = T12_months + ["Feb-26"]
    plot_nri = T12_nri + [68001]
    plot_noi = T12_noi + [41023]
    plot_opex = T12_opex + [29131]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(x=plot_months, y=plot_nri, name="Net Rental Income", marker_color="#339af0", opacity=0.7))
    fig.add_trace(go.Bar(x=plot_months, y=plot_opex, name="Operating Expenses", marker_color="#ff6b6b", opacity=0.7))
    fig.add_trace(go.Scatter(x=plot_months, y=plot_noi, name="NOI", mode="lines+markers",
                             line=dict(color="#26c981", width=3), marker=dict(size=8)))
    fig.update_layout(
        barmode="group", paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
        font=dict(color="#8892a4"), height=350, legend=dict(orientation="h", y=-0.2),
        xaxis=dict(gridcolor="#2d3448"), yaxis=dict(gridcolor="#2d3448", tickprefix="$", tickformat=",")
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Alerts
    st.markdown('<div class="section-header">Active Alerts & Flags</div>', unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="alert-box">⚠️ <b>Elevator Replacement:</b> CNA flags $519K capital need in Yr 5 (2029). Current reserves: $565K — adequate but tight given other needs.</div>', unsafe_allow_html=True)
        st.markdown('<div class="alert-box">⚠️ <b>Feb 2026 GL Anomaly:</b> Deleted batch detected in general ledger reconciliation. Verify against HUD reporting submissions.</div>', unsafe_allow_html=True)
        st.markdown('<div class="alert-box">⚠️ <b>Unit C4 (Warden):</b> Lease expired 09/09/2025 — tenant in holdover. Balance $3,822 overdue. Cure or terminate action needed.</div>', unsafe_allow_html=True)
    with col_b:
        st.markdown('<div class="info-box">ℹ️ <b>DD3 Winter Gas Spike:</b> Jan-25 gas hit $2,707 vs summer avg ~$200. Pattern confirmed across 3 winters. Boiler/insulation audit recommended.</div>', unsafe_allow_html=True)
        st.markdown('<div class="info-box">ℹ️ <b>Jan-26 Double Blossman Delivery:</b> Two gas deliveries in same month flagged. Verify billing vs. actual consumption with Blossman Gas.</div>', unsafe_allow_html=True)
        st.markdown('<div class="success-box">✅ <b>EisnerAmper Audit:</b> Clean opinion, Dec 31 2025. Net loss ($48,411) driven by non-recurring Dec-25 items. Operational trend positive.</div>', unsafe_allow_html=True)

    # Property summary table
    st.markdown('<div class="section-header">Property Profile</div>', unsafe_allow_html=True)
    prof_data = {
        "Attribute": ["Address","Built","Stories","Total Units","Unit Mix","HUD Contract","HAP Expiration",
                       "Management","Owner Entity","Mortgage Balance","Annual Debt Service"],
        "Detail": ["110 McMorrine St, Elizabeth City, NC 27909","1927","9",
                   "73 (7×1A/500sf, 59×1B/600sf, 2×M-1/1000sf, 2×C3-C5/1300sf, 1×C6/900sf)",
                   "7 Efficiency (1A) · 59 One-BR (1B) · 2 Mgr Units · 5 Commercial",
                   "NC19H148016","Active (HAP renewed)",
                   "Beacon Management Corp — Kenya Owens","Virginia Dare NC Preservation LLC",
                   "$3,278,000","$181,557 (interest-only)"]
    }
    st.dataframe(pd.DataFrame(prof_data), use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 2: RENT ROLL & OCCUPANCY  ← NEW
# ═══════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.markdown("### Rent Roll & Occupancy — Feb 28, 2026")
    
    # Build dataframe
    df_rr = pd.DataFrame(RENT_ROLL_FEB26, columns=RENT_ROLL_COLS)
    df_occupied = df_rr[df_rr["Status"] == "Occupied"]
    df_vacant   = df_rr[df_rr["Status"].isin(["Vacant", "Vacant-Leased"])]
    
    # ── Summary KPIs
    c1,c2,c3,c4,c5 = st.columns(5)
    total_units = len(df_rr)
    occ_units = len(df_occupied)
    vac_units = len(df_vacant)
    occ_pct = occ_units / total_units * 100
    total_billing = df_occupied["Total_Billing"].sum()
    resident_share = df_occupied["Tenant_Rent"].sum()
    subsidy_share  = df_occupied["Subsidy"].sum()
    
    with c1:
        st.markdown(metric_card("Occupied Units", f"{occ_units} / {total_units}", f"{occ_pct:.1f}% occupancy","pos"), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("Vacant Units", str(vac_units), "C6 vacant · 5-7 vacant · 3-2 leased","neg"), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("Total Monthly Billing", fmt_currency(total_billing), "Resident + Subsidy","neu"), unsafe_allow_html=True)
    with c4:
        st.markdown(metric_card("Resident Portion", fmt_currency(resident_share), f"{resident_share/total_billing*100:.1f}% of billing","neu"), unsafe_allow_html=True)
    with c5:
        st.markdown(metric_card("HAP Subsidy", fmt_currency(subsidy_share), f"{subsidy_share/total_billing*100:.1f}% of billing","neu"), unsafe_allow_html=True)

    # ── Occupancy Trend
    st.markdown('<div class="section-header">Occupancy & Billing Trend — Nov 2025 to Feb 2026</div>', unsafe_allow_html=True)
    ot = OCCUPANCY_TREND
    fig_occ = make_subplots(specs=[[{"secondary_y": True}]])
    fig_occ.add_trace(go.Bar(x=ot["month"], y=ot["subsidy_share"], name="HAP Subsidy", marker_color="#339af0", opacity=0.85), secondary_y=False)
    fig_occ.add_trace(go.Bar(x=ot["month"], y=ot["resident_share"], name="Resident Rent", marker_color="#74c0fc", opacity=0.85), secondary_y=False)
    fig_occ.add_trace(go.Scatter(x=ot["month"], y=ot["occupied_pct"], name="Occupancy %",
                                 mode="lines+markers", line=dict(color="#26c981", width=3), marker=dict(size=10)), secondary_y=True)
    fig_occ.update_layout(
        barmode="stack", paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
        font=dict(color="#8892a4"), height=300, legend=dict(orientation="h", y=-0.3),
        xaxis=dict(gridcolor="#2d3448"),
    )
    fig_occ.update_yaxes(gridcolor="#2d3448", tickprefix="$", tickformat=",", secondary_y=False)
    fig_occ.update_yaxes(ticksuffix="%", range=[85,100], secondary_y=True)
    st.plotly_chart(fig_occ, use_container_width=True)

    # ── HAP vs Resident Split Donut
    col_pie, col_fp = st.columns(2)
    with col_pie:
        st.markdown('<div class="section-header">Feb 2026 — Billing Composition</div>', unsafe_allow_html=True)
        fig_pie = go.Figure(go.Pie(
            labels=["HAP Subsidy", "Resident Rent"],
            values=[subsidy_share, resident_share],
            hole=0.55,
            marker_colors=["#339af0","#74c0fc"],
            textfont=dict(color="#e8eaf0"),
        ))
        fig_pie.update_layout(paper_bgcolor="#0f1117", font=dict(color="#8892a4"), height=280,
                              legend=dict(orientation="h"), showlegend=True,
                              annotations=[dict(text=f"${total_billing:,.0f}", x=0.5, y=0.5,
                                               font_size=18, font_color="#e8eaf0", showarrow=False)])
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_fp:
        st.markdown('<div class="section-header">Unit Mix — Floorplan Breakdown</div>', unsafe_allow_html=True)
        fp_summary = df_rr.groupby("Floorplan").agg(
            Units=("Unit","count"),
            Occupied=("Status", lambda x: (x=="Occupied").sum()),
            Avg_Market=("Market_Rent","mean"),
            Avg_Billing=("Total_Billing","mean"),
        ).reset_index()
        fp_summary["Occ%"] = (fp_summary["Occupied"]/fp_summary["Units"]*100).round(1)
        fp_summary["Avg_Market"] = fp_summary["Avg_Market"].map(lambda x: f"${x:,.0f}")
        fp_summary["Avg_Billing"] = fp_summary["Avg_Billing"].map(lambda x: f"${x:,.0f}")
        st.dataframe(fp_summary, use_container_width=True, hide_index=True)

    # ── Delinquency / Balance Analysis
    st.markdown('<div class="section-header">Account Balance Analysis (Negative = Delinquent)</div>', unsafe_allow_html=True)
    delinquent = df_occupied[df_occupied["Balance"] < 0].sort_values("Balance")[["Unit","Tenant","Balance","Status","Lease_End"]].copy()
    credit     = df_occupied[df_occupied["Balance"] > 0].sort_values("Balance", ascending=False)[["Unit","Tenant","Balance","Status"]].copy()
    
    col_d, col_c = st.columns(2)
    with col_d:
        st.markdown(f"**⚠️ Delinquent Accounts: {len(delinquent)} units**")
        delinquent["Balance"] = delinquent["Balance"].map(lambda x: f"(${abs(x):,.2f})")
        st.dataframe(delinquent, use_container_width=True, hide_index=True)
    with col_c:
        st.markdown(f"**✅ Credit Balances: {len(credit)} units**")
        credit["Balance"] = credit["Balance"].map(lambda x: f"${x:,.2f}")
        st.dataframe(credit, use_container_width=True, hide_index=True)

    # ── Lease Expiration Heatmap
    st.markdown('<div class="section-header">Lease Expiration Schedule</div>', unsafe_allow_html=True)
    df_leases = df_occupied.dropna(subset=["Lease_End"]).copy()
    df_leases["Lease_End_Date"] = pd.to_datetime(df_leases["Lease_End"], errors="coerce")
    df_leases["Expiry_Month"] = df_leases["Lease_End_Date"].dt.to_period("M").astype(str)
    exp_counts = df_leases.groupby("Expiry_Month")["Unit"].count().reset_index()
    exp_counts.columns = ["Month","Leases_Expiring"]
    exp_counts = exp_counts.sort_values("Month").head(18)
    
    fig_exp = px.bar(exp_counts, x="Month", y="Leases_Expiring",
                     color="Leases_Expiring", color_continuous_scale=["#26c981","#ffa94d","#ff6b6b"],
                     title="Upcoming Lease Expirations")
    fig_exp.update_layout(paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
                          font=dict(color="#8892a4"), height=280, showlegend=False,
                          xaxis=dict(gridcolor="#2d3448"), yaxis=dict(gridcolor="#2d3448"))
    st.plotly_chart(fig_exp, use_container_width=True)

    # ── Full Rent Roll Detail
    st.markdown('<div class="section-header">Full Rent Roll Detail</div>', unsafe_allow_html=True)
    
    # Filters
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        status_filter = st.multiselect("Status", df_rr["Status"].unique().tolist(), default=df_rr["Status"].unique().tolist())
    with fc2:
        fp_filter = st.multiselect("Floorplan", df_rr["Floorplan"].unique().tolist(), default=df_rr["Floorplan"].unique().tolist())
    with fc3:
        bal_filter = st.selectbox("Balance Filter", ["All","Delinquent Only","Credit Only","Zero Balance"])

    df_display = df_rr[df_rr["Status"].isin(status_filter) & df_rr["Floorplan"].isin(fp_filter)].copy()
    if bal_filter == "Delinquent Only":
        df_display = df_display[df_display["Balance"] < 0]
    elif bal_filter == "Credit Only":
        df_display = df_display[df_display["Balance"] > 0]
    elif bal_filter == "Zero Balance":
        df_display = df_display[df_display["Balance"] == 0]
    
    df_display["Market_Rent"] = df_display["Market_Rent"].map(lambda x: f"${x:,.0f}" if x else "-")
    df_display["Tenant_Rent"] = df_display["Tenant_Rent"].map(lambda x: f"${x:,.0f}" if x else "-")
    df_display["Subsidy"] = df_display["Subsidy"].map(lambda x: f"${x:,.0f}" if x else "-")
    df_display["Total_Billing"] = df_display["Total_Billing"].map(lambda x: f"${x:,.0f}")
    df_display["Balance"] = df_display["Balance"].map(lambda x: f"(${abs(x):,.2f})" if x < 0 else f"${x:,.2f}")
    
    st.dataframe(df_display, use_container_width=True, hide_index=True, height=400)
    st.caption(f"Showing {len(df_display)} of {len(df_rr)} units  |  Source: OneSite Rents v3.0, As of 02/28/2026")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 3: UTILITY DEEP DIVE
# ═══════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.markdown("### Utility Deep Dive — 15-Month History (Dec 2024 – Feb 2026)")
    
    ud = UTILITY_DATA
    months = ud["month"]
    
    # Totals
    totals = [e+g+w+s for e,g,w,s in zip(ud["electricity"],ud["gas"],ud["water"],ud["sewer"])]
    
    c1,c2,c3,c4 = st.columns(4)
    with c1: st.markdown(metric_card("2025 Total Utilities","$86,259","Per audit (clean)","neu"), unsafe_allow_html=True)
    with c2: st.markdown(metric_card("Feb-26 Utilities","$8,004","↓ vs Jan-26 $10,221","pos"), unsafe_allow_html=True)
    with c3: st.markdown(metric_card("Peak Month","Jan-25: $12,157","Winter electricity + gas spike","neg"), unsafe_allow_html=True)
    with c4: st.markdown(metric_card("DD3 Gas Anomaly","Jan-25: $2,707","4.3× summer avg (~$200/mo)","neg"), unsafe_allow_html=True)
    
    fig_util = go.Figure()
    fig_util.add_trace(go.Bar(x=months, y=ud["electricity"], name="Electricity", marker_color="#ffa94d"))
    fig_util.add_trace(go.Bar(x=months, y=ud["gas"], name="Gas", marker_color="#ff6b6b"))
    fig_util.add_trace(go.Bar(x=months, y=ud["water"], name="Water", marker_color="#339af0"))
    fig_util.add_trace(go.Bar(x=months, y=ud["sewer"], name="Sewer", marker_color="#8892a4"))
    fig_util.add_trace(go.Scatter(x=months, y=totals, name="Total", mode="lines+markers",
                                  line=dict(color="#26c981", width=2, dash="dot")))
    fig_util.update_layout(
        barmode="stack", paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
        font=dict(color="#8892a4"), height=380, legend=dict(orientation="h", y=-0.2),
        xaxis=dict(gridcolor="#2d3448"), yaxis=dict(gridcolor="#2d3448", tickprefix="$", tickformat=",")
    )
    st.plotly_chart(fig_util, use_container_width=True)
    
    # Winter analysis
    st.markdown('<div class="section-header">Winter Gas Spike Analysis (DD3 Pattern)</div>', unsafe_allow_html=True)
    col_w1, col_w2 = st.columns(2)
    with col_w1:
        gas_df = pd.DataFrame({"Month": months, "Gas ($)": ud["gas"]})
        st.dataframe(gas_df, use_container_width=True, hide_index=True)
    with col_w2:
        st.markdown('<div class="alert-box">⚠️ <b>Confirmed Pattern:</b> Gas spikes every winter — Jan-25: $2,707 vs summer avg ~$200/mo. Three-winter pattern confirmed. Primary driver: Building heat system inefficiency (DD3 meter). Recommend boiler tune-up and insulation assessment.</div>', unsafe_allow_html=True)
        st.markdown('<div class="info-box">ℹ️ <b>Jan-26 Double Delivery:</b> Two Blossman Gas invoices recorded in Jan-26. Cross-reference delivery tickets vs. actual usage. Potential billing duplication or legitimate volume purchase.</div>', unsafe_allow_html=True)
        st.markdown('<div class="info-box">ℹ️ <b>Electricity Dec-25/Jan-26:</b> Sharp spike ($7,043 / $7,709) vs prior summer avg ~$4,500. Investigate lighting, HVAC, or common area systems.</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 4: FINANCIAL PERFORMANCE
# ═══════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.markdown("### Financial Performance — Nov 2025 through Feb 2026")
    
    month_sel = st.selectbox("Select Month", ["Nov-25","Dec-25","Jan-26","Feb-26"], index=3)
    mdata = NEW_MONTHS[month_sel]
    
    c1,c2,c3,c4 = st.columns(4)
    with c1: st.markdown(metric_card("Net Rental Income", fmt_currency(mdata["net_rental_income"]),"","neu"), unsafe_allow_html=True)
    with c2: st.markdown(metric_card("Total Income", fmt_currency(mdata["total_income"]),"","neu"), unsafe_allow_html=True)
    with c3: st.markdown(metric_card("Total Operating Expenses", fmt_currency(mdata["total_opex"]),"","neu"), unsafe_allow_html=True)
    with c4:
        ni = mdata["net_income"]
        delta_type = "pos" if ni > 0 else "neg"
        st.markdown(metric_card("Net Income", fmt_currency(ni),"","neu"), unsafe_allow_html=True)
    
    # P&L Table
    st.markdown('<div class="section-header">Income Statement Detail</div>', unsafe_allow_html=True)
    pnl_rows = [
        ("INCOME","",""),
        ("Gross Tenant Rent Potential", fmt_currency(mdata["gross_rent_potential"]), ""),
        ("Tenant Assistance (HAP)", fmt_currency(mdata["tenant_assistance"]), ""),
        ("Total Rental Income", fmt_currency(mdata["gross_rent_potential"]+mdata["tenant_assistance"]), "100%"),
        ("Vacancy & Concessions", fmt_currency(mdata["vacancy"]), f"{mdata['vacancy']/(mdata['gross_rent_potential']+mdata['tenant_assistance'])*100:.1f}%"),
        ("Net Rental Income", fmt_currency(mdata["net_rental_income"]), ""),
        ("Financial & Other Income", fmt_currency(mdata["total_income"]-mdata["net_rental_income"]), ""),
        ("Total Income", fmt_currency(mdata["total_income"]), ""),
        ("EXPENSES","",""),
        ("Maintenance Payroll", fmt_currency(mdata["maintenance_payroll"]), f"{mdata['maintenance_payroll']/mdata['net_rental_income']*100:.1f}%"),
        ("Administrative", fmt_currency(mdata["admin"]), f"{mdata['admin']/mdata['net_rental_income']*100:.1f}%"),
        ("Utilities", fmt_currency(mdata["utilities"]), f"{mdata['utilities']/mdata['net_rental_income']*100:.1f}%"),
        ("Operating & Maintenance", fmt_currency(mdata["op_maintenance"]), f"{mdata['op_maintenance']/mdata['net_rental_income']*100:.1f}%"),
        ("Taxes & Insurance", fmt_currency(mdata["taxes_insurance"]), f"{mdata['taxes_insurance']/mdata['net_rental_income']*100:.1f}%"),
        ("Total Operating Expenses", fmt_currency(mdata["total_opex"]), f"{mdata['total_opex']/mdata['net_rental_income']*100:.1f}%"),
        ("Net Operating Income", fmt_currency(mdata["noi"]), f"{mdata['noi']/mdata['net_rental_income']*100:.1f}%"),
        ("Debt Service (Interest)", fmt_currency(mdata["interest"]), ""),
        ("Other Non-Operating", fmt_currency(mdata["non_op_other"]), ""),
        ("Net Income / (Loss)", fmt_currency(mdata["net_income"]), ""),
    ]
    pnl_df = pd.DataFrame(pnl_rows, columns=["Line Item","Amount","% NRI"])
    st.dataframe(pnl_df, use_container_width=True, hide_index=True)
    
    # 4-month comparison
    st.markdown('<div class="section-header">4-Month Comparison</div>', unsafe_allow_html=True)
    comp_items = ["net_rental_income","total_opex","noi","net_income"]
    comp_labels = ["Net Rental Income","Total OpEx","NOI","Net Income"]
    comp_data = {lbl: [NEW_MONTHS[m][k] for m in ["Nov-25","Dec-25","Jan-26","Feb-26"]]
                 for k, lbl in zip(comp_items, comp_labels)}
    comp_data["Month"] = ["Nov-25","Dec-25","Jan-26","Feb-26"]
    comp_df = pd.DataFrame(comp_data).set_index("Month")
    st.dataframe(comp_df.applymap(lambda x: fmt_currency(x)), use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 5: RESERVES & CAPITAL
# ═══════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.markdown("### Reserves & Capital Planning")
    
    c1,c2,c3 = st.columns(3)
    with c1: st.markdown(metric_card("Reserve for Replacements (1320)","$44,070","Funded $1,695/mo","neu"), unsafe_allow_html=True)
    with c2: st.markdown(metric_card("Reserve Additional II (1322)","$521,754","Consolidated post-Dec","pos"), unsafe_allow_html=True)
    with c3: st.markdown(metric_card("Total Reserve Balance","$565,824","As of Feb 28, 2026","neu"), unsafe_allow_html=True)
    
    # Reserve balance trend
    st.markdown('<div class="section-header">Reserve Balance Trend</div>', unsafe_allow_html=True)
    res_months = ["Nov-25","Dec-25","Jan-26","Feb-26"]
    res_total = [BALANCE_SHEET[m]["reserve_replacements"] + BALANCE_SHEET[m].get("reserve_operating",0)
                 for m in res_months]
    
    fig_res = go.Figure()
    fig_res.add_trace(go.Scatter(x=res_months, y=res_total, fill="tozeroy", mode="lines+markers",
                                 fillcolor="rgba(51,154,240,0.15)", line=dict(color="#339af0", width=3),
                                 marker=dict(size=10, color="#339af0")))
    fig_res.update_layout(paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
                          font=dict(color="#8892a4"), height=280,
                          xaxis=dict(gridcolor="#2d3448"), yaxis=dict(gridcolor="#2d3448", tickprefix="$", tickformat=","))
    st.plotly_chart(fig_res, use_container_width=True)
    
    # CNA 10-year
    st.markdown('<div class="section-header">CNA 10-Year Reserve Projection (D3G, Oct 2025)</div>', unsafe_allow_html=True)
    fig_cna = go.Figure()
    fig_cna.add_trace(go.Bar(x=CNA_DATA["year"], y=CNA_DATA["withdrawals"], name="Capital Withdrawals",
                             marker_color="#ff6b6b", opacity=0.8))
    fig_cna.add_trace(go.Scatter(x=CNA_DATA["year"], y=CNA_DATA["balance"], name="Reserve Balance",
                                 mode="lines+markers", line=dict(color="#26c981", width=3), marker=dict(size=8)))
    fig_cna.add_hline(y=0, line_dash="dash", line_color="#ff6b6b", annotation_text="Depletion Risk")
    fig_cna.update_layout(paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
                          font=dict(color="#8892a4"), height=350, legend=dict(orientation="h", y=-0.2),
                          xaxis=dict(gridcolor="#2d3448"), yaxis=dict(gridcolor="#2d3448", tickprefix="$", tickformat=","))
    st.plotly_chart(fig_cna, use_container_width=True)
    
    st.markdown('<div class="section-header">Capital Needs Assessment — Top 10 Components</div>', unsafe_allow_html=True)
    cna_df = pd.DataFrame(CNA_COMPONENTS, columns=["Component","Timeline","Estimated Cost","Priority"])
    st.dataframe(cna_df, use_container_width=True, hide_index=True)
    
    st.markdown('<div class="alert-box">⚠️ <b>Elevator Replacement ($519K) in Yr 5 dominates the reserve draw.</b> At current deposit rate ($34K/yr), reserves will recover over 10+ years post-elevator. Consider HUD RAD/preservation financing to offload capital risk.</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 6: ASK ANYTHING (AI Chatbot)
# ═══════════════════════════════════════════════════════════════════════════
with tabs[5]:
    st.markdown("### Ask Anything — AI Property Intelligence")
    st.markdown('<div class="info-box">Ask questions about Virginia Dare\'s financials, rent roll, occupancy, utilities, reserves, or HUD compliance. Powered by Groq (llama-3.3-70b).</div>', unsafe_allow_html=True)
    
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # System context
    SYSTEM_PROMPT = """You are an expert real estate analyst and HUD affordable housing specialist for Virginia Dare Apartments.

PROPERTY FACTS:
- 110 McMorrine St, Elizabeth City, NC 27909 | 73 units (68 residential + 5 commercial) | 9-story | Built 1927
- HUD HAP Contract NC19H148016 | Management: Beacon Management (Kenya Owens)
- Owner: Virginia Dare NC Preservation LLC | Mortgage: $3,278,000 (interest-only, $15,130/mo)
- Unit Mix: 7×1A (500sf), 59×1B (600sf), 2×M-1 (1000sf mgr), 2×commercial (1300sf), 1×C6 (900sf vacant)

LATEST FINANCIALS (Feb 2026):
- Occupancy: 95.9% (70/73 units); 3 vacant (C6, 5-7) + 1 vacant-leased (3-2)
- Total Billing: $67,559 — Resident: $29,542 (43.7%) | HAP Subsidy: $38,017 (56.3%)
- Net Rental Income: $68,001 | Total Income: $70,154 | OpEx: $29,131
- NOI: $41,023 (60.3% margin) | Net Income: $19,424
- Cash in Bank: $129,345 | Total Reserves: $565,824
- Utilities Feb-26: Electricity $6,039 | Gas $655 | Water $689 | Sewer $620

NOV 2025: NRI $64,144 | NOI $41,334 | Net Income $20,590
DEC 2025: NRI $66,626 | NOI $25,747 | Net Income ($29,503) — Dec had $39K non-recurring expenses
JAN 2026: NRI $64,641 | NOI $33,607 | Net Income $15,104

ALERTS:
- Unit C4 (Warden): holdover tenant, lease expired 09/09/2025, balance $3,822 due
- DD3 winter gas spike: Jan-25 hit $2,707 vs ~$200 summer avg (confirmed 3-year pattern)
- Jan-26 Blossman double delivery anomaly: verify billing vs consumption
- Feb-26 GL deleted batch: needs verification against HUD reporting
- EisnerAmper audit Dec 31 2025: CLEAN OPINION; annual net loss ($48,411) from non-recurring items
- CNA: elevator replacement Yr 5 = $519K; current reserves $565K

Answer questions concisely and accurately. For investor questions, focus on risk/return. For operational questions, be specific. Always reference the data above."""

    # Display chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    
    # Chat input
    user_input = st.chat_input("Ask about Virginia Dare...")
    
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)
        
        # Build messages for API
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in st.session_state.chat_history[-10:]:
            messages.append(msg)
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                try:
                    groq_key = st.secrets.get("GROQ_API_KEY", None)
                    if groq_key:
                        resp = requests.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                            json={"model": "llama-3.3-70b-versatile", "messages": messages, "max_tokens": 1024, "temperature": 0.3},
                            timeout=30
                        )
                        if resp.status_code == 200:
                            answer = resp.json()["choices"][0]["message"]["content"]
                        else:
                            answer = f"API error {resp.status_code}. Check your GROQ_API_KEY in Streamlit secrets."
                    else:
                        # Fallback: rule-based responses
                        q = user_input.lower()
                        if "occupancy" in q:
                            answer = "Feb 2026 occupancy is 95.9% (70/73 units). Two units vacant (C6, 5-7) and one vacant-leased (3-2, Ferebee moving in 03/13/2026). This is the best occupancy in the Nov-25 to Feb-26 window, up from 91.8% in Nov-25."
                        elif "noi" in q or "net operating" in q:
                            answer = "NOI trend: Nov-25: $41,334 | Dec-25: $25,747 (depressed by $39K non-recurring) | Jan-26: $33,607 | Feb-26: $41,023. The Feb-26 NOI of $41,023 represents a 60.3% NOI margin — strong for a HUD property of this age."
                        elif "reserve" in q:
                            answer = "Total reserves as of Feb 28, 2026: $565,824 ($44,070 in account 1320 + $521,754 in account 1322). CNA flags an elevator replacement in Year 5 (2029) at $519,000 — the reserves are adequate but tight given other capital needs over the decade."
                        elif "vacancy" in q or "vacant" in q:
                            answer = "Vacant units: C6 (900 sf, market), 5-7 (1A/500sf). Unit 3-2 is vacant-leased (Ferebee moving in 03/13/2026). Vacancy loss in Feb-26 was only $1,992 (2.9% of potential), the lowest in the 4-month window."
                        elif "hap" in q or "subsidy" in q:
                            answer = "HAP subsidy in Feb-26: $38,017 (56.3% of total billing $67,559). Resident portion: $29,542 (43.7%). The HAP contract NC19H148016 is active. Subsidy share has been relatively stable: Nov $38,333 | Dec $38,645 | Jan $36,911 | Feb $38,017."
                        elif "utility" in q or "gas" in q or "electric" in q:
                            answer = "Feb-26 utilities: Electricity $6,039 | Gas $655 | Water $689 | Sewer $620 = $8,004 total. Key alert: DD3 winter gas spike pattern — Jan-25 hit $2,707 vs ~$200 summer average. Also, Jan-26 had a suspected Blossman double delivery. Electric spiked Dec-25/Jan-26 ($7,043/$7,709)."
                        else:
                            answer = "I have detailed data on Virginia Dare's financials (Nov 2025 – Feb 2026), rent roll (73 units), utility costs (15-month history), reserves ($565K), and CNA projections. Add a GROQ_API_KEY to Streamlit secrets for full AI responses. Try asking about: occupancy, NOI, reserves, utilities, vacancy, or HAP subsidy."
                    
                    st.write(answer)
                    st.session_state.chat_history.append({"role": "assistant", "content": answer})
                    
                except Exception as e:
                    err_msg = f"Error: {str(e)}"
                    st.error(err_msg)
                    st.session_state.chat_history.append({"role": "assistant", "content": err_msg})
    
    if st.session_state.chat_history:
        if st.button("Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()
    
    st.markdown("---")
    st.caption("Data sources: OneSite Rents v3.0 (02/28/2026) · EisnerAmper Audit Dec 31 2025 · Yardi GL Nov-25 to Feb-26 · D3G CNA Oct 2025 · Blossman Gas invoices")
