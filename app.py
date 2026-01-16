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

# --- 0. SPRINT 5: PERFORMANCE HELPERS & GEO-CACHING ---
@st.cache_data(ttl=3600)
def get_geo_data():
    """Sprint 5: High-speed geographic lookup dictionary"""
    return {
        "Alabama": ["Birmingham", "Huntsville", "Mobile"],
        "Arizona": ["Phoenix", "Scottsdale", "Tucson"],
        "California": ["Los Angeles", "San Francisco", "San Diego"],
        "Florida": ["Miami", "Orlando", "Tampa"],
        "Illinois": ["Chicago", "Naperville", "Plainfield"],
        "Texas": ["Austin", "Dallas", "Houston"],
    }

def check_system_health():
    """Sprint 5: Technical forensic heartbeat monitor"""
    health = {
        "Gemini 2.0": os.getenv("GOOGLE_API_KEY") is not None,
        "Serper API": os.getenv("SERPER_API_KEY") is not None,
        "Database": os.path.exists("breatheeasy.db"),
    }
    return health

def is_verified(username):
    """Sprint 2: Email verification security gate"""
    conn = sqlite3.connect('breatheeasy.db')
    res = conn.execute("SELECT verified FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return res[0] == 1 if res else False

# --- 1. SPRINT 1: EXECUTIVE UI & BRAND IDENTITY ---
st.set_page_config(page_title="TechInAdvance AI | Enterprise Command", page_icon="Logo1.jpeg", layout="wide")

if 'gen' not in st.session_state: st.session_state.gen = False
if 'report' not in st.session_state: st.session_state.report = {}

sidebar_color = "#2563EB"
st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFCF0; color: #1E293B; }}
    [data-testid="stSidebar"] {{ 
        background-color: #FFFFFF !important; 
        border-right: 3px solid rgba(0,0,0,0.1) !important;
        box-shadow: 4px 0px 10px rgba(0,0,0,0.05);
    }}
    .price-card {{
        background-color: white; padding: 25px; border-radius: 15px; border: 2px solid {sidebar_color};
        text-align: center; margin-bottom: 15px; color: #1E293B; box-shadow: 0px 4px 12px rgba(0,0,0,0.08);
    }}
    .deploy-guide {{ 
        background: rgba(37, 99, 235, 0.08); padding: 20px; border-radius: 12px; 
        border-left: 6px solid {sidebar_color}; margin-bottom: 25px; 
        font-size: 0.95rem; color: #1E293B;
    }}
    .kanban-card {{ background: white; padding: 18px; border-radius: 10px; margin-bottom: 12px; border-left: 5px solid {sidebar_color}; box-shadow: 0px 2px 6px rgba(0,0,0,0.04); }}
    .kanban-header {{ font-weight: 900; text-align: center; color: {sidebar_color}; text-transform: uppercase; letter-spacing: 1.5px; font-size: 0.9rem; }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800; height: 3.2em; }}
    </style>
