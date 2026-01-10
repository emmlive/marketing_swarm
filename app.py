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
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- 1. SYSTEM INITIALIZATION ---
os.environ["OTEL_SDK_DISABLED"] = "true"
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

st.set_page_config(page_title="BreatheEasy AI | Enterprise", page_icon="🌬️", layout="wide")

# --- 2. DATABASE & TEAM EMAIL FEATURE ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance_mode', 'OFF')")
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, 
                  package TEXT, logo_path TEXT, last_login TEXT, usage_count INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    
    c.execute("SELECT username FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, email, name, password, role, package, last_login) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited', datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit(); conn.close()

def send_team_alert(subject, message):
    """Sends internal alerts to the Admin Team Email"""
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
    except Exception as e:
        print(f"Alert Failed: {e}")

init_db()

# --- 3. UI STYLING ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stDeployButton {display:none;}
    .tier-badge { padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; background: #0056b3; color: white; }
    .pricing-card { border: 1px solid #ddd; padding: 25px; border-radius: 12px; text-align: center; background: white; height: 100%; box-shadow: 2px 4px 8px rgba(0,0,0,0.05); }
    .agent-log { font-family: 'Courier New', monospace; font-size: 12px; color: #2ecc71; background: #1e1e1e; padding: 10px; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- 4. EXPORT GENERATORS ---
def create_word_doc(content, logo_path=None):
    doc = Document()
    if logo_path and os.path.exists(logo_path):
        try: doc.add_picture(logo_path, width=Inches(1.5))
        except: pass
    doc.add_heading('BreatheEasy AI | Strategy Report', 0)
    for line in content.split('\n'): doc.add_paragraph(line)
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city, logo_path=None):
    pdf = FPDF(); pdf.add_page()
    if logo_path and os.path.exists(logo_path):
        try: pdf.image(logo_path, 10, 8, 33); pdf.ln(20)
        except: pass
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'{service} Strategy - {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=10); clean = content.encode('latin-1', 'ignore').decode('latin-1')
    pdf.multi_cell(0, 7, txt=clean); return pdf.output(dest='S').encode('latin-1')

# --- 5. AUTHENTICATION & REGISTRATION ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn); conn.close()
    return {'usernames': {row['username']: {'email': row['email'], 'name': row['name'], 'password': row['password'], 
            'package': row.get('package', 'Basic'), 'logo_path': row.get('logo_path')} for _, row in df.iterrows()}}

@st.dialog("🎓 Strategy Masterclass")
def video_tutorial():
    st.write("### How to close $10k+ clients using these reports.")
    st.video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    if st.button("Close"): st.rerun()

authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days'])

authenticator.login(location='main')

if st.session_state["authentication_status"] is None:
    st.markdown("<h1 style='text-align: center;'>🌬️ BreatheEasy AI</h1>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        try:
            res_forgot = authenticator.forgot_password(location='main')
            if res_forgot[0]: st.success('Check email for new password.')
        except: pass
    with col2:
        # FIX: Explicit Registration Form
        with st.expander("🆕 New User? Register Here"):
            try:
                res_reg = authenticator.register_user(location='main', pre_authorization=False)
                if res_reg:
                    e, u, n = res_reg
                    if e:
                        h_pw = stauth.Hasher.hash(authenticator.credentials['usernames'][u]['password'])
                        conn = sqlite3.connect('breatheeasy.db')
                        conn.cursor().execute("INSERT INTO users (username, email, name, password, role, package, last_login) VALUES (?,?,?,?,?,?,?)",
                                              (u, e, n, h_pw, 'member', 'Basic', datetime.now().strftime("%Y-%m-%d %H:%M")))
                        conn.commit(); conn.close()
                        send_team_alert("New User", f"User {u} ({n}) has registered for the Basic tier.")
                        st.success('Registration successful! Please login above.')
            except Exception as ex: st.info("Fill the form to register.")
    st.stop()

# --- 6. DASHBOARD (LOGGED IN) ---
if st.session_state["authentication_status"]:
    username = st.session_state["username"]
    user_info = get_db_creds()['usernames'].get(username, {})
    user_tier = user_info.get('package', 'Basic')
    user_logo = user_info.get('logo_path')

    PACKAGE_CONFIG = {
        "Basic": {"industries": ["HVAC", "Plumbing"], "files": 1, "blog": False, "branding": False, "desc": "Solo Contractor Starter"},
        "Pro": {"industries": ["HVAC", "Plumbing", "Restoration", "Solar"], "files": 5, "blog": True, "branding": True, "desc": "Growth Agency Level"},
        "Unlimited": {"industries": ["HVAC", "Plumbing", "Restoration", "Solar", "Roofing", "Law Firm", "Medical", "Custom"], "files": 20, "blog": True, "branding": True, "desc": "Enterprise Power"}
    }

    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state['name']} <span class='tier-badge'>{user_tier}</span>", unsafe_allow_html=True)
        if st.button("🎓 Video Tutorial"): video_tutorial()
        
        if PACKAGE_CONFIG[user_tier]["branding"]:
            with st.expander("🎨 Custom Branding"):
                logo_file = st.file_uploader("Upload Logo", type=['png', 'jpg'])
                if logo_file:
                    os.makedirs("logos", exist_ok=True)
                    user_logo = f"logos/{username}.png"
                    with open(user_logo, "wb") as f: f.write(logo_file.getvalue())
                    conn = sqlite3.connect('breatheeasy.db')
                    conn.cursor().execute("UPDATE users SET logo_path = ? WHERE username = ?", (user_logo, username))
                    conn.commit(); conn.close(); st.success("Branding Applied!")
        
        authenticator.logout('Sign Out', 'sidebar')
        st.divider()

        st.subheader("📁 Asset Manager")
        max_f = PACKAGE_CONFIG[user_tier]["files"]
        st.file_uploader(f"Max {max_f} assets", accept_multiple_files=True)
        
        # Industry/Service Map
        full_map = {"HVAC": ["AC Replacement", "Duct Cleaning"], "Plumbing": ["Sewer Repair", "Tankless Heaters"], "Custom": ["Manual Entry"]}
        allowed = PACKAGE_CONFIG[user_tier]["industries"]
        main_cat = st.selectbox("Industry", [i for i in full_map.keys() if i in allowed])
        target_service = st.selectbox("Service", full_map[main_cat]) if main_cat != "Custom" else st.text_input("Service")
        city_input = st.text_input("City", placeholder="Naperville, IL")

        # Agents
        include_blog = st.toggle("📝 SEO Blog Strategist", value=True) if PACKAGE_CONFIG[user_tier]["blog"] else False
        include_comp = st.toggle("🕵️ Competitor Intelligence", value=True) if user_tier != "Basic" else False
        
        run_button = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

    tabs = st.tabs(["🔥 Launchpad", "📊 Database", "📱 Preview", "💎 Pricing", "🛠️ Admin" if username=="admin" else "📋 History"])

    with tabs[0]: # OUTPUT
        if run_button and city_input:
            # PERFORMANCE FEEDBACK: Real-time console
            with st.status("🐝 Swarm Coordinating... (Agent Reasoning in Progress)", expanded=True) as status:
                st.write("🔍 Market Analyst researching local trends...")
                run_marketing_swarm({'city': city_input, 'industry': main_cat, 'service': target_service, 'blog': include_blog, 'comp': include_comp})
                st.write("✍️ Creative Director drafting high-ticket copy...")
                st.write("🛡️ Proofreader verifying SEO and brand safety...")
                status.update(label="✅ Analysis Complete!", state="complete", expanded=False)
                
                if os.path.exists("final_marketing_strategy.md"):
                    with open("final_marketing_strategy.md", "r") as f: st.session_state['copy'] = f.read()
                    st.session_state['gen'] = True
                    # Log usage
                    conn = sqlite3.connect('breatheeasy.db')
                    conn.cursor().execute("UPDATE users SET usage_count = usage_count + 1 WHERE username = ?", (username,))
                    conn.commit(); conn.close()
        
        if st.session_state.get('gen'):
            copy = st.session_state['copy']
            st.subheader("📥 Download Deliverables")
            col1, col2 = st.columns(2)
            col1.download_button("📄 Word Doc", create_word_doc(copy, user_logo), f"{city_input}_Report.docx", use_container_width=True)
            col2.download_button("📕 PDF Report", create_pdf(copy, target_service, city_input, user_logo), f"{city_input}_Report.pdf", use_container_width=True)
            st.divider()
            st.markdown(copy)

    with tabs[3]: # PRICING
        c1, c2, c3 = st.columns(3)
        for i, (p_name, p_val) in enumerate(PACKAGE_CONFIG.items()):
            with [c1, c2, c3][i]:
                st.markdown(f"""<div class="pricing-card"><h3>{p_name}</h3><p>{p_val['desc']}</p><hr><ul style="text-align:left;font-size:12px;"><li>{len(p_val['industries'])} Industries</li><li>{p_val['files']} Files</li><li>{'✅' if p_val['blog'] else '❌'} Blog AI</li></ul></div>""", unsafe_allow_html=True)
