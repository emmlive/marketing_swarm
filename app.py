import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
import json
from datetime import datetime
from main import run_marketing_swarm 
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from io import BytesIO
from PIL import Image

# --- HELPER FUNCTIONS: VERIFICATION & SYSTEM HEALTH ---

def check_system_health():
    """Sprint 5: Verifies critical infrastructure status"""
    health = {
        "Gemini 2.0": os.getenv("GOOGLE_API_KEY") is not None,
        "Serper API": os.getenv("SERPER_API_KEY") is not None,
        "Database": os.path.exists("breatheeasy.db"),
    }
    return health

def is_verified(username):
    """Checks if the user has completed the email verification gate"""
    conn = sqlite3.connect('breatheeasy.db')
    res = conn.execute("SELECT verified FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return res[0] == 1 if res else False

def trigger_verification(email):
    """UI Trigger for unverified accounts"""
    st.warning("⚠️ Account Not Verified")
    st.info(f"Verification link sent to: {email}")
    if st.button("Simulate Email Link Click (Demo Mode)", use_container_width=True):
        conn = sqlite3.connect('breatheeasy.db')
        conn.execute("UPDATE users SET verified = 1 WHERE username = ?", (st.session_state["username"],))
        conn.commit()
        conn.close()
        st.success("Email Verified! Reloading...")
        st.rerun()

@st.cache_data(ttl=3600)
def get_geo_data():
    """Sprint 5: Performance optimization for geographic selectors"""
    return {
        "Alabama": ["Birmingham", "Huntsville", "Mobile"],
        "Arizona": ["Phoenix", "Scottsdale", "Tucson"],
        "California": ["Los Angeles", "San Francisco", "San Diego"],
        "Florida": ["Miami", "Orlando", "Tampa"],
        "Illinois": ["Chicago", "Naperville", "Plainfield"],
        "Texas": ["Austin", "Dallas", "Houston"],
    }

# --- 1. SYSTEM INITIALIZATION ---
if 'theme' not in st.session_state: st.session_state.theme = 'light'
if 'processing' not in st.session_state: st.session_state.processing = False
if 'gen' not in st.session_state: st.session_state.gen = False
if 'report' not in st.session_state: st.session_state.report = {}

def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

os.environ["OTEL_SDK_DISABLED"] = "true"
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

st.set_page_config(page_title="TechInAdvance AI | Enterprise Command", page_icon="Logo1.jpeg", layout="wide")

# --- 2. EXECUTIVE UI CSS ---
sidebar_color = "#2563EB"
st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFCF0; color: #1E293B; }}
    [data-testid="stSidebar"] {{ 
        background-color: {"#1E293B" if st.session_state.theme == 'dark' else "#FFFFFF"} !important; 
        border-right: 3px solid rgba(0,0,0,0.1) !important;
        box-shadow: 4px 0px 10px rgba(0,0,0,0.05);
    }}
    .price-card {{
        background-color: white; padding: 20px; border-radius: 12px; border: 2px solid {sidebar_color};
        text-align: center; margin-bottom: 15px; color: #1E293B; box-shadow: 0px 4px 8px rgba(0,0,0,0.05);
    }}
    .guide-box {{ background: #F1F5F9; padding: 15px; border-radius: 8px; border: 1px dashed {sidebar_color}; font-size: 0.85rem; margin-bottom: 20px; color: #475569; }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800; height: 3.2em; }}
    .kanban-card {{ background: white; padding: 18px; border-radius: 10px; margin-bottom: 12px; border-left: 5px solid {sidebar_color}; box-shadow: 0px 2px 6px rgba(0,0,0,0.04); }}
    .kanban-header {{ font-weight: 900; text-align: center; color: {sidebar_color}; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 1.5px; font-size: 0.9rem; border-bottom: 2px solid {sidebar_color}33; padding-bottom: 8px; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, plan TEXT, credits INTEGER DEFAULT 0, logo_path TEXT, team_id TEXT, verified INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT, team_id TEXT, status TEXT DEFAULT 'Discovery')''')
    c.execute('''CREATE TABLE IF NOT EXISTS master_audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, user TEXT, action_type TEXT, target_biz TEXT, location TEXT, credit_cost INTEGER, status TEXT)''')
    hashed_pw = stauth.Hasher.hash('admin123')
    c.execute("""INSERT OR IGNORE INTO users VALUES ('admin', 'admin@techinadvance.ai', 'Admin', ?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001', 1)""", (hashed_pw,))
    conn.commit()
    conn.close()

init_db()

# --- 4. AUTHENTICATION ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
    conn.close()
    return {'usernames': {row['username']: {'email':row['email'], 'name':row['name'], 'password':row['password']} for _, row in df.iterrows()}}

# Persist Authenticator in session state to avoid key collision
if 'authenticator' not in st.session_state:
    st.session_state.authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

authenticator = st.session_state.authenticator

if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=200)
    auth_tabs = st.tabs(["🔑 Login", "📝 Enrollment", "🤝 Join Team", "❓ Recovery"])
    with auth_tabs[0]: authenticator.login(location='main')
    with auth_tabs[1]:
        plan = st.selectbox("Select Business Plan", ["Basic", "Pro", "Enterprise"])
        if authenticator.register_user(location='main'):
            st.success("Registration successful! Please log in.")
    st.stop()

# --- 5. LOGGED-IN SESSION ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()
is_admin = user_row.get('role') == 'admin'

# --- EXPORT HELPERS ---
def create_word_doc(content, title):
    doc = Document()
    doc.add_heading(f'Intelligence Brief: {title}', 0)
    doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f'{service} Strategy - {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 7, txt=str(content).encode('latin-1', 'ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

# --- 6. SIDEBAR ---
with st.sidebar:
    health = check_system_health()
    st.caption(f"{'🟢' if all(health.values()) else '🔴'} **SYSTEM OPERATIONAL**")
    st.image(user_row['logo_path'], width=120)
    st.metric("Credits Available", user_row['credits'])
    biz_name = st.text_input("Brand Name", placeholder="e.g. Acme Solar")
    location_data = get_geo_data()
    selected_state = st.selectbox("🎯 Target State", sorted(location_data.keys()))
    selected_city = st.selectbox("Select City", location_data[selected_state])
    full_loc = f"{selected_city}, {selected_state}"
    svc = st.text_input("Service Type")
    
    toggles = {k: st.toggle(v, value=True) for k, v in {
        "analyst": "🕵️ Analyst", "ads": "📺 Ad Tracker", "builder": "🎨 Creative", 
        "strategist": "👔 Strategist", "social": "✍ Social", "geo": "🧠 GEO", 
        "audit": "🌐 Auditor", "seo": "✍ SEO"}.items()}
    
    if is_verified(st.session_state["username"]):
        run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
    else:
        trigger_verification(user_row['email'])
        run_btn = False 

    authenticator.logout('Sign Out', 'sidebar')

# --- 7. SWARM ENGINE ---
if run_btn:
    if not biz_name: st.error("Identification required.")
    else:
        with st.status("🛠️ Coordinating Swarm Agents...", expanded=True) as status:
            report_data = run_marketing_swarm({'city': full_loc, 'biz_name': biz_name, 'service': svc, 'toggles': toggles})
            st.session_state.report = report_data
            st.session_state.gen = True
            
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
            conn.execute("INSERT INTO master_audit_logs (timestamp, user, action_type, target_biz, location, credit_cost, status) VALUES (?,?,?,?,?,?,?)", 
                         (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_row['username'], "SWARM_LAUNCH", biz_name, full_loc, 1, "SUCCESS"))
            conn.commit(); conn.close(); st.rerun()

# --- 8. COMMAND CENTER (FIXED KEYERROR 9) ---

# Define the logical tab layout
agent_map = [
    ("🕵️ Analyst", "analyst"), ("📺 Ads", "ads"), ("🎨 Creative", "creative"), 
    ("👔 Strategist", "strategist"), ("📱 Social", "social"), ("📍 GEO", "geo"), 
    ("🌐 Auditor", "audit"), ("✍ SEO", "seo")
]

# Build tab labels dynamically based on user role
all_tab_labels = ["📖 Guide"] + [a[0] for a in agent_map] + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_admin: all_tab_labels.append("⚙ Admin")

# Create the tabs and a dictionary for safe name-based access
tabs_obj = st.tabs(all_tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(all_tab_labels)}

with TAB["📖 Guide"]:
    st.header("📖 Agent Intelligence Manual")
    st.info("The Omni-Swarm coordinates specialized AI agents for high-ticket growth.")

# Agent Rendering Loop
for title, key in agent_map:
    with TAB[title]:
        if st.session_state.gen:
            content = st.session_state.report.get(key, "Intelligence Pending...")
            edited = st.text_area(f"Refine {title}", value=str(content), height=350, key=f"edit_{key}")
            c1, c2 = st.columns(2)
            with c1: st.download_button("📄 Word Brief", create_word_doc(edited, title), f"{title}.docx", key=f"w_{key}")
            with c2: st.download_button("📕 PDF Report", create_pdf(edited, svc, full_loc), f"{title}.pdf", key=f"p_{key}")
        else:
            st.info("Launch Swarm to populate Command Seat.")

with TAB["👁️ Vision"]:
    st.subheader("👁️ Vision Inspector")
    v_file = st.file_uploader("Upload Forensic Evidence", type=['png','jpg','jpeg'])
    if v_file: st.image(v_file, use_container_width=True)

with TAB["🎬 Veo Studio"]:
    st.subheader("🎬 Veo Cinematic Studio")
    st.warning("Veo Studio requires an active creative report context.")

with TAB["🤝 Team Intel"]:
    st.header("🤝 Global Pipeline Kanban")
    conn = sqlite3.connect('breatheeasy.db')
    team_df = pd.read_sql_query("SELECT * FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
    if not team_df.empty: st.dataframe(team_df, use_container_width=True)
    conn.close()

# THE FIX: Only attempt to render Admin if the tab exists in our dictionary
if "⚙ Admin" in TAB:
    with TAB["⚙ Admin"]:
        st.header("⚙️ God-Mode Management")
        st.warning("⚡ Root Access: Viewing global system infrastructure.")
        conn = sqlite3.connect('breatheeasy.db')
        m1, m2 = st.columns(2)
        m1.metric("Global Swarms", pd.read_sql_query("SELECT COUNT(*) as count FROM master_audit_logs", conn).iloc[0]['count'])
        m2.metric("Total Users", pd.read_sql_query("SELECT COUNT(*) as count FROM users", conn).iloc[0]['count'])
        st.subheader("📊 Activity Audit Trail")
        audit_df = pd.read_sql_query("SELECT timestamp, user, action_type, status FROM master_audit_logs ORDER BY id DESC LIMIT 100", conn)
        st.dataframe(audit_df, use_container_width=True)
        
        st.subheader("👤 User Credit Management")
        u_list = pd.read_sql_query("SELECT username FROM users", conn)['username'].tolist()
        target_u = st.selectbox("Select User", u_list)
        amt = st.number_input("Credits to Add", 10)
        if st.button("Inject Credits"):
            conn.execute("UPDATE users SET credits = credits + ? WHERE username = ?", (amt, target_u))
            conn.commit(); st.success("Done"); st.rerun()
        conn.close()
