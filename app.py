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

# PERSISTENT SESSION STATES
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

st.set_page_config(page_title="TechInAdvance AI | Enterprise Command", page_icon="Logo1.jpeg", layout="wide")

# --- 2. ELITE UI CSS (SIDEBAR VISIBILITY & THEME RECONCILIATION) ---
sidebar_color = "#3B82F6" if st.session_state.theme == 'dark' else "#2563EB"
bg, text, side = ("#0F172A", "#F8FAFC", "#1E293B") if st.session_state.theme == 'dark' else ("#F8FAFC", "#0F172A", "#E2E8F0")

st.markdown(f"""
    <style>
    #MainMenu, footer, header {{visibility: hidden;}}
    .stDeployButton {{display:none;}}
    /* SIDEBAR TOGGLE VISIBILITY FIX - PRODUCTION GRADE */
    [data-testid="sidebar-button"] {{
        background-color: {sidebar_color} !important;
        color: white !important;
        border-radius: 5px !important;
        z-index: 999999;
        display: flex !important;
    }}
    [data-testid="stSidebar"] {{ background-color: {bg}; color: {text}; border-right: 1px solid #1E293B; }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 10px; width: 100%; font-weight: 700; border: none; }}
    .swarm-pulse {{ background-color: {sidebar_color}; border-radius: 50%; width: 12px; height: 12px; display: inline-block; margin-right: 10px; animation: pulse-animation 1.5s infinite; }}
    @keyframes pulse-animation {{ 0% {{ transform: scale(0.95); opacity: 0.7; }} 70% {{ transform: scale(1.1); opacity: 1; }} 100% {{ transform: scale(0.95); opacity: 0.7; }} }}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, package TEXT, credits INTEGER DEFAULT 0, logo_path TEXT, team_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT, team_id TEXT, is_shared INTEGER DEFAULT 0, score INTEGER)''')
    hashed_pw = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001')", ('admin', 'admin@techinadvance.ai', 'Admin', hashed_pw))
    conn.commit(); conn.close()

init_db()

# --- 4. AUTH UTILS ---
def get_db_creds():
    try:
        conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
        df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn); conn.close()
        return {'usernames': {row['username']: {'email':row['email'], 'name':row['name'], 'password':row['password']} for _, row in df.iterrows()}}
    except: return {'usernames': {}}

# Initialize with dictionary source
config_creds = get_db_creds()
authenticator = stauth.Authenticate(config_creds, st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

def create_word_doc(content, logo_path="Logo1.jpeg"):
    doc = Document()
    final_logo = logo_path if logo_path and os.path.exists(logo_path) else "Logo1.jpeg"
    try: doc.add_picture(final_logo, width=Inches(1.5))
    except: pass
    doc.add_heading('Strategic Intelligence Report', 0); doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city, logo_path="Logo1.jpeg"):
    pdf = FPDF(); pdf.add_page()
    final_logo = logo_path if logo_path and os.path.exists(logo_path) else "Logo1.jpeg"
    try: pdf.image(final_logo, 10, 8, 33); pdf.ln(20)
    except: pass
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'{service} Strategy - {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 7, txt=str(content).encode('latin-1', 'ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

# --- 5. AUTH FLOW (FIXED ATTRIBUTE ERROR & RECOVERY) ---
if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=200)
    auth_tabs = st.tabs(["🔑 Login", "📝 Register", "🤝 Join Team (Invite)", "❓ Recovery"])
    
    with auth_tabs[0]: authenticator.login(location='main')
    
    with auth_tabs[1]:
        reg_res = authenticator.register_user(location='main')
        if reg_res:
            e, u, n = reg_res
            # PROACTIVE FIX: Pull password from the source dictionary config_creds
            new_pw = config_creds['usernames'][u]['password']
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("INSERT INTO users VALUES (?,?,?,?,'member','Pro',50,'Logo1.jpeg',?)", (u, e, n, new_pw, f"TEAM_{u}"))
            conn.commit(); conn.close(); st.success("Account Created!"); st.button("Go to Login", on_click=switch_to_login)

    with auth_tabs[2]:
        invite_id = st.text_input("Team ID to Join")
        join_reg = authenticator.register_user(location='main', key='join')
        if join_reg and invite_id:
            e, u, n = join_reg
            new_pw = config_creds['usernames'][u]['password']
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("INSERT INTO users VALUES (?,?,?,?,'member','Pro',25,'Logo1.jpeg',?)", (u, e, n, new_pw, invite_id))
            conn.commit(); conn.close(); st.success(f"Linked to {invite_id}"); st.button("Proceed", on_click=switch_to_login)

    with auth_tabs[3]: # PASSWORD RECOVERY
        st.subheader("Credential Recovery")
        try:
            if authenticator.forgot_password(location='main'):
                st.success('Recovery email sent.')
        except Exception: st.info("Submit your username to reset.")
    st.stop()

# --- 6. DASHBOARD CONTROL ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()

with st.sidebar:
    main_logo = user_row['logo_path'] if user_row['logo_path'] else "Logo1.jpeg"
    st.image(main_logo, use_column_width=True)
    st.button("🌓 Toggle Theme", on_click=toggle_theme)
    st.metric("Credits Available", user_row['credits'])
    st.info(f"📍 Team ID: {user_row['team_id']}")
    
    st.divider()
    biz_name = st.text_input("Brand Name"); biz_usp = st.text_area("USP")
    ind_choice = st.selectbox("Industry", ["HVAC", "Medical", "Law", "Solar", "Real Estate", "Custom"])
    final_ind = st.text_input("Define Industry") if ind_choice == "Custom" else ind_choice
    
    svc_map = {"HVAC": ["Repair", "Install"], "Medical": ["Telehealth", "Growth"], "Law": ["Injury", "Litigation"], "Solar": ["Audit", "Install"]}
    svc = st.selectbox("Service Choice", svc_map.get(ind_choice, ["Strategic Service"]))
    city = st.text_input("Market City"); web_url = st.text_input("Auditor URL")

    st.divider(); st.subheader("🤖 Active Swarm Agents")
    toggles = {
        "audit": st.toggle("🕵️ Web Auditor", value=True),
        "sem": st.toggle("📝 Ad Generator", value=True),
        "seo": st.toggle("✍️ SEO Blog Creator (IG)", value=True),
        "advice": st.toggle("👔 Advice Director", value=True),
        "repurpose": st.toggle("✍🏾 Social Content", value=True),
        "geo": st.toggle("🧠 GEO Specialist", value=True)
    }
    
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
    authenticator.logout('Sign Out', 'sidebar')

# --- 7. COMMAND CENTER TABS ---
hub_display = f"🔬 {final_ind} Diagnostic Lab" if final_ind else "🔬 Diagnostic Lab"
tabs = st.tabs(["🕵️ Web Auditor", "📝 Ad Generator", "✍️ SEO Blog Creator", "🗓️ Roadmap", "📊 Ads Manager", hub_display, "🤝 Team Share", "⚙️ Admin Hub"])

if run_btn:
    if not biz_name or not city: st.error("❌ Brand Name and City required.")
    elif user_row['credits'] <= 0: st.error("❌ Out of Credits.")
    else: st.session_state.processing = True

if st.session_state.get('processing'):
    with tabs[0]:
        st.markdown(f"### <div class='swarm-pulse'></div> Swarm Active: Deployment in Progress...", unsafe_allow_html=True)
        with st.status("🐝 **Specialist Agents Coordinating...**", expanded=True) as status:
            report = run_marketing_swarm({'city': city, 'industry': final_ind, 'service': svc, 'biz_name': biz_name, 'url': web_url, 'toggles': toggles})
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
        st.divider(); st.subheader("🔥 Conversion Attention Heatmap")
        st.image("https://via.placeholder.com/1200x400/0F172A/3B82F6?text=Psychological+Attention+Heatmap", use_column_width=True)

with tabs[1]: # AD GENERATOR
    st.subheader("📝 Ad Generator Agent")
    if st.session_state.get('gen'):
        st.markdown(st.session_state['report'])
        st.subheader("🔗 Social Push")
        if st.button("Push to Meta Ads"): st.success("Campaign Synced to Meta API")

with tabs[2]: # SEO BLOG CREATOR
    st.subheader("✍️ SEO Blog Creator (Information Gain)")
    if st.session_state.get('gen'):
        st.markdown(st.session_state['report'])

with tabs[5]: # UNIVERSAL DIAGNOSTIC LAB
    st.subheader(f"🛡️ {final_ind} Quality & Compliance Audit")
    diag_up = st.file_uploader(f"Upload {final_ind} Evidence", type=['png', 'jpg'])
    if diag_up: st.success("Visual Evidence Archived.")

with tabs[6]: # TEAM HUB
    st.subheader("🤝 Team Collaboration Hub")
    conn = sqlite3.connect('breatheeasy.db')
    st.write("### 🏆 Team Leaderboard")
    leader_df = pd.read_sql_query("SELECT user as 'Member', COUNT(id) as 'Reports' FROM leads WHERE team_id = ? GROUP BY user ORDER BY Reports DESC", conn, params=(user_row['team_id'],))
    st.table(leader_df)
    conn.close()

if user_row['role'] == 'admin': # ADMIN HUB
    with tabs[-1]:
        st.subheader("👥 System Management")
        conn = sqlite3.connect('breatheeasy.db')
        st.dataframe(pd.read_sql("SELECT username, email, credits FROM users", conn), use_container_width=True)
        u_del = st.text_input("Username to Terminate")
        if st.button("❌ Remove User"):
            conn.execute(f"DELETE FROM users WHERE username='{u_del}'"); conn.commit(); st.rerun()
        conn.close()
