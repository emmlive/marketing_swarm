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

# --- HELPER FUNCTIONS ---

def check_system_health():
    health = {
        "Gemini 2.0": os.getenv("GOOGLE_API_KEY") is not None,
        "Serper API": os.getenv("SERPER_API_KEY") is not None,
        "Database": os.path.exists("breatheeasy.db"),
    }
    return health

def is_verified(username):
    conn = sqlite3.connect('breatheeasy.db')
    res = conn.execute("SELECT verified FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return res[0] == 1 if res else False

def trigger_verification(email):
    st.warning("⚠️ Account Not Verified")
    if st.button("Verify Email (Simulate Click)", use_container_width=True):
        conn = sqlite3.connect('breatheeasy.db')
        conn.execute("UPDATE users SET verified = 1 WHERE username = ?", (st.session_state["username"],))
        conn.commit(); conn.close()
        st.success("Verified!"); st.rerun()

@st.cache_data(ttl=3600)
def get_geo_data():
    return {
        "Alabama": ["Birmingham", "Huntsville"],
        "Arizona": ["Phoenix", "Scottsdale"],
        "California": ["Los Angeles", "San Francisco"],
        "Florida": ["Miami", "Orlando"],
        "Illinois": ["Chicago", "Naperville"],
        "Texas": ["Austin", "Dallas"],
    }

# --- 1. SYSTEM INITIALIZATION ---
if 'theme' not in st.session_state: st.session_state.theme = 'light'
if 'gen' not in st.session_state: st.session_state.gen = False
if 'report' not in st.session_state: st.session_state.report = {}

st.set_page_config(page_title="TechInAdvance AI", page_icon="Logo1.jpeg", layout="wide")

# --- 2. EXECUTIVE UI CSS ---
sidebar_color = "#2563EB"
st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFCF0; color: #1E293B; }}
    .price-card {{ background: white; padding: 20px; border-radius: 12px; border: 2px solid {sidebar_color}; text-align: center; color: #1E293B; }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE INITIALIZATION (AUTHENTICATOR V0.3.0+ COMPLIANT) ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    
    # 1. Ensure CORE TABLES exist
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, 
                    role TEXT, plan TEXT, credits INTEGER, logo_path TEXT, 
                    team_id TEXT, verified INTEGER DEFAULT 0)''')
                    
    c.execute('''CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, 
                    industry TEXT, service TEXT, city TEXT, content TEXT, 
                    team_id TEXT, status TEXT DEFAULT 'Discovery')''')
                    
    c.execute('''CREATE TABLE IF NOT EXISTS master_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, user TEXT, 
                    action_type TEXT, target_biz TEXT, location TEXT, 
                    credit_cost INTEGER, status TEXT)''')

    # 2. SCHEMA MIGRATION: Add team_id to leads if it was missing from Sprint 3
    try:
        c.execute("SELECT team_id FROM leads LIMIT 1")
    except sqlite3.OperationalError:
        st.warning("⚠️ Migrating database to Sprint 4 (Adding Team Support)...")
        c.execute("ALTER TABLE leads ADD COLUMN team_id TEXT")
        c.execute("UPDATE leads SET team_id = 'HQ_001' WHERE team_id IS NULL")

    # 3. Ensure Admin user exists with correct hash
    admin_hash = stauth.Hasher.hash('admin123')
    c.execute("""INSERT OR IGNORE INTO users 
                 (username, email, name, password, role, plan, credits, logo_path, team_id, verified) 
                 VALUES (?,?,?,?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001', 1)""", 
              ('admin', 'admin@techinadvance.ai', 'Admin', admin_hash))
    
    conn.commit()
    conn.close()

# Run the fix
init_db()

# --- 3.5 CREDENTIAL LOADER (MUST BE ABOVE AUTHENTICATOR) ---
def get_db_creds():
    try:
        conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
        # We fetch the latest user list to populate the authenticator
        df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
        conn.close()
        
        # Standard dictionary format for streamlit-authenticator
        return {
            'usernames': {
                row['username']: {
                    'email': row['email'], 
                    'name': row['name'], 
                    'password': row['password']
                } for _, row in df.iterrows()
            }
        }
    except Exception as e:
        st.error(f"Failed to load credentials: {e}")
        return {'usernames': {}}

# --- 4. AUTHENTICATION INITIALIZATION ---

# 4A. Credential Loader
def get_db_creds():
    try:
        conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
        df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
        conn.close()
        return {
            'usernames': {
                row['username']: {
                    'email': row['email'], 
                    'name': row['name'], 
                    'password': row['password']
                } for _, row in df.iterrows()
            }
        }
    except Exception:
        return {'usernames': {}}

# 4B. Initialize Authenticator in Session State (Prevents Duplicate Key Error)
if 'authenticator' not in st.session_state:
    st.session_state.authenticator = stauth.Authenticate(
        get_db_creds(), 
        st.secrets['cookie']['name'], 
        st.secrets['cookie']['key'], 
        30
    )

authenticator = st.session_state.authenticator

# 4C. THE LOGIN GATE
if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=200)
    auth_tabs = st.tabs(["🔑 Login", "📝 Enrollment", "🤝 Join Team", "❓ Recovery"])
    
    with auth_tabs[0]:
        authenticator.login(location='main')
        if st.session_state["authentication_status"] is False:
            st.error('Username/password is incorrect')
        elif st.session_state["authentication_status"] is None:
            st.warning('Please enter your username and password')
    
    with auth_tabs[1]:
        st.subheader("Enrollment")
        if authenticator.register_user(location='main'):
            st.success('User registered successfully! Please log in.')

    with auth_tabs[2]:
        st.text_input("Enter Team ID", key="join_team_gate")
        st.button("Request Access", key="join_team_btn_gate")

    with auth_tabs[3]:
        # FIXED: Only call these ONCE here to avoid "2 forget passwords"
        st.subheader("Account Recovery")
        try:
            authenticator.forgot_password(location='main')
            authenticator.forgot_username(location='main')
        except Exception as e:
            st.error(f"Recovery Error: {e}")

    # CRITICAL: Stop the script here. This prevents the NameError on user_row.
    st.stop()

# --- 5. LOGGED-IN SESSION (ONLY ACCESSIBLE AFTER LOGIN) ---
try:
    conn = sqlite3.connect('breatheeasy.db')
    # Use st.session_state["username"] which is guaranteed by the Authenticator
    query = "SELECT * FROM users WHERE username = ?"
    user_data = pd.read_sql_query(query, conn, params=(st.session_state["username"],))
    conn.close()

    if not user_data.empty:
        user_row = user_data.iloc[0]
        is_admin = (user_row['role'] == 'admin')
    else:
        st.error("User profile not found in database.")
        st.stop()
except Exception as e:
    st.error(f"Session Loading Error: {e}")
    st.stop()

# Now user_row['logo_path'] will work perfectly because the code only reaches this point after login.

# --- 6. EXPORT HELPERS ---
def create_word_doc(content, title):
    doc = Document(); doc.add_heading(title, 0); doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'{service} - {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 7, txt=str(content).encode('latin-1', 'ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

# --- 7. SIDEBAR ---
with st.sidebar:
    st.image(user_row['logo_path'], width=120)
    st.metric("Credits", user_row['credits'])
    biz_name = st.text_input("Brand Name")
    
    geo = get_geo_data()
    state = st.selectbox("State", list(geo.keys()))
    city = st.selectbox("City", geo[state])
    full_loc = f"{city}, {state}"
    
    ind_cat = st.selectbox("Industry", ["HVAC", "Solar", "Legal", "Custom"])
    svc = st.text_input("Service Type")
    
    toggles = {k: st.toggle(v, value=True) for k, v in {
        "analyst": "🕵️ Analyst", "builder": "🎨 Creative", 
        "manager": "👔 Strategist", "social": "✍ Social", "geo": "🧠 GEO", 
        "audit": "🌐 Auditor", "seo": "✍ SEO"}.items()}
    
    if is_verified(st.session_state["username"]):
        run_btn = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)
    else:
        trigger_verification(user_row['email'])
        run_btn = False

    authenticator.logout('Sign Out', 'sidebar')

# --- 8. EXECUTION ENGINE ---
if run_btn:
    if not biz_name: st.error("Brand Name missing")
    else:
        with st.status("🛠️ Swarm Running...", expanded=True) as status:
            report_data = run_marketing_swarm({
                'city': full_loc, 'industry': ind_cat, 'service': svc, 
                'biz_name': biz_name, 'toggles': toggles
            })
            st.session_state.report = report_data
            st.session_state.gen = True
            
            # DB Log
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
            conn.execute("INSERT INTO master_audit_logs (timestamp, user, action_type, target_biz, location, status) VALUES (?,?,?,?,?,?)", 
                         (datetime.now().strftime("%Y-%m-%d"), st.session_state["username"], "SWARM", biz_name, full_loc, "SUCCESS"))
            conn.commit(); conn.close()
            st.rerun()

# --- 9. MULTIMODAL COMMAND CENTER (SPRINT 1-5 INTEGRATED) ---

# 1. DEFINE THE COMPLETE TAB LIST
# We define these globally so they exist even before 'gen' is True
agent_map = [
    ("🕵️ Analyst", "analyst"), ("🎨 Creative", "creative"), 
    ("👔 Strategist", "strategist"), ("📱 Social", "social"), 
    ("📍 GEO", "geo"), ("🌐 Auditor", "auditor"), ("✍ SEO", "seo")
]

tab_labels = ["📖 Guide"] + [a[0] for a in agent_map] + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_admin:
    tab_labels.append("⚙ Admin")

# 2. INITIALIZE TABS
tabs_list = st.tabs(tab_labels)
TAB = {name: tabs_list[i] for i, name in enumerate(tab_labels)}

# --- TAB: GUIDE (SPRINT 1) ---
with TAB["📖 Guide"]:
    st.header("📖 Agent Intelligence Manual")
    st.info("The Omni-Swarm engine coordinates 8 specialized AI agents to engineer high-ticket growth.")
    g1, g2 = st.columns(2)
    with g1:
        with st.expander("🕵️ Intelligence Cluster", expanded=True):
            st.markdown("- **Analyst:** Market Entry Gaps\n- **Vision:** Forensic Diagnostics\n- **Auditor:** Conversion Leaks")
    with g2:
        with st.expander("👔 Strategy Cluster", expanded=True):
            st.markdown("- **Creative:** Multi-channel Hooks\n- **SEO:** Technical E-E-A-T Articles\n- **Strategist:** 30-Day ROI Roadmap")

# --- TABS: DYNAMIC AGENT RENDERING (SPRINT 2 & 3) ---
for i, (title, report_key) in enumerate(agent_map):
    with TAB[title]:
        if st.session_state.gen:
            st.subheader(f"{title} Intelligence")
            content = st.session_state.report.get(report_key, "Intelligence pending...")
            
            # Refinement & Export Engine
            edited = st.text_area(f"Refine {title}", value=str(content), height=350, key=f"edit_{report_key}")
            c1, c2 = st.columns(2)
            with c1: st.download_button("📄 Word Brief", create_word_doc(edited, title), f"{title}.docx", key=f"w_{report_key}")
            with c2: st.download_button("📕 PDF Report", create_pdf(edited, svc, full_loc), f"{title}.pdf", key=f"p_{report_key}")
        else:
            st.info(f"🚀 Launch the Omni-Swarm to populate the {title} Command Seat.")

# --- TAB: VISION INSPECTOR (SPRINT 4) ---
with TAB["👁️ Vision"]:
    st.subheader("👁️ Vision Inspector")
    if st.session_state.gen:
        v_intel = st.session_state.report.get('vision_intel', "Vision diagnostics pending.")
        st.markdown(f'<div style="background:#f0f2f6; p:20px; border-radius:10px;">{v_intel}</div>', unsafe_allow_html=True)
    v_file = st.file_uploader("Upload Forensic Evidence", type=['png','jpg','jpeg'], key="vis_upload")
    if v_file: st.image(v_file, caption="Asset for Analysis", use_container_width=True)

# --- TAB: VEO STUDIO (SPRINT 5) ---
with TAB["🎬 Veo Studio"]:
    st.subheader("🎬 Veo Cinematic Studio")
    if st.session_state.gen:
        creative_context = st.session_state.report.get('creative', '')
        v_prompt = st.text_area("Video Scene Prompt", value=str(creative_context)[:500], height=150)
        if st.button("📽️ GENERATE AD", type="primary"):
            with st.spinner("Rendering..."):
                v_vid = generate_cinematic_ad(v_prompt)
                if v_vid: st.video(v_vid)
    else:
        st.warning("Swarm required to generate video context.")

# --- TAB: TEAM INTEL KANBAN (SPRINT 4) ---
with TAB["🤝 Team Intel"]:
    st.header("🤝 Global Pipeline Kanban")
    try:
        conn = sqlite3.connect('breatheeasy.db')
        # We check if the table is empty first
        check_leads = pd.read_sql_query("SELECT count(*) as count FROM leads", conn)
        
        if check_leads.iloc[0]['count'] > 0:
            team_df = pd.read_sql_query("SELECT * FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
            st.dataframe(team_df, use_container_width=True, hide_index=True)
        else:
            st.info("Your pipeline is currently empty. Launch a Swarm to generate leads.")
        conn.close()
    except Exception as e:
        st.error(f"Kanban Data Error: Ensure database migration is complete.")

# --- TAB: GOD-MODE ADMIN (STABILIZED) ---
if is_admin:
    with TAB["⚙ Admin"]:
        st.header("⚙️ God-Mode Management")
        conn = sqlite3.connect('breatheeasy.db')
        
        # 1. Global Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Global Swarms", pd.read_sql_query("SELECT COUNT(*) FROM master_audit_logs", conn).iloc[0,0])
        m2.metric("Total Users", pd.read_sql_query("SELECT COUNT(*) FROM users", conn).iloc[0,0])
        m3.metric("System Health", "Verified")

        # 2. Audit Table
        audit_df = pd.read_sql_query("SELECT timestamp, user, action_type, status FROM master_audit_logs ORDER BY id DESC LIMIT 50", conn)
        st.dataframe(audit_df, use_container_width=True, hide_index=True)
        
        # 3. Credit Injection
        st.subheader("👤 User Credit Management")
        all_u = pd.read_sql_query("SELECT username FROM users", conn)['username'].tolist()
        u_sel = st.selectbox("Target Account", all_u)
        u_amt = st.number_input("Credits to Inject", 10, 500, 50)
        if st.button("Execute Injection"):
            conn.execute("UPDATE users SET credits = credits + ? WHERE username = ?", (u_amt, u_sel))
            conn.commit(); st.success(f"Injected {u_amt} to {u_sel}"); st.rerun()
        conn.close()
