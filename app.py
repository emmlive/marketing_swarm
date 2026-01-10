import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
from datetime import datetime
from main import run_marketing_swarm 
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from io import BytesIO

# --- 1. SYSTEM INITIALIZATION ---
os.environ["OTEL_SDK_DISABLED"] = "true"
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

st.set_page_config(page_title="BreatheEasy AI | Master", page_icon="🌬️", layout="wide")

# --- 2. DATABASE ---
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

init_db()

# --- 3. EXPORT LOGIC (Download Deliverables) ---
def create_word_doc(content, logo_path=None):
    doc = Document()
    if logo_path and os.path.exists(logo_path):
        try: doc.add_picture(logo_path, width=Inches(1.5))
        except: pass
    doc.add_heading('BreatheEasy AI | Strategy Report', 0)
    doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city, logo_path=None):
    pdf = FPDF(); pdf.add_page()
    if logo_path and os.path.exists(logo_path):
        try: pdf.image(logo_path, 10, 8, 33); pdf.ln(20)
        except: pass
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'{service} Strategy - {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 7, txt=str(content).encode('latin-1', 'ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

# --- 4. AUTH & REGISTRATION ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn); conn.close()
    return {'usernames': {row['username']: {'email': row['email'], 'name': row['name'], 'password': row['password'], 
            'package': row.get('package', 'Basic'), 'credits': row.get('credits', 0), 'logo_path': row.get('logo_path')} for _, row in df.iterrows()}}

authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days'])

if not st.session_state.get("authentication_status"):
    st.markdown("<h1 style='text-align: center;'>🌬️ BreatheEasy AI Master</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["🔑 Login", "📝 Register"])
    with t1: authenticator.login(location='main')
    with t2:
        res_reg = authenticator.register_user(location='main', pre_authorization=False)
        if res_reg:
            e, u, n = res_reg
            h_pw = stauth.Hasher.hash(authenticator.credentials['usernames'][u]['password'])
            conn = sqlite3.connect('breatheeasy.db')
            conn.cursor().execute("INSERT INTO users (username, email, name, password, role, package, credits) VALUES (?,?,?,?,?,?,?)",
                                  (u, e, n, h_pw, 'member', 'Basic', 5))
            conn.commit(); conn.close(); st.success('Registered! Go to Login.')
    st.stop()

# --- 5. DASHBOARD ---
username = st.session_state["username"]
user_info = get_db_creds()['usernames'].get(username, {})
user_tier = user_info.get('package', 'Basic')
user_logo = user_info.get('logo_path')
user_credits = user_info.get('credits', 0)

with st.sidebar:
    st.markdown(f"### 👋 {st.session_state['name']} <span style='background:#0056b3;color:white;padding:2px 8px;border-radius:12px;font-size:10px;'>{user_tier}</span>", unsafe_allow_html=True)
    st.metric("Credits Available", user_credits)
    authenticator.logout('Sign Out', 'sidebar')
    st.divider()
    
    ind_map = {"HVAC": ["AC Repair", "Duct Cleaning"], "Plumbing": ["Sewer Line", "Tankless"], "Custom": ["Manual"]}
    main_cat = st.selectbox("Industry", list(ind_map.keys()))
    target_service = st.selectbox("Service", ind_map[main_cat]) if main_cat != "Custom" else st.text_input("Service")
    city = st.text_input("City")
    run_btn = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

# --- 6. TABS ---
tabs = st.tabs(["🔥 Launchpad", "📊 Database", "📱 Preview", "👁️ Visual Inspector", "💎 Pricing"])

with tabs[0]: # LAUNCHPAD
    if run_btn and city:
        if user_credits > 0:
            with st.status("🐝 Swarm Coordinating...", expanded=True) as status:
                res = run_marketing_swarm({'city': city, 'industry': main_cat, 'service': target_service})
                st.session_state['copy'] = res
                st.session_state['gen'] = True
                conn = sqlite3.connect('breatheeasy.db')
                conn.cursor().execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (username,))
                conn.cursor().execute("INSERT INTO leads (date, user, industry, service, city, content) VALUES (?,?,?,?,?,?)",
                                      (datetime.now().strftime("%Y-%m-%d"), username, main_cat, target_service, city, str(res)))
                conn.commit(); conn.close(); st.rerun()
        else: st.error("Out of credits.")

    if st.session_state.get('gen'):
        st.subheader("📥 Download Deliverables")
        c1, c2 = st.columns(2)
        c1.download_button("📄 Word Doc", create_word_doc(st.session_state['copy'], user_logo), f"Strategy_{city}.docx", use_container_width=True)
        c2.download_button("📕 PDF Report", create_pdf(st.session_state['copy'], target_service, city, user_logo), f"Strategy_{city}.pdf", use_container_width=True)
        st.markdown(st.session_state['copy'])

with tabs[3]: # VISUAL INSPECTOR
    st.subheader("👁️ Visual Brand Strategist")
    up = st.file_uploader("Upload on-site photo", type=['png', 'jpg'])
    if up: st.image(up, caption="Visual Agent: Analyzing job site for trust-building prompts...")
