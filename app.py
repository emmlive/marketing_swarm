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

# --- 1. CORE SYSTEM CONFIG ---
st.set_page_config(page_title="TechInAdvance AI | Enterprise", page_icon="Logo1.jpeg", layout="wide")

if 'gen' not in st.session_state: st.session_state.gen = False
if 'report' not in st.session_state: st.session_state.report = {}

# --- 2. EXECUTIVE UI CSS (CLEAN & STABLE) ---
sidebar_color = "#2563EB"
st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFCF0; }}
    .price-card {{ background: white; padding: 20px; border-radius: 12px; border: 2px solid {sidebar_color}; text-align: center; margin-bottom: 10px; }}
    .deploy-guide {{ background: rgba(37,99,235,0.07); padding: 15px; border-radius: 10px; border-left: 6px solid {sidebar_color}; margin-bottom: 20px; }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 700; width: 100%; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE ENGINE (SELF-HEALING) ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, plan TEXT, credits INTEGER, logo_path TEXT, team_id TEXT, verified INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT, team_id TEXT, status TEXT DEFAULT "Discovery")')
    c.execute('CREATE TABLE IF NOT EXISTS master_audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, user TEXT, action_type TEXT, target_biz TEXT, location TEXT, credit_cost INTEGER, status TEXT)')
    
    # Reset Admin for fresh start
    admin_pw = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users VALUES ('admin','admin@tech.ai','Admin',?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001',1)", (admin_pw,))
    conn.commit()
    conn.close()

init_db()

# --- 4. AUTHENTICATION GATE ---
def get_creds():
    conn = sqlite3.connect('breatheeasy.db')
    df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
    conn.close()
    return {'usernames': {row['username']: {'email':row['email'], 'name':row['name'], 'password':row['password']} for _, row in df.iterrows()}}

# Use session state to prevent Duplicate Widget Errors
if 'auth' not in st.session_state:
    st.session_state.auth = stauth.Authenticate(get_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

if not st.session_state.get("authentication_status"):
    t_login, t_reg, t_lost = st.tabs(["🔑 Login", "📝 Enrollment", "❓ Recovery"])
    with t_login:
        st.session_state.auth.login(location='main')
    with t_reg:
        st.subheader("Tiered Enterprise Plans")
        c1, c2, c3 = st.columns(3)
        c1.markdown('<div class="price-card"><h3>Basic</h3><h2>$99</h2></div>', unsafe_allow_html=True)
        c2.markdown('<div class="price-card" style="border-color:#7C3AED;"><h3>Pro</h3><h2>$249</h2></div>', unsafe_allow_html=True)
        c3.markdown('<div class="price-card"><h3>Enterprise</h3><h2>$499</h2></div>', unsafe_allow_html=True)
        if st.session_state.auth.register_user(location='main'): st.success("Registered! Go to Login.")
    with t_lost:
        st.session_state.auth.forgot_password(location='main')
    st.stop()

# --- 5. DATA FETCH ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()
is_admin = (user_row['role'] == 'admin')

# --- 6. EXPORT HELPERS ---
def export_word(content, title):
    doc = Document(); doc.add_heading(title, 0); doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def export_pdf(content, title):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, title, 0, 1, 'C')
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 7, txt=str(content).encode('latin-1','ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

# --- 7. SIDEBAR ---
with st.sidebar:
    st.image(user_row['logo_path'], width=120)
    st.metric("Credits", user_row['credits'])
    st.divider()
    biz_name = st.text_input("Brand Name")
    full_loc = st.text_input("Location (City, State)")
    ind = st.selectbox("Industry", ["HVAC", "Solar", "Legal", "Medical", "Custom"])
    svc = st.text_input("Service Type")
    
    if user_row['verified'] == 1:
        run_btn = st.button("🚀 LAUNCH SWARM", type="primary")
    else:
        st.warning("Verification Required")
        if st.button("Demo: Verify Now"):
            conn = sqlite3.connect('breatheeasy.db'); conn.execute("UPDATE users SET verified=1 WHERE username=?", (user_row['username'],)); conn.commit(); conn.close(); st.rerun()
        run_btn = False
    
    st.session_state.auth.logout('Sign Out', 'sidebar')

# --- 8. EXECUTION ---
if run_btn:
    if not biz_name or not full_loc: st.error("Please fill in Name and Location")
    else:
        with st.status("🛠️ Swarm Agents Active...") as status:
            res = run_marketing_swarm({'city': full_loc, 'biz_name': biz_name, 'industry': ind, 'service': svc})
            st.session_state.report = res
            st.session_state.gen = True
            
            # Update DB
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
            conn.execute("INSERT INTO master_audit_logs (timestamp, user, action_type, target_biz, location, status) VALUES (?,?,?,?,?,?)", 
                         (datetime.now().strftime("%Y-%m-%d"), user_row['username'], "SWARM", biz_name, full_loc, "SUCCESS"))
            conn.commit(); conn.close(); st.rerun()

# --- 9. COMMAND CENTER ---
agent_map = [("🕵️ Analyst", "analyst"), ("🎨 Creative", "creative"), ("👔 Strategist", "strategist"), ("📱 Social", "social"), ("🌐 Auditor", "auditor")]
DEPLOY_GUIDES = {"analyst": "Identify Market Gaps", "creative": "Copy for Ads", "strategist": "30-Day Roadmap", "social": "Viral Hooks", "auditor": "Web Fixes"}

tab_labels = ["📖 Guide"] + [a[0] for a in agent_map] + ["🤝 Team Intel"]
if is_admin: tab_labels.append("⚙ Admin")

tabs = st.tabs(tab_labels)

with tabs[0]:
    st.header("📖 Manual")
    st.info("Coordinates specialized AI agents for business growth.")

for i, (title, key) in enumerate(agent_map):
    with tabs[i+1]:
        st.markdown(f'<div class="deploy-guide"><b>🚀 GUIDE:</b> {DEPLOY_GUIDES[key]}</div>', unsafe_allow_html=True)
        if st.session_state.gen:
            content = st.session_state.report.get(key, "Pending...")
            edited = st.text_area("Refine Output", value=str(content), height=300, key=f"ed_{key}")
            c1, c2 = st.columns(2)
            c1.download_button("📄 Word", export_word(edited, title), f"{key}.docx")
            c2.download_button("📕 PDF", export_pdf(edited, title), f"{key}.pdf")
        else: st.info("Launch Swarm to see results.")

with tabs[-2 if not is_admin else -2]: # Team Intel
    st.header("🤝 Pipeline")
    conn = sqlite3.connect('breatheeasy.db')
    st.dataframe(pd.read_sql_query("SELECT city, service, status FROM leads", conn), use_container_width=True)
    conn.close()

if is_admin:
    with tabs[-1]:
        st.header("⚙️ God-Mode")
        conn = sqlite3.connect('breatheeasy.db')
        st.metric("Global Swarms", pd.read_sql_query("SELECT COUNT(*) FROM master_audit_logs", conn).iloc[0,0])
        st.dataframe(pd.read_sql_query("SELECT * FROM master_audit_logs ORDER BY id DESC LIMIT 20", conn))
        conn.close()
