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

# --- 1. SYSTEM INITIALIZATION ---
try:
    import stripe
    stripe.api_key = st.secrets.get("STRIPE_API_KEY", "sk_test_placeholder")
except ImportError:
    stripe = None

# PERSISTENT SESSION STATES
if 'theme' not in st.session_state: st.session_state.theme = 'dark'
if 'auth_tab' not in st.session_state: st.session_state.auth_tab = "🔑 Login"
if 'processing' not in st.session_state: st.session_state.processing = False
if 'video_url' not in st.session_state: st.session_state.video_url = None

os.environ["OTEL_SDK_DISABLED"] = "true"
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

st.set_page_config(page_title="TechInAdvance AI | Enterprise Command", page_icon="Logo1.jpeg", layout="wide")

# --- 2. EXHAUSTIVE INDUSTRY & SERVICE LIBRARY ---
INDUSTRY_LIBRARY = {
    "HVAC & Home Services": ["AC Repair", "Heating Install", "Plumbing", "Roofing Audit", "Electrical", "Pest Control"],
    "Medical & Healthcare": ["Telehealth Growth", "Dental Implants", "Plastic Surgery", "Physical Therapy", "Chiropractic Marketing"],
    "Legal Services": ["Personal Injury", "Criminal Defense", "Family Law", "Corporate Litigation", "Immigration Law"],
    "Solar & Energy": ["Residential ROI Audit", "Commercial Install", "Battery Storage", "EV Charging Infrastructure"],
    "SaaS & Tech": ["Product Launch", "User Retention", "Enterprise Sales", "API Adoption", "Growth Hacking"],
    "E-commerce": ["DTC Brand Growth", "Amazon SEO", "Email Automation", "Influencer Strategy", "Conversion Rate Optimization"],
    "Real Estate": ["Luxury Listings", "Buyer Lead Gen", "Commercial Leasing", "Property Management", "Short-term Rental ROI"],
    "Finance & Fintech": ["Wealth Management", "Crypto Adoption", "Mortgage Lending", "Tax Strategy", "Business Funding"]
}

# --- 3. UI CSS (ELITE UI AUDIT & ALIGNMENT) ---
sidebar_color = "#3B82F6" if st.session_state.theme == 'dark' else "#2563EB"
bg, text, side = ("#0F172A", "#F8FAFC", "#1E293B") if st.session_state.theme == 'dark' else ("#F8FAFC", "#0F172A", "#E2E8F0")

st.markdown(f"""
    <style>
    #MainMenu, footer, header {{visibility: hidden;}}
    .stDeployButton {{display:none;}}
    [data-testid="sidebar-button"] {{ background-color: {sidebar_color} !important; color: white !important; z-index: 999999; display: flex !important; }}
    [data-testid="stSidebar"] {{ background-color: {bg}; color: {text}; border-right: 1px solid #1E293B; }}
    [data-testid="stMetric"] {{ background-color: {side}; padding: 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800 !important; text-transform: uppercase; transition: all 0.3s ease; }}
    div.stButton > button:hover {{ transform: translateY(-2px); box-shadow: 0px 4px 15px {sidebar_color}66; }}
    .insight-card {{ background-color: {side}; padding: 25px; border-radius: 15px; border-left: 5px solid {sidebar_color}; margin-top: 15px; line-height: 1.6; }}
    .swarm-pulse {{ background-color: {sidebar_color}; border-radius: 50%; width: 12px; height: 12px; display: inline-block; margin-right: 10px; animation: pulse-animation 1.5s infinite; }}
    @keyframes pulse-animation {{ 0% {{ transform: scale(0.95); opacity: 0.7; }} 70% {{ transform: scale(1.1); opacity: 1; }} 100% {{ transform: scale(0.95); opacity: 0.7; }} }}
    </style>
""", unsafe_allow_html=True)

# --- 4. DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, package TEXT, credits INTEGER DEFAULT 0, logo_path TEXT, team_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT, team_id TEXT, is_shared INTEGER DEFAULT 0, score INTEGER)''')
    hashed_pw = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001')", ('admin', 'admin@techinadvance.ai', 'Admin', hashed_pw))
    conn.commit(); conn.close()

init_db()

# --- 5. AUTH UTILS & EXPORTS ---
def get_db_creds():
    try:
        conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
        df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn); conn.close()
        return {'usernames': {row['username']: {'email':row['email'], 'name':row['name'], 'password':row['password']} for _, row in df.iterrows()}}
    except: return {'usernames': {}}

