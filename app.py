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
from PIL import Image

# --- SECTION #0: PERFORMANCE HELPERS & SPRINT 5 GEO-CACHING ---

@st.cache_data(ttl=3600)
def get_geo_data():
    """Restored: Full 2026 High-speed geographic lookup"""
    return {
        "Alabama": ["Birmingham", "Huntsville", "Mobile"],
        "Arizona": ["Phoenix", "Scottsdale", "Tucson"],
        "California": ["Los Angeles", "San Francisco", "San Diego"],
        "Florida": ["Miami", "Orlando", "Tampa"],
        "Illinois": ["Chicago", "Naperville", "Plainfield"],
        "Texas": ["Austin", "Dallas", "Houston"],
    }

def check_system_health():
    """Restored: Sprint 5 Forensic Heartbeat"""
    health = {
        "Gemini 2.0": os.getenv("GOOGLE_API_KEY") is not None,
        "Serper API": os.getenv("SERPER_API_KEY") is not None,
        "Database": os.path.exists("breatheeasy.db"),
    }
    return health

def is_verified(username):
    """Restored: Sprint 2 Security Gate"""
    conn = sqlite3.connect('breatheeasy.db')
    res = conn.execute("SELECT verified FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return res[0] == 1 if res else False

def toggle_theme():
    """Restored: Sprint 1 Dark/Light Toggle"""
    if 'theme' not in st.session_state: st.session_state.theme = 'light'
    st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'

def update_account_settings(username, new_email, new_name):
    """Restored: Sprint 4 Profile Management"""
    conn = sqlite3.connect('breatheeasy.db')
    conn.execute("UPDATE users SET email = ?, name = ? WHERE username = ?", (new_email, new_name, username))
    conn.commit(); conn.close()
    st.success("Profile Updated!")

# --- SPRINT 3: HIGH-FIDELITY EXPORT ENGINE ---
def export_word(content, title):
    doc = Document(); doc.add_heading(f'Intelligence Brief: {title}', 0)
    doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def export_pdf(content, title):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f'Intelligence Brief: {title}', 0, 1, 'C')
    pdf.set_font("Arial", size=10)
    clean_text = str(content).encode('latin-1', 'ignore').decode('latin-1')
    pdf.multi_cell(0, 7, txt=clean_text)
    return pdf.output(dest='S').encode('latin-1')

# --- SECTION #1: UI CONFIG & DB INITIALIZATION ---
st.set_page_config(page_title="TechInAdvance AI | Command", page_icon="Logo1.jpeg", layout="wide")

if 'gen' not in st.session_state: st.session_state.gen = False
if 'report' not in st.session_state: st.session_state.report = {}

