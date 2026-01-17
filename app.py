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

st.set_page_config(page_title="BreatheEasy AI | Enterprise Command", page_icon="🌬️", layout="wide")

# --- 2. DATABASE ARCHITECTURE ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance_mode', 'OFF')")
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, 
                  package TEXT, credits INTEGER DEFAULT 0, logo_path TEXT, last_login TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    
    # Ensure Admin exists
    c.execute("SELECT username FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, email, name, password, role, package, credits) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited', 9999))
    conn.commit(); conn.close()

def send_team_alert(subject, message):
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["EMAIL_SENDER"]
        msg['To'] = st.secrets["TEAM_EMAIL"]
        msg['Subject'] = f"🚨 BreatheEasy Alert: {subject}"
        msg.attach(MIMEText(message, 'plain'))
        server = smtplib.SMTP(st.secrets["SMTP_SERVER"], st.secrets["SMTP_PORT"])
        server.starttls()
        server.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"])
        server.send_message(msg); server.quit()
    except: pass

init_db()

# --- 3. UI STYLING & SAAS CONFIG ---
PACKAGE_CONFIG = {
    "Basic": {"industries": ["HVAC", "Plumbing"], "credits": 5, "max_files": 1, "blog": False, "branding": False, "desc": "Perfect for solo contractors."},
    "Pro": {"industries": ["HVAC", "Plumbing", "Restoration", "Solar"], "credits": 50, "max_files": 5, "blog": True, "branding": True, "desc": "For growing agencies."},
    "Unlimited": {"industries": ["HVAC", "Plumbing", "Restoration", "Solar", "Roofing", "Law Firm", "Medical", "Custom"], "credits": 999, "max_files": 20, "blog": True, "branding": True, "desc": "Enterprise Power."}
}

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .tier-badge { padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; background: #0056b3; color: white; }
    .pricing-card { border: 1px solid #ddd; padding: 25px; border-radius: 12px; text-align: center; background: white; height: 100%; box-shadow: 2px 4px 8px rgba(0,0,0,0.05); }
    .agent-thought { background: #1e1e1e; color: #2ecc71; font-family: 'Courier New', monospace; padding: 10px; border-radius: 5px; font-size: 12px; margin-bottom: 10px; }
    a[href*="forgot_password"] { display: inline-block; padding: 0.6rem 1.2rem; background-color: white; color: #31333F !important; border: 1px solid #ddd; border-radius: 0.5rem; text-decoration: none !important; font-size: 14px; margin-top: 10px; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

# --- 4. EXPORT GENERATORS ---
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

# --- 5. AUTHENTICATION & REGISTRATION ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn); conn.close()
    return {'usernames': {row['username']: {'email': row['email'], 'name': row['name'], 'password': row['password'], 
            'package': row.get('package', 'Basic'), 'credits': row.get('credits', 0), 'logo_path': row.get('logo_path')} for _, row in df.iterrows()}}

authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days'])

@st.dialog("🎓 Strategy Masterclass")
def video_tutorial():
    st.write("### How to close $10k+ clients using these reports.")
    st.video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    if st.button("Close"): st.rerun()

if not st.session_state.get("authentication_status"):
    st.markdown("<h1 style='text-align: center;'>🌬️ BreatheEasy AI Master</h1>", unsafe_allow_html=True)
    l_tab, r_tab = st.tabs(["🔑 Login", "📝 Register"])
    with l_tab:
        authenticator.login(location='main')
        try:
            res_forgot = authenticator.forgot_password(location='main')
            if res_forgot[0]: st.success('Reset link sent.')
        except: pass
    with r_tab:
        res_reg = authenticator.register_user(location='main', pre_authorization=False)
        if res_reg:
            e, u, n = res_reg
            h_pw = stauth.Hasher.hash(authenticator.credentials['usernames'][u]['password'])
            conn = sqlite3.connect('breatheeasy.db')
            conn.cursor().execute("INSERT INTO users (username, email, name, password, role, package, credits) VALUES (?,?,?,?,?,?,?)",
                                  (u, e, n, h_pw, 'member', 'Basic', 5))
            conn.commit(); conn.close()
            send_team_alert("New Registration", f"User {u} joined the platform.")
            st.success('Registered! Go to Login tab.')
    st.stop()

# --- 6. PROTECTED DASHBOARD ---
username = st.session_state["username"]
user_info = get_db_creds()['usernames'].get(username, {})
user_tier = user_info.get('package', 'Basic')
user_logo = user_info.get('logo_path')
user_credits = user_info.get('credits', 0)

with st.sidebar:
    st.markdown(f"### 👋 {st.session_state['name']} <span class='tier-badge'>{user_tier}</span>", unsafe_allow_html=True)
    st.metric("Credits Available", user_credits)
    if st.button("🎓 Video Tutorial"): video_tutorial()
    
    if PACKAGE_CONFIG[user_tier]["branding"]:
        with st.expander("🎨 Custom Branding"):
            logo_file = st.file_uploader("Upload Company Logo", type=['png', 'jpg'])
            if logo_file:
                os.makedirs("logos", exist_ok=True)
                user_logo = f"logos/{username}.png"
                with open(user_logo, "wb") as f: f.write(logo_file.getvalue())
                conn = sqlite3.connect('breatheeasy.db')
                conn.cursor().execute("UPDATE users SET logo_path = ? WHERE username = ?", (user_logo, username))
                conn.commit(); conn.close(); st.success("Branding Applied!")

    authenticator.logout('Sign Out', 'sidebar')
    st.divider()

    # DYNAMIC INPUTS
    full_map = {"HVAC": ["AC Replacement", "Duct Cleaning", "IAQ Audit"], "Plumbing": ["Sewer Line", "Tankless Install"], "Solar": ["Residential Grid"], "Custom": ["Manual"]}
    allowed = PACKAGE_CONFIG[user_tier]["industries"]
    main_cat = st.selectbox("Industry", [i for i in full_map.keys() if i in allowed])
    target_service = st.selectbox("Service", full_map[main_cat]) if main_cat != "Custom" else st.text_input("Service Name")
    city_input = st.text_input("City")
    
    st.subheader("🕵️ Specialists")
    include_blog = st.toggle("📝 SEO Blog Strategist", value=True) if PACKAGE_CONFIG[user_tier]["blog"] else False
    include_visual = st.toggle("👁️ Visual Inspector Agent", value=False)
    run_button = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

# --- 7. TABS ---
tabs = st.tabs(["🔥 Launchpad", "📊 Database", "📱 Preview", "👁️ Visual Inspector", "💎 Pricing", "🛠️ Admin" if username=="admin" else "📋 History"])

with tabs[0]: # LAUNCHPAD
    if run_button and city_input:
        if user_credits > 0:
            with st.status("🐝 Swarm Processing...", expanded=True) as status:
                st.markdown(f"<div class='agent-thought'>Analyst: Researching {target_service} in {city_input}...</div>", unsafe_allow_html=True)
                res = run_marketing_swarm({'city': city_input, 'industry': main_cat, 'service': target_service})
                st.session_state['copy'] = res
                st.session_state['gen'] = True
                conn = sqlite3.connect('breatheeasy.db')
                conn.cursor().execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (username,))
                conn.cursor().execute("INSERT INTO leads (date, user, industry, service, city, content) VALUES (?,?,?,?,?,?)",
                                      (datetime.now().strftime("%Y-%m-%d"), username, main_cat, target_service, city_input, str(res)))
                conn.commit(); conn.close(); st.rerun()
        else: st.error("Out of credits.")

    if st.session_state.get('gen'):
        copy = st.session_state['copy']
        st.subheader("📥 Download Deliverables")
        col1, col2 = st.columns(2)
        col1.download_button("📄 Word Doc", create_word_doc(copy, user_logo), f"Report_{city_input}.docx", use_container_width=True)
        col2.download_button("📕 PDF Report", create_pdf(copy, target_service, city_input, user_logo), f"Report_{city_input}.pdf", use_container_width=True)
        st.divider()
        st.markdown(copy)

with tabs[1]: # DATABASE
    st.subheader("📊 Campaign Database")
    conn = sqlite3.connect('breatheeasy.db')
    df = pd.read_sql_query("SELECT date, industry, service, city FROM leads WHERE user = ?", conn, params=(username,))
    st.dataframe(df, use_container_width=True); conn.close()

with tabs[3]: # VISUAL INSPECTOR
    st.subheader("👁️ Visual Brand Strategist")
    up = st.file_uploader("Upload jobsite photo", type=['png', 'jpg'])
    if up: st.image(up, caption="Processing for visual identity prompts...", width=400)

with tabs[4]: # PRICING
    c1, c2, c3 = st.columns(3)
    for i, (p_name, p_val) in enumerate(PACKAGE_CONFIG.items()):
        with [c1, c2, c3][i]:
            st.markdown(f"""<div class="pricing-card"><h3>{p_name}</h3><h1 style='color:#2ecc71;'>{p_val['credits']}</h1><p>Credits Included</p><p>{p_val['desc']}</p></div>""", unsafe_allow_html=True)import streamlit as st
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

st.set_page_config(page_title="BreatheEasy AI | Enterprise Command", page_icon="🌬️", layout="wide")

# --- 2. DATABASE ARCHITECTURE ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance_mode', 'OFF')")
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, 
                  package TEXT, credits INTEGER DEFAULT 0, logo_path TEXT, last_login TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    
    # Ensure Admin exists
    c.execute("SELECT username FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, email, name, password, role, package, credits) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited', 9999))
    conn.commit(); conn.close()

def send_team_alert(subject, message):
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["EMAIL_SENDER"]
        msg['To'] = st.secrets["TEAM_EMAIL"]
        msg['Subject'] = f"🚨 BreatheEasy Alert: {subject}"
        msg.attach(MIMEText(message, 'plain'))
        server = smtplib.SMTP(st.secrets["SMTP_SERVER"], st.secrets["SMTP_PORT"])
        server.starttls()
        server.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"])
        server.send_message(msg); server.quit()
    except: pass

init_db()

# --- 3. UI STYLING & SAAS CONFIG ---
PACKAGE_CONFIG = {
    "Basic": {"industries": ["HVAC", "Plumbing"], "credits": 5, "max_files": 1, "blog": False, "branding": False, "desc": "Perfect for solo contractors."},
    "Pro": {"industries": ["HVAC", "Plumbing", "Restoration", "Solar"], "credits": 50, "max_files": 5, "blog": True, "branding": True, "desc": "For growing agencies."},
    "Unlimited": {"industries": ["HVAC", "Plumbing", "Restoration", "Solar", "Roofing", "Law Firm", "Medical", "Custom"], "credits": 999, "max_files": 20, "blog": True, "branding": True, "desc": "Enterprise Power."}
}

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .tier-badge { padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; background: #0056b3; color: white; }
    .pricing-card { border: 1px solid #ddd; padding: 25px; border-radius: 12px; text-align: center; background: white; height: 100%; box-shadow: 2px 4px 8px rgba(0,0,0,0.05); }
    .agent-thought { background: #1e1e1e; color: #2ecc71; font-family: 'Courier New', monospace; padding: 10px; border-radius: 5px; font-size: 12px; margin-bottom: 10px; }
    a[href*="forgot_password"] { display: inline-block; padding: 0.6rem 1.2rem; background-color: white; color: #31333F !important; border: 1px solid #ddd; border-radius: 0.5rem; text-decoration: none !important; font-size: 14px; margin-top: 10px; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

# --- 4. EXPORT GENERATORS ---
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

# --- 5. AUTHENTICATION & REGISTRATION ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn); conn.close()
    return {'usernames': {row['username']: {'email': row['email'], 'name': row['name'], 'password': row['password'], 
            'package': row.get('package', 'Basic'), 'credits': row.get('credits', 0), 'logo_path': row.get('logo_path')} for _, row in df.iterrows()}}

authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days'])

@st.dialog("🎓 Strategy Masterclass")
def video_tutorial():
    st.write("### How to close $10k+ clients using these reports.")
    st.video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    if st.button("Close"): st.rerun()

if not st.session_state.get("authentication_status"):
    st.markdown("<h1 style='text-align: center;'>🌬️ BreatheEasy AI Master</h1>", unsafe_allow_html=True)
    l_tab, r_tab = st.tabs(["🔑 Login", "📝 Register"])
    with l_tab:
        authenticator.login(location='main')
        try:
            res_forgot = authenticator.forgot_password(location='main')
            if res_forgot[0]: st.success('Reset link sent.')
        except: pass
    with r_tab:
        res_reg = authenticator.register_user(location='main', pre_authorization=False)
        if res_reg:
            e, u, n = res_reg
            h_pw = stauth.Hasher.hash(authenticator.credentials['usernames'][u]['password'])
            conn = sqlite3.connect('breatheeasy.db')
            conn.cursor().execute("INSERT INTO users (username, email, name, password, role, package, credits) VALUES (?,?,?,?,?,?,?)",
                                  (u, e, n, h_pw, 'member', 'Basic', 5))
            conn.commit(); conn.close()
            send_team_alert("New Registration", f"User {u} joined the platform.")
            st.success('Registered! Go to Login tab.')
    st.stop()

# --- 6. PROTECTED DASHBOARD ---
username = st.session_state["username"]
user_info = get_db_creds()['usernames'].get(username, {})
user_tier = user_info.get('package', 'Basic')
user_logo = user_info.get('logo_path')
user_credits = user_info.get('credits', 0)

with st.sidebar:
    st.markdown(f"### 👋 {st.session_state['name']} <span class='tier-badge'>{user_tier}</span>", unsafe_allow_html=True)
    st.metric("Credits Available", user_credits)
    if st.button("🎓 Video Tutorial"): video_tutorial()
    
    if PACKAGE_CONFIG[user_tier]["branding"]:
        with st.expander("🎨 Custom Branding"):
            logo_file = st.file_uploader("Upload Company Logo", type=['png', 'jpg'])
            if logo_file:
                os.makedirs("logos", exist_ok=True)
                user_logo = f"logos/{username}.png"
                with open(user_logo, "wb") as f: f.write(logo_file.getvalue())
                conn = sqlite3.connect('breatheeasy.db')
                conn.cursor().execute("UPDATE users SET logo_path = ? WHERE username = ?", (user_logo, username))
                conn.commit(); conn.close(); st.success("Branding Applied!")

    authenticator.logout('Sign Out', 'sidebar')
    st.divider()

    # DYNAMIC INPUTS
    full_map = {"HVAC": ["AC Replacement", "Duct Cleaning", "IAQ Audit"], "Plumbing": ["Sewer Line", "Tankless Install"], "Solar": ["Residential Grid"], "Custom": ["Manual"]}
    allowed = PACKAGE_CONFIG[user_tier]["industries"]
    main_cat = st.selectbox("Industry", [i for i in full_map.keys() if i in allowed])
    target_service = st.selectbox("Service", full_map[main_cat]) if main_cat != "Custom" else st.text_input("Service Name")
    city_input = st.text_input("City")
    
    st.subheader("🕵️ Specialists")
    include_blog = st.toggle("📝 SEO Blog Strategist", value=True) if PACKAGE_CONFIG[user_tier]["blog"] else False
    include_visual = st.toggle("👁️ Visual Inspector Agent", value=False)
    run_button = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

# --- 7. TABS ---
tabs = st.tabs(["🔥 Launchpad", "📊 Database", "📱 Preview", "👁️ Visual Inspector", "💎 Pricing", "🛠️ Admin" if username=="admin" else "📋 History"])

with tabs[0]: # LAUNCHPAD
    if run_button and city_input:
        if user_credits > 0:
            with st.status("🐝 Swarm Processing...", expanded=True) as status:
                st.markdown(f"<div class='agent-thought'>Analyst: Researching {target_service} in {city_input}...</div>", unsafe_allow_html=True)
                res = run_marketing_swarm({'city': city_input, 'industry': main_cat, 'service': target_service})
                st.session_state['copy'] = res
                st.session_state['gen'] = True
                conn = sqlite3.connect('breatheeasy.db')
                conn.cursor().execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (username,))
                conn.cursor().execute("INSERT INTO leads (date, user, industry, service, city, content) VALUES (?,?,?,?,?,?)",
                                      (datetime.now().strftime("%Y-%m-%d"), username, main_cat, target_service, city_input, str(res)))
                conn.commit(); conn.close(); st.rerun()
        else: st.error("Out of credits.")

    if st.session_state.get('gen'):
        copy = st.session_state['copy']
        st.subheader("📥 Download Deliverables")
        col1, col2 = st.columns(2)
        col1.download_button("📄 Word Doc", create_word_doc(copy, user_logo), f"Report_{city_input}.docx", use_container_width=True)
        col2.download_button("📕 PDF Report", create_pdf(copy, target_service, city_input, user_logo), f"Report_{city_input}.pdf", use_container_width=True)
        st.divider()
        st.markdown(copy)

with tabs[1]: # DATABASE
    st.subheader("📊 Campaign Database")
    conn = sqlite3.connect('breatheeasy.db')
    df = pd.read_sql_query("SELECT date, industry, service, city FROM leads WHERE user = ?", conn, params=(username,))
    st.dataframe(df, use_container_width=True); conn.close()

with tabs[3]: # VISUAL INSPECTOR
    st.subheader("👁️ Visual Brand Strategist")
    up = st.file_uploader("Upload jobsite photo", type=['png', 'jpg'])
    if up: st.image(up, caption="Processing for visual identity prompts...", width=400)

with tabs[4]: # PRICING
    c1, c2, c3 = st.columns(3)
    for i, (p_name, p_val) in enumerate(PACKAGE_CONFIG.items()):
        with [c1, c2, c3][i]:
            st.markdown(f"""<div class="pricing-card"><h3>{p_name}</h3><h1 style='color:#2ecc71;'>{p_val['credits']}</h1><p>Credits Included</p><p>{p_val['desc']}</p></div>""", unsafe_allow_html=True)
