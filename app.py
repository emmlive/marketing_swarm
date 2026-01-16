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

# --- 0. HELPERS: SYSTEM HEALTH & GEO ---
def check_system_health():
    return {"Gemini 2.0": os.getenv("GOOGLE_API_KEY") is not None, "Database": os.path.exists("breatheeasy.db")}

def is_verified(username):
    conn = sqlite3.connect('breatheeasy.db')
    res = conn.execute("SELECT verified FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return res[0] == 1 if res else False

@st.cache_data(ttl=3600)
def get_geo_data():
    return {
        "Alabama": ["Birmingham", "Huntsville"], "Arizona": ["Phoenix", "Scottsdale"],
        "California": ["Los Angeles", "San Francisco"], "Florida": ["Miami", "Orlando"],
        "Illinois": ["Chicago", "Naperville"], "Texas": ["Austin", "Dallas"]
    }

# --- 1. INITIALIZATION ---
if 'gen' not in st.session_state: st.session_state.gen = False
if 'report' not in st.session_state: st.session_state.report = {}
st.set_page_config(page_title="TechInAdvance AI | Enterprise Command", page_icon="Logo1.jpeg", layout="wide")

# --- 2. CSS STYLING (SPRINT 1) ---
sidebar_color = "#2563EB"
st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFCF0; }}
    .price-card {{ background: white; padding: 20px; border-radius: 12px; border: 2px solid {sidebar_color}; text-align: center; margin-bottom: 15px; }}
    .deploy-guide {{ background: rgba(37,99,235,0.1); padding: 15px; border-radius: 10px; border-left: 6px solid {sidebar_color}; margin-bottom: 20px; }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE (SPRINT 4 INFRASTRUCTURE) ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, plan TEXT, credits INTEGER, logo_path TEXT, team_id TEXT, verified INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT, team_id TEXT, status TEXT DEFAULT "Discovery")')
    c.execute('CREATE TABLE IF NOT EXISTS master_audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, user TEXT, action_type TEXT, target_biz TEXT, location TEXT, credit_cost INTEGER, status TEXT)')
    admin_hash = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users VALUES ('admin','admin@tech.ai','Admin',?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001',1)", (admin_hash,))
    conn.commit(); conn.close()
init_db()

# --- 4. AUTH & PRICING GATE ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db')
    df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
    conn.close()
    return {'usernames': {row['username']: {'email':row['email'], 'name':row['name'], 'password':row['password']} for _, row in df.iterrows()}}

if 'authenticator' not in st.session_state:
    st.session_state.authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)
authenticator = st.session_state.authenticator

if not st.session_state.get("authentication_status"):
    t1, t2, t3 = st.tabs(["🔑 Login", "📝 Enrollment", "❓ Recovery"])
    with t1: authenticator.login(location='main')
    with t2:
        st.subheader("Choose Your Growth Plan")
        p1, p2, p3 = st.columns(3)
        p1.markdown('<div class="price-card"><h3>Basic</h3><h2>$99</h2><p>50 Credits</p></div>', unsafe_allow_html=True)
        p2.markdown('<div class="price-card" style="border-color:#7C3AED;"><h3>Pro</h3><h2>$249</h2><p>150 Credits</p></div>', unsafe_allow_html=True)
        p3.markdown('<div class="price-card"><h3>Enterprise</h3><h2>$499</h2><p>Unlimited</p></div>', unsafe_allow_html=True)
        if authenticator.register_user(location='main'): st.success("Registered! Log in now.")
    with t3: 
        authenticator.forgot_password(location='main')
        authenticator.forgot_username(location='main')
    st.stop()

# --- 5. LOGGED-IN DATA ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()
is_admin = user_row['role'] == 'admin'

# --- 6. SIDEBAR ---
with st.sidebar:
    st.image(user_row['logo_path'], width=120)
    st.metric("Credits", user_row['credits'])
    biz_name = st.text_input("Brand Name")
    loc_data = get_geo_data()
    state = st.selectbox("State", sorted(loc_data.keys()))
    city = st.selectbox("City", sorted(loc_data[state]))
    full_loc = f"{city}, {state}"
    svc = st.text_input("Service Type")
    toggles = {k: st.toggle(v, value=True) for k, v in {"analyst": "🕵️ Analyst", "ads": "📺 Ads", "creative": "🎨 Creative", "strategist": "👔 Strategist", "social": "📱 Social", "geo": "📍 GEO", "audit": "🌐 Auditor", "seo": "✍ SEO"}.items()}
    
    if is_verified(st.session_state["username"]):
        run_btn = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)
    else:
        st.warning("Verify Account to Launch")
        run_btn = False
    authenticator.logout('Sign Out', 'sidebar')

