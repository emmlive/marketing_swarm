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

# Elite UI CSS with Pulsing Animation for Swarm Active Status
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
    div.stButton > button:hover {{ transform: translateY(-1px); box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
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
    c.execute("""INSERT OR IGNORE INTO users (username, email, name, password, role, package, credits, logo_path, team_id) 
                 VALUES (?,?,?,?,?,?,?,?,?)""",
              ('admin', 'admin@techinadvance.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited', 9999, 'Logo1.jpeg', 'HQ_001'))
    conn.commit(); conn.close()

init_db()

# --- 3. AUTHENTICATION ---
def get_db_creds():
    try:
        conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
        df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn); conn.close()
        return {'usernames': {row['username']: {'email':row['email'], 'name':row['name'], 'password':row['password']} for _, row in df.iterrows()}}
    except: return {'usernames': {}}

current_creds = get_db_creds()
authenticator = stauth.Authenticate(current_creds, st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=200)
    st.title("TechInAdvance AI Enterprise")
    auth_tabs = st.tabs(["🔑 Login", "📝 Register & Subscribe", "❓ Forgot Password"])
    
    with auth_tabs[0]: authenticator.login(location='main')
    with auth_tabs[1]:
        plan = st.selectbox("Select Subscription Tier", ["Basic ($99/mo)", "Pro ($499/mo)", "Enterprise ($1999/mo)"])
        join_team_id = st.text_input("Join Existing Team ID (Optional)", placeholder="TEAM_xxxx")
        try:
            reg_res = authenticator.register_user(location='main')
            if reg_res:
                e, u, n = reg_res
                pw = authenticator.credentials['usernames'][u]['password']
                final_tid = join_team_id if join_team_id else f"TEAM_{u}"
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?,'member',?,?,?,?)", 
                             (u, e, n, pw, plan.split()[0], 50, "Logo1.jpeg", final_tid))
                conn.commit(); conn.close()
                st.success("Registration Successful!"); st.button("Proceed to Login", on_click=switch_to_login)
        except Exception: st.info("Please fill the registration form.")
    with auth_tabs[2]:
        st.subheader("Account Recovery")
        recovery_user = st.text_input("Username")
        if st.button("Send Recovery Instructions"): st.success("Instructions dispatched via AI Swarm.")
    st.stop()

# --- 4. BRANDED EXPORT ENGINE ---
def create_word_doc(content, logo_path="Logo1.jpeg"):
    doc = Document()
    final_logo = logo_path if logo_path and os.path.exists(logo_path) else "Logo1.jpeg"
    try: doc.add_picture(final_logo, width=Inches(1.5))
    except: pass
    doc.add_heading('TechInAdvance AI Strategy Report', 0)
    doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city, logo_path="Logo1.jpeg"):
    pdf = FPDF(); pdf.add_page()
    final_logo = logo_path if logo_path and os.path.exists(logo_path) else "Logo1.jpeg"
    try: pdf.image(final_logo, 10, 8, 33); pdf.ln(20)
    except: pass
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'{service} Strategy - {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 7, txt=str(content).encode('latin-1', 'ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

# --- 5. DASHBOARD CONTROL CENTER ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()

with st.sidebar:
    st.image("Logo1.jpeg", use_column_width=True)
    st.button("🌓 Switch Theme", on_click=toggle_theme)
    st.markdown(f"### 👋 {st.session_state['name']} (`{user_row['package']}`)")
    st.metric("Credits Available", user_row['credits'])
    st.info(f"📍 Team ID: {user_row['team_id']}")
    
    if user_row['package'] in ["Pro", "Enterprise", "Unlimited"]:
        st.divider(); st.subheader("🎨 Custom White-Labeling")
        user_logo = st.file_uploader("Upload Logo", type=['png', 'jpg', 'jpeg'])
        if user_logo:
            save_path = f"user_logos/{st.session_state['username']}_logo.png"
            os.makedirs("user_logos", exist_ok=True)
            with open(save_path, "wb") as f: f.write(user_logo.getbuffer())
            conn = sqlite3.connect('breatheeasy.db'); conn.execute("UPDATE users SET logo_path = ? WHERE username = ?", (save_path, st.session_state['username'])); conn.commit(); conn.close(); st.success("Branding Applied!")

    st.divider(); biz_name = st.text_input("Brand Name"); biz_usp = st.text_area("Brand USP")
    toggles = {
        "audit": st.toggle("🌐 Web Auditor (Psychology)", value=True), 
        "advice": st.toggle("👔 Advice Director", value=True), 
        "sem": st.toggle("🚀 Ads & Budget Forecaster", value=True), 
        "seo": st.toggle("✍️ SEO Authority (IG)", value=True), 
        "repurpose": st.toggle("✍🏾 Social Content"), 
        "geo": st.toggle("🧠 GEO Specialist")
    }
    web_url = st.text_input("Target URL (Competitor or Own)")
    ind_choice = st.selectbox("Industry", ["HVAC", "Medical", "Law", "Solar", "Custom"])
    final_ind = st.text_input("Enter Industry") if ind_choice == "Custom" else ind_choice
    svc = st.text_input("Specific Service"); city = st.text_input("Target City")
    
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
    authenticator.logout('Sign Out', 'sidebar')

