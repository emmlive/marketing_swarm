import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
import json
from datetime import datetime
from main import run_marketing_swarm 
from docx import Document
from fpdf import FPDF
from io import BytesIO

# --- 0. SPRINT 5: PERFORMANCE HELPERS & GEO-CACHING ---
@st.cache_data(ttl=3600)
def get_geo_data():
    return {
        "Alabama": ["Birmingham", "Huntsville", "Mobile"],
        "Arizona": ["Phoenix", "Scottsdale", "Tucson"],
        "California": ["Los Angeles", "San Francisco", "San Diego"],
        "Florida": ["Miami", "Orlando", "Tampa"],
        "Texas": ["Austin", "Dallas", "Houston"],
    }

def check_system_health():
    return {
        "Gemini 2.0": os.getenv("GOOGLE_API_KEY") is not None,
        "Serper API": os.getenv("SERPER_API_KEY") is not None,
        "Database": os.path.exists("breatheeasy.db"),
    }

# --- 1. SPRINT 1: EXECUTIVE UI & BRAND IDENTITY ---
st.set_page_config(page_title="TechInAdvance AI | Command", page_icon="Logo1.jpeg", layout="wide")

if 'gen' not in st.session_state: st.session_state.gen = False
if 'report' not in st.session_state: st.session_state.report = {}

sidebar_color = "#2563EB"
st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFCF0; color: #1E293B; }}
    [data-testid="stSidebar"] {{ border-right: 3px solid rgba(0,0,0,0.1); }}
    .price-card {{ background: white; padding: 25px; border-radius: 15px; border: 2px solid {sidebar_color}; text-align: center; margin-bottom: 15px; box-shadow: 0px 4px 10px rgba(0,0,0,0.05); }}
    .deploy-guide {{ background: rgba(37, 99, 235, 0.08); padding: 18px; border-radius: 12px; border-left: 6px solid {sidebar_color}; margin-bottom: 25px; }}
    .kanban-card {{ background: white; padding: 15px; border-radius: 10px; margin-bottom: 12px; border-left: 5px solid {sidebar_color}; box-shadow: 0px 2px 6px rgba(0,0,0,0.04); }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800; height: 3.2em; }}
    </style>
