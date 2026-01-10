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

# --- 1. CORE DATABASE & MAINTENANCE SYSTEM ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    # Settings Table for Maintenance Mode
    c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance_mode', 'OFF')")
    
    # Tables for Leads and Logs
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, admin_user TEXT, action TEXT, target_user TEXT, details TEXT)''')
    
    # Enhanced User Table: Added last_login and usage_count
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, 
                  package TEXT, logo_path TEXT, last_login TEXT, usage_count INTEGER DEFAULT 0)''')
    
    c.execute("SELECT username FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, email, name, password, role, package, last_login) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited', datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()

def toggle_maintenance(status):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    conn.cursor().execute("UPDATE settings SET value = ? WHERE key = 'maintenance_mode'", (status,))
    conn.commit(); conn.close()

def is_maintenance_on():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    res = conn.cursor().execute("SELECT value FROM settings WHERE key = 'maintenance_mode'").fetchone()
    conn.close()
    return res[0] == 'ON' if res else False

def update_login_stats(username):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.cursor().execute("UPDATE users SET last_login = ?, usage_count = usage_count + 1 WHERE username = ?", (now, username))
    conn.commit(); conn.close()

def reset_database():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS leads"); c.execute("DROP TABLE IF EXISTS users")
    c.execute("DROP TABLE IF EXISTS audit_logs"); c.execute("DROP TABLE IF EXISTS settings")
    conn.commit(); conn.close(); init_db()

# --- 2. STARTUP & AUTH ---
init_db()
maintenance_status = is_maintenance_on()

def get_users_from_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    u_dict = {'usernames': {}}
    for _, row in df.iterrows():
        u_dict['usernames'][row['username']] = {
            'email': row['email'], 'name': row['name'], 'password': row['password'],
            'package': row.get('package', 'Basic'), 'logo_path': row.get('logo_path'),
            'last_login': row.get('last_login'), 'usage_count': row.get('usage_count')
        }
    return u_dict

# --- 3. EXPORT GENERATORS ---
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
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'Omni-Channel Report: {service}', 0, 1, 'C')
    pdf.set_font("Arial", size=11); clean = content.encode('latin-1', 'ignore').decode('latin-1')
    pdf.multi_cell(0, 8, txt=clean); return pdf.output(dest='S').encode('latin-1')

# --- 4. LOGIN FLOW ---
db_credentials = get_users_from_db()
authenticator = stauth.Authenticate(db_credentials, st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days'])
authenticator.login(location='main')

if st.session_state["authentication_status"] is None:
    st.markdown("<h1 style='text-align: center;'>🌬️ BreatheEasy AI</h1>", unsafe_allow_html=True)
    # Registration logic included here in your previous block...
    st.stop()

# --- 5. MAINTENANCE & SESSION HANDLING ---
if st.session_state["authentication_status"]:
    username = st.session_state["username"]
    is_admin = (username == "admin")

    if maintenance_status and not is_admin:
        st.error("🚧 THE SITE IS CURRENTLY UNDER MAINTENANCE. PLEASE CHECK BACK LATER.")
        st.stop()

    if 'stats_updated' not in st.session_state:
        update_login_stats(username)
        st.session_state['stats_updated'] = True

    user_info = get_users_from_db()['usernames'].get(username, {})
    user_tier = user_info.get('package', 'Basic')
    user_logo = user_info.get('logo_path')

    # Sidebar
    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state['name']} <span style='background:#0056b3;color:white;padding:2px 8px;border-radius:10px;font-size:12px;'>{user_tier}</span>", unsafe_allow_html=True)
        st.write(f"Usage: {user_info.get('usage_count', 0)} Swarms")
        authenticator.logout('Sign Out', 'sidebar')
        st.divider()
        industries = ["HVAC", "Solar", "Restoration", "Roofing", "Plumbing", "Law Firm", "Medical", "Custom"]
        main_cat = st.selectbox("Industry", industries)
        target_service = st.text_input("Service")
        city_input = st.text_input("City")
        run_button = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

    tabs = st.tabs(["🔥 Strategy", "📅 7-Day Calendar", "📊 Previews", "💎 Tiers", "🛠️ Admin" if is_admin else "ℹ️ Support"])

    with tabs[0]: # STRATEGY & EXPORTS
        if run_button and city_input:
            with st.spinner("Analyzing market battlecards..."):
                run_marketing_swarm({'city': city_input, 'industry': main_cat, 'service': target_service})
                if os.path.exists("final_marketing_strategy.md"):
                    with open("final_marketing_strategy.md", "r", encoding="utf-8") as f: content = f.read()
                    st.session_state['ad_copy'] = content
                    st.session_state['calendar'] = [f"**Day {i}**: Content for {target_service} in {city_input}" for i in range(1, 8)]
                    st.session_state['generated'] = True
        
        if st.session_state.get('generated'):
            copy = st.session_state['ad_copy']
            c1, c2 = st.columns(2)
            c1.download_button("📥 Word Report", create_word_doc(copy, user_logo), f"Strategy_{city_input}.docx", use_container_width=True)
            c2.download_button("📕 PDF Report", create_pdf(copy, target_service, city_input, user_logo), f"Strategy_{city_input}.pdf", use_container_width=True)
            st.markdown(copy)

    with tabs[1]: # CONTENT CALENDAR
        if st.session_state.get('generated'):
            st.subheader("🗓️ Automated Social Media Calendar")
            for day_post in st.session_state['calendar']:
                st.info(day_post)
        else: st.info("Run strategy to generate your weekly calendar.")

    with tabs[2]: # PREVIEWS
        if st.session_state.get('generated'):
            copy = st.session_state['ad_copy']
            st.markdown("### 🌐 Google Ad Preview")
            
            st.markdown(f"<div style='border:1px solid #ddd;padding:15px;border-radius:8px;'><div style='color:#1a0dab;font-size:18px;'>Top Rated {target_service} in {city_input}</div><div style='color:#4d5156;'>{copy[:150]}...</div></div>", unsafe_allow_html=True)
        else: st.info("Run strategy first.")

    if is_admin:
        with tabs[-1]:
            st.subheader("🛠️ Admin God-Mode")
            # Maintenance Toggle
            m_label = "TURN MAINTENANCE OFF" if maintenance_status else "TURN MAINTENANCE ON"
            if st.button(m_label):
                toggle_maintenance("OFF" if maintenance_status else "ON")
                st.rerun()
            
            # User Insights
            st.write("### User Activity Tracker")
            st.dataframe(pd.DataFrame(get_users_from_db()['usernames']).T[['email', 'last_login', 'usage_count']], use_container_width=True)
            
            if st.button("💣 RESET DATABASE"):
                reset_database()
                st.rerun()