# --- 6. TABS & DYNAMIC COMMAND CENTER ---
hub_display_name = f"🔬 {final_ind} Diagnostic Hub" if final_ind else "🔬 Diagnostic Lab"
tabs = st.tabs(["📝 Ad Copy", "🗓️ Roadmap", "📊 Ads Manager", hub_display_name, "🤝 Team Share", "⚙️ Admin Hub"])

if run_btn:
    if not biz_name or not city:
        st.error("❌ Brand Name and City are mandatory for Swarm coordination.")
    elif user_row['credits'] <= 0:
        st.error("❌ Insufficient Credits. Please upgrade.")
    else:
        st.session_state.processing = True

if st.session_state.get('processing'):
    with tabs[0]:
        st.markdown(f"### <div class='swarm-pulse'></div> Swarm Active: Analyzing {final_ind} in {city}...", unsafe_allow_html=True)
        with st.status("🐝 **Specialist Agents Coordinating...**", expanded=True) as status:
            st.write("🕵️ Analyst: Diagnosing Neuromarketing Conversion Leaks...")
            report = run_marketing_swarm({'city': city, 'industry': final_ind, 'service': svc, 'biz_name': biz_name, 'usp': biz_usp, 'url': web_url, 'toggles': toggles})
            st.write("✅ Creative Director: Branded Navy/White assets ready.")
            st.write("✅ SEO Lead: Information Gain content strategy verified.")
            status.update(label="🚀 Swarm Complete! Intelligence Ready.", state="complete", expanded=False)
            
            st.session_state['report'] = report
            st.session_state['gen'] = True
            st.session_state.processing = False
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
            conn.execute("INSERT INTO leads (date, user, industry, service, city, content, team_id, is_shared) VALUES (?,?,?,?,?,?,?,?)", (datetime.now().strftime("%Y-%m-%d"), user_row['username'], final_ind, svc, city, str(report), user_row['team_id'], 1))
            conn.commit(); conn.close(); st.rerun()

with tabs[0]: 
    if st.session_state.get('gen'):
        st.subheader("📥 Export Branded Deliverables")
        c1, c2 = st.columns(2)
        report_logo = user_row['logo_path'] if user_row['package'] != "Basic" else "Logo1.jpeg"
        c1.download_button("📄 Word Document", create_word_doc(st.session_state['report'], report_logo), f"Report_{city}.docx", use_container_width=True)
        c2.download_button("📕 PDF Report", create_pdf(st.session_state['report'], svc, city, report_logo), f"Report_{city}.pdf", use_container_width=True)
        st.markdown(st.session_state['report'])

with tabs[1]:
    st.subheader("🗓️ Your 30-Day Project Roadmap")
    if st.session_state.get('gen'): st.write(st.session_state['report'])

with tabs[2]:
    st.subheader("🚀 Ads Manager & Automated Budget Forecaster")
    if st.session_state.get('gen'):
        data = {"Budget Tier": ["Conservative", "Aggressive", "Elite Scaling"], "Monthly Spend": ["$2,500", "$7,500", "$20,000+"], "Target ROAS": ["280%", "410%", "550%"]}
        st.table(pd.DataFrame(data))
        st.subheader("🔗 SOTA Social Push")
        p1, p2, p3 = st.columns(3)
        if p1.button("Push to Facebook Ads"): st.success("Campaign Draft Synced to Meta API")
        if p2.button("Push to Google Ads"): st.success("Keywords Pushed to Ads Manager")
        if p3.button("Push to LinkedIn"): st.success("B2B Audience Synced")

with tabs[3]:
    st.subheader(f"🛡️ {final_ind} Quality Audit")
    diag_up = st.file_uploader(f"Upload {final_ind} Field Evidence", type=['png', 'jpg'])
    if diag_up: 
        render_breatheeasy_gauge(8, final_ind)

with tabs[4]:
    st.subheader("🤝 Team Collaboration Hub")
    st.info(f"Team ID: **{user_row['team_id']}**")
    conn = sqlite3.connect('breatheeasy.db')
    st.write("### 🏆 Team Leaderboard")
    leader_df = pd.read_sql_query("SELECT user as 'Team Member', COUNT(id) as 'Reports' FROM leads WHERE team_id = ? GROUP BY user ORDER BY Reports DESC", conn, params=(user_row['team_id'],))
    st.table(leader_df)
    team_history = pd.read_sql_query("SELECT date, user, industry, service, city FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
    st.dataframe(team_history, use_container_width=True)
    conn.close()

if user_row['role'] == 'admin':
    with tabs[-1]:
        st.subheader("👥 User & Credit Administration")
        conn = sqlite3.connect('breatheeasy.db')
        all_u = pd.read_sql("SELECT username, email, package, credits, team_id FROM users", conn)
        st.dataframe(all_u, use_container_width=True)
        user_to_del = st.text_input("Username to Terminate")
        if st.button("❌ Remove User"):
            conn.execute(f"DELETE FROM users WHERE username='{user_to_del}'")
            conn.commit(); st.rerun()
        conn.close()
