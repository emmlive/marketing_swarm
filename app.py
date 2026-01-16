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

# --- 0. HELPER FUNCTIONS: VERIFICATION, SYSTEM HEALTH & EXPORTS ---

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

def create_word_doc(content, title):
    doc = Document()
    doc.add_heading(f'Intelligence Brief: {title}', 0)
    doc.add_paragraph(str(content))
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

def create_pdf(content, title):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f'Intelligence Brief: {title}', 0, 1, 'C')
    pdf.set_font("Arial", size=11)
    # Sanitize content for PDF encoding
    clean_text = str(content).encode('latin-1', 'ignore').decode('latin-1')
    pdf.multi_cell(0, 10, txt=clean_text)
    return pdf.output(dest='S').encode('latin-1')

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

# --- 2. EXECUTIVE UI CSS (SPRINT 1) ---
sidebar_color = "#2563EB"
st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFCF0; color: #1E293B; }}
    .price-card {{ background-color: white; padding: 20px; border-radius: 12px; border: 2px solid {sidebar_color}; text-align: center; margin-bottom: 15px; }}
    .deploy-guide {{ background: rgba(37, 99, 235, 0.1); padding: 15px; border-radius: 10px; border-left: 6px solid {sidebar_color}; margin-bottom: 25px; }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800; height: 3.2em; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, plan TEXT, credits INTEGER DEFAULT 0, logo_path TEXT, team_id TEXT, verified INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS master_audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, user TEXT, action_type TEXT, target_biz TEXT, location TEXT, credit_cost INTEGER, status TEXT)')
    admin_hash = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users VALUES ('admin','admin@tech.ai','Admin',?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001',1)", (admin_hash,))
    conn.commit()
    conn.close()

init_db()

# --- 4. AUTHENTICATION & TIERED PRICING (SPRINT 2) ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
    conn.close()
    return {'usernames': {row['username']: {'email':row['email'], 'name':row['name'], 'password':row['password']} for _, row in df.iterrows()}}

if 'authenticator' not in st.session_state:
    st.session_state.authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

authenticator = st.session_state.authenticator

if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=200)
    auth_tabs = st.tabs(["🔑 Login", "📝 Enrollment", "🤝 Join Team", "❓ Recovery"])
    
    with auth_tabs[1]:
        st.subheader("Select Your Growth Tier")
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown('<div class="price-card"><h3>Basic</h3><h2>$99</h2><p>50 Credits</p></div>', unsafe_allow_html=True)
        with c2: st.markdown('<div class="price-card" style="border-color:#7C3AED;"><h3>Pro</h3><h2>$249</h2><p>150 Credits</p></div>', unsafe_allow_html=True)
        with c3: st.markdown('<div class="price-card"><h3>Enterprise</h3><h2>$499</h2><p>Unlimited</p></div>', unsafe_allow_html=True)
        if authenticator.register_user(location='main'): st.success("Registered! Log in now.")
    
    with auth_tabs[0]: authenticator.login(location='main')
    with auth_tabs[3]:
        authenticator.forgot_password(location='main')
        authenticator.forgot_username(location='main')
    st.stop()

# Load User Data
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()
is_admin = user_row['role'] == 'admin'

# --- 5. SIDEBAR COMMAND CONSOLE (SPRINT 5) ---
with st.sidebar:
    st.image(user_row['logo_path'], width=120)
    st.metric("Credits Available", user_row['credits'])
    biz_name = st.text_input("Brand Name", placeholder="Acme Solar")
    loc_data = get_geo_data()
    state = st.selectbox("Target State", sorted(loc_data.keys()))
    city = st.selectbox("Select City", loc_data[state])
    full_loc = f"{city}, {state}"
    
    svc = st.text_input("Service Type")
    toggles = {k: st.toggle(v, value=True) for k, v in {
        "analyst": "🕵️ Analyst", "ads": "📺 Ad Tracker", "creative": "🎨 Creative", 
        "strategist": "👔 Strategist", "social": "📱 Social", "geo": "📍 GEO", 
        "audit": "🌐 Auditor", "seo": "✍ SEO"}.items()}
    
    if is_verified(st.session_state["username"]):
        run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
    else:
        st.warning("Account Verification Required")
        run_btn = False
    authenticator.logout('Sign Out', 'sidebar')