sidebar_color = "#2563EB"
st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFCF0; color: #1E293B; }}
    [data-testid="stSidebar"] {{ background-color: #FFFFFF !important; border-right: 3px solid rgba(0,0,0,0.1) !important; }}
    .price-card {{ background: white; padding: 25px; border-radius: 15px; border: 2px solid {sidebar_color}; text-align: center; margin-bottom: 15px; box-shadow: 0px 4px 10px rgba(0,0,0,0.05); }}
    .deploy-guide {{ background: rgba(37, 99, 235, 0.08); padding: 18px; border-radius: 12px; border-left: 6px solid {sidebar_color}; margin-bottom: 25px; }}
    .kanban-card {{ background: white; padding: 15px; border-radius: 10px; margin-bottom: 12px; border-left: 5px solid {sidebar_color}; box-shadow: 0px 2px 6px rgba(0,0,0,0.04); }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800; height: 3.2em; }}
    </style>
""", unsafe_allow_html=True)

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

# --- SECTION #2: AUTHENTICATION & SIGN UP TIERS ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
    conn.close()
    return {'usernames': {r['username']: {'email':r['email'], 'name':r['name'], 'password':r['password']} for _,r in df.iterrows()}}

if 'authenticator' not in st.session_state:
    st.session_state.authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

authenticator = st.session_state.authenticator

if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=180)
    auth_tabs = st.tabs(["🔑 Login", "📝 Sign Up", "🤝 Join Team", "❓ Forget Password"])
    with auth_tabs[0]: authenticator.login(location='main')
    with auth_tabs[1]:
        st.subheader("Select Enterprise Package")
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown('<div class="price-card"><h3>Basic</h3><h2>$99</h2><p>50 Credits</p></div>', unsafe_allow_html=True)
        with c2: st.markdown('<div class="price-card" style="border-color:#7C3AED;"><h3>Pro</h3><h2>$249</h2><p>150 Credits</p></div>', unsafe_allow_html=True)
        with c3: st.markdown('<div class="price-card"><h3>Enterprise</h3><h2>$499</h2><p>Unlimited</p></div>', unsafe_allow_html=True)
        if authenticator.register_user(location='main'): st.success("Sign up complete!")
    with auth_tabs[3]: authenticator.forgot_password(location='main')
    st.stop()

# --- SECTION #3: SESSION DATA ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()
is_admin = (user_row['role'] == 'admin')

# --- SECTION #4: DYNAMIC COMMAND SIDEBAR ---
with st.sidebar:
    health = check_system_health()
    col_h, col_t = st.columns([2, 1])
    with col_h: st.caption(f"{'🟢' if all(health.values()) else '🔴'} **SYSTEM OPERATIONAL**")
    with col_t: 
        if st.button("🌓"): toggle_theme()

    st.image(user_row['logo_path'], width=120)
    st.metric("Credits Available", user_row['credits'])
    st.divider()

    biz_name = st.text_input("🏢 Brand Name", placeholder="Acme Solar")
    industry_map = {
        "Residential Services": ["HVAC", "Roofing", "Solar", "Plumbing"],
        "Medical & Health": ["Dental", "Plastic Surgery", "Veterinary"],
        "Legal & Professional": ["Family Law", "Personal Injury", "CPA"],
        "Other (Manual Entry)": []
    }
    selected_ind_cluster = st.selectbox("📂 Industry Cluster", sorted(list(industry_map.keys())))
    
    if selected_ind_cluster == "Other (Manual Entry)":
        final_ind = st.text_input("Type Industry Name", key="custom_ind")
        final_service = st.text_input("Type Specific Service", key="custom_svc")
    else:
        final_ind = selected_ind_cluster
        service_list = industry_map[selected_ind_cluster]
        final_service = st.selectbox("🛠️ Specific Service", service_list)

    geo_dict = get_geo_data()
    selected_state = st.selectbox("🎯 Target State", sorted(geo_dict.keys()))
    selected_city = st.selectbox(f"🏙️ Select City", sorted(geo_dict[selected_state]) + ["Other (Manual City)"])
    full_loc = f"{selected_city}, {selected_state}"

    st.divider()
    agent_info = st.text_area("✍️ Strategic Directives", placeholder="e.g. Focus on high-ticket luxury clients...", key="agent_directives_box")

    st.subheader("🤖 Swarm Personnel")
    agent_config = {"analyst": "🕵️ Analyst", "ads": "📺 Ad Tracker", "creative": "🎨 Creative", "strategist": "👔 Strategist", "social": "📱 Social", "geo": "📍 GEO", "audit": "🌐 Auditor", "seo": "✍ SEO"}
    toggles = {k: st.toggle(v, value=True, key=f"tg_{k}") for k, v in agent_config.items()}

    st.divider()
    if is_verified(st.session_state["username"]):
        run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
    else:
        st.error("🛡️ Verification Locked")
        if st.button("🔓 DEMO: Verify Now", use_container_width=True):
            conn = sqlite3.connect('breatheeasy.db'); conn.execute("UPDATE users SET verified=1 WHERE username=?", (user_row['username'],)); conn.commit(); conn.close(); st.rerun()
        run_btn = False

    authenticator.logout('🔒 Sign Out', 'sidebar')

# --- SECTION #5: EXECUTION ENGINE ---
if run_btn:
    with st.status("🛠️ Coordinating Swarm Agents...", expanded=True) as status:
        report = run_marketing_swarm({'city': full_loc, 'biz_name': biz_name, 'service': final_service, 'directives': agent_info})
        st.session_state.report = report
        st.session_state.gen = True
        conn = sqlite3.connect('breatheeasy.db')
        conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
        conn.execute("INSERT INTO master_audit_logs (timestamp, user, action_type, target_biz, location, status) VALUES (?,?,?,?,?,?)", 
                     (datetime.now().strftime("%Y-%m-%d %H:%M"), user_row['username'], "SWARM", biz_name, full_loc, "SUCCESS"))
        conn.commit(); conn.close(); st.rerun()

# --- SECTION #6: MULTIMODAL COMMAND CENTER ---
tab_labels = ["📖 Guide", "🕵️ Analyst", "📺 Ads", "🎨 Creative", "👔 Strategist", "📱 Social", "📍 GEO", "🌐 Auditor", "✍ SEO", "👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_admin: tab_labels.append("⚙ Admin")

tabs_obj = st.tabs(tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(tab_labels)}

# A. Guide & Manual (Sprint 1)
with TAB["📖 Guide"]:
    st.header("📖 Agent Intelligence Manual")
    st.markdown("""
    The **Omni-Swarm** engine coordinates 8 specialized AI agents to engineer growth.
    - **Forensics:** Web Auditor & Ad Tracker identify rival psychological and technical weaknesses.
    - **Strategy:** Swarm Strategist builds a phased 30-Day ROI Roadmap.
    - **Production:** Creative & SEO Architects build high-converting assets.
    """)

# B. Dynamic Agent Seats (Sprints 2 & 3)
DEPLOY_GUIDES = {"analyst": "Identify Price-Gaps.", "ads": "Copy platform hooks.", "creative": "Implement copy/prompts.", "strategist": "CEO-level checklist.", "social": "Deploy viral hooks.", "geo": "Update citations.", "audit": "Patch technical leaks.", "seo": "Publish for SGE."}
for title, key in agent_map:
    with TAB[title]:
        st.markdown(f'<div class="deploy-guide"><b>🚀 DEPLOYMENT GUIDE:</b><br>{DEPLOY_GUIDES.get(key,"Review report.")}</div>', unsafe_allow_html=True)
        if st.session_state.gen:
            content = st.session_state.report.get(key, "Intelligence generation in progress...")
            edited = st.text_area(f"Refine {title}", value=str(content), height=400, key=f"ed_{key}")
            c1, c2 = st.columns(2)
            with c1: st.download_button("📄 Word", export_word(edited, title), f"{key}.docx")
            with c2: st.download_button("📕 PDF", export_pdf(edited, title), f"{key}.pdf")

# C. Vision & Veo Studio (Sprints 4 & 5)
with TAB["👁️ Vision"]:
    st.subheader("👁️ Forensic Vision Inspector")
    v_file = st.file_uploader("Upload Evidence", type=['png','jpg','jpeg'], key="vis_up")
    if v_file: st.image(v_file, use_container_width=True)

with TAB["🎬 Veo Studio"]:
    st.subheader("🎬 Veo Cinematic Studio")
    if st.session_state.gen:
        v_prompt = st.text_area("Scene Description", value=str(st.session_state.report.get('creative', ''))[:500])
        if st.button("📽️ GENERATE AD"): st.info("Veo Rendering Engine Active...")

# D. Team Intel Kanban (Sprint 4)
with TAB["🤝 Team Intel"]:
    st.header("🤝 Team Account & Lead Pipeline")
    t1, t2 = st.columns([1, 2])
    with t1:
        st.subheader("👤 Account Tools")
        with st.form("profile_form"):
            n_name = st.text_input("Name", user_row['name'])
            n_email = st.text_input("Email", user_row['email'])
            if st.form_submit_button("Save"): update_account_settings(user_row['username'], n_email, n_name)
    with t2:
        st.subheader("📊 Kanban Pipeline")
        conn = sqlite3.connect('breatheeasy.db')
        team_df = pd.read_sql_query("SELECT id, city, service, status FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
        if not team_df.empty:
            stages = ["Discovery", "Execution", "ROI Verified"]
            cols = st.columns(3)
            for i, stage in enumerate(stages):
                with cols[i]:
                    st.markdown(f"**{stage}**")
                    for _, lead in team_df[team_df['status'] == stage].iterrows():
                        st.markdown(f'<div class="kanban-card">{lead["city"]}<br><small>{lead["service"]}</small></div>', unsafe_allow_html=True)
        conn.close()

# E. God-Mode Admin (Sprint 4)
if "⚙ Admin" in TAB:
    with TAB["⚙ Admin"]:
        st.header("⚙️ God-Mode Forensics")
        conn = sqlite3.connect('breatheeasy.db')
        m1, m2 = st.columns(2); m1.metric("Global Swarms", pd.read_sql_query("SELECT COUNT(*) FROM master_audit_logs", conn).iloc[0,0]); m2.metric("Total Users", pd.read_sql_query("SELECT COUNT(*) FROM users", conn).iloc[0,0])
        st.dataframe(pd.read_sql_query("SELECT * FROM master_audit_logs ORDER BY id DESC LIMIT 50", conn), use_container_width=True)
        u_df = pd.read_sql_query("SELECT username, credits FROM users", conn)
        target = st.selectbox("Inject Credits", u_df['username'])
        if st.button("Inject 100"): conn.execute("UPDATE users SET credits = credits + 100 WHERE username = ?", (target,)); conn.commit(); st.rerun()
        conn.close()
