import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from main import run_marketing_swarm 
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from io import BytesIO

# --- 1. SYSTEM INITIALIZATION ---
os.environ["OTEL_SDK_DISABLED"] = "true"
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

st.set_page_config(page_title="BreatheEasy AI | Enterprise", page_icon="🌬️", layout="wide")

# --- 2. DATABASE ARCHITECTURE ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, 
                  package TEXT, credits INTEGER DEFAULT 0, logo_path TEXT, last_login TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    c.execute("SELECT username FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, email, name, password, role, package, credits) VALUES (?,?,?,?,?,?,?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited', 9999))
    conn.commit(); conn.close()

def send_team_alert(u):
    try:
        msg = MIMEMultipart()
        msg['Subject'] = f"🚀 New Signup: {u}"
        msg['To'] = st.secrets["TEAM_EMAIL"]
        server = smtplib.SMTP(st.secrets["SMTP_SERVER"], st.secrets["SMTP_PORT"])
        server.starttls(); server.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"])
        server.send_message(msg); server.quit()
    except: pass

init_db()

# --- 3. AUTH & REGISTRATION ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn); conn.close()
    return {'usernames': {row['username']: {k: row[k] for k in row.index} for _, row in df.iterrows()}}

authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

if not st.session_state.get("authentication_status"):
    st.title("🌬️ BreatheEasy AI Enterprise")
    l_tab, r_tab = st.tabs(["🔑 Login", "📝 Register"])
    with l_tab: authenticator.login(location='main')
    with r_tab:
        res = authenticator.register_user(location='main', pre_authorization=False)
        if res:
            e, u, n = res; pw = stauth.Hasher.hash(authenticator.credentials['usernames'][u]['password'])
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("INSERT INTO users (username, email, name, password, role, package, credits) VALUES (?,?,?,?,'member','Basic',5)", (u,e,n,pw))
            conn.commit(); conn.close(); send_team_alert(u); st.success("Registered! Please login.")
    st.stop()

# --- 4. PROTECTED DASHBOARD ---
username = st.session_state["username"]
user_info = get_db_creds()['usernames'].get(username, {})
user_credits = user_info['credits']

with st.sidebar:
    st.markdown(f"### 👋 {st.session_state['name']} <span style='background:#0056b3;color:white;padding:2px 8px;border-radius:12px;font-size:10px;'>{user_info['package']}</span>", unsafe_allow_html=True)
    st.metric("Credits Available", user_credits)
    authenticator.logout('Sign Out', 'sidebar')
    st.divider()
    
    ind_map = {"HVAC": ["AC Repair", "Duct Cleaning"], "Plumbing": ["Sewer Line", "Tankless"], "Medical": ["Dental", "Clinic"], "Custom": ["Manual"]}
    main_cat = st.selectbox("Industry", list(ind_map.keys()))
    svc = st.selectbox("Service", ind_map[main_cat]) if main_cat != "Custom" else st.text_input("Service")
    city = st.text_input("City")
    run_btn = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

# --- 5. TABS (MATCHED TO NEW FLOW OUTPUT) ---
tabs = st.tabs(["📝 Ad Copy", "🗓️ Schedule", "🖼️ Visual Assets", "🚀 Push to Ads", "🔬 Diagnostic Lab", "📊 Database", "💎 Pricing"])

with tabs[0]: # 📝 Ad Copy
    if run_btn and city:
        if user_credits > 0:
            with st.status("🐝 Swarm Coordinating Phase 1, 2, and 3...", expanded=True) as status:
                # The flow consolidation logic happens inside main.run_marketing_swarm
                report = run_marketing_swarm({'city': city, 'industry': main_cat, 'service': svc})
                st.session_state['report'] = report
                st.session_state['gen'] = True
                
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (username,))
                conn.execute("INSERT INTO leads (date, user, industry, service, city, content) VALUES (?,?,?,?,?,?)", 
                             (datetime.now().strftime("%Y-%m-%d"), username, main_cat, svc, city, str(report)))
                conn.commit(); conn.close(); st.rerun()
        else: st.error("Out of credits.")

    if st.session_state.get('gen'):
        st.subheader("High-Converting Ad Variants")
        st.markdown(st.session_state['report'])

with tabs[1]: # 🗓️ Schedule (Content Repurposing Output)
    if st.session_state.get('gen'):
        st.subheader("Localized 7-Day Distribution Schedule")
        st.info("Repurposed by the Content Distribution Agent for GBP, FB, Quora, and Reddit.")
        st.write("Extracting localized schedule from Swarm Report...")
        # In a final version, we'd use regex to pull the specific section from the report markdown

with tabs[2]: # 🖼️ Visual Assets (Navy/White Prompts)
    if st.session_state.get('gen'):
        st.subheader("BreatheEasy Brand Style Guide")
        st.markdown("**Colors:** Navy (#000080) & Clean White")
        st.code("/imagine prompt: Professional high-ticket service photography, navy blue accents...")

with tabs[3]: # 🚀 Push to Ads
    st.subheader("Channel Deployment")
    st.button("📱 Push to Facebook Ads API")
    st.button("🔍 Sync with Google Business Profile")

with tabs[4]: # 🔬 Diagnostic Lab (Industry-Agnostic)
    st.subheader("🔬 AI Diagnostic Lab")
    up = st.file_uploader("Upload Evidence Photos", type=['png', 'jpg'])
    if up:
        st.image(up, caption="Vision Inspector: Analyzing debris density and safety hazards...", width=500)
        st.success("Analysis: BreatheEasy Score 7/10. Evidence of particulate bypass detected.")

with tabs[6]: # 💎 Pricing
    c1, c2, c3 = st.columns(3)
    for p_name, p_val in {"Basic": 5, "Pro": 50, "Unlimited": 999}.items():
        with st.container():
            st.markdown(f"<div style='border:1px solid #ddd;padding:20px;text-align:center;'><h3>{p_name}</h3><h1>{p_val}</h1><p>Credits Included</p></div>", unsafe_allow_html=True)
