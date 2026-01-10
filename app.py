import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
import requests
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

st.set_page_config(page_title="BreatheEasy AI | Enterprise Command", page_icon="🌬️", layout="wide")

# --- 2. DATABASE ARCHITECTURE ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    # Settings & Maintenance
    c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance_mode', 'OFF')")
    # User Table with SaaS Analytics
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, 
                  package TEXT, logo_path TEXT, last_login TEXT, usage_count INTEGER DEFAULT 0)''')
    # Campaign History
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    # Admin Sequential Safety
    c.execute("SELECT username FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, email, name, password, role, package, last_login) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited', datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit(); conn.close()

def reset_database():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS leads")
    c.execute("DROP TABLE IF EXISTS users")
    c.execute("DROP TABLE IF EXISTS settings")
    conn.commit(); conn.close()
    init_db()

def get_maintenance_status():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    res = conn.cursor().execute("SELECT value FROM settings WHERE key = 'maintenance_mode'").fetchone()
    conn.close()
    return res[0] == 'ON' if res else False

init_db()

# --- 3. DOCUMENT GENERATION LOGIC ---
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
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'Strategy: {service} in {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=10); clean = content.encode('latin-1', 'ignore').decode('latin-1')
    pdf.multi_cell(0, 7, txt=clean); return pdf.output(dest='S').encode('latin-1')

# --- 4. AUTHENTICATION & SECURITY ---
def get_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    return {'usernames': {row['username']: {'email': row['email'], 'name': row['name'], 'password': row['password'], 
            'package': row.get('package', 'Basic'), 'logo_path': row.get('logo_path'), 
            'usage_count': row.get('usage_count', 0)} for _, row in df.iterrows()}}

authenticator = stauth.Authenticate(get_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days'])

# --- 5. UI STYLING (Whitelabel + Custom Buttons) ---
st.markdown("""
    <style>
    /* HIDE STREAMLIT BRANDING (GITHUB, FORK, 3 DOTS) */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    
    .tier-badge { padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; background: #0056b3; color: white; }
    .mockup-container { background: white; border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin-bottom: 10px; }
    .pricing-card { border: 1px solid #ddd; padding: 20px; border-radius: 10px; text-align: center; background: white; height: 100%; }

    /* FORGOT PASSWORD BUTTON STYLING */
    p:has(a[href*="forgot_password"]), a[href*="forgot_password"] {
        display: inline-block;
        padding: 0.5rem 1rem;
        background-color: #ffffff;
        color: #31333F !important;
        border: 1px solid rgba(49, 51, 63, 0.2);
        border-radius: 0.5rem;
        text-decoration: none !important;
        font-size: 14px;
        transition: background-color 0.2s;
        margin-top: 10px;
    }
    a[href*="forgot_password"]:hover { background-color: #f0f2f6; border-color: #0056b3; }
    </style>
""", unsafe_allow_html=True)

# --- 6. AUTHENTICATION FLOW ---
authenticator.login(location='main')

if st.session_state["authentication_status"] is True:
    username = st.session_state["username"]
    user_info = get_creds()['usernames'].get(username, {})
    tier = user_info.get('package', 'Basic')
    is_admin = (username == "admin")

    if get_maintenance_status() and not is_admin:
        st.error("🚧 BreatheEasy AI is currently under maintenance for system upgrades.")
        st.stop()

    # SAAS GATING CONFIG
    TIER_LIMITS = {
        "Basic": {"industries": ["HVAC", "Plumbing"], "files": 1, "blog": False},
        "Pro": {"industries": ["HVAC", "Plumbing", "Restoration", "Solar"], "files": 5, "blog": True},
        "Unlimited": {"industries": ["HVAC", "Plumbing", "Restoration", "Solar", "Law Firm", "Medical", "Custom"], "files": 20, "blog": True}
    }

    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state['name']} <span class='tier-badge'>{tier}</span>", unsafe_allow_html=True)
        if st.button("🔑 Change Password"):
            if authenticator.reset_password(username, 'Reset password'):
                new_h = stauth.Hasher.hash(authenticator.credentials['usernames'][username]['password'])
                conn = sqlite3.connect('breatheeasy.db')
                conn.cursor().execute("UPDATE users SET password = ? WHERE username = ?", (new_h, username))
                conn.commit(); conn.close(); st.success('Password updated!')
        authenticator.logout('Sign Out', 'sidebar')
        st.divider()
        
        main_cat = st.selectbox("Industry", TIER_LIMITS[tier]["industries"])
        target_service = st.text_input("Service (e.g. Mold Remediation)")
        if TIER_LIMITS[tier]["blog"]: include_blog = st.toggle("📝 SEO Blog Creator", value=True)
        else: st.info("🔒 SEO Blog (Upgrade to Pro)"); include_blog = False
        
        max_f = TIER_LIMITS[tier]["files"]
        uploaded = st.file_uploader(f"Client Assets (Max {max_f})", accept_multiple_files=True)
        city = st.text_input("City")
        launch = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

    tabs = st.tabs(["🔥 Strategy", "📅 7-Day Calendar", "📱 Previews", "💎 Pricing", "🛠️ Admin" if is_admin else "📋 History"])

    with tabs[0]: # STRATEGY & DOWNLOADS
        if launch and city:
            with st.spinner("AI Agents coordinating strategy..."):
                run_marketing_swarm({'city': city, 'industry': main_cat, 'service': target_service, 'blog': include_blog})
                if os.path.exists("final_marketing_strategy.md"):
                    with open("final_marketing_strategy.md", "r") as f: st.session_state['copy'] = f.read()
                    st.session_state['gen'] = True
                    conn = sqlite3.connect('breatheeasy.db')
                    conn.cursor().execute("UPDATE users SET usage_count = usage_count + 1 WHERE username = ?", (username,))
                    conn.cursor().execute("INSERT INTO leads (date, user, industry, service, city, content) VALUES (?,?,?,?,?,?)",
                                          (datetime.now().strftime("%Y-%m-%d"), username, main_cat, target_service, city, st.session_state['copy']))
                    conn.commit(); conn.close()

        if st.session_state.get('gen'):
            copy = st.session_state['copy']
            col1, col2 = st.columns(2)
            col1.download_button("📄 Word Doc", create_word_doc(copy, user_info.get('logo_path')), f"{city}_Strategy.docx", use_container_width=True)
            col2.download_button("📕 PDF Report", create_pdf(copy, target_service, city, user_info.get('logo_path')), f"{city}_Strategy.pdf", use_container_width=True)
            st.markdown(copy)

    with tabs[2]: # MOCKUPS
        if st.session_state.get('gen'):
            st.markdown(f"<div class='mockup-container'><div style='color:#1a0dab;font-size:18px;'>#1 {target_service} in {city}</div><p>{st.session_state['copy'][:150]}...</p></div>", unsafe_allow_html=True)

    if is_admin:
        with tabs[-1]:
            st.subheader("🛠️ Admin Suite")
            if st.button("TOGGLE MAINTENANCE"):
                m_on = get_maintenance_status()
                conn = sqlite3.connect('breatheeasy.db')
                conn.cursor().execute("UPDATE settings SET value = ? WHERE key = 'maintenance_mode'", ("OFF" if m_on else "ON",))
                conn.commit(); conn.close(); st.rerun()
            
            if st.button("💣 RESET ALL DATA"):
                reset_database()
                st.rerun()

            conn = sqlite3.connect('breatheeasy.db')
            st.dataframe(pd.read_sql_query("SELECT username, package, last_login, usage_count FROM users", conn), use_container_width=True)
            conn.close()

elif st.session_state["authentication_status"] is None:
    st.markdown("<h1 style='text-align: center;'>🌬️ BreatheEasy AI</h1>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        try:
            u_forgot, e_forgot, p_forgot = authenticator.forgot_password('Forgot password')
            if u_forgot:
                hashed_f = stauth.Hasher.hash(p_forgot)
                conn = sqlite3.connect('breatheeasy.db')
                conn.cursor().execute("UPDATE users SET password = ? WHERE username = ?", (hashed_f, u_forgot))
                conn.commit(); conn.close(); st.success('Check email for new password.')
        except Exception as e: st.error(e)
    with col2:
        with st.expander("🆕 Register Here"):
            res = authenticator.register_user(pre_authorization=False)
            if res:
                e, u, n = res
                if e:
                    hashed_reg = stauth.Hasher.hash(authenticator.credentials['usernames'][u]['password'])
                    conn = sqlite3.connect('breatheeasy.db')
                    conn.cursor().execute("INSERT INTO users (username, email, name, password, role, package, last_login) VALUES (?,?,?,?,?,?,?)",
                                          (u, e, n, hashed_reg, 'member', 'Basic', datetime.now().strftime("%Y-%m-%d %H:%M")))
                    conn.commit(); conn.close(); st.success('Registered!'); st.rerun()