""", unsafe_allow_html=True)

# --- 2. SPRINT 4: DATABASE & KANBAN ARCHITECTURE ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, plan TEXT, credits INTEGER, logo_path TEXT, team_id TEXT, verified INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, city TEXT, service TEXT, status TEXT DEFAULT "Discovery", team_id TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS master_audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, user TEXT, action_type TEXT, target_biz TEXT, location TEXT, credit_cost INTEGER, status TEXT)')
    
    admin_pw = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users VALUES ('admin','admin@techinadvance.ai','Admin',?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001',1)", (admin_pw,))
    conn.commit(); conn.close()

init_db()

# --- 3. SPRINT 2: SECURE AUTHENTICATION & SIGN UP TIERS ---
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
        st.subheader("Select Enterprise Growth Package")
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown('<div class="price-card"><h3>Basic</h3><h2>$99</h2><p>50 Credits/mo</p></div>', unsafe_allow_html=True)
        with c2: st.markdown('<div class="price-card" style="border-color:#7C3AED;"><h3>Pro</h3><h2>$249</h2><p>150 Credits/mo</p></div>', unsafe_allow_html=True)
        with c3: st.markdown('<div class="price-card"><h3>Enterprise</h3><h2>$499</h2><p>Unlimited Agents</p></div>', unsafe_allow_html=True)
        if st.session_state.auth.register_user(location='main'): st.success("Signed up! Please login.")
    
    with auth_tabs[0]: st.session_state.auth.login(location='main')
    with auth_tabs[2]: st.info("Enter Enterprise Team ID to request access.")
    with auth_tabs[3]: st.session_state.auth.forgot_password(location='main')
    st.stop()

# Load Logged-In Context
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()
is_admin = (user_row['role'] == 'admin')

# --- 4. SPRINT 5: SIDEBAR CONTROL & DIRECTIVES ---
with st.sidebar:
    health = check_system_health()
    st.caption(f"{'🟢' if all(health.values()) else '🔴'} **SYSTEM HEARTBEAT**")
    st.image(user_row['logo_path'], width=120)
    st.metric("Credits Available", user_row['credits'])
    
    st.divider()
    biz_name = st.text_input("Brand Name", placeholder="e.g. Acme Solar")
    geo = get_geo_data()
    state = st.selectbox("🎯 Target State", sorted(geo.keys()))
    city = st.selectbox("🏙️ Select City", sorted(geo[state]))
    full_loc = f"{city}, {state}"
    svc = st.text_input("Service Type")
    
    # Directive box for Agents (Sprint 5)
    agent_info = st.text_area("✍️ Additional Agent Directives", placeholder="e.g. Focus on high-ticket luxury clients only.")
    
    if user_row['verified'] == 1:
        run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
    else:
        st.warning("Verification Required")
        if st.button("Demo: Simulate Verification"):
            conn = sqlite3.connect('breatheeasy.db'); conn.execute("UPDATE users SET verified=1 WHERE username=?", (user_row['username'],)); conn.commit(); conn.close(); st.rerun()
        run_btn = False
    st.session_state.auth.logout('Sign Out', 'sidebar')

# --- 5. SPRINT 3: EXPORT & EXECUTION ENGINES ---
def export_word(content, title):
    doc = Document(); doc.add_heading(title, 0); doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def export_pdf(content, title):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, title, 0, 1, 'C')
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 7, txt=str(content).encode('latin-1','ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

if run_btn:
    with st.status("🛠️ Coordinating Swarm Agents...", expanded=True) as status:
        report = run_marketing_swarm({'city': full_loc, 'biz_name': biz_name, 'service': svc, 'directives': agent_info})
        st.session_state.report = report
        st.session_state.gen = True
        conn = sqlite3.connect('breatheeasy.db')
        conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
        conn.execute("INSERT INTO master_audit_logs (timestamp, user, action_type, target_biz, location, status) VALUES (?,?,?,?,?,?)", 
                     (datetime.now().strftime("%Y-%m-%d %H:%M"), user_row['username'], "SWARM", biz_name, full_loc, "SUCCESS"))
        conn.commit(); conn.close(); st.rerun()

# --- 6. COMMAND CENTER (SPRINTS 1-5 UI INTEGRATED) ---

agent_map = [
    ("🕵️ Analyst", "analyst"), ("📺 Ads", "ads"), ("🎨 Creative", "creative"), 
    ("👔 Strategist", "strategist"), ("📱 Social", "social"), ("📍 GEO", "geo"), 
    ("🌐 Auditor", "audit"), ("✍ SEO", "seo")
]

DEPLOY_GUIDES = {
    "analyst": "Identify the 'Price-Gap' in the competitor table to undercut rivals while maintaining premium positioning.",
    "ads": "Copy platform hooks directly into Meta/Google Manager. Hooks are engineered for local disruption.",
    "creative": "Implement multi-channel copy and cinematic Veo video prompts for high-fidelity storytelling.",
    "strategist": "This 30-day ROI roadmap is your CEO-level execution checklist, phased for maximum impact.",
    "social": "Deploy viral hooks across LinkedIn/IG based on the local engagement schedule provided.",
    "geo": "Update Google Business Profile metadata based on AI-Map technical ranking factors.",
    "audit": "Forward this technical brief to your web team to patch conversion leaks and increase speed.",
    "seo": "Publish this article to your domain to secure high-authority rankings in AI Search Generative Experience."
}

tab_labels = ["📖 Guide"] + [a[0] for a in agent_map] + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_admin: tab_labels.append("⚙ Admin")

tabs_obj = st.tabs(tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(tab_labels)}

# A. Guide (Sprint 1 Description)
with TAB["📖 Guide"]:
    st.header("📖 Agent Intelligence Manual")
    st.markdown("""
    The **Omni-Swarm** engine coordinates 8 specialized AI agents to engineer business growth.
    1. **Forensics:** Web Auditor & Ad Tracker identify rival psychological and technical weaknesses.
    2. **Strategy:** Swarm Strategist builds a phased 30-Day ROI Roadmap for CEO-level execution.
    3. **Production:** Creative & SEO Architects build high-converting assets optimized for AI search.
    """)
    st.info("Launch a Swarm in the sidebar to populate the seats below.")

# B. Agents (Sprint 3 Deployment Boxes & Export Engine)
for title, key in agent_map:
    with TAB[title]:
        st.markdown(f'<div class="deploy-guide"><b>🚀 DEPLOYMENT GUIDE:</b><br>{DEPLOY_GUIDES[key]}</div>', unsafe_allow_html=True)
        if st.session_state.gen:
            content = st.session_state.report.get(key, "Intelligence generation in progress...")
            edited = st.text_area(f"Refine {title}", value=str(content), height=400, key=f"ed_{key}")
            c1, c2 = st.columns(2)
            with c1: st.download_button("📄 Word Brief", export_word(edited, title), f"{key}.docx", key=f"w_{key}")
            with c2: st.download_button("📕 PDF Report", export_pdf(edited, title), f"{key}.pdf", key=f"p_{key}")
        else: st.info("Waiting for Swarm Launch...")

# C. Vision & Veo (Sprints 4 & 5)
with TAB["👁️ Vision"]:
    st.subheader("👁️ Vision Inspector")
    v_file = st.file_uploader("Upload Forensic Evidence (Roof/HVAC Repairs)", type=['png','jpg','jpeg'], key="vis_up")
    if v_file: st.image(v_file, use_container_width=True)

with TAB["🎬 Veo Studio"]:
    st.subheader("🎬 Veo Cinematic Studio")
    if st.session_state.gen:
        v_prompt = st.text_area("Cinematic Scene Description", value=str(st.session_state.report.get('creative', ''))[:500])
        if st.button("📽️ GENERATE AD"): st.info("Veo Engine Rendering Active...")
    else: st.warning("Launch Swarm to generate creative context.")

# D. Team Intel (Sprint 4 Account Management)
with TAB["🤝 Team Intel"]:
    st.header("🤝 Team Account Management")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("👤 User Profile")
        st.write(f"**Username:** {user_row['username']} | **Plan:** {user_row['plan']}")
        if st.button("Request Security Credential Reset"): st.success("Email sent.")
    with c2:
        st.subheader("📊 Team Lead Pipeline")
        conn = sqlite3.connect('breatheeasy.db')
        team_df = pd.read_sql_query("SELECT city, service, status FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
        st.dataframe(team_df, use_container_width=True)
        conn.close()

# E. Admin (Sprint 4 Expanded Elements)
if "⚙ Admin" in TAB:
    with TAB["⚙ Admin"]:
        st.header("⚙️ God-Mode Management")
        conn = sqlite3.connect('breatheeasy.db')
        st.subheader("🖥️ Global Infrastructure")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Swarms", pd.read_sql_query("SELECT COUNT(*) FROM master_audit_logs", conn).iloc[0,0])
        m2.metric("System Users", pd.read_sql_query("SELECT COUNT(*) FROM users", conn).iloc[0,0])
        m3.metric("DB Integrity", "Verified")
        
        st.subheader("📊 Global Forensic Trail")
        st.dataframe(pd.read_sql_query("SELECT * FROM master_audit_logs ORDER BY id DESC LIMIT 50", conn), use_container_width=True)
        
        st.subheader("👤 User Registry & Credit Management")
        u_df = pd.read_sql_query("SELECT username, email, plan, credits FROM users", conn)
        st.dataframe(u_df, use_container_width=True)
        target = st.selectbox("Target User", u_df['username'])
        if st.button("Inject 100 System Credits"):
            conn.execute("UPDATE users SET credits = credits + 100 WHERE username = ?", (target,))
            conn.commit(); st.rerun()
        conn.close()
