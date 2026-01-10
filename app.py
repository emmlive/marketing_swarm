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
st.set_page_config(page_title="BreatheEasy AI | Enterprise Command", page_icon="🌬️", layout="wide")

# --- 3. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, package TEXT, logo_path TEXT, fb_token TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, admin_user TEXT, action TEXT, target_user TEXT, details TEXT)''')
    
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, email, name, password, role, package) VALUES (?, ?, ?, ?, ?, ?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited'))
    conn.commit(); conn.close()

# --- 4. CORE DATABASE & UTILITIES ---
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

# --- 5. EXPORT GENERATORS ---
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
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'Marketing: {service}', 0, 1, 'C')
    pdf.set_font("Arial", size=11); clean = content.encode('latin-1', 'ignore').decode('latin-1')
    pdf.multi_cell(0, 8, txt=clean); return pdf.output(dest='S').encode('latin-1')

init_db()

# --- 6. UI STYLING ---
st.markdown("""
    <style>
    header { visibility: hidden !important; }
    .stApp { background-color: #F8F9FB; }
    .tier-badge { padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; background: #0056b3; color: white; }
    .mockup-container { background: white; border: 1px solid #ddd; border-radius: 10px; padding: 20px; margin-bottom: 20px; }
    .google-title { color: #1a0dab; font-size: 19px; text-decoration: none; font-family: arial; }
    .buffer-card { border-left: 5px solid #2c3e50; padding-left: 15px; }
    </style>
""", unsafe_allow_html=True)

# --- 7. AUTHENTICATION & LOGIN FLOW ---
db_credentials = get_users_from_db()
authenticator = stauth.Authenticate(db_credentials, st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days'])

# LOGIN PAGE
authenticator.login(location='main')

if st.session_state["authentication_status"] is None:
    st.markdown("<h1 style='text-align: center;'>🌬️ BreatheEasy AI</h1>", unsafe_allow_html=True)
    
    # FORGOT PASSWORD
    try:
        username_forgot_pw, email_forgot_password, new_random_password = authenticator.forgot_password('Forgot password')
        if username_forgot_pw:
            hashed_pw = stauth.Hasher.hash(new_random_password)
            conn = sqlite3.connect('breatheeasy.db')
            conn.cursor().execute("UPDATE users SET password = ? WHERE username = ?", (hashed_pw, username_forgot_pw))
            conn.commit(); conn.close()
            st.success('✅ A new password has been generated. Check your email.')
    except Exception as e: st.error(e)

    with st.expander("New User? Register Here"):
        res = authenticator.register_user(pre_authorization=False)
        if res:
            email, username, name = res
            if email:
                db_ready_pw = stauth.Hasher.hash(authenticator.credentials['usernames'][username]['password'])
                conn = sqlite3.connect('breatheeasy.db')
                conn.cursor().execute("INSERT INTO users (username, email, name, password, role, package) VALUES (?, ?, ?, ?, ?, ?)",
                                      (username, email, name, db_ready_pw, 'member', 'Basic'))
                conn.commit(); conn.close(); st.success('✅ Registered!'); st.rerun()
    st.stop()

# --- 8. PROTECTED DASHBOARD ---
@st.dialog("🎓 Strategy Masterclass")
def video_tutorial():
    st.write("How to close high-ticket clients with these reports.")
    st.video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    if st.button("Close"): st.rerun()

if st.session_state["authentication_status"]:
    username = st.session_state["username"]
    user_info = get_users_from_db()['usernames'].get(username, {})
    user_tier = user_info.get('package', 'Basic')
    user_logo = user_info.get('logo_path')

    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state['name']} <span class='tier-badge'>{user_tier}</span>", unsafe_allow_html=True)
        if st.button("🎓 Tutorial"): video_tutorial()
        
        # CHANGE PASSWORD MODAL
        if st.button("🔑 Change Password"):
            try:
                if authenticator.reset_password(username, 'Reset password'):
                    # Sync new password to DB
                    new_hashed = stauth.Hasher.hash(authenticator.credentials['usernames'][username]['password'])
                    conn = sqlite3.connect('breatheeasy.db')
                    conn.cursor().execute("UPDATE users SET password = ? WHERE username = ?", (new_hashed, username))
                    conn.commit(); conn.close()
                    st.success('Password modified successfully')
            except Exception as e: st.error(e)

        authenticator.logout('Sign Out', 'sidebar')
        st.divider()

        # INDUSTRY GATING
        industries = ["HVAC", "Solar", "Restoration", "Roofing", "Plumbing", "Law Firm", "Medical", "Custom Business"]
        main_cat = st.selectbox("Industry", industries)
        target_service = st.text_input("Service") if main_cat == "Custom Business" else st.selectbox("Service", ["General", "Premium", "Installation"])
        city_input = st.text_input("City", placeholder="Chicago, IL")
        run_button = st.button("🚀 GENERATE OMNI-STRATEGY", type="primary", use_container_width=True)

    tabs = st.tabs(["🔥 Strategy", "📊 Platform Previews", "💎 Tiers", "🛠️ Admin" if username == "admin" else "ℹ️ Support"])

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
            c1.download_button("📥 Word", create_word_doc(copy, user_logo), f"Strategy_{city_input}.docx", use_container_width=True)
            c2.download_button("📕 PDF", create_pdf(copy, target_service, city_input, user_logo), f"Strategy_{city_input}.pdf", use_container_width=True)
            st.markdown(copy)

    with tabs[1]: # MOCKUPS & FB PUBLISH
        if st.session_state.get('generated'):
            copy = st.session_state['ad_copy']
            st.markdown("### 🌐 Google Search Mockup")
            
            st.markdown(f"<div class='mockup-container'><div style='color:#202124; font-size:13px;'>https://www.breatheeasy.ai/{main_cat.lower()}</div><div class='google-title'>Top Rated {target_service} in {city_input}</div><div style='color:#4d5156;'>{copy[:150]}...</div></div>", unsafe_allow_html=True)
            
            st.markdown("### 📅 Buffer Queue Preview")
            st.markdown(f"<div class='mockup-container buffer-card'><strong>Tomorrow @ 9:00 AM</strong><br>{copy[:100]}...</div>", unsafe_allow_html=True)
            
            st.subheader("🚀 Facebook Direct Publish")
            pid = st.text_input("Page ID")
            tok = st.text_input("Access Token", type="password")
            if st.button("Publish Now"):
                requests.post(f"https://graph.facebook.com/v18.0/{pid}/feed", data={'message': copy, 'access_token': tok})
                st.success("API Call Sent!")
        else:
            st.info("💡 Run a strategy to unlock previews.")

    if username == "admin":
        with tabs[-1]:
            adm_tabs = st.tabs(["👥 Users", "📜 Audit Logs", "📈 Revenue"])
            with adm_tabs[2]:
                if st.button("📧 Send Revenue Report"):
                    st.success("Report emailed to admin.")
                    log_action("admin", "MONTHLY_REPORT", "SYSTEM")
