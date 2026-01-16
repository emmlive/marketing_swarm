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
    
    # Create Tables
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY, 
                    email TEXT, 
                    name TEXT, 
                    password TEXT, 
                    role TEXT, 
                    plan TEXT, 
                    credits INTEGER, 
                    logo_path TEXT, 
                    team_id TEXT, 
                    verified INTEGER DEFAULT 0)''')
                    
    c.execute('''CREATE TABLE IF NOT EXISTS master_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    timestamp TEXT, 
                    user TEXT, 
                    action_type TEXT, 
                    target_biz TEXT, 
                    location TEXT, 
                    credit_cost INTEGER, 
                    status TEXT)''')
    
    # --- NEW HASHER SYNTAX ---
    # In v0.3.0+, we use stauth.Hasher.hash() as a static method
    admin_hashed_pw = stauth.Hasher.hash('admin123')
    
    # Initialize Root Admin
    c.execute("""INSERT OR IGNORE INTO users 
                 (username, email, name, password, role, plan, credits, logo_path, team_id, verified) 
                 VALUES (?,?,?,?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001', 1)""", 
              ('admin', 'admin@techinadvance.ai', 'Admin', admin_hashed_pw))
    
    conn.commit()
    conn.close()

init_db()
# --- 4. AUTHENTICATION ---
db_credentials = get_db_creds()
authenticator = stauth.Authenticate(
    db_credentials, 
    st.secrets['cookie']['name'], 
    st.secrets['cookie']['key'], 
    30
)

# New syntax: .login() no longer returns a tuple you can unpack
if not st.session_state.get("authentication_status"):
    auth_tabs = st.tabs(["🔑 Login", "📝 Enrollment", "❓ Recovery"])
    with auth_tabs[0]:
        # Just call it; it updates st.session_state internally
        authenticator.login(location='main') 
        
    with auth_tabs[1]:
        # Update your registration hashing if you have custom logic:
        # new_hash = stauth.Hasher.hash(user_input_password)
        pass

    if st.session_state["authentication_status"] is False:
        st.error('Username/password is incorrect')
    
    st.stop()

# --- 5. LOGGED-IN SESSION ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()

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

# --- 9. DYNAMIC REPORT TABS ---
if st.session_state.gen:
    # We map keys to match your main.py outputs exactly
    agent_map = [
        ("🕵️ Analyst", "analyst"), ("🎨 Creative", "creative"), 
        ("👔 Strategist", "strategist"), ("📱 Social", "social"), 
        ("📍 GEO", "geo"), ("🌐 Auditor", "auditor"), ("✍ SEO", "seo")
    ]
    
    tabs = st.tabs([a[0] for a in agent_map] + ["⚙ Admin"])
    
    for i, (title, key) in enumerate(agent_map):
        with tabs[i]:
            st.subheader(title)
            content = st.session_state.report.get(key, "Pending...")
            edited = st.text_area(f"Refine {title}", value=str(content), height=300, key=f"edit_{key}")
            c1, c2 = st.columns(2)
            c1.download_button("📄 Word", create_word_doc(edited, title), f"{key}.docx", key=f"w_{key}")
            c2.download_button("📕 PDF", create_pdf(edited, svc, full_loc), f"{key}.pdf", key=f"p_{key}")

    # GOD-MODE ADMIN
    with tabs[-1]:
        if user_row['role'] == 'admin':
            st.header("⚙️ Admin God-Mode")
            conn = sqlite3.connect('breatheeasy.db')
            logs = pd.read_sql_query("SELECT * FROM master_audit_logs ORDER BY id DESC", conn)
            st.dataframe(logs, use_container_width=True)
            
            st.subheader("Credit Injection")
            u_to_pay = st.selectbox("User", pd.read_sql_query("SELECT username FROM users", conn))
            amt = st.number_input("Amount", 10)
            if st.button("Inject"):
                conn.execute("UPDATE users SET credits = credits + ? WHERE username = ?", (amt, u_to_pay))
                conn.commit(); st.success("Done"); st.rerun()
            conn.close()
        else:
            st.error("Access Denied")
else:
    st.info("👋 Configure the sidebar and click Launch.")
