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
    if st.button("Simulate Email Link Click (Demo Mode)", use_container_width=True):
        conn = sqlite3.connect('breatheeasy.db')
        conn.execute("UPDATE users SET verified = 1 WHERE username = ?", (st.session_state["username"],))
        conn.commit(); conn.close()
        st.success("Email Verified! Reloading..."); st.rerun()

@st.cache_data(ttl=3600)
def get_geo_data():
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
if 'gen' not in st.session_state: st.session_state.gen = False
if 'report' not in st.session_state: st.session_state.report = {}

st.set_page_config(page_title="TechInAdvance AI | Enterprise Command", page_icon="Logo1.jpeg", layout="wide")

# --- 2. EXECUTIVE UI CSS ---
sidebar_color = "#2563EB"
st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFCF0; color: #1E293B; }}
    .price-card {{ background: white; padding: 20px; border-radius: 12px; border: 2px solid {sidebar_color}; text-align: center; margin-bottom: 15px; color: #1E293B; }}
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
    
    # Ensure Admin Exists
    admin_hash = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users VALUES ('admin','admin@tech.ai','Admin',?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001',1)", (admin_hash,))
    conn.commit(); conn.close()

init_db()

# --- 4. AUTHENTICATION & SESSION LOADING ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
    conn.close()
    return {'usernames': {row['username']: {'email':row['email'], 'name':row['name'], 'password':row['password']} for _, row in df.iterrows()}}

if 'authenticator' not in st.session_state:
    st.session_state.authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

authenticator = st.session_state.authenticator

if not st.session_state.get("authentication_status"):
    auth_tabs = st.tabs(["🔑 Login", "📝 Enrollment", "🤝 Join Team", "❓ Recovery"])
    with auth_tabs[0]: authenticator.login(location='main')
    with auth_tabs[1]:
        plan = st.selectbox("Plan", ["Basic", "Pro", "Enterprise"])
        if authenticator.register_user(location='main'):
            st.success("Registered! Log in now.")
    with auth_tabs[3]:
        authenticator.forgot_password(location='main')
        authenticator.forgot_username(location='main')
    st.stop()

# Load Logged-In User Data
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()
is_admin = user_row['role'] == 'admin'

# --- 5. EXPORT HELPERS ---
def create_word_doc(content, title):
    doc = Document(); doc.add_heading(title, 0); doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'{service} - {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 7, txt=str(content).encode('latin-1', 'ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

# --- 6. SIDEBAR COMMAND CONSOLE ---
with st.sidebar:
    st.image(user_row['logo_path'], width=120)
    st.metric("Credits Available", user_row['credits'])
    biz_name = st.text_input("Brand Name", placeholder="Acme Solar")
    
    loc_data = get_geo_data()
    state = st.selectbox("Target State", sorted(loc_data.keys()))
    city = st.selectbox("Select City", sorted(loc_data[state]))
    full_loc = f"{city}, {state}"
    
    ind_cat = st.selectbox("Industry", ["HVAC", "Medical", "Solar", "Legal", "Custom"])
    svc = st.text_input("Service Type")
    
    toggles = {k: st.toggle(v, value=True) for k, v in {
        "analyst": "🕵️ Analyst", "ads": "📺 Ad Tracker", "creative": "🎨 Creative", 
        "strategist": "👔 Strategist", "social": "✍ Social", "geo": "🧠 GEO", 
        "audit": "🌐 Auditor", "seo": "✍ SEO"}.items()}
    
    if is_verified(st.session_state["username"]):
        run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
    else:
        trigger_verification(user_row['email']); run_btn = False

    authenticator.logout('Sign Out', 'sidebar')

# --- 7. SWARM EXECUTION ---
if run_btn:
    if not biz_name: st.error("Brand Name Required")
    else:
        with st.status("🛠️ Coordinating Swarm...", expanded=True) as status:
            report_data = run_marketing_swarm({'city': full_loc, 'industry': ind_cat, 'service': svc, 'biz_name': biz_name, 'toggles': toggles})
            st.session_state.report = report_data
            st.session_state.gen = True
            
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
            conn.execute("INSERT INTO master_audit_logs (timestamp, user, action_type, target_biz, location, credit_cost, status) VALUES (?,?,?,?,?,?,?)", 
                         (datetime.now().strftime("%Y-%m-%d"), st.session_state["username"], "SWARM", biz_name, full_loc, 1, "SUCCESS"))
            conn.commit(); conn.close(); st.rerun()

# --- 8. MULTIMODAL COMMAND CENTER (SPRINT 1-5 UI) ---

# Define Tab Labels
agent_map = [
    ("🕵️ Analyst", "analyst"), ("📺 Ads", "ads"), ("🎨 Creative", "creative"), 
    ("👔 Strategist", "strategist"), ("✍ Social", "social"), ("🧠 GEO", "geo"), 
    ("🌐 Auditor", "audit"), ("✍ SEO", "seo")
]
tab_labels = ["📖 Guide"] + [a[0] for a in agent_map] + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_admin: tab_labels.append("⚙ Admin")

tabs = st.tabs(tab_labels)
TAB = {name: tabs[i] for i, name in enumerate(tab_labels)}

# A. Guide Tab
with TAB["📖 Guide"]:
    st.header("📖 Agent Intelligence Manual")
    st.info("The Omni-Swarm engine coordinates 8 specialized AI agents.")
    st.markdown("### 🕵️ Intelligence Cluster\n- **Analyst:** Market Entry Gaps\n- **Vision:** Forensic Diagnostics")

# B. Dynamic Agent Rendering (Deployment Guides Included)
DEPLOYMENT_GUIDES = {
    "analyst": "Identify the 'Price-Gap' in the competitor table.",
    "ads": "Copy these platform-specific ad sets directly into Google/Meta Ads Manager.",
    "creative": "Implement these multi-channel copy sets.",
    "strategist": "This 30-day roadmap is your CEO-level execution checklist.",
    "social": "Deploy hooks across LinkedIn, IG, and X.",
    "geo": "Update your Google Business Profile keywords.",
    "audit": "Forward this technical brief to your web team.",
    "seo": "Publish this technical article to your domain."
}

for i, (title, key) in enumerate(agent_map):
    with TAB[title]:
        guide = DEPLOYMENT_GUIDES.get(key, "Review this report to align with your strategy.")
        st.markdown(f'<div style="background:rgba(37,99,235,0.1); padding:15px; border-radius:10px; border-left:6px solid #2563EB; margin-bottom:20px;"><b>🚀 DEPLOYMENT GUIDE:</b><br>{guide}</div>', unsafe_allow_html=True)
        
        if st.session_state.gen:
            content = st.session_state.report.get(key, "Pending...")
            edited = st.text_area(f"Refine {title}", value=str(content), height=350, key=f"edit_{key}")
            c1, c2 = st.columns(2)
            c1.download_button("📄 Word", create_word_doc(edited, title), f"{key}.docx", key=f"w_{key}")
            c2.download_button("📕 PDF", create_pdf(edited, svc, full_loc), f"{key}.pdf", key=f"p_{key}")
        else:
            st.info(f"Launch Swarm to populate the {title} seat.")

# C. Specialty Tabs
with TAB["👁️ Vision"]:
    st.subheader("👁️ Vision Inspector")
    v_file = st.file_uploader("Upload Forensic Evidence", type=['png','jpg','jpeg'])
    if v_file: st.image(v_file, use_container_width=True)

with TAB["🎬 Veo Studio"]:
    st.subheader("🎬 Veo Cinematic Studio")
    if st.session_state.gen:
        v_prompt = st.text_area("Video Scene Prompt", value=str(st.session_state.report.get('creative', ''))[:500])
        if st.button("📽️ GENERATE AD"):
            with st.spinner("Rendering..."):
                v_vid = generate_cinematic_ad(v_prompt)
                if v_vid: st.video(v_vid)
    else: st.warning("Launch Swarm first.")

with TAB["🤝 Team Intel"]:
    st.header("🤝 Global Pipeline Kanban")
    conn = sqlite3.connect('breatheeasy.db')
    team_df = pd.read_sql_query("SELECT * FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
    if not team_df.empty:
        st.dataframe(team_df, use_container_width=True, hide_index=True)
    conn.close()

if is_admin:
    with TAB["⚙ Admin"]:
        st.header("⚙️ God-Mode Management")
        conn = sqlite3.connect('breatheeasy.db')
        m1, m2 = st.columns(2)
        m1.metric("Global Swarms", pd.read_sql_query("SELECT COUNT(*) FROM master_audit_logs", conn).iloc[0,0])
        m2.metric("Total Users", pd.read_sql_query("SELECT COUNT(*) FROM users", conn).iloc[0,0])
        
        audit_df = pd.read_sql_query("SELECT timestamp, user, action_type, status FROM master_audit_logs ORDER BY id DESC LIMIT 50", conn)
        st.dataframe(audit_df, use_container_width=True)
        
        st.subheader("Credit Injection")
        all_u = pd.read_sql_query("SELECT username FROM users", conn)['username'].tolist()
        u_sel = st.selectbox("Target", all_u)
        amt = st.number_input("Credits", 10, 100, 10)
        if st.button("Inject"):
            conn.execute("UPDATE users SET credits = credits + ? WHERE username = ?", (amt, u_sel))
            conn.commit(); st.success("Credits Added!"); st.rerun()
        conn.close()
