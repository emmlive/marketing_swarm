import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
import requests
import urllib.parse
from datetime import datetime
from main import run_marketing_swarm 
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- 1. PRE-IMPORT KEY MAPPING ---
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

# --- 2. PAGE CONFIGURATION ---
st.set_page_config(page_title="BreatheEasy AI | Enterprise", page_icon="🌬️", layout="wide")

# --- 3. DATABASE CORE & RESET LOGIC ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, package TEXT, logo_path TEXT, fb_token TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, admin_user TEXT, action TEXT, target_user TEXT, details TEXT)''')
    
    # Check for admin to prevent IntegrityError
    c.execute("SELECT username FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, email, name, password, role, package) VALUES (?, ?, ?, ?, ?, ?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited'))
    conn.commit()
    conn.close()

def reset_database():
    """Wipes all data and re-initializes with admin user"""
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS leads")
    c.execute("DROP TABLE IF EXISTS users")
    c.execute("DROP TABLE IF EXISTS audit_logs")
    conn.commit()
    conn.close()
    init_db()

# --- 4. UTILITY FUNCTIONS ---
def log_action(admin_user, action, target_user, details=""):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.cursor().execute("INSERT INTO audit_logs (timestamp, admin_user, action, target_user, details) VALUES (?, ?, ?, ?, ?)",
                          (timestamp, admin_user, action, target_user, details))
    conn.commit(); conn.close()

def get_users_from_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    u_dict = {'usernames': {}}
    for _, row in df.iterrows():
        u_dict['usernames'][row['username']] = {
            'email': row['email'], 'name': row['name'], 'password': row['password'],
            'package': row.get('package', 'Basic'), 'logo_path': row.get('logo_path')
        }
    return u_dict

# --- 5. DOCUMENT GENERATORS ---
def create_word_doc(content, logo_path=None):
    doc = Document()
    if logo_path and os.path.exists(logo_path):
        try: doc.add_picture(logo_path, width=Inches(1.5))
        except: pass
    doc.add_heading('BreatheEasy AI Strategy Report', 0)
    for line in content.split('\n'): doc.add_paragraph(line)
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city, logo_path=None):
    pdf = FPDF(); pdf.add_page()
    if logo_path and os.path.exists(logo_path):
        try: pdf.image(logo_path, 10, 8, 33); pdf.ln(20)
        except: pass
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'Report: {service} in {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=11); clean = content.encode('latin-1', 'ignore').decode('latin-1')
    pdf.multi_cell(0, 8, txt=clean); return pdf.output(dest='S').encode('latin-1')

