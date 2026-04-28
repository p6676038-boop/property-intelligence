import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from groq import Groq
import PyPDF2
import io
import os

st.set_page_config(
    page_title="Property Intelligence System",
    page_icon="🏢",
    layout="wide"
)

# ---- STYLING ----
st.markdown("""
<style>
.main-header {font-size: 2rem; font-weight: 600; color: #1a1a2e;}
.sub-header {font-size: 0.9rem; color: #666; margin-bottom: 2rem;}
.metric-card {background: #f8f9fa; padding: 1rem; border-radius: 8px; border-left: 4px solid #378ADD;}
.alert-red {background: #FCEBEB; padding: 0.8rem; border-radius: 8px; border-left: 4px solid #E24B4A; margin: 0.5rem 0;}
.alert-yellow {background: #FAEEDA; padding: 0.8rem; border-radius: 8px; border-left: 4px solid #EF9F27; margin: 0.5rem 0;}
.alert-green {background: #EAF3DE; padding: 0.8rem; border-radius: 8px; border-left: 4px solid #1D9E75; margin: 0.5rem 0;}
</style>
""", unsafe_allow_html=True)

# ---- SESSION STATE ----
if "messages" not in st.session_state:
    st.session_state.messages = []
if "documents" not in st.session_state:
    st.session_state.documents = {}
if "groq_key" not in st.session_state:
    st.session_state.groq_key = ""

# ---- SIDEBAR ----
with st.sidebar:
    st.image("https://img.icons8.com/color/96/building.png", width=60)
    st.title("Property Intelligence")
    st.markdown("---")
    
    # API Key
    api_key = st.text_input("🔑 Groq API Key", type="password", value=st.session_state.groq_key)
    if api_key:
        st.session_state.groq_key = api_key
    
    st.markdown("---")
    
    # Property selector
    property_name = st.selectbox("🏢 Select Property", [
        "Virginia Dare Apartments",
        "Add more properties..."
    ])
    
    st.markdown("---")
    
    # File uploader
    st.subheader("📁 Upload Documents")
    uploaded_files = st.file_uploader(
        "Upload PDF, Excel, CSV files",
        accept_multiple_files=True,
        type=["pdf", "xlsx", "xls", "csv"]
    )
    
    if uploaded_files:
        for file in uploaded_files:
            if file.name not in st.session_state.documents:
                content = ""
                if file.name.endswith(".pdf"):
                    try:
                        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
                        for page in pdf_reader.pages:
                            content += page.extract_text() + "\n"
                    except:
                        content = f"PDF file: {file.name}"
                elif file.name.endswith((".xlsx", ".xls")):
                    try:
                        xl = pd.ExcelFile(file)
                        for sheet in xl.sheet_names:
                            df = xl.parse(sheet)
                            content += f"\n--- Sheet: {sheet} ---\n"
                            content += df.to_string() + "\n"
                    except:
                        content = f"Excel file: {file.name}"
                elif file.name.endswith(".csv"):
                    try:
                        df = pd.read_csv(file)
                        content = df.to_string()
                    except:
                        content = f"CSV file: {file.name}"
                
                st.session_state.documents[file.name] = content
                st.success(f"✅ {file.name}")
    
    if st.session_state.documents:
        st.markdown(f"**{len(st.session_state.documents)} files loaded**")
        for fname in st.session_state.documents.keys():
            st.caption(f"📄 {fname}")

# ---- MAIN CONTENT ----
tab1, tab2 = st.tabs(["📊 Executive Summary", "💬 Ask Anything"])