""", unsafe_allow_html=True)

# --- 2. SPRINT 4: DATABASE INFRASTRUCTURE ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, plan TEXT, credits INTEGER, logo_path TEXT, team_id TEXT, verified INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, city TEXT, service TEXT, status TEXT DEFAULT "Discovery", team_id TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS master_audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, user TEXT, action_type TEXT, target_biz TEXT, location TEXT, credit_cost INTEGER, status TEXT)')
    
    admin_pw = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users VALUES ('admin','admin@tech.ai','Admin',?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001',1)", (admin_pw,))
    conn.commit(); conn.close()

init_db()

# --- 3. SPRINT 2: AUTHENTICATION & SIGN UP Tiers ---
def get_creds():
    conn = sqlite3.connect('breatheeasy.db')
    df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
    conn.close()
    return {'usernames': {r['username']: {'email':r['email'], 'name':r['name'], 'password':r['password']} for _,r in df.iterrows()}}

if 'auth' not in st.session_state:
    st.session_state.auth = stauth.Authenticate(get_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=180)
    auth_tabs = st.tabs(["🔑 Login", "📝 Sign Up", "🤝 Join Team", "❓ Forget Password"])
    
    with auth_tabs[1]:
        st.subheader("Select Enterprise Package")
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown('<div class="price-card"><h3>Basic</h3><h2>$99</h2><p>50 Credits/mo</p></div>', unsafe_allow_html=True)
        with c2: st.markdown('<div class="price-card" style="border-color:#7C3AED;"><h3>Pro</h3><h2>$249</h2><p>150 Credits/mo</p></div>', unsafe_allow_html=True)
        with c3: st.markdown('<div class="price-card"><h3>Enterprise</h3><h2>$499</h2><p>Unlimited</p></div>', unsafe_allow_html=True)
        if st.session_state.auth.register_user(location='main'): st.success("Sign up complete! Log in now.")
    
    with auth_tabs[0]: st.session_state.auth.login(location='main')
    with auth_tabs[3]: st.session_state.auth.forgot_password(location='main')
    st.stop()

# Load User Context
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()
is_admin = (user_row['role'] == 'admin')

# --- 4. SPRINT 5: SIDEBAR & DIRECTIVES ---
with st.sidebar:
    health = check_system_health()
    st.caption(f"{'🟢' if all(health.values()) else '🔴'} **SYSTEM HEARTBEAT**")
    st.image(user_row['logo_path'], width=120)
    st.metric("Credits Available", user_row['credits'])
    
    biz_name = st.text_input("Brand Name")
    geo = get_geo_data()
    state = st.selectbox("🎯 Target State", sorted(geo.keys()))
    city = st.selectbox("🏙️ Select City", sorted(geo[state]))
    full_loc = f"{city}, {state}"
    svc = st.text_input("Service Type")
    
    # Directive box for Agents
    agent_info = st.text_area("✍️ Additional Agent Directives", placeholder="e.g. Focus on high-ticket luxury clients.")
    
    if user_row['verified'] == 1:
        run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary")
    else:
        st.warning("Verification Required")
        if st.button("Demo: Simulate Verification"):
            conn = sqlite3.connect('breatheeasy.db'); conn.execute("UPDATE users SET verified=1 WHERE username=?", (user_row['username'],)); conn.commit(); conn.close(); st.rerun()
        run_btn = False
    st.session_state.auth.logout('Sign Out', 'sidebar')

# --- 5. SPRINT 3: AGENT SEATS & DEPLOYMENT GUIDES ---
agent_map = [("🕵️ Analyst", "analyst"), ("📺 Ads", "ads"), ("🎨 Creative", "creative"), ("👔 Strategist", "strategist"), ("📱 Social", "social"), ("📍 GEO", "geo"), ("🌐 Auditor", "auditor"), ("✍ SEO", "seo")]
DEPLOY_GUIDES = {
    "analyst": "Identify the 'Price-Gap' in the competitor table to undercut rivals.",
    "ads": "Copy platform hooks directly into Meta/Google Manager for local disruption.",
    "creative": "Implement multi-channel copy and cinematic Veo video prompts.",
    "strategist": "This 30-day ROI roadmap is your CEO-level execution checklist.",
    "social": "Deploy viral hooks across LinkedIn/IG based on the local engagement schedule.",
    "geo": "Update Google Business Profile metadata based on AI-Map ranking factors.",
    "audit": "Forward this technical brief to your web team to patch conversion leaks.",
    "seo": "Publish this technical article to secure high-authority rankings in AI-Search (SGE)."
}

tab_labels = ["📖 Guide"] + [a[0] for a in agent_map] + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_admin: tab_labels.append("⚙ Admin")

tabs_obj = st.tabs(tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(tab_labels)}

# Render Guide Description (Sprint 1)
with TAB["📖 Guide"]:
    st.header("📖 Agent Intelligence Manual")
    st.markdown("""
    The **Omni-Swarm** engine coordinates 8 specialized AI agents to engineer growth.
    1. **Forensics:** Identifying competitor weaknesses via Web Auditor and Ad Tracker.
    2. **Strategy:** Synthesizing data into a phased 30-Day ROI Roadmap.
    3. **Production:** Building high-fidelity copy and cinematic video assets.
    """)

# Dynamic Agent Rendering (Sprint 3)
for title, key in agent_map:
    with TAB[title]:
        st.markdown(f'<div class="deploy-guide"><b>🚀 DEPLOYMENT GUIDE:</b><br>{DEPLOY_GUIDES[key]}</div>', unsafe_allow_html=True)
        if st.session_state.gen:
            content = st.session_state.report.get(key, "Generating intelligence...")
            st.text_area(f"Refine {title}", value=str(content), height=400)
        else: st.info("Launch Swarm to see results.")

# --- 6. SPRINT 4: TEAM TOOLS & ADMIN GOD-MODE ---
with TAB["🤝 Team Intel"]:
    st.header("🤝 Team Account Management")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("👤 User Tools")
        st.write(f"**Account:** {user_row['name']}")
        st.write(f"**Plan:** {user_row['plan']}")
        if st.button("Request Security Credentials Reset"): st.success("Verification email sent.")
    with c2:
        st.subheader("📊 Team Pipeline")
        conn = sqlite3.connect('breatheeasy.db')
        team_df = pd.read_sql_query("SELECT city, service, status FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
        st.dataframe(team_df, use_container_width=True)
        conn.close()

if "⚙ Admin" in TAB:
    with TAB["⚙ Admin"]:
        st.header("⚙️ God-Mode Management")
        conn = sqlite3.connect('breatheeasy.db')
        
        st.subheader("📊 Global Forensic Trail")
        audit_df = pd.read_sql_query("SELECT * FROM master_audit_logs ORDER BY id DESC LIMIT 100", conn)
        st.dataframe(audit_df, use_container_width=True)
        
        st.subheader("👤 User Registry Management")
        u_df = pd.read_sql_query("SELECT username, email, plan, credits FROM users", conn)
        st.dataframe(u_df, use_container_width=True)
        
        target_u = st.selectbox("Select Target User", u_df['username'])
        if st.button("Inject 100 System Credits"):
            conn.execute("UPDATE users SET credits = credits + 100 WHERE username = ?", (target_u,))
            conn.commit(); st.success("Credits Injected"); st.rerun()
        conn.close()
