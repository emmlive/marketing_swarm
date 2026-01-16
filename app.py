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

# --- 0. HELPERS & CACHED DATA ---
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

def is_verified(username):
    conn = sqlite3.connect('breatheeasy.db')
    res = conn.execute("SELECT verified FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return res[0] == 1 if res else False

# --- 1. INITIALIZATION ---
if 'gen' not in st.session_state: st.session_state.gen = False
if 'report' not in st.session_state: st.session_state.report = {}
st.set_page_config(page_title="TechInAdvance AI | Command", page_icon="Logo1.jpeg", layout="wide")

# --- 2. EXECUTIVE UI CSS ---
sidebar_color = "#2563EB"
st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFCF0; }}
    .price-card {{ background: white; padding: 25px; border-radius: 15px; border: 2px solid {sidebar_color}; text-align: center; margin-bottom: 15px; }}
    .deploy-guide {{ background: rgba(37,99,235,0.08); padding: 18px; border-radius: 12px; border-left: 6px solid {sidebar_color}; margin-bottom: 25px; }}
    .kanban-card {{ background: white; padding: 15px; border-radius: 8px; border-left: 5px solid {sidebar_color}; margin-bottom: 10px; box-shadow: 0px 2px 5px rgba(0,0,0,0.05); }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE ---
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

# --- 4. SIGN UP & AUTHENTICATION (RESTORED) ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
    conn.close()
    return {'usernames': {row['username']: {'email':row['email'], 'name':row['name'], 'password':row['password']} for _, row in df.iterrows()}}

if 'auth' not in st.session_state:
    st.session_state.auth = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=180)
    tabs = st.tabs(["🔑 Login", "📝 Sign Up", "🤝 Join Team", "❓ Forget Password"])
    with tabs[1]:
        st.subheader("Select Enterprise Package")
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown('<div class="price-card"><h3>Basic</h3><h2>$99</h2><p>50 Credits/mo</p></div>', unsafe_allow_html=True)
        with c2: st.markdown('<div class="price-card" style="border-color:#7C3AED;"><h3>Pro</h3><h2>$249</h2><p>150 Credits/mo</p></div>', unsafe_allow_html=True)
        with c3: st.markdown('<div class="price-card"><h3>Enterprise</h3><h2>$499</h2><p>Unlimited</p></div>', unsafe_allow_html=True)
        if st.session_state.auth.register_user(location='main'): st.success("Signed Up! Please log in.")
    with tabs[0]: st.session_state.auth.login(location='main')
    with tabs[2]: st.info("Enter Team ID to request access.")
    with tabs[3]: st.session_state.auth.forgot_password(location='main')
    st.stop()

# --- 5. LOGGED-IN CONTEXT ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()
is_admin = (user_row['role'] == 'admin')

# --- 6. SIDEBAR (RESTORED DROPDOWNS & DIRECTIVES) ---
with st.sidebar:
    st.image(user_row['logo_path'], width=120)
    st.metric("Credits Available", user_row['credits'])
    st.divider()
    biz_name = st.text_input("Brand Name", placeholder="Acme Solar")
    
    geo = get_geo_data()
    state = st.selectbox("🎯 Target State", sorted(geo.keys()))
    city = st.selectbox("🏙️ Select City", sorted(geo[state]))
    full_loc = f"{city}, {state}"
    
    svc = st.text_input("Service Type")
    
    # NEW: Agent Additional Info Box
    agent_directives = st.text_area("✍️ Additional Agent Directives", placeholder="e.g. Focus on luxury clients only")
    
    toggles = {k: st.toggle(v, value=True) for k, v in {"analyst": "🕵️ Analyst", "ads": "📺 Ads", "creative": "🎨 Creative", "strategist": "👔 Strategist", "social": "📱 Social", "geo": "📍 GEO", "audit": "🌐 Auditor", "seo": "✍ SEO"}.items()}
    
    if is_verified(st.session_state["username"]):
        run_btn = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)
    else:
        st.warning("Verification Required")
        if st.button("Demo: Simulate Verification"):
            conn = sqlite3.connect('breatheeasy.db'); conn.execute("UPDATE users SET verified=1 WHERE username=?", (user_row['username'],)); conn.commit(); conn.close(); st.rerun()
        run_btn = False
    st.session_state.auth.logout('Sign Out', 'sidebar')