config_creds = get_db_creds()
authenticator = stauth.Authenticate(config_creds, st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

# --- VIDEO GENERATION HELPER (CHAPTER 8: VEO) ---
def generate_cinematic_ad(prompt):
    try:
        video = st.video_generation(
            prompt=f"Elite cinematic marketing ad: {prompt}. High-end professional color grading, 4k, slow motion, corporate commercial style.",
            aspect_ratio="16:9"
        )
        return video
    except Exception as e:
        st.error(f"Veo Generation Failed: {e}")
        return None

def create_word_doc(content, logo_path="Logo1.jpeg"):
    doc = Document()
    final_logo = logo_path if logo_path and os.path.exists(logo_path) else "Logo1.jpeg"
    try: doc.add_picture(final_logo, width=Inches(1.5))
    except: pass
    doc.add_heading('Strategic Intelligence Brief', 0); doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city, logo_path="Logo1.jpeg"):
    pdf = FPDF(); pdf.add_page()
    final_logo = logo_path if logo_path and os.path.exists(logo_path) else "Logo1.jpeg"
    try: pdf.image(final_logo, 10, 8, 33); pdf.ln(20)
    except: pass
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'{service} Strategy - {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 7, txt=str(content).encode('latin-1', 'ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

# --- 6. AUTH FLOW & PRICE PLANS ---
if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=200)
    auth_tabs = st.tabs(["🔑 Login", "📝 Register & Plans", "🤝 Join Team", "❓ Recovery"])
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
            if u in config_creds['usernames']:
                pw = config_creds['usernames'][u]['password']
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("INSERT INTO users VALUES (?,?,?,?,'member',?,50,'Logo1.jpeg',?)", (u, e, n, pw, plan, f"TEAM_{u}"))
                conn.commit(); conn.close(); st.success("Account Created!"); st.button("Log In Now", on_click=switch_to_login)
    with auth_tabs[3]:
        try:
            username_to_reset, email_to_reset, new_password = authenticator.forgot_password(location='main')
            if username_to_reset:
                st.success('New password generated. Update your records.')
                hashed_pw = stauth.Hasher.hash(new_password)
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("UPDATE users SET password = ? WHERE username = ?", (hashed_pw, username_to_reset))
                conn.commit(); conn.close()
        except Exception: st.info("Enter details to initiate recovery.")
    st.stop()

# --- 7. DASHBOARD DATA ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()

with st.sidebar:
    st.image(user_row['logo_path'] if user_row['logo_path'] else "Logo1.jpeg", use_container_width=True)
    m_col, t_col = st.columns(2)
    with m_col: st.metric("Credits", user_row['credits'])
    with t_col:
        st.markdown(f"""<div style="background:{side}; padding:10px; border-radius:10px; border:1px solid rgba(255,255,255,0.1); height:80px; text-align:center;">
        <small style="opacity:0.7;">TEAM ID</small><br><b>{user_row['team_id']}</b></div>""", unsafe_allow_html=True)
    st.divider()
    biz_name = st.text_input("Brand Name"); biz_usp = st.text_area("Core USP")
    ind_cat = st.selectbox("Industry Sector", list(INDUSTRY_LIBRARY.keys()) + ["Custom"])
    final_ind = st.text_input("Define Industry") if ind_cat == "Custom" else ind_cat
    svc = st.selectbox("Service Focus", INDUSTRY_LIBRARY[ind_cat]) if ind_cat != "Custom" else st.text_input("Define Service")
    city = st.text_input("Market City"); web_url = st.text_input("Audit URL")
    st.divider(); st.subheader("🤖 Swarm Personnel")
    toggles = {k: st.toggle(v, value=True) for k, v in {"analyst": "🕵️ Analyst", "builder": "🎨 Creative", "manager": "👔 Strategist", "social": "✍🏾 Social", "geo": "🧠 GEO", "audit": "🌐 Auditor"}.items()}
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary")
    authenticator.logout('Sign Out', 'sidebar')

# --- 8. TABS ---
hub_label = f"🔬 {final_ind} Diagnostic Lab" if final_ind else "🔬 Diagnostic Lab"
tabs = st.tabs(["🕵️ Analyst", "🎨 Creative", "👔 Strategist", "✍🏾 Social", "🧠 GEO", "🌐 Auditor", "🎬 Cinematic Studio", hub_label, "🤝 Team Share", "⚙️ Admin"])

if run_btn:
    if not biz_name or not city: st.error("❌ Mandatory Fields Missing.")
    elif user_row['credits'] <= 0: st.error("❌ Out of Credits.")
    else: st.session_state.processing = True

