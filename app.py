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

# --- 1. THEME ENGINE & SYSTEM INITIALIZATION ---
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

os.environ["OTEL_SDK_DISABLED"] = "true"
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

st.set_page_config(page_title="BreatheEasy AI | Enterprise Swarm", page_icon="🌬️", layout="wide")

# SaaS Dynamic Styling logic
if st.session_state.theme == 'dark':
    bg, text, side, card, btn = "#0F172A", "#F8FAFC", "#1E293B", "#334155", "#3B82F6"
else:
    bg, text, side, card, btn = "#F8FAFC", "#0F172A", "#E2E8F0", "#FFFFFF", "#2563EB"

st.markdown(f"""
    <style>
    #MainMenu, footer, header {{visibility: hidden;}}
    .stDeployButton {{display:none;}}
    [data-testid="stSidebar"] {{ background-color: {bg}; color: {text}; border-right: 1px solid {card}; }}
    [data-testid="stSidebar"] * {{ color: {text} !important; }}
    .st-emotion-cache-1kyx7g3 {{ background-color: {side} !important; border-radius: 12px; padding: 20px; }}
    div.stButton > button {{ background-color: {btn}; color: white; border-radius: 10px; font-weight: 700; width: 100%; border: none; }}
    div.stButton > button:hover {{ opacity: 0.9; transform: translateY(-1px); }}
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE ARCHITECTURE ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    # 1. username, 2. email, 3. name, 4. password, 5. role, 
    # 6. package, 7. credits, 8. logo_path, 9. team_id (Total 9 columns)
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, 
                  package TEXT, credits INTEGER DEFAULT 0, logo_path TEXT, team_id TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, 
                  service TEXT, city TEXT, content TEXT, team_id TEXT, is_shared INTEGER DEFAULT 0, score INTEGER)''')
    
    hashed_pw = stauth.Hasher.hash('admin123')
    
    # FIX: Added the 9th value (None) for logo_path before 'HQ_001'
    c.execute("""INSERT OR IGNORE INTO users VALUES (?,?,?,?,?,?,?,?,?)""",
              ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited', 9999, None, 'HQ_001'))
    
    conn.commit()
    conn.close()

# --- 3. EXPORT GENERATORS ---
def create_word_doc(content, logo_path=None):
    doc = Document()
    if logo_path and os.path.exists(logo_path):
        try: doc.add_picture(logo_path, width=Inches(1.5))
        except: pass
    doc.add_heading('BreatheEasy AI Strategy Report', 0)
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

# --- 4. UI COMPONENTS ---
def render_breatheeasy_gauge(score, industry):
    color = "#ff4b4b" if score < 4 else "#ffa500" if score < 7 else "#2ecc71"
    label = f"{industry} Health Status" if industry != "HVAC" else "BreatheEasy™ Score"
    st.markdown(f"""
        <div style="text-align: center; border: 2px solid #ddd; padding: 25px; border-radius: 20px; background: #ffffff; color: #1E293B;">
            <h3 style="margin: 0;">{label}</h3>
            <div style="font-size: 64px; font-weight: 800; color: {color};">{score}/10</div>
            <div style="width: 100%; background: #E2E8F0; border-radius: 999px; height: 16px; margin-top: 15px;">
                <div style="width: {score*10}%; background: {color}; height: 16px; border-radius: 999px;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- 5. AUTHENTICATION & SaaS REGISTRATION ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn); conn.close()
    return {'usernames': {row['username']: {k: row[k] for k in row.index} for _, row in df.iterrows()}}

authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

if not st.session_state.get("authentication_status"):
    st.title("🌬️ BreatheEasy AI Enterprise Swarm")
    l_tab, r_tab, f_tab = st.tabs(["🔑 Login", "📝 Register & Choose Plan", "❓ Forgot Password"])
    with l_tab: authenticator.login(location='main')
    with r_tab:
        plan = st.selectbox("Select Subscription Tier", ["Basic (5 Credits)", "Pro (50 Credits)", "Unlimited (Full Swarm)"])
        res = authenticator.register_user(pre_authorization=False)
        if res:
            e, u, n = res; pw = stauth.Hasher.hash(authenticator.credentials['usernames'][u]['password'])
            creds = 5 if "Basic" in plan else 50 if "Pro" in plan else 9999
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("INSERT INTO users VALUES (?,?,?,?,'member',?,?,?,?)", (u, e, n, pw, plan.split()[0], creds, None, f"TEAM_{u}"))
            conn.commit(); conn.close(); st.success("Registered! Login to begin.")
    with f_tab: st.info("Manual Reset: Contact support@airductify.com")
    st.stop()

# --- 6. SIDEBAR: RICH DASHBOARD ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()

with st.sidebar:
    st.button("🌓 Switch Theme", on_click=toggle_theme)
    st.markdown(f"### 👋 {st.session_state['name']} (`{user_row['package']}`)")
    st.metric("Credits Available", user_row['credits'])
    
    st.divider()
    biz_name = st.text_input("Business Name")
    biz_usp = st.text_area("Unique Selling Proposition (USP)")
    
    st.divider()
    toggles = {
        "audit": st.toggle("🌐 Website Audit Manager", value=True),
        "advice": st.toggle("👔 Advice Director", value=True),
        "sem": st.toggle("🔍 SEM Specialist"),
        "seo": st.toggle("✍️ SEO Creator"),
        "repurpose": st.toggle("✍🏾 Content Repurposer"),
        "geo": st.toggle("🧠 GEO Specialist", disabled=(user_row['package']=="Basic")),
        "analytics": st.toggle("📊 Analytics Specialist")
    }
    
    web_url = st.text_input("Website URL") if toggles["audit"] else ""
    ind = st.selectbox("Industry", ["HVAC", "Medical", "Law", "Solar", "Real Estate"])
    svc = st.text_input("Service Type")
    city = st.text_input("Target City")
    
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary")
    authenticator.logout('Sign Out', 'sidebar')

# --- 7. TABS: FULL DASHBOARD ---
hub_name = f"🔬 {ind} Diagnostic Hub" if ind else "🔬 Diagnostic Lab"
tabs = st.tabs(["📝 Ad Copy", "🗓️ User Schedule", "🖼️ Visual Assets", hub_name, "🤝 Team Share", "⚙️ Admin"])

with tabs[0]: # Ad Copy & Strategic Logic
    if run_btn and city:
        if user_row['credits'] > 0 and biz_name:
            with st.status("🐝 Swarm Processing: Managers, Analysts & Creatives active...", expanded=True):
                report = run_marketing_swarm({'city': city, 'industry': ind, 'service': svc, 'biz_name': biz_name, 'usp': biz_usp, 'url': web_url, 'toggles': toggles})
                st.session_state['report'] = report
                st.session_state['gen'] = True
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
                conn.execute("INSERT INTO leads (date, user, industry, service, city, content, team_id, is_shared) VALUES (?,?,?,?,?,?,?,?)", 
                             (datetime.now().strftime("%Y-%m-%d"), user_row['username'], ind, svc, city, str(report), user_row['team_id'], 1))
                conn.commit(); conn.close(); st.rerun()
        elif not biz_name: st.error("Business Name required.")

    if st.session_state.get('gen'):
        st.subheader("📥 Export Strategy")
        c1, c2 = st.columns(2)
        c1.download_button("📄 Word Document", create_word_doc(st.session_state['report'], user_row['logo_path']), f"Report_{city}.docx", use_container_width=True)
        c2.download_button("📕 PDF Report", create_pdf(st.session_state['report'], svc, city, user_row['logo_path']), f"Report_{city}.pdf", use_container_width=True)
        st.markdown(st.session_state['report'])

with tabs[1]: # User Schedule
    st.subheader("🗓️ Your 30-Day Project Roadmap")
    if st.session_state.get('gen'):
        st.info("Dynamic Level-of-Effort schedule based on Swarm results.")
        st.write(st.session_state['report'])

with tabs[3]: # Dynamic Diagnostic Hub
    st.subheader(f"🛡️ {ind} Safety & Quality Evidence Audit")
    diag_up = st.file_uploader(f"Upload {ind} Field Evidence", type=['png', 'jpg'])
    if diag_up:
        score = 8 if ind == "Medical" else 4 if ind == "HVAC" else 7
        render_breatheeasy_gauge(score, ind)
        if st.button("💾 SAVE SCORE TO DATABASE"):
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE leads SET score = ? WHERE user = ? ORDER BY id DESC LIMIT 1", (score, st.session_state['username']))
            conn.commit(); conn.close(); st.success("Score Saved!")

if user_row['role'] == 'admin':
    with tabs[-1]:
        st.subheader("👥 User & Credit Administration")
        conn = sqlite3.connect('breatheeasy.db')
        all_u = pd.read_sql("SELECT username, email, package, credits FROM users", conn)
        st.dataframe(all_u, use_container_width=True)
        user_to_del = st.text_input("Username to Terminate")
        if st.button("❌ Remove User"):
            conn.execute(f"DELETE FROM users WHERE username='{user_to_del}'")
            conn.commit(); st.rerun()
        conn.close()