# --- 7. EXECUTION ---
if run_btn:
    with st.status("🛠️ Swarm Running...") as status:
        report_data = run_marketing_swarm({'city': full_loc, 'biz_name': biz_name, 'service': svc, 'toggles': toggles})
        st.session_state.report = report_data
        st.session_state.gen = True
        conn = sqlite3.connect('breatheeasy.db')
        conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
        conn.execute("INSERT INTO master_audit_logs (timestamp, user, action_type, target_biz, location, status) VALUES (?,?,?,?,?,?)", (datetime.now().strftime("%Y-%m-%d"), st.session_state["username"], "SWARM", biz_name, full_loc, "SUCCESS"))
        conn.commit(); conn.close(); st.rerun()

# --- 8. THE MULTIMODAL COMMAND CENTER (SPRINT 1-5 UI) ---
agent_map = [("🕵️ Analyst", "analyst"), ("📺 Ads", "ads"), ("🎨 Creative", "creative"), ("👔 Strategist", "strategist"), ("📱 Social", "social"), ("📍 GEO", "geo"), ("🌐 Auditor", "audit"), ("✍ SEO", "seo")]
DEPLOY_GUIDES = {
    "analyst": "Identify the 'Price-Gap' in the competitor table.", "ads": "Copy platform ad sets directly into Meta/Google.",
    "creative": "Implement multi-channel copy and Veo video prompts.", "strategist": "Your 30-day CEO roadmap.",
    "social": "Deploy viral hooks across LinkedIn and IG.", "geo": "Update Google Business Profile metadata.",
    "audit": "Forward this technical brief to your web developers.", "seo": "Publish technical E-E-A-T articles to your domain."
}

tab_labels = ["📖 Guide"] + [a[0] for a in agent_map] + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_admin: tab_labels.append("⚙ Admin")

tabs = st.tabs(tab_labels)
TAB = {name: tabs[i] for i, name in enumerate(tab_labels)}

with TAB["📖 Guide"]:
    st.header("📖 Agent Intelligence Manual")
    st.info("Coordinates 8 specialized AI agents for growth.")

for title, key in agent_map:
    with TAB[title]:
        st.markdown(f'<div class="deploy-guide"><b>🚀 DEPLOYMENT GUIDE:</b><br>{DEPLOY_GUIDES[key]}</div>', unsafe_allow_html=True)
        if st.session_state.gen:
            content = st.session_state.report.get(key, "Pending...")
            st.text_area(f"Refine {title}", value=str(content), height=350, key=f"edit_{key}")
            st.download_button("📄 Download Brief", str(content), f"{key}.txt")
        else: st.info(f"Launch swarm to populate the {title} seat.")

with TAB["👁️ Vision"]:
    st.subheader("👁️ Vision Inspector")
    st.file_uploader("Upload Evidence", type=['png','jpg','jpeg'])

with TAB["🎬 Veo Studio"]:
    st.subheader("🎬 Veo Cinematic Studio")
    if st.session_state.gen:
        v_prompt = st.text_area("Video Scene Prompt", value=str(st.session_state.report.get('creative', ''))[:300])
        if st.button("📽️ GENERATE AD"): st.info("Veo Rendering Engine Active...")
    else: st.warning("Launch swarm first.")

with TAB["🤝 Team Intel"]:
    st.header("🤝 Global Pipeline Kanban")
    conn = sqlite3.connect('breatheeasy.db')
    leads = pd.read_sql_query("SELECT * FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
    st.dataframe(leads, use_container_width=True)
    conn.close()

if is_admin:
    with TAB["⚙ Admin"]:
        st.header("⚙️ God-Mode Management")
        conn = sqlite3.connect('breatheeasy.db')
        m1, m2 = st.columns(2)
        m1.metric("Global Swarms", pd.read_sql_query("SELECT COUNT(*) FROM master_audit_logs", conn).iloc[0,0])
        m2.metric("Total Users", pd.read_sql_query("SELECT COUNT(*) FROM users", conn).iloc[0,0])
        st.dataframe(pd.read_sql_query("SELECT * FROM master_audit_logs ORDER BY id DESC LIMIT 50", conn))
        conn.close()