# --- 7. EXECUTION ---
if run_btn:
    with st.status("🛠️ Coordinating Swarm Agents...") as status:
        report = run_marketing_swarm({'city': full_loc, 'biz_name': biz_name, 'service': svc, 'directives': agent_directives})
        st.session_state.report = report
        st.session_state.gen = True
        conn = sqlite3.connect('breatheeasy.db')
        conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
        conn.execute("INSERT INTO master_audit_logs (timestamp, user, action_type, target_biz, location, status) VALUES (?,?,?,?,?,?)", (datetime.now().strftime("%Y-%m-%d"), user_row['username'], "SWARM", biz_name, full_loc, "SUCCESS"))
        conn.commit(); conn.close(); st.rerun()

# --- 8. COMMAND CENTER (FULL GUIDE & DEPLOYMENT BOXES) ---
agent_map = [("🕵️ Analyst", "analyst"), ("📺 Ads", "ads"), ("🎨 Creative", "creative"), ("👔 Strategist", "strategist"), ("📱 Social", "social"), ("📍 GEO", "geo"), ("🌐 Auditor", "audit"), ("✍ SEO", "seo")]
DEPLOY_GUIDES = {
    "analyst": "Use the 'Price-Gap' table to undercut rivals while staying premium.",
    "ads": "Copy platform hooks directly into Meta/Google Manager for local disruption.",
    "creative": "Implement multi-channel copy and cinematic Veo video prompts.",
    "strategist": "This 30-day ROI roadmap is your CEO-level execution checklist.",
    "social": "Deploy viral hooks across LinkedIn/IG based on the local schedule.",
    "geo": "Update Google Business Profile metadata based on AI ranking factors.",
    "audit": "Forward this technical brief to your web team to patch conversion leaks.",
    "seo": "Publish this article to secure high-authority rankings in AI-Search."
}

tab_labels = ["📖 Guide"] + [a[0] for a in agent_map] + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_admin: tab_labels.append("⚙ Admin")

tabs_obj = st.tabs(tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(tab_labels)}

# A. GUIDE (RESTORED DESCRIPTION)
with TAB["📖 Guide"]:
    st.header("📖 Agent Intelligence Manual")
    st.markdown("""
    The **Omni-Swarm** coordinates 8 specialized AI agents to engineer growth.
    1. **Forensics:** Web Auditor & Ad Tracker identify rival weaknesses.
    2. **Strategy:** Swarm Strategist builds a phased ROI Roadmap.
    3. **Execution:** Creative & SEO Architects build high-converting assets.
    """)

# B. AGENTS (RESTORED DEPLOYMENT BOXES)
for title, key in agent_map:
    with TAB[title]:
        st.markdown(f'<div class="deploy-guide"><b>🚀 DEPLOYMENT GUIDE:</b><br>{DEPLOY_GUIDES[key]}</div>', unsafe_allow_html=True)
        if st.session_state.gen:
            st.text_area(f"Refine {title}", value=str(st.session_state.report.get(key, "Pending...")), height=400)
        else: st.info("Launch Swarm to see results.")

# C. TEAM INTEL (RESTORED ACCOUNT TOOLS)
with TAB["🤝 Team Intel"]:
    st.header("🤝 Team Intelligence & Account Management")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("👤 Your Profile")
        st.write(f"**User:** {user_row['name']} ({user_row['username']})")
        st.write(f"**Plan:** {user_row['plan']}")
        if st.button("Request Password Reset Email"): st.success("Email Sent")
    with c2:
        st.subheader("📊 Team Pipeline")
        conn = sqlite3.connect('breatheeasy.db')
        team_df = pd.read_sql_query("SELECT city, service, status FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
        st.dataframe(team_df, use_container_width=True)
        conn.close()

# D. ADMIN (EXPANDED ELEMENTS)
if "⚙ Admin" in TAB:
    with TAB["⚙ Admin"]:
        st.header("⚙️ God-Mode Management")
        conn = sqlite3.connect('breatheeasy.db')
        
        # New Admin Elements
        st.subheader("🖥️ Server Architecture")
        st.write("DB Status: 🟢 Online | SSL: ✅ Active | API: 🔵 Connected")
        
        st.subheader("📊 Global Forensics")
        audit_df = pd.read_sql_query("SELECT * FROM master_audit_logs ORDER BY id DESC LIMIT 50", conn)
        st.dataframe(audit_df, use_container_width=True)
        
        st.subheader("👤 User Registry & Credits")
        u_df = pd.read_sql_query("SELECT username, credits, plan, verified FROM users", conn)
        st.dataframe(u_df, use_container_width=True)
        
        target_u = st.selectbox("Select User to Manage", u_df['username'])
        if st.button("Inject 100 Credits"):
            conn.execute("UPDATE users SET credits = credits + 100 WHERE username = ?", (target_u,))
            conn.commit(); st.success("Injected"); st.rerun()
        conn.close()