# --- 6. SWARM EXECUTION ENGINE ---
if run_btn:
    with st.status("🛠️ Coordinating Swarm...", expanded=True) as status:
        report_data = run_marketing_swarm({'city': full_loc, 'biz_name': biz_name, 'service': svc, 'toggles': toggles})
        st.session_state.report = report_data
        st.session_state.gen = True
        
        conn = sqlite3.connect('breatheeasy.db')
        conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
        conn.execute("INSERT INTO master_audit_logs (timestamp, user, action_type, target_biz, location, credit_cost, status) VALUES (?,?,?,?,?,?,?)", 
                     (datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state["username"], "SWARM", biz_name, full_loc, 1, "SUCCESS"))
        conn.commit(); conn.close()
        st.rerun()

# --- 7. MULTIMODAL COMMAND CENTER (SPRINT 1-5 UI + EXPORT ENGINE) ---

agent_map = [
    ("🕵️ Analyst", "analyst"), ("📺 Ads", "ads"), ("🎨 Creative", "creative"), 
    ("👔 Strategist", "strategist"), ("📱 Social", "social"), ("📍 GEO", "geo"), 
    ("🌐 Auditor", "audit"), ("✍ SEO", "seo")
]
DEPLOYMENT_GUIDES = {
    "analyst": "Identify the 'Price-Gap' in the competitor table to undercut rivals.",
    "ads": "Copy these platform-specific ad sets directly into Google/Meta Ads Manager.",
    "creative": "Implement these multi-channel copy sets and Veo video prompts.",
    "strategist": "This 30-day roadmap is your CEO-level execution checklist.",
    "social": "Deploy viral hooks across LinkedIn, IG, and X.",
    "geo": "Update your Google Business Profile keywords and local citations.",
    "audit": "Forward this technical brief to your web development team.",
    "seo": "Publish this technical article to secure high-authority AI rankings."
}

tab_labels = ["📖 Guide"] + [a[0] for a in agent_map] + ["👁️ Vision", "🎬 Veo Studio"]
if is_admin: tab_labels.append("⚙ Admin")

tabs = st.tabs(tab_labels)
TAB = {name: tabs[i] for i, name in enumerate(tab_labels)}

# A. Guide Tab
with TAB["📖 Guide"]:
    st.header("📖 Agent Intelligence Manual")
    st.info("The Omni-Swarm engine coordinates 8 specialized AI agents.")

# B. Dynamic Agent Rendering with Export Logic
for i, (title, key) in enumerate(agent_map):
    with TAB[title]:
        st.markdown(f'<div class="deploy-guide"><b>🚀 DEPLOYMENT GUIDE:</b><br>{DEPLOYMENT_GUIDES.get(key, "")}</div>', unsafe_allow_html=True)
        
        if st.session_state.gen:
            content = st.session_state.report.get(key, "Intelligence Pending...")
            edited_text = st.text_area(f"Refine {title}", value=str(content), height=350, key=f"text_{key}")
            
            # --- THE EXPORT ENGINE ---
            st.write("### 📤 Export Intelligence")
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="📄 Download Word Brief",
                    data=create_word_doc(edited_text, title),
                    file_name=f"{key}_brief.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"word_{key}",
                    use_container_width=True
                )
            with col2:
                st.download_button(
                    label="📕 Download PDF Report",
                    data=create_pdf(edited_text, title),
                    file_name=f"{key}_report.pdf",
                    mime="application/pdf",
                    key=f"pdf_{key}",
                    use_container_width=True
                )
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
        st.text_area("Video Scene Prompt", value=str(st.session_state.report.get('creative', ''))[:500])
        st.button("📽️ GENERATE AD")
    else: st.warning("Launch Swarm first.")

if is_admin:
    with TAB["⚙ Admin"]:
        st.header("⚙️ God-Mode Management")
        conn = sqlite3.connect('breatheeasy.db')
        m1, m2 = st.columns(2)
        m1.metric("Global Swarms", pd.read_sql_query("SELECT COUNT(*) FROM master_audit_logs", conn).iloc[0,0])
        m2.metric("Total Users", pd.read_sql_query("SELECT COUNT(*) FROM users", conn).iloc[0,0])
        st.dataframe(pd.read_sql_query("SELECT * FROM master_audit_logs ORDER BY id DESC LIMIT 50", conn))
        conn.close()
