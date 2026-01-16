import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
from datetime import datetime
from main import run_marketing_swarm 
from docx import Document
from fpdf import FPDF
from io import BytesIO

# --- 0. HELPERS & SYSTEM HEALTH (SPRINT 5) ---
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

# --- 1. INITIALIZATION ---
if 'gen' not in st.session_state: st.session_state.gen = False
if 'report' not in st.session_state: st.session_state.report = {}
if 'theme' not in st.session_state: st.session_state.theme = 'light'

st.set_page_config(page_title="TechInAdvance AI | Enterprise Command", page_icon="Logo1.jpeg", layout="wide")

# --- 2. EXECUTIVE UI CSS (SPRINT 1) ---
sidebar_color = "#2563EB"
st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFCF0; color: #1E293B; }}
    .price-card {{ 
        background: white; padding: 25px; border-radius: 15px; 
        border: 2px solid {sidebar_color}; text-align: center; 
        box-shadow: 0px 4px 10px rgba(0,0,0,0.05);
    }}
    .deploy-guide {{ 
        background: rgba(37,99,235,0.08); padding: 18px; border-radius: 12px; 
        border-left: 6px solid {sidebar_color}; margin-bottom: 25px;
    }}
    div.stButton > button {{ 
        background-color: {sidebar_color}; color: white; 
        border-radius: 8px; font-weight: 800; height: 3.2em;
    }}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE INITIALIZATION (SPRINT 4) ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, plan TEXT, credits INTEGER, logo_path TEXT, team_id TEXT, verified INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT, team_id TEXT, status TEXT DEFAULT 'Discovery')''')
    c.execute('''CREATE TABLE IF NOT EXISTS master_audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, user TEXT, action_type TEXT, target_biz TEXT, location TEXT, credit_cost INTEGER, status TEXT)''')
    
    admin_hash = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users VALUES ('admin','admin@tech.ai','Admin',?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001',1)", (admin_hash,))
    conn.commit()
    conn.close()

init_db()

# --- 4. AUTHENTICATION & TIERED PRICING (SPRINT 2) ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db')
    df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
    conn.close()
    return {'usernames': {row['username']: {'email':row['email'], 'name':row['name'], 'password':row['password']} for _, row in df.iterrows()}}

if 'authenticator' not in st.session_state:
    st.session_state.authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

authenticator = st.session_state.authenticator

if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=180)
    auth_tabs = st.tabs(["🔑 Login", "📝 Enrollment", "❓ Recovery"])
    
    with auth_tabs[0]:
        authenticator.login(location='main')
    
    with auth_tabs[1]:
        st.subheader("Select Your Growth Tier")
        col1, col2, col3 = st.columns(3)
        with col1: st.markdown('<div class="price-card"><h3>Basic</h3><h2>$99</h2><p>50 Credits</p></div>', unsafe_allow_html=True)
        with col2: st.markdown('<div class="price-card" style="border-color:#7C3AED;"><h3>Pro</h3><h2>$249</h2><p>150 Credits</p></div>', unsafe_allow_html=True)
        with col3: st.markdown('<div class="price-card"><h3>Enterprise</h3><h2>$499</h2><p>Unlimited</p></div>', unsafe_allow_html=True)
        
        if authenticator.register_user(location='main'):
            st.success("Registration successful! Please Log In.")
            
    with auth_tabs[2]:
        authenticator.forgot_password(location='main')
        authenticator.forgot_username(location='main')
    st.stop()

# --- 5. LOGGED-IN DATA FETCH ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()
is_admin = (user_row['role'] == 'admin')

# --- 6. EXPORT ENGINES (SPRINT 3) ---
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

# --- 7. SIDEBAR COMMAND CONSOLE (SPRINT 5) ---
with st.sidebar:
    health = check_system_health()
    st.caption(f"{'🟢' if all(health.values()) else '🔴'} **SYSTEM HEARTBEAT**")
    st.image(user_row['logo_path'], width=120)
    st.metric("Credits Available", user_row['credits'])
    
    biz_name = st.text_input("Brand Name", placeholder="Acme Solar")
    loc_data = get_geo_data()
    state = st.selectbox("Target State", sorted(loc_data.keys()))
    city = st.selectbox("Select City", sorted(loc_data[state]))
    full_loc = f"{city}, {state}"
    
    svc = st.text_input("Service Type", placeholder="e.g. Roof Repair")
    
    with st.expander("🤖 Swarm Personnel"):
        toggles = {k: st.toggle(v, value=True) for k, v in {
            "analyst": "🕵️ Analyst", "ads": "📺 Ad Tracker", "creative": "🎨 Creative", 
            "strategist": "👔 Strategist", "social": "📱 Social", "geo": "📍 GEO", 
            "audit": "🌐 Auditor", "seo": "✍ SEO"}.items()}
    
    if is_verified(st.session_state["username"]):
        run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
    else:
        st.warning("🛡️ Verification Required")
        if st.button("Simulate Email Verification"):
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE users SET verified = 1 WHERE username = ?", (st.session_state["username"],))
            conn.commit(); conn.close(); st.rerun()
        run_btn = False

    authenticator.logout('Sign Out', 'sidebar')

# --- 8. SWARM EXECUTION ---
if run_btn:
    if not biz_name: st.error("Brand Name required.")
    else:
        with st.status("🛠️ Coordinating Swarm Agents...", expanded=True) as status:
            report_data = run_marketing_swarm({'city': full_loc, 'biz_name': biz_name, 'service': svc, 'toggles': toggles})
            st.session_state.report = report_data
            st.session_state.gen = True
            
            # Atomic Log & Credit Deduction
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
            conn.execute("INSERT INTO master_audit_logs (timestamp, user, action_type, target_biz, location, credit_cost, status) VALUES (?,?,?,?,?,?,?)", 
                         (datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state["username"], "SWARM", biz_name, full_loc, 1, "SUCCESS"))
            conn.commit(); conn.close()
            st.rerun()

# --- 9. MULTIMODAL COMMAND CENTER (SPRINT 1-5 UI) ---

# 1. Define Map
agent_map = [
    ("🕵️ Analyst", "analyst"), ("📺 Ads", "ads"), ("🎨 Creative", "creative"), 
    ("👔 Strategist", "strategist"), ("📱 Social", "social"), ("📍 GEO", "geo"), 
    ("🌐 Auditor", "audit"), ("✍ SEO", "seo")
]

# 2. Deployment Guides (Sprint 3)
DEPLOY_GUIDES = {
    "analyst": "Identify the 'Price-Gap' in the competitor table to undercut rivals.",
    "ads": "Copy platform-specific hooks directly into your Ads Manager.",
    "creative": "Implement these multi-channel copy sets and Veo prompts.",
    "strategist": "Your 30-Day CEO-level ROI execution checklist.",
    "social": "Deploy viral hooks across LinkedIn, IG, and X.",
    "geo": "Update your Google Business Profile keywords and metadata.",
    "audit": "Forward this technical brief to your web developers immediately.",
    "seo": "Publish this technical article to secure high-authority AI rankings."
}

# 3. Create Dynamic Tabs
tab_labels = ["📖 Guide"] + [a[0] for a in agent_map] + ["👁️ Vision", "🎬 Veo Studio", "⚙ Admin"]
tabs_list = st.tabs(tab_labels)
TAB = {name: tabs_list[i] for i, name in enumerate(tab_labels)}

# Render Agent Content
for title, key in agent_map:
    with TAB[title]:
        st.markdown(f'<div class="deploy-guide"><b>🚀 DEPLOYMENT GUIDE:</b><br>{DEPLOY_GUIDES[key]}</div>', unsafe_allow_html=True)
        if st.session_state.gen:
            content = st.session_state.report.get(key, "Intelligence Pending...")
            edited = st.text_area(f"Refine {title}", value=str(content), height=350, key=f"edit_{key}")
            
            c1, c2 = st.columns(2)
            with c1: st.download_button("📄 Word Brief", create_word_doc(edited, title), f"{key}.docx", key=f"w_{key}")
            with c2: st.download_button("📕 PDF Report", create_pdf(edited, svc, full_loc), f"{key}.pdf", key=f"p_{key}")
        else:
            st.info(f"Launch Swarm to populate the {title} seat.")

# Rendering Specialty Tabs
with TAB["👁️ Vision"]:
    st.subheader("👁️ Vision Inspector")
    v_file = st.file_uploader("Upload Forensic Evidence", type=['png','jpg','jpeg'])
    if v_file: st.image(v_file, use_container_width=True)

with TAB["🎬 Veo Studio"]:
    st.subheader("🎬 Veo Cinematic Studio")
    if st.session_state.gen:
        v_prompt = st.text_area("Video Scene Prompt", value=str(st.session_state.report.get('creative', ''))[:400])
        if st.button("📽️ GENERATE AD"): st.info("Veo Engine Rendering Cinematic Asset...")
    else: st.warning("Launch swarm first to generate creative context.")

if is_admin:
    with TAB["⚙ Admin"]:
        st.header("⚙️ God-Mode Management")
        conn = sqlite3.connect('breatheeasy.db')
        m1, m2 = st.columns(2)
        m1.metric("Global Swarms", pd.read_sql_query("SELECT COUNT(*) FROM master_audit_logs", conn).iloc[0,0])
        m2.metric("Total Users", pd.read_sql_query("SELECT COUNT(*) FROM users", conn).iloc[0,0])
        st.subheader("Audit Trail")
        st.dataframe(pd.read_sql_query("SELECT * FROM master_audit_logs ORDER BY id DESC LIMIT 50", conn), use_container_width=True)
        conn.close()