# ======== TAB 1 — EXECUTIVE SUMMARY ========
with tab1:
    st.markdown('<p class="main-header">🏢 Virginia Dare Apartments</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">110 McMorrine Street, Elizabeth City, NC · 68 units · HUD HAP</p>', unsafe_allow_html=True)
    
    # KPI Cards
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("Monthly Rent", "$61,992", "68 units")
    with col2:
        st.metric("Latest Utility Bill", "$8,355", "Mar-26")
    with col3:
        st.metric("Reserve Balance", "$734,280", "Yr 1")
    with col4:
        st.metric("Critical Repairs", "$13,540", "3 open")
    with col5:
        st.metric("DD3 Demand", "$1,784", "↑ 2x YoY")
    with col6:
        st.metric("NOI Potential Gain", "$39K+/yr", "if fixed")
    
    st.markdown("---")
    
    # Alerts
    st.subheader("🚨 Alerts & Findings")
    
    alerts = [
        ("🔴 Critical", "Demand charge (DD3) up 2× year-over-year — Feb-25 spike to $2,707. Aging HVAC/boiler pulling peak load. Action: HVAC PM contract immediately."),
        ("🔴 Critical", "3 HUD life safety violations open: GFCI outlets ($4,760), smoke detectors ($2,380), UFAS accessibility ($5,000). Must resolve before HUD inspection."),
        ("🟡 High", "Elevator replacements (Yr 4-6) will draw $707K from reserves. Current utility spikes are early warning signal of mechanical failure."),
        ("🟡 High", "Propane/gas visibility near zero — only 1 Blossman invoice available. Request all 2024-2025 invoices immediately."),
        ("🔵 Medium", "Water usage reads exactly 99 units every single month — likely estimated meter. Request verification from City of Elizabeth City."),
        ("🔵 Medium", "Office account (Apr-26) had $405 past due — missed payment. Flag to management as process issue."),
    ]
    
    for level, text in alerts:
        if "Critical" in level:
            st.markdown(f'<div class="alert-red"><strong>{level}:</strong> {text}</div>', unsafe_allow_html=True)
        elif "High" in level:
            st.markdown(f'<div class="alert-yellow"><strong>{level}:</strong> {text}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="alert-green"><strong>{level}:</strong> {text}</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Utility Chart
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("⚡ Utility Bills — Main Account (Actual)")
        utility_data = {
            "Month": ["Nov-24","Dec-24","Jan-25","Feb-25","Mar-25","Apr-25","May-25","Aug-25","Sep-25","Oct-25","Mar-26","Apr-26"],
            "Total Bill": [4614,5876,5474,8889,8895,5095,4759,5852,6173,4951,7967,7967],
            "DD3 Demand": [492,1061,1061,2707,2707,846,646,1108,1108,815,1784,1784],
            "Electric": [2195,2763,2763,3841,3841,2235,2131,2641,2641,2140,3823,3823],
            "Water+Sewer": [1543,1543,1543,1558,1558,1543,1543,1543,1543,1543,1543,1543],
        }
        df_utility = pd.DataFrame(utility_data)
        
        fig1 = px.bar(df_utility, x="Month", y=["Electric","DD3 Demand","Water+Sewer"],
                     title="Utility Breakdown by Month",
                     color_discrete_map={"Electric":"#378ADD","DD3 Demand":"#E24B4A","Water+Sewer":"#7F77DD"})
        fig1.add_hline(y=7000, line_dash="dash", line_color="orange", annotation_text="Budget ~$7K")
        fig1.update_layout(height=400)
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.subheader("📈 DD3 Demand Charge Trend")
        fig2 = px.line(df_utility, x="Month", y="DD3 Demand",
                      title="Demand Charge Month by Month",
                      markers=True, color_discrete_sequence=["#E24B4A"])
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)
    
    st.markdown("---")
    
    # Reserve Schedule
    st.subheader("🏦 Replacement Reserve — Balance Projection")
    reserve_data = {
        "Year": ["Yr 1","Yr 2","Yr 3","Yr 4","Yr 5","Yr 6","Yr 7","Yr 8"],
        "Balance": [734280,769342,809824,626409,428488,236185,221978,174855],
        "Draw": [0,0,4227,229410,242554,235422,55896,89523],
    }
    df_reserve = pd.DataFrame(reserve_data)
    
    fig3 = go.Figure()
    fig3.add_bar(x=df_reserve["Year"], y=df_reserve["Balance"], name="Reserve Balance",
                marker_color=["#1D9E75" if b > 400000 else "#EF9F27" if b > 200000 else "#E24B4A" for b in df_reserve["Balance"]])
    fig3.add_scatter(x=df_reserve["Year"], y=df_reserve["Draw"], name="Annual Draw",
                    line=dict(color="#E24B4A", dash="dash"), mode="lines+markers")
    fig3.update_layout(title="Reserve Balance vs Annual Draw", height=350)
    st.plotly_chart(fig3, use_container_width=True)
    
    st.markdown("---")
    
    # Action Plan
    st.subheader("✅ Action Plan — Ranked by Urgency")
    actions = [
        {"#": 1, "Action": "Email Kenya Owens — request all Blossman propane invoices 2024-2025", "Deadline": "This week", "Cost": "$0"},
        {"#": 2, "Action": "Pull Feb 2025 work orders — identify $2,707 demand spike root cause", "Deadline": "This week", "Cost": "$0"},
        {"#": 3, "Action": "Request water meter verification from City of Elizabeth City", "Deadline": "2 weeks", "Cost": "$0"},
        {"#": 4, "Action": "Confirm refuse charge split with commercial tenants", "Deadline": "2 weeks", "Cost": "$0 → saves $1-3K/yr"},
        {"#": 5, "Action": "Clear roof drains — standing water observed in CNA", "Deadline": "Immediate", "Cost": "$2,500"},
        {"#": 6, "Action": "HVAC PM contract — all 77 systems", "Deadline": "30 days", "Cost": "$3,600/yr → saves $6,200/yr"},
        {"#": 7, "Action": "LED retrofit — common areas + exterior", "Deadline": "60 days", "Cost": "$12,000 → saves $8,400/yr"},
        {"#": 8, "Action": "Demand controller / peak shaving relay", "Deadline": "60 days", "Cost": "$4-8K → saves $5-12K/yr"},
    ]
    df_actions = pd.DataFrame(actions)
    st.dataframe(df_actions, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.markdown('<div class="alert-green"><strong>💰 Value Creation:</strong> Top 4 improvements = ~$26,800/yr savings. At 6% cap rate = <strong>$447,000 added property value.</strong></div>', unsafe_allow_html=True)

# ======== TAB 2 — ASK ANYTHING ========
with tab2:
    st.markdown('<p class="main-header">💬 Ask Anything</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Ask any question about Virginia Dare or any uploaded property documents.</p>', unsafe_allow_html=True)
    
    if not st.session_state.groq_key:
        st.warning("⚠️ Please enter your Groq API Key in the sidebar to use the chat!")
    else:
        # Suggested questions
        st.markdown("**Quick questions:**")
        cols = st.columns(4)
        suggestions = [
            "Why are utilities over budget?",
            "What caused the Feb-25 demand spike?",
            "When will reserves run low?",
            "What are the critical HUD violations?",
            "How much can NOI improve?",
            "What should I ask management?",
            "Compare Mar-26 vs Mar-25 bills",
            "What is the propane situation?",
        ]
        for i, s in enumerate(suggestions):
            with cols[i % 4]:
                if st.button(s, key=f"sug_{i}"):
                    st.session_state.messages.append({"role": "user", "content": s})
        
        st.markdown("---")
        
        # Chat history
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
        
        # Chat input
        if prompt := st.chat_input("Ask anything about your properties..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)
            
            with st.chat_message("assistant"):
                with st.spinner("Analyzing documents..."):
                    try:
                        # Build context from uploaded documents
                        doc_context = ""
                        if st.session_state.documents:
                            doc_context = "\n\nUPLOADED DOCUMENTS:\n"
                            for fname, content in st.session_state.documents.items():
                                doc_context += f"\n--- {fname} ---\n{content[:3000]}\n"
                        
                        system_prompt = f"""You are a senior real estate financial analyst. You have access to property documents and data for Virginia Dare Apartments and other properties.

VIRGINIA DARE KEY DATA:
- 68 units, 9-story, built 1927, Elizabeth City NC, HUD HAP contract
- Monthly rent: $61,992 | Annual: $743,904
- Utility bills (main account): Nov-24 $4,614 | Feb-25 $8,889 (SPIKE - demand $2,707) | Mar-25 $8,895 | Apr-25 $5,095 | Aug-25 $5,852 | Mar-26 $7,967 | Apr-26 $7,967
- DD3 Demand charge is the main budget overage driver - ranges $492 to $2,707
- Reserve balance Yr1: $734,280 | Major draws Yr4-6: $707K (elevators)
- Critical repairs: $13,540 (GFCI, smoke detectors, UFAS)
- Propane: Blossman Gas, Jan-25 invoice $394 for 172 gal @ $2.099/gal
- Management: Beacon Management (Kenya Owens)
{doc_context}

Answer with specific numbers, flag risks, and always suggest action items. Be concise but thorough."""

                        client = Groq(api_key=st.session_state.groq_key)
                        
                        chat_history = [{"role": m["role"], "content": m["content"]} 
                                       for m in st.session_state.messages[:-1]]
                        
                        response = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[
                                {"role": "system", "content": system_prompt},
                                *chat_history,
                                {"role": "user", "content": prompt}
                            ],
                            max_tokens=1000
                        )
                        
                        reply = response.choices[0].message.content
                        st.write(reply)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                    
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
        
        if st.session_state.messages:
            if st.button("🗑️ Clear Chat"):
                st.session_state.messages = []
                st.rerun()
