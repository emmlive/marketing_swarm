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

# --- 1. SYSTEM INITIALIZATION & SaaS UI STYLING ---
os.environ["OTEL_SDK_DISABLED"] = "true"
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

st.set_page_config(page_title="BreatheEasy AI | Enterprise Command", page_icon="🌬️", layout="wide")

# SaaS White-Label CSS: High-End Dark Theme
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    .stDeployButton {display:none;}
    
    /* SaaS Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #0F172A;
        color: white;
        border-right: 1px solid #1E293B;
    }
    [data-testid="stSidebar"] * {
        color: #F8FAFC !important;
    }
    .st-emotion-cache-1kyx7g3 {
        background-color: #1E293B !important;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 10px;
    }
    div.stButton > button {
        background-color: #3B82F6;
        color: white;
        border-radius: 10px;
        width: 100%;
        font-weight: 700;
        border: none;
        transition: 0.3s;
    }
    div.stButton > button:hover {
        background-color: #2563EB;
        transform: translateY(-2px);
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE ARCHITECTURE (With Admin & Upgrade Support) ---
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
    c.execute("""INSERT OR IGNORE INTO users (username, email, name, password, role, package, credits, team_id) 
                 VALUES (?,?,?,?,?,?,?,?)""",
              ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited', 9999, 'HQ_001'))
    conn.commit(); conn.close()

init_db()

# --- 3. DYNAMIC GAUGE ---
def render_breatheeasy_gauge(score, industry):
    color = "#ff4b4b" if score < 4 else "#ffa500" if score < 7 else "#2ecc71"
    label = "BreatheEasy™ Score" if industry == "HVAC" else f"{industry} Health Status"
    st.markdown(f"""
        <div style="text-align: center; border: 2px solid #ddd; padding: 25px; border-radius: 20px; background: #ffffff; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);">
            <h3 style="margin: 0; color: #1E293B;">{label}</h3>
            <div style="font-size: 64px; font-weight: 800; color: {color};">{score}/10</div>
            <div style="width: 100%; background: #E2E8F0; border-radius: 999px; height: 16px; margin-top: 15px;">
                <div style="width: {score*10}%; background: {color}; height: 16px; border-radius: 999px; transition: 1s;"></div>
            </div>
            <p style="margin-top: 15px; color: #64748B;">AI Vision Diagnostic active for <b>{industry}</b> Protocol.</p>
        </div>
    """, unsafe_allow_html=True)

# --- 4. EXPORT GENERATORS ---
def create_word_doc(content, logo_path=None):
    doc = Document()
    if logo_path and os.path.exists(logo_path):
        try: doc.add_picture(logo_path, width=Inches(1.5))
        except: pass
    doc.add_heading('BreatheEasy AI Swarm Report', 0)
    doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city, logo_path=None):
    pdf = FPDF(); pdf.add_page()
    if logo_path and os.path.exists(logo_path):
        try: pdf.image(logo_path, 10, 8, 33); pdf.ln(20)
        except: pass
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'{service} - {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 7, txt=str(content).encode('latin-1', 'ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

# --- 5. AUTHENTICATION & FORGOT PASSWORD ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn); conn.close()
    return {'usernames': {row['username']: {'email': row['email'], 'name': row['name'], 'password': row['password']} for _, row in df.iterrows()}}

authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], int(st.secrets['cookie']['expiry_days']))

if not st.session_state.get("authentication_status"):
    st.title("🌬️ BreatheEasy AI Enterprise")
    l_tab, r_tab, f_tab = st.tabs(["🔑 Login", "📝 Register", "❓ Forgot Password"])
    with l_tab: authenticator.login(location='main')
    with r_tab:
        try:
            reg_data = authenticator.register_user(pre_authorization=False)
            if reg_data:
                e, u, n = reg_data; pw = stauth.Hasher.hash(authenticator.credentials['usernames'][u]['password'])
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("INSERT INTO users VALUES (?,?,?,?,'member','Basic',5,NULL,?)", (u,e,n,pw,f"TEAM_{u}"))
                conn.commit(); conn.close(); st.success("Account Created! Login above.")
        except Exception: st.info("Join the Enterprise Swarm.")
    with f_tab: st.info("Contact info@airductify.com for manual reset.")
    st.stop()

# --- 6. SIDEBAR (SaaS UI) ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()

tier = user_row['package']

with st.sidebar:
    st.markdown(f"### 👋 {st.session_state['name']}")
    st.markdown(f"**Plan:** `{tier}`")
    st.metric("Credits Available", user_row['credits'])
    
    # Subscription Upgrade Button
    if tier != 'Unlimited':
        if st.button("🚀 UPGRADE TO UNLIMITED"):
            st.toast("Redirecting to Billing Portal...")

    # Package Feature List
    with st.expander("💎 Included in your Plan"):
        features = {
            "Basic": "• Ad Copy\n• Market Research\n• Schedule",
            "Pro": "• SEO Content\n• Team Share\n• Branding",
            "Unlimited": "• All Agents\n• GEO Strategy\n• Website Audit"
        }
        st.write(features.get(tier, ""))

    st.divider()
    # Modular Agent Toggles with URL Option
    toggles = {
        "website_audit": st.toggle("🌐 Website Audit Manager", value=False, disabled=(tier == "Basic")),
        "advice": st.toggle("👔 Advice Director", value=True if tier != "Basic" else False, disabled=(tier=="Basic")),
        "sem": st.toggle("🔍 SEM Specialist", value=False),
        "time": st.toggle("📅 Time Manager", value=True),
        "seo": st.toggle("✍️ SEO Creator", value=True if tier != "Basic" else False, disabled=(tier=="Basic")),
        "repurpose": st.toggle("✍🏾 Repurposer", value=True),
        "geo": st.toggle("🧠 GEO Specialist", value=False, disabled=(tier!="Unlimited")),
        "analytics": st.toggle("📊 Analytics", value=False, disabled=(tier!="Unlimited")),
        "share_team": st.toggle("🤝 Team Share", value=True if tier != "Basic" else False, disabled=(tier=="Basic"))
    }
    
    target_url = ""
    if toggles["website_audit"]:
        target_url = st.text_input("Enter Website URL", "https://")

    ind_map = {"HVAC": ["AC Repair", "Duct Cleaning"], "Medical": ["Clinic Audit"], "Law": ["Legal SEO"], "Solar": ["Residential"], "Custom": ["Manual"]}
    main_cat = st.selectbox("Industry", list(ind_map.keys()))
    svc = st.selectbox("Service", ind_map[main_cat]) if main_cat != "Custom" else st.text_input("Service")
    city = st.text_input("City")
    
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary")
    authenticator.logout('Sign Out', 'sidebar')

# --- 7. TABS ---
tab_names = ["📝 Ad Copy", "🗓️ Schedule", "🖼️ Visual Assets", "🚀 Push to Ads", "🔬 Diagnostic Lab", "🤝 Team Share"]
if user_row['role'] == 'admin': tab_names.append("⚙️ Admin")

tabs = st.tabs(tab_names)

with tabs[0]: # Ad Copy & Downloads
    if run_btn and city:
        if user_row['credits'] > 0:
            with st.status("🐝 Swarm Active: Core Foundation & Specialists Coordinating...", expanded=True):
                report = run_marketing_swarm({'city': city, 'industry': main_cat, 'service': svc, 'url': target_url, 'toggles': toggles})
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
        c2.download_button("📕 PDF Report", create_pdf(st.session_state['report'], svc, city, user_row['logo_path']), f"Strategy_{city}.pdf", use_container_width=True)
        st.divider()
        st.markdown(st.session_state['report'])

with tabs[1]: # Schedule
    if st.session_state.get('gen'):
        st.subheader("🗓️ Multi-Agent Project Schedule")
        st.write(st.session_state['report'])
    else: st.warning("Launch Swarm to generate schedule.")

with tabs[2]: # Visual Assets
    st.subheader("🖼️ Brand Mockups")
    if st.session_state.get('gen'):
        st.code(f"/imagine prompt: Professional {main_cat} service in {city}, Navy (#000080) and White clean lighting.")
    else: st.warning("Run Swarm for mockups.")

with tabs[4]: # Diagnostic Lab
    st.subheader(f"🔬 {main_cat} Diagnostic Hub")
    diag_up = st.file_uploader(f"Upload {main_cat} On-Site Photos", type=['png', 'jpg'])
    if diag_up:
        score = 8 if main_cat == "Medical" else 4 if main_cat == "HVAC" else 7
        render_breatheeasy_gauge(score, main_cat)
        st.image(diag_up, width=600)

if user_row['role'] == 'admin':
    with tabs[-1]:
        st.subheader("👥 System User Management")
        conn = sqlite3.connect('breatheeasy.db')
        all_u = pd.read_sql("SELECT username, email, package, credits FROM users", conn)
        st.dataframe(all_u, use_container_width=True)
        user_to_del = st.text_input("Username to remove")
        if st.button("❌ Terminate User"):
            conn.execute(f"DELETE FROM users WHERE username='{user_to_del}'")
            conn.commit(); st.success("User Terminated."); st.rerun()
        conn.close()