# --- 6. STARTUP & AUTH ---
init_db()
db_credentials = get_users_from_db()
authenticator = stauth.Authenticate(db_credentials, st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days'])

# LOGIN PAGE
authenticator.login(location='main')

if st.session_state["authentication_status"] is None:
    st.markdown("<h1 style='text-align: center;'>🌬️ BreatheEasy AI</h1>", unsafe_allow_html=True)
    
    # Forgot Password Flow
    try:
        username_forgot_pw, email_forgot_password, new_random_password = authenticator.forgot_password('Forgot password')
        if username_forgot_pw:
            hashed_pw = stauth.Hasher.hash(new_random_password)
            conn = sqlite3.connect('breatheeasy.db')
            conn.cursor().execute("UPDATE users SET password = ? WHERE username = ?", (hashed_pw, username_forgot_pw))
            conn.commit(); conn.close()
            st.success('✅ Temporary password generated. Check email.')
    except Exception as e: st.error(e)

    with st.expander("Register New Account"):
        res = authenticator.register_user(pre_authorization=False)
        if res:
            email, username, name = res
            if email:
                try:
                    hashed_reg = stauth.Hasher.hash(authenticator.credentials['usernames'][username]['password'])
                    conn = sqlite3.connect('breatheeasy.db')
                    conn.cursor().execute("INSERT INTO users (username, email, name, password, role, package) VALUES (?, ?, ?, ?, ?, ?)",
                                          (username, email, name, hashed_reg, 'member', 'Basic'))
                    conn.commit(); conn.close(); st.success('✅ Registered!'); st.rerun()
                except sqlite3.IntegrityError: st.error("Username taken.")
    st.stop()

# --- 7. DASHBOARD & UI ---
@st.dialog("🎓 Masterclass")
def video_tutorial():
    st.video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    if st.button("Close"): st.rerun()

if st.session_state["authentication_status"]:
    username = st.session_state["username"]
    user_info = get_users_from_db()['usernames'].get(username, {})
    user_tier = user_info.get('package', 'Basic')
    user_logo = user_info.get('logo_path')

    # Sidebar
    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state['name']} <span style='background:#0056b3;color:white;padding:2px 8px;border-radius:10px;font-size:12px;'>{user_tier}</span>", unsafe_allow_html=True)
        if st.button("🎓 Tutorial"): video_tutorial()
        
        # Change Password
        if st.button("🔑 Change Password"):
            if authenticator.reset_password(username, 'Reset password'):
                new_h = stauth.Hasher.hash(authenticator.credentials['usernames'][username]['password'])
                conn = sqlite3.connect('breatheeasy.db')
                conn.cursor().execute("UPDATE users SET password = ? WHERE username = ?", (new_h, username))
                conn.commit(); conn.close(); st.success('Modified!')

        authenticator.logout('Sign Out', 'sidebar')
        st.divider()
        industries = ["HVAC", "Solar", "Restoration", "Roofing", "Plumbing", "Law Firm", "Medical", "Custom"]
        main_cat = st.selectbox("Industry", industries)
        target_service = st.text_input("Service")
        city_input = st.text_input("City")
        run_button = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

    tabs = st.tabs(["🔥 Strategy", "📊 Previews", "💎 Tiers", "🛠️ Admin" if username == "admin" else "ℹ️ Support"])

    with tabs[0]: # STRATEGY & DOWNLOADS
        if run_button and city_input:
            with st.spinner("Swarm Coordinating..."):
                run_marketing_swarm({'city': city_input, 'industry': main_cat, 'service': target_service})
                if os.path.exists("final_marketing_strategy.md"):
                    with open("final_marketing_strategy.md", "r", encoding="utf-8") as f: content = f.read()
                    st.session_state['ad_copy'] = content
                    st.session_state['generated'] = True

        if st.session_state.get('generated'):
            copy = st.session_state['ad_copy']
            c1, c2 = st.columns(2)
            c1.download_button("📥 Word", create_word_doc(copy, user_logo), f"Report_{city_input}.docx", use_container_width=True)
            c2.download_button("📕 PDF", create_pdf(copy, target_service, city_input, user_logo), f"Report_{city_input}.pdf", use_container_width=True)
            st.markdown(copy)

    with tabs[1]: # MOCKUPS
        if st.session_state.get('generated'):
            copy = st.session_state['ad_copy']
            st.markdown("### 🌐 Google Ad Preview")
            st.markdown(f"<div style='border:1px solid #ddd;padding:15px;border-radius:8px;'><div style='color:#1a0dab;font-size:18px;'>Top Rated {target_service} in {city_input}</div><div style='color:#4d5156;'>{copy[:150]}...</div></div>", unsafe_allow_html=True)
            st.markdown("### 📅 Buffer Queue Preview")
            st.markdown(f"<div style='border-left:5px solid #2c3e50;padding-left:10px;'><strong>Tomorrow @ 9:00 AM</strong><br>{copy[:100]}...</div>", unsafe_allow_html=True)
        else: st.info("Run strategy first.")

    if username == "admin":
        with tabs[-1]:
            st.subheader("🛠️ Admin Suite")
            # --- DATABASE RESET BUTTON ---
            st.warning("⚠️ **Danger Zone**: Resetting the database will delete all users, leads, and logs.")
            if st.button("💣 RESET DATABASE"):
                st.session_state['confirm_reset'] = True
            
            if st.session_state.get('confirm_reset'):
                st.error("ARE YOU ABSOLUTELY SURE? This cannot be undone.")
                if st.button("YES, DELETE EVERYTHING"):
                    reset_database()
                    st.session_state['confirm_reset'] = False
                    st.success("Database wiped. Refreshing...")
                    st.rerun()
                if st.button("NO, CANCEL"):
                    st.session_state['confirm_reset'] = False
                    st.rerun()
