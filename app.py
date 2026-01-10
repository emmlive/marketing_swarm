import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
import urllib.parse
from datetime import datetime, timedelta
from main import run_marketing_swarm 
from docx import Document
from fpdf import FPDF
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- 1. PRE-IMPORT KEY MAPPING ---
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

# --- 2. PAGE CONFIGURATION ---
st.set_page_config(page_title="BreatheEasy AI | Enterprise", page_icon="🌬️", layout="wide")

# --- 3. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, package TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, admin_user TEXT, action TEXT, target_user TEXT, details TEXT)''')
    
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, email, name, password, role, package) VALUES (?, ?, ?, ?, ?, ?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited'))
    conn.commit()
    conn.close()

# --- 4. EMAIL & REPORTING LOGIC ---
def send_admin_alert(subject, body):
    msg = MIMEMultipart()
    msg["From"] = st.secrets["EMAIL_SENDER"]
    msg["To"] = st.secrets["TEAM_EMAIL"]
    msg["Subject"] = f"🔔 BreatheEasy: {subject}"
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"])
            server.sendmail(st.secrets["EMAIL_SENDER"], st.secrets["TEAM_EMAIL"], msg.as_string())
        return True
    except: return False

def generate_monthly_report():
    """Compiles revenue and activity data from the last 30 days."""
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    
    # Get New Registrations
    new_users = pd.read_sql_query("SELECT COUNT(*) as count FROM users WHERE username != 'admin'", conn)['count'][0]
    
    # Get Revenue Actions (Upgrades)
    upgrades = pd.read_sql_query("SELECT details FROM audit_logs WHERE action = 'UPDATE_TIER'", conn)
    pro_count = upgrades[upgrades['details'].str.contains("Pro", na=False)].shape[0]
    unlimited_count = upgrades[upgrades['details'].str.contains("Unlimited", na=False)].shape[0]
    
    # Calculate Est. Revenue
    total_rev = (pro_count * 49) + (unlimited_count * 99)
    
    # Get Service Popularity
    leads = pd.read_sql_query("SELECT industry, service FROM leads", conn)
    service_summary = leads.groupby(['industry', 'service']).size().reset_index(name='usage_count')
    
    report_body = f"""
    BREATHEEASY AI - MONTHLY PERFORMANCE REPORT
    Generated: {datetime.now().strftime('%Y-%m-%d')}
    --------------------------------------------
    📈 USER GROWTH:
    Total Active Members: {new_users}
    
    💰 REVENUE SUMMARY:
    New Pro Upgrades: {pro_count} ($49/ea)
    New Unlimited Upgrades: {unlimited_count} ($99/ea)
    ESTIMATED MONTHLY REVENUE: ${total_rev}
    
    🛠️ SERVICE USAGE (Top Industries):
    {service_summary.to_string(index=False)}
    
    --------------------------------------------
    End of Report.
    """
    conn.close()
    return send_admin_alert("Monthly Revenue & Usage Report", report_body)

# --- 5. LOGGING & DB UPDATES ---
def log_action(admin_user, action, target_user, details=""):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO audit_logs (timestamp, admin_user, action, target_user, details) VALUES (?, ?, ?, ?, ?)",
              (timestamp, admin_user, action, target_user, details))
    conn.commit()
    conn.close()

def update_user_package(username, new_package, admin_name):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT package FROM users WHERE username = ?", (username,))
    old_p = c.fetchone()[0]
    c.execute("UPDATE users SET package = ? WHERE username = ?", (new_package, username))
    conn.commit()
    conn.close()
    log_action(admin_name, "UPDATE_TIER", username, f"Changed from {old_p} to {new_package}")
    send_admin_alert("Tier Update", f"User {username} upgraded to {new_package}.")

def get_users_from_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    user_dict = {'usernames': {}}
    for _, row in df.iterrows():
        user_dict['usernames'][row['username']] = {
            'email': row['email'], 'name': row['name'], 'password': row['password'], 'package': row.get('package', 'Basic')
        }
    return user_dict

init_db()

# --- 6. AUTHENTICATION ---
db_credentials = get_users_from_db()
authenticator = stauth.Authenticate(
    db_credentials, st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days']
)
authenticator.login(location='main')

if st.session_state["authentication_status"] is None:
    st.warning('Welcome. Please login.')
    with st.expander("New User? Register Here"):
        try:
            res = authenticator.register_user(pre_authorization=False)
            if res:
                email, username, name = res
                if email:
                    db_ready_pw = stauth.Hasher.hash(authenticator.credentials['usernames'][username]['password'])
                    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
                    conn.cursor().execute("INSERT INTO users (username, email, name, password, role, package) VALUES (?, ?, ?, ?, ?, ?)",
                                          (username, email, name, db_ready_pw, 'member', 'Basic'))
                    conn.commit(); conn.close()
                    send_admin_alert("New Registration", f"New user signed up: {name} ({username})")
                    st.success('✅ Registered!'); st.rerun()
        except Exception as e: st.error(e)
    st.stop()

# --- 7. DASHBOARD LOGIC ---
if st.session_state["authentication_status"]:
    username = st.session_state["username"]
    current_db_data = get_users_from_db()
    user_tier = current_db_data['usernames'][username].get('package', 'Basic')

    # Sidebar, Pricing, and Launchpad logic remains identical to previous version...
    # (Abbreviated here for brevity, keep your existing Launchpad/Social Preview code)

    tab_list = ["🔥 Launchpad", "📊 Database", "📱 Social Preview", "💎 Pricing"]
    if username == "admin": tab_list.append("🛠️ Admin Panel")
    tabs = st.tabs(tab_list)

    # ... [Existing Tabs Code] ...

    if username == "admin":
        with tabs[-1]:
            admin_sub_tabs = st.tabs(["👥 Users", "📜 Logs", "📈 Reports"])
            
            with admin_sub_tabs[2]:
                st.header("Financial & Usage Reports")
                st.write("Generate a detailed summary of revenue and top-performing services.")
                if st.button("📧 Send Monthly Report Now"):
                    with st.spinner("Compiling database records..."):
                        if generate_monthly_report():
                            st.success("Report successfully emailed to the team!")
                        else:
                            st.error("Failed to send email. Check your SMTP secrets.")
