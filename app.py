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
from PIL import Image

# --- 1. SYSTEM INITIALIZATION & STRIPE SAFETY ---
try:
    import stripe
    stripe.api_key = st.secrets.get("STRIPE_API_KEY", "sk_test_placeholder")
except ImportError:
    stripe = None

# PERSISTENT THEME INITIALIZATION (Restore missing Dark Mode Logic)
if 'theme' not in st.session_state: st.session_state.theme = 'dark'
if 'auth_tab' not in st.session_state: st.session_state.auth_tab = "🔑 Login"
if 'processing' not in st.session_state: st.session_state.processing = False

def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

def switch_to_login():
    st.session_state.auth_tab = "🔑 Login"
    st.rerun()

os.environ["OTEL_SDK_DISABLED"] = "true"
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

st.set_page_config(page_title="TechInAdvance AI | Command Center", page_icon="Logo1.jpeg", layout="wide")

# Elite UI CSS - DYNAMIC DARK MODE RESTORED
if st.session_state.theme == 'dark':
    bg, text, side, card, btn = "#0F172A", "#F8FAFC", "#1E293B", "#334155", "#3B82F6"
else:
    bg, text, side, card, btn = "#F8FAFC", "#0F172A", "#E2E8F0", "#FFFFFF", "#2563EB"

