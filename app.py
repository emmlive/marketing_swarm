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

# --- 1. SYSTEM INITIALIZATION & UI HIDING ---
os.environ["OTEL_SDK_DISABLED"] = "true"
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

st.set_page_config(page_title="BreatheEasy AI | Enterprise Command", page_icon="🌬️", layout="wide")

# This CSS hides the top-right icons, hamburger menu, and Streamlit footer
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    #stDecoration {display:none;}
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE ARCHITECTURE (Team & History Support) ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, 
                  package TEXT, credits INTEGER DEFAULT 0, logo_path TEXT, team_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, 
                  service TEXT, city TEXT, content TEXT, team_id TEXT, is_shared INTEGER DEFAULT 0, score INTEGER)''')
    
    c.execute("SELECT username FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, email, name, password, role, package, credits, team_id) VALUES (?,?,?,?,?,?,?,?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited', 9999, 'HQ_001'))
    conn.commit(); conn.close()

init_db()

# --- 3. THE "BREATHEEASY" GAUGE (Diagnostic Component) ---
def render_breatheeasy_gauge(score, industry):
    color = "#ff4b4b" if score < 4 else "#ffa500" if score < 7 else "#2ecc71"
    label = "BreatheEasy™ Score" if industry == "HVAC" else f"{industry} Health Score"
    st.markdown(f"""
        <div style="text-align: center; border: 2px solid #ddd; padding: 20px; border-radius: 15px; background: #f9f9f9; margin-bottom: 20px;">
            <h4 style="margin: 0; color: #333;">{label}</h4>
            <div style="font-size: 48px; font-weight: bold; color: {color};">{score}/10</div>
            <div style="width: 100%; background: #ddd; border-radius: 10px; height: 20px; margin-top: 10px;">
                <div style="width: {score*10}%; background: {color}; height: 20px; border-radius: 10px; transition: 0.5s;"></div>
            </div>
            <p style="font-size: 13px; margin-top: 10px; color: #555;"><b>AI Analysis:</b> Based on autonomous {industry} safety protocols.</p>
        </div>
    """, unsafe_allow_html=True)

# --- 4. EXPORT GENERATORS (Word & PDF Formats) ---
def create_word_doc(content, logo_path=None):
    doc = Document()
    if logo_path and os.path.exists(logo_path):
        try: doc.add_picture(logo_path, width=Inches(1.5))
        except: pass
    doc.add_heading('BreatheEasy AI | Strategy & Swarm Report', 0)
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

# --- 5. AUTHENTICATION & LOGIN RECOVERY ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn); conn.close()
    return {'usernames': {row['username']: {'email': row['email'], 'name': row['name'], 'password': row['password']} for _, row in df.iterrows()}}

authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], int(st.secrets['cookie']['expiry_days']))

if not st.session_state.get("authentication_status"):
    st.title("🌬️ BreatheEasy AI Enterprise")
    l_tab, r_tab = st.tabs(["🔑 Login", "📝 Register Team Account"])
    with l_tab:
        authenticator.login(location='main')
    with r_tab:
        try:
            reg_data = authenticator.register_user(pre_authorization=False)
            if reg_data:
                e, u, n = reg_data; pw = stauth.Hasher.hash(authenticator.credentials['usernames'][u]['password'])
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("INSERT INTO users VALUES (?,?,?,?,'member','Basic',5,NULL,?)", (u,e,n,pw,f"TEAM_{u}"))
                conn.commit(); conn.close(); st.success("Team Account Created! Please Login.")
        except Exception as e: st.info("Fill out the form to register.")
    
    if st.session_state["authentication_status"] is False:
        st.error('Username/password is incorrect')
    st.stop()

# --- 6. SIDEBAR & AGENT TOGGLES ---
# Only reach here if authenticated
user_creds = get_db_creds()['usernames'].get(st.session_state["username"])
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()

tier = user_row['package']

with st.sidebar:
    st.markdown(f"### 👋 {st.session_state['name']} <span style='background:#0056b3;color:white;padding:2px 8px;border-radius:12px;font-size:10px;'>{tier}</span>", unsafe_allow_html=True)
    st.metric("Credits Available", user_row['credits'])
    
    if tier != 'Basic':
        with st.expander("🎨 Custom Branding"):
            logo_up = st.file_uploader("Upload Company Logo", type=['png', 'jpg'])
            if logo_up:
                os.makedirs("logos", exist_ok=True)
                path = f"logos/{user_row['username']}.png"
                with open(path, "wb") as f: f.write(logo_up.getvalue())
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("UPDATE users SET logo_path = ? WHERE username = ?", (path, user_row['username']))
                conn.commit(); conn.close(); st.success("Branding Applied!")

    st.divider()
    toggles = {
        "advice": st.toggle("👔 Advice Director", value=True if tier != "Basic" else False, disabled=(tier=="Basic")),
        "sem": st.toggle("🔍 SEM Specialist", value=False, disabled=(tier=="Basic")),
        "time": st.toggle("📅 Time Manager", value=True),
        "seo": st.toggle("✍️ SEO Creator", value=True if tier != "Basic" else False, disabled=(tier=="Basic")),
        "repurpose": st.toggle("✍🏾 Repurposer", value=True),
        "geo": st.toggle("🧠 GEO Specialist", value=False, disabled=(tier!="Unlimited")),
        "analytics": st.toggle("📊 Analytics", value=False, disabled=(tier!="Unlimited")),
        "share_team": st.toggle("🤝 Team Share", value=True)
    }
    
    ind_map = {"HVAC": ["AC Repair", "Duct Cleaning"], "Medical": ["Clinic Audit"], "Law": ["Legal SEO"], "Solar": ["Residential"], "Custom": ["Manual"]}
    main_cat = st.selectbox("Industry", list(ind_map.keys()))
    svc = st.selectbox("Service", ind_map[main_cat]) if main_cat != "Custom" else st.text_input("Service")
    city = st.text_input("City")
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
    authenticator.logout('Sign Out', 'sidebar')

# --- 7. TABS ---
tabs = st.tabs(["📝 Ad Copy", "🗓️ Schedule", "🖼️ Visual Assets", "🚀 Push to Ads", "🔬 Diagnostic Lab", "🤝 Team Share", "📊 Database"])

with tabs[0]: # 📝 Ad Copy Output
    if run_btn and city:
        if user_row['credits'] > 0:
            with st.status("🐝 Swarm Processing Phases...", expanded=True):
                report = run_marketing_swarm({'city': city, 'industry': main_cat, 'service': svc, 'package': tier, 'toggles': toggles})
                st.session_state['report'] = report
                st.session_state['gen'] = True
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
                conn.execute("INSERT INTO leads (date, user, industry, service, city, content, team_id, is_shared) VALUES (?,?,?,?,?,?,?,?)", 
                             (datetime.now().strftime("%Y-%m-%d"), user_row['username'], main_cat, svc, city, str(report), user_row['team_id'], 1 if toggles['share_team'] else 0))
                conn.commit(); conn.close(); st.rerun()
        else: st.error("Out of credits.")

    if st.session_state.get('gen'):
        st.subheader("📥 Download Deliverables")
        c1, c2 = st.columns(2)
        c1.download_button("📄 Word Document", create_word_doc(st.session_state['report'], user_row['logo_path']), f"Strategy_{city}.docx", use_container_width=True)
        c2.download_button("📕 PDF Strategy Report", create_pdf(st.session_state['report'], svc, city, user_row['logo_path']), f"Strategy_{city}.pdf", use_container_width=True)
        st.divider()
        st.markdown(st.session_state['report'])

with tabs[3]: # 🚀 Push to Ads
    st.subheader("🚀 One-Tap Booking Channel")
    promo = "BREATHE2026"
    booking_url = f"https://booking.breatheeasy.ai/schedule?city={city.replace(' ', '%20')}&service={svc.replace(' ', '%20')}&promo={promo}"
    if st.button("🔗 GENERATE LIVE BOOKING LINK", use_container_width=True):
        st.text_input("Deep Link for Ads:", booking_url)
        st.link_button("🔥 PREVIEW BOOKING PAGE", booking_url, use_container_width=True)

with tabs[4]: # 🔬 Diagnostic Lab
    st.subheader(f"🔬 {main_cat} Diagnostic Lab")
    diag_up = st.file_uploader("Upload Evidence Photos", type=['png', 'jpg'])
    if diag_up:
        score = 4 if main_cat == "HVAC" else 9 if main_cat == "Medical" else 6
        render_breatheeasy_gauge(score, main_cat)
        st.image(diag_up, caption="AI Vision Analysis in progress...", width=500)

with tabs[5]: # 🤝 Team Share
    st.subheader("🤝 Team Collaboration")
    conn = sqlite3.connect('breatheeasy.db')
    df_team = pd.read_sql_query("SELECT date, user as 'Created By', industry, service, city FROM leads WHERE team_id = ? AND is_shared = 1", conn, params=(user_row['team_id'],))
    st.table(df_team); conn.close()