if st.session_state.get('processing'):
    with tabs[0]:
        with st.status("🛠️ **Swarm Coordination...**", expanded=True) as status:
            try:
                st.write("<div class='swarm-pulse'></div> **Phase 1:** Researching market gaps...", unsafe_allow_html=True)
                report = run_marketing_swarm({'city': city, 'industry': final_ind, 'service': svc, 'biz_name': biz_name, 'usp': biz_usp, 'url': web_url, 'toggles': toggles})
                st.write("🎨 **Phase 2:** Building creative assets and video prompts...")
                st.write("👔 **Phase 3:** Finalizing ROI roadmap...")
                st.session_state.report, st.session_state.gen = report, True
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
                conn.execute("INSERT INTO leads (date, user, industry, service, city, content, team_id) VALUES (?,?,?,?,?,?,?)", (datetime.now().strftime("%Y-%m-%d"), user_row['username'], final_ind, svc, city, str(report), user_row['team_id']))
                conn.commit(); conn.close(); status.update(label="✅ Swarm Success!", state="complete")
            except Exception as e: st.error(f"⚠️ Error: {str(e)}")
            finally: st.session_state.processing = False; st.rerun()

# --- 9. RENDER SEATS ---
def render_seat(idx, title, icon, data_key, guide_text):
    with tabs[idx]:
        st.markdown(f"### {icon} {title} Command Seat")
        with st.expander("💡 Strategy Guide"): st.info(guide_text)
        if st.session_state.get('gen'):
            report_dict = st.session_state.get('report', {})
            agent_data = report_dict.get(data_key, "No data returned.")
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1: st.success(f"Verified {title} Intelligence")
            with c2: st.download_button("📄 Word", create_word_doc(agent_data, user_row['logo_path']), f"{title}.docx", use_container_width=True, key=f"w_{data_key}")
            with c3: st.download_button("📕 PDF", create_pdf(agent_data, svc, city, user_row['logo_path']), f"{title}.pdf", use_container_width=True, key=f"p_{data_key}")
            st.markdown(f"""<div class="insight-card">{agent_data.replace('•', '<br>•')}</div>""", unsafe_allow_html=True)
        else: st.info(f"Launch Swarm to populate {title} seat.")

guides = {"analyst": "Identify gaps.", "creative": "Use AI art prompts.", "strategist": "ROI Roadmap.", "social": "Viral hooks.", "geo": "AI Search SEO.", "auditor": "Fix UX leaks."}

render_seat(0, "Market Analyst", "🕵️", "analyst", guides["analyst"])
render_seat(1, "Creative Director", "🎨", "creative", guides["creative"])
render_seat(2, "Lead Strategist", "👔", "strategist", guides["strategist"])
render_seat(3, "Social Content", "✍🏾", "social", guides["social"])
render_seat(4, "GEO Specialist", "🧠", "geo", guides["geo"])
render_seat(5, "Web Auditor", "🌐", "auditor", guides["auditor"])

# --- 10. CINEMATIC STUDIO (CHAPTER 8: VEO) ---
with tabs[6]:
    st.markdown("### 🎬 Veo Cinematic Studio")
    st.info("Transform your Creative Brief into a high-end AI Video Ad using Veo (3 Credits Daily).")
    if st.session_state.get('gen'):
        # Extract prompt from creative agent output
        raw_creative = st.session_state.report.get('creative', '')
        # Simple extraction logic for the video prompt section
        default_video_prompt = raw_creative.split("Video Prompt:")[-1] if "Video Prompt:" in raw_creative else raw_creative[:300]
        
        video_prompt = st.text_area("Video Script/Scene Description", value=default_video_prompt, height=150)
        
        if st.button("📽️ GENERATE CINEMATIC AD"):
            with st.spinner("Veo is rendering your ad..."):
                video_file = generate_cinematic_ad(video_prompt)
                if video_file:
                    st.video(video_file)
                    st.success("Cinematic Ad Rendered Successfully.")
    else:
        st.warning("Generate a swarm report first to unlock the Cinematic Studio.")

if user_row['role'] == 'admin':
    with tabs[-1]:
        conn = sqlite3.connect('breatheeasy.db')
        st.dataframe(pd.read_sql("SELECT username, email, credits FROM users", conn), use_container_width=True)
        u_del = st.text_input("Terminate User")
        if st.button("❌ Remove User"):
            conn.execute("DELETE FROM users WHERE username=?", (u_del,))
            conn.commit(); st.rerun()
        conn.close()
