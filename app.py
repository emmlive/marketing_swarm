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

# --- 2. ELITE UI CSS (SIDEBAR & THEME) ---
sidebar_color = "#3B82F6" if st.session_state.theme == 'dark' else "#2563EB"
bg, text, side = ("#0F172A", "#F8FAFC", "#1E293B") if st.session_state.theme == 'dark' else ("#F8FAFC", "#0F172A", "#E2E8F0")

st.markdown(f"""
    <style>
    #MainMenu, footer, header {{visibility: hidden;}}
    .stDeployButton {{display:none;}}
    /* SIDEBAR TOGGLE VISIBILITY FIX */
    [data-testid="sidebar-button"] {{
        background-color: {sidebar_color} !important;
        color: white !important;
        border-radius: 5px !important;
        z-index: 999999;
        display: flex !important;
        box-shadow: 0px 0px 10px rgba(0,0,0,0.5);
    }}
    div.stButton > button {{ 
        background-color: {sidebar_color}; 
        color: white; 
        border-radius: 10px; 
        width: 100%; 
        font-weight: 800 !important; 
        border: none;
        text-transform: uppercase;
    }}
    [data-testid="stSidebar"] {{ background-color: {bg}; color: {text}; border-right: 1px solid #1E293B; }}
    .st-emotion-cache-1kyx7g3 {{ background-color: {side} !important; border-radius: 12px; padding: 20px; }}
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

# Initialize data source
config_creds = get_db_creds()
authenticator = stauth.Authenticate(config_creds, st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

def create_word_doc(content, logo_path="Logo1.jpeg"):
    doc = Document()
    final_logo = logo_path if logo_path and os.path.exists(logo_path) else "Logo1.jpeg"
    try: doc.add_picture(final_logo, width=Inches(1.5))
    except: pass
    doc.add_heading('Strategic Market Intelligence Brief', 0); doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city, logo_path="Logo1.jpeg"):
    pdf = FPDF(); pdf.add_page()
    final_logo = logo_path if logo_path and os.path.exists(logo_path) else "Logo1.jpeg"
    try: pdf.image(final_logo, 10, 8, 33); pdf.ln(20)
    except: pass
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'{service} Strategy - {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 7, txt=str(content).encode('latin-1', 'ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

# --- 5. AUTH FLOW (PERMANENT ATTRIBUTE FIX) ---
if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=200)
    auth_tabs = st.tabs(["🔑 Login", "📝 Register & Plans", "🤝 Join Team (Invite)", "❓ Recovery"])
    
    with auth_tabs[0]: authenticator.login(location='main')
    
    with auth_tabs[1]:
        st.subheader("Elite Subscription Tiers")
        c1, c2, c3 = st.columns(3)
        c1.metric("Basic", "$99/mo", "50 Credits")
        c2.metric("Pro", "$499/mo", "250 Credits")
        c3.metric("Enterprise", "$1999/mo", "Unlimited")
        plan = st.selectbox("Select Tier", ["Basic", "Pro", "Enterprise"])
        reg_res = authenticator.register_user(location='main')
        if reg_res:
            e, u, n = reg_res
            # THE PERMANENT FIX: Access config_creds directly. 
            # The library updates this dict by reference when reg_res is true.
            if u in config_creds['usernames']:
                pw = config_creds['usernames'][u]['password']
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("INSERT INTO users VALUES (?,?,?,?,'member',?,50,'Logo1.jpeg',?)", (u, e, n, pw, plan, f"TEAM_{u}"))
                conn.commit(); conn.close(); st.success("Account Created!"); st.button("Log In Now", on_click=switch_to_login)

    with auth_tabs[2]:
        invite_id = st.text_input("Enter Team ID")
        join_reg = authenticator.register_user(location='main', key='join')
        if join_reg and invite_id:
            e, u, n = join_reg
            if u in config_creds['usernames']:
                pw = config_creds['usernames'][u]['password']
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("INSERT INTO users VALUES (?,?,?,?,'member','Pro',25,'Logo1.jpeg',?)", (u, e, n, pw, invite_id))
                conn.commit(); conn.close(); st.success(f"Linked to {invite_id}!"); st.button("Proceed", on_click=switch_to_login)

    with auth_tabs[3]: authenticator.forgot_password(location='main')
    st.stop()

# --- 6. DASHBOARD CONTROL ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()

with st.sidebar:
    main_logo = user_row['logo_path'] if user_row['logo_path'] else "Logo1.jpeg"
    st.image(main_logo, use_column_width=True)
    st.button("**🌓 TOGGLE THEME**", on_click=toggle_theme)
    st.metric("Credits Available", user_row['credits'])
    st.info(f"📍 Team ID: {user_row['team_id']}")
    
    st.divider()
    biz_name = st.text_input("Brand Name"); biz_usp = st.text_area("Core USP")
    ind_choice = st.selectbox("Industry", ["HVAC", "Medical", "Law", "Solar", "Real Estate", "Custom"])
    final_ind = st.text_input("Define Industry") if ind_choice == "Custom" else ind_choice
    
    svc_map = {"HVAC": ["Repair", "Install"], "Medical": ["Telehealth", "Clinical Audit"], "Law": ["Personal Injury", "Litigation"], "Solar": ["ROI Audit", "Install"], "Real Estate": ["Listing Swarm", "Buyer Lead Gen"]}
    svc = st.selectbox("Specific Service", svc_map.get(ind_choice, ["Strategic Service"]))
    city = st.text_input("Market City"); web_url = st.text_input("Audit URL")

    st.divider(); st.subheader("🤖 Swarm Personnel")
    toggles = {
        "analyst": st.toggle("🕵️ Market Analyst (Researcher)", value=True),
        "builder": st.toggle("🎨 Creative Director (Builder)", value=True),
        "manager": st.toggle("👔 Strategist (Manager)", value=True),
        "social": st.toggle("✍🏾 Social Content Agent", value=True),
        "geo": st.toggle("🧠 GEO Specialist", value=True),
        "audit": st.toggle("🌐 Web Auditor", value=True)
    }
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary")
    authenticator.logout('Sign Out', 'sidebar')

# --- 7. COMMAND CENTER TABS ---
hub_name = f"🔬 {final_ind} Diagnostic Lab" if final_ind else "🔬 Diagnostic Lab"
tabs = st.tabs(["🕵️ Analyst", "🎨 Creative", "👔 Strategist", "✍🏾 Social", "🧠 GEO", "🌐 Auditor", hub_name, "🤝 Team Share", "⚙️ Admin"])

if run_btn:
    if not biz_name or not city: st.error("❌ Mandatory Fields Missing.")
    elif user_row['credits'] <= 0: st.error("❌ Out of Credits.")
    else: st.session_state.processing = True

if st.session_state.get('processing'):
    with tabs[0]:
        st.markdown(f"### <div class='swarm-pulse'></div> Swarm Active...")
        with st.status("🛠️ **Multi-Agent Coordination in Progress...**", expanded=True) as status:
            report = run_marketing_swarm({'city': city, 'industry': final_ind, 'service': svc, 'biz_name': biz_name, 'usp': biz_usp, 'url': web_url, 'toggles': toggles})
            status.update(label="🚀 Swarm Complete!", state="complete")
            st.session_state['report'] = report
            st.session_state['gen'] = True
            st.session_state.processing = False
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
            conn.execute("INSERT INTO leads (date, user, industry, service, city, content, team_id) VALUES (?,?,?,?,?,?,?)", (datetime.now().strftime("%Y-%m-%d"), user_row['username'], final_ind, svc, city, str(report), user_row['team_id']))
            conn.commit(); conn.close(); st.rerun()

# --- 8. SEAT OUTPUT LOGIC ---
def render_seat(idx, title, icon, data_key):
    with tabs[idx]:
        st.subheader(f"{icon} {title} Command Seat")
        if st.session_state.get('gen'):
            agent_data = st.session_state['report'].get(data_key, "Intelligence pending...")
            
            if idx == 0: # Analyst Seat adds Exports
                st.subheader("📥 Export Deliverables")
                c1, c2 = st.columns(2)
                r_logo = user_row['logo_path'] if user_row['logo_path'] else "Logo1.jpeg"
                c1.download_button("📄 Word Document", create_word_doc(agent_data, r_logo), f"Report_{city}.docx", use_container_width=True)
                c2.download_button("📕 PDF Report", create_pdf(agent_data, svc, city, r_logo), f"Report_{city}.pdf", use_container_width=True)
            
            st.markdown(agent_data)
        else: st.info(f"Deploy Swarm to populate {title} intelligence.")

render_seat(0, "Market Analyst", "🕵️", "analyst")
render_seat(1, "Creative Director", "🎨", "creative")
render_seat(2, "Lead Strategist", "👔", "strategist")
render_seat(3, "Social Content", "✍🏾", "social")
render_seat(4, "GEO Specialist", "🧠", "geo")
render_seat(5, "Web Auditor", "🌐", "auditor")

with tabs[6]: # INDUSTRY DIAGNOSTIC LAB
    st.subheader(f"🛡️ {final_ind} Diagnostic Lab")
    diag_up = st.file_uploader(f"Upload {final_ind} Field Evidence", type=['png', 'jpg'])
    if diag_up: st.success("Visual Evidence Archived for AI Risk Scoring.")

with tabs[7]: # TEAM HUB
    st.info(f"Organization ID: **{user_row['team_id']}**")
    conn = sqlite3.connect('breatheeasy.db')
    st.write("### 🏆 Leadership Board")
    st.table(pd.read_sql_query("SELECT user as 'Member', COUNT(id) as 'Reports' FROM leads WHERE team_id = ? GROUP BY user ORDER BY Reports DESC", conn, params=(user_row['team_id'],)))
    conn.close()

if user_row['role'] == 'admin': # ADMIN HUB
    with tabs[-1]:
        st.subheader("⚙️ System Administration")
        conn = sqlite3.connect('breatheeasy.db')
        st.dataframe(pd.read_sql("SELECT username, email, credits FROM users", conn), use_container_width=True)
        u_del = st.text_input("Terminate User Access")
        if st.button("❌ Remove User"):
            conn.execute(f"DELETE FROM users WHERE username='{u_del}'"); conn.commit(); st.rerun()
        conn.close()