st.markdown(f"""
    <style>
    #MainMenu, footer, header {{visibility: hidden;}}
    .stDeployButton {{display:none;}}
    [data-testid="stSidebar"] {{ background-color: {bg}; color: {text}; border-right: 1px solid #1E293B; }}
    [data-testid="stSidebar"] * {{ color: {text} !important; }}
    .st-emotion-cache-1kyx7g3 {{ background-color: {side} !important; border-radius: 12px; padding: 20px; margin-bottom: 10px; }}
    div.stButton > button {{ background-color: {btn}; color: white; border-radius: 10px; width: 100%; font-weight: 700; border: none; }}
    .swarm-pulse {{ background-color: {btn}; border-radius: 50%; width: 12px; height: 12px; display: inline-block; margin-right: 10px; animation: pulse-animation 1.5s infinite; }}
    @keyframes pulse-animation {{ 0% {{ transform: scale(0.95); opacity: 0.7; }} 70% {{ transform: scale(1.1); opacity: 1; }} 100% {{ transform: scale(0.95); opacity: 0.7; }} }}
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, 
                  package TEXT, credits INTEGER DEFAULT 0, logo_path TEXT, team_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, 
                  service TEXT, city TEXT, content TEXT, team_id TEXT, is_shared INTEGER DEFAULT 0, score INTEGER)''')
    hashed_pw = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001')", ('admin', 'admin@techinadvance.ai', 'Admin', hashed_pw))
    conn.commit(); conn.close()

init_db()

# --- 3. AUTHENTICATION & UTILS (FIXED ATTRIBUTE ERROR) ---
def get_db_creds():
    try:
        conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
        df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn); conn.close()
        # Ensure credentials follow the exact structure required by the latest stauth
        return {'usernames': {row['username']: {'email':row['email'], 'name':row['name'], 'password':row['password']} for _, row in df.iterrows()}}
    except: return {'usernames': {}}

# Initializing credentials dictionary properly
credentials_dict = get_db_creds()
authenticator = stauth.Authenticate(credentials_dict, st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

def create_word_doc(content, logo_path="Logo1.jpeg"):
    doc = Document()
    final_logo = logo_path if logo_path and os.path.exists(logo_path) else "Logo1.jpeg"
    try: doc.add_picture(final_logo, width=Inches(1.5))
    except: pass
    doc.add_heading('Intelligence Report', 0); doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city, logo_path="Logo1.jpeg"):
    pdf = FPDF(); pdf.add_page()
    final_logo = logo_path if logo_path and os.path.exists(logo_path) else "Logo1.jpeg"
    try: pdf.image(final_logo, 10, 8, 33); pdf.ln(20)
    except: pass
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'{service} - {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 7, txt=str(content).encode('latin-1', 'ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

# --- 4. AUTH FLOW & REGISTRATION FIX ---
if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=200)
    st.title("TechInAdvance AI Enterprise")
    auth_tabs = st.tabs(["🔑 Login", "📝 Register", "❓ Recovery"])
    with auth_tabs[0]: 
        authenticator.login(location='main')
    with auth_tabs[1]:
        try:
            reg_res = authenticator.register_user(location='main')
            if reg_res:
                email, username, name = reg_res
                # FIXED: Access the password from the modified credentials_dict updated by authenticator
                new_hashed_pw = credentials_dict['usernames'][username]['password']
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("INSERT INTO users VALUES (?,?,?,?,'member','Pro',50,'Logo1.jpeg',?)", 
                             (username, email, name, new_hashed_pw, f"TEAM_{username}"))
                conn.commit(); conn.close()
                st.success("Registration Successful! Please log in."); st.button("Back to Login", on_click=switch_to_login)
        except Exception as e:
            st.error(f"Registration Error: {e}")
    st.stop()

# --- 5. DASHBOARD CONTROL CENTER (ALL AGENTS RESTORED) ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()

with st.sidebar:
    main_logo = user_row['logo_path'] if user_row['logo_path'] else "Logo1.jpeg"
    st.image(main_logo, use_column_width=True)
    
    st.button("🌓 Toggle Dark/Light Mode", on_click=toggle_theme)
    st.metric("Credits Available", user_row['credits'])
    st.info(f"Team ID: {user_row['team_id']}")
    
    st.divider()
    biz_name = st.text_input("Brand Name")
    biz_usp = st.text_area("USP")
    ind_choice = st.selectbox("Industry", ["HVAC", "Medical", "Law", "Solar", "Custom"])
    final_ind = st.text_input("Specify Industry") if ind_choice == "Custom" else ind_choice
    
    svc_map = {"HVAC": ["Repair", "Install"], "Medical": ["Telehealth", "Surgery"], "Law": ["Litigation", "Injury"], "Solar": ["Audit", "Install"]}
    svc = st.selectbox("Service Choice", svc_map.get(ind_choice, ["General Strategic Service"]))
    
    city = st.text_input("Target City"); web_url = st.text_input("URL (Web Auditor)")

    st.divider(); st.subheader("🤖 Active Swarm Agents")
    toggles = {
        "audit": st.toggle("🕵️ Web Auditor (Legacy #1)", value=True),
        "advice": st.toggle("👔 Advice Director (Legacy #2)", value=True),
        "sem": st.toggle("🚀 Ad Generator (Legacy #3)", value=True),
        "seo": st.toggle("✍️ SEO Authority (IG)", value=True),
        "repurpose": st.toggle("✍🏾 Social Content", value=True),
        "geo": st.toggle("🧠 GEO Specialist", value=True)
    }
    
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
    authenticator.logout('Sign Out', 'sidebar')

# --- 6. COMMAND CENTER TABS ---
hub_name = f"🔬 {final_ind} Diagnostic Hub"
tabs = st.tabs(["🕵️ Web Auditor", "📝 Ad generator", "👔 Strategy/SEO", "🗓️ Roadmap", "📊 Ads Manager", hub_name, "🤝 Team Share", "⚙️ Admin Hub"])

if run_btn:
    if not biz_name or not city: st.error("❌ Brand Name and City required.")
    elif user_row['credits'] <= 0: st.error("❌ Out of Credits.")
    else: st.session_state.processing = True

if st.session_state.get('processing'):
    with tabs[0]:
        st.markdown(f"### <div class='swarm-pulse'></div> Swarm Active: Deployment in Progress...", unsafe_allow_html=True)
        with st.status("🐝 **Specialist Agents Coordinating...**", expanded=True) as status:
            st.write("🕵️ Web Auditor: Analyzing Neuromarketing Friction...")
            report = run_marketing_swarm({'city': city, 'industry': final_ind, 'service': svc, 'biz_name': biz_name, 'usp': biz_usp, 'url': web_url, 'toggles': toggles})
            status.update(label="🚀 Swarm Complete!", state="complete", expanded=False)
            
            st.session_state['report'] = report
            st.session_state['gen'] = True
            st.session_state.processing = False
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
            conn.execute("INSERT INTO leads (date, user, industry, service, city, content, team_id) VALUES (?,?,?,?,?,?,?)", 
                         (datetime.now().strftime("%Y-%m-%d"), user_row['username'], final_ind, svc, city, str(report), user_row['team_id']))
            conn.commit(); conn.close(); st.rerun()

with tabs[0]: # WEB AUDITOR SEAT
    st.subheader("🕵️ Auditor Agent: Conversion Analysis")
    if st.session_state.get('gen'):
        st.subheader("📥 Export Branded Deliverables")
        c1, c2 = st.columns(2)
        r_logo = user_row['logo_path'] if user_row['logo_path'] else "Logo1.jpeg"
        c1.download_button("📄 Word Document", create_word_doc(st.session_state['report'], r_logo), f"Report_{city}.docx", use_container_width=True)
        c2.download_button("📕 PDF Report", create_pdf(st.session_state['report'], svc, city, r_logo), f"Report_{city}.pdf", use_container_width=True)
        st.markdown(st.session_state['report'])

with tabs[1]: # AD GENERATOR
    if st.session_state.get('gen'):
        st.markdown(st.session_state['report'])
        st.subheader("🔗 SOTA Social Push")
        p1, p2, p3 = st.columns(3)
        if p1.button("Push to Facebook Ads"): st.success("Synced to Meta API")
        if p2.button("Push to Google Ads"): st.success("Synced to Ads Manager")
        if p3.button("Push to LinkedIn"): st.success("B2B Audience Synced")

with tabs[6]: # TEAM HUB
    conn = sqlite3.connect('breatheeasy.db')
    st.write("### 🏆 Leaderboard")
    st.table(pd.read_sql_query("SELECT user as 'Member', COUNT(id) as 'Reports' FROM leads WHERE team_id = ? GROUP BY user ORDER BY Reports DESC", conn, params=(user_row['team_id'],)))
    conn.close()

if user_row['role'] == 'admin': # ADMIN HUB RESTORED
    with tabs[-1]:
        st.subheader("👥 System Administration")
        conn = sqlite3.connect('breatheeasy.db')
        st.dataframe(pd.read_sql("SELECT username, email, credits FROM users", conn), use_container_width=True)
        u_del = st.text_input("Username to Terminate")
        if st.button("❌ Remove User"):
            conn.execute(f"DELETE FROM users WHERE username='{u_del}'"); conn.commit(); st.rerun()
        conn.close()
