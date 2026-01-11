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
if 'theme' not in st.session_state: st.session_state.theme = 'light'
if 'processing' not in st.session_state: st.session_state.processing = False
if 'gen' not in st.session_state: st.session_state.gen = False
if 'report' not in st.session_state: st.session_state.report = {}

def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

def switch_to_login():
    st.session_state.auth_tab = "🔑 Login"
    st.rerun()

os.environ["OTEL_SDK_DISABLED"] = "true"
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

st.set_page_config(page_title="TechInAdvance AI | Command Hub", page_icon="Logo1.jpeg", layout="wide")

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

# --- 3. UI CSS (CREAM MAIN / SIDEBAR BOX BORDER) ---
sidebar_color = "#3B82F6" if st.session_state.theme == 'dark' else "#2563EB"
bg = "#FDFCF0" # Champagne Cream Main
text = "#1E293B" 
side_bg = "#1E293B" if st.session_state.theme == 'dark' else "#FFFFFF"
side_text = "#F8FAFC" if st.session_state.theme == 'dark' else "#1E293B"
side_border = "rgba(255,255,255,0.2)" if st.session_state.theme == 'dark' else "rgba(0,0,0,0.18)"

st.markdown(f"""
    <style>
    #MainMenu, footer, header {{visibility: hidden;}}
    .stApp {{ background-color: {bg}; color: {text}; }}
    [data-testid="stSidebar"] {{ 
        background-color: {side_bg} !important; 
        border-right: 2.5px solid {side_border} !important;
        box-shadow: 4px 0px 15px rgba(0,0,0,0.05);
    }}
    .sidebar-brand {{ text-align: center; padding-bottom: 20px; border-bottom: 1px solid {side_border}; margin-bottom: 20px; }}
    .price-card {{
        background-color: white; padding: 25px; border-radius: 15px; border: 2px solid {sidebar_color};
        text-align: center; margin-bottom: 20px; color: #1E293B; box-shadow: 0px 4px 10px rgba(0,0,0,0.05);
    }}
    [data-testid="stMetric"] {{ background-color: {side_bg}; padding: 15px; border-radius: 10px; border: 1.5px solid {side_border}; }}
    .insight-card {{ background-color: white; padding: 25px; border-radius: 15px; border-left: 5px solid {sidebar_color}; margin-top: 15px; line-height: 1.6; white-space: pre-wrap; color: #1E293B; }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800 !important; width: 100%; transition: 0.3s; height: 3.2em; }}
    </style>
""", unsafe_allow_html=True)

# --- 4. DATABASE ENGINE (FIXED TYPEERROR HASHING) ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, package TEXT, credits INTEGER DEFAULT 0, logo_path TEXT, team_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT, team_id TEXT, status TEXT DEFAULT 'Active')''')
    # MODERN HASHING LOGIC
    hashed_pw = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001')", ('admin', 'admin@techinadvance.ai', 'Admin', hashed_pw))
    conn.commit(); conn.close()

init_db()

# --- 5. AUTH & HELPERS ---
def get_db_creds():
    try:
        conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
        df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn); conn.close()
        return {'usernames': {row['username']: {'email':row['email'], 'name':row['name'], 'password':row['password']} for _, row in df.iterrows()}}
    except: return {'usernames': {}}

config_creds = get_db_creds()
authenticator = stauth.Authenticate(config_creds, st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

def create_word_doc(content, logo_path="Logo1.jpeg"):
    doc = Document()
    try: doc.add_picture(logo_path if os.path.exists(logo_path) else "Logo1.jpeg", width=Inches(1.5))
    except: pass
    doc.add_heading('Strategic Intelligence Brief', 0); doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city, logo_path="Logo1.jpeg"):
    pdf = FPDF(); pdf.add_page()
    try: pdf.image(logo_path if os.path.exists(logo_path) else "Logo1.jpeg", 10, 8, 33); pdf.ln(20)
    except: pass
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'{service} Strategy - {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 7, txt=str(content).encode('latin-1', 'ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

def generate_cinematic_ad(prompt):
    try:
        return st.video_generation(prompt=f"Elite cinematic marketing ad: {prompt}. 4k.", aspect_ratio="16:9")
    except Exception as e:
        st.error(f"Veo Error: {e}"); return None

# --- 6. AUTHENTICATION & REGISTRATION (HARDENED) ---
if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=200)
    auth_tabs = st.tabs(["🔑 Login", "📝 Register & Plans", "🤝 Join Team", "❓ Recovery"])
    with auth_tabs[0]: 
        authenticator.login(location='main')

    with auth_tabs[1]:
        st.markdown("### Enterprise Enrollment")
        p1, p2, p3 = st.columns(3)
        with p1: st.markdown('<div class="price-card">BASIC<br><h3>$99</h3></div>', unsafe_allow_html=True)
        with p2: st.markdown('<div class="price-card">PRO<br><h3>$499</h3></div>', unsafe_allow_html=True)
        with p3: st.markdown('<div class="price-card">ENTERPRISE<br><h3>$1,999</h3></div>', unsafe_allow_html=True)
        
        reg_res = authenticator.register_user(location='main')
        if reg_res:
            e, u, n = reg_res
            # FIX: Manually hashing to avoid internal object AttributeError
            raw_pw = st.text_input("Security Password", type="password", key="reg_pw_final")
            plan = st.selectbox("Select Tier", ["Basic", "Pro", "Enterprise"])
            if st.button("Finalize Account"):
                hashed = stauth.Hasher.hash(raw_pw)
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("INSERT INTO users VALUES (?,?,?,?,'member',?,50,'Logo1.jpeg',?)", (u, e, n, hashed, plan, f"TEAM_{u}"))
                conn.commit(); conn.close(); st.success("Account Ready! Please Log In."); st.rerun()
    with auth_tabs[3]: authenticator.forgot_password(location='main')
    st.stop()

# --- 7. DASHBOARD DATA ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()

with st.sidebar:
    st.markdown('<div class="sidebar-brand">', unsafe_allow_html=True)
    st.image(user_row['logo_path'], width=120)
    st.markdown(f'<h2 style="color:{sidebar_color};">TechInAdvance</h2>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.button("🌓 Toggle Sidebar", on_click=toggle_theme)
    m_col, t_col = st.columns(2)
    with m_col: st.metric("Credits", user_row['credits'])
    with t_col: st.markdown(f"""<div style="background:{side_bg}; padding:10px; border-radius:10px; border:1px solid {side_border}; text-align:center;"><small>TEAM ID</small><br><b>{user_row['team_id']}</b></div>""", unsafe_allow_html=True)
    st.divider()
    biz_name = st.text_input("Brand Name")
    city_in = st.text_input("Market City")
    st.divider()
    toggles = {k: st.toggle(v, value=True) for k, v in {"analyst": "🕵️ Analyst", "ads": "📺 Ad Tracker", "builder": "🎨 Creative", "manager": "👔 Strategist", "social": "✍🏾 Social", "geo": "🧠 GEO", "audit": "🌐 Auditor", "seo": "✍️ SEO Blogger"}.items()}
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary")
    authenticator.logout('Sign Out', 'sidebar')

# --- 8. COMMAND CENTER TABS ---
tabs = st.tabs(["🕵️ Analyst", "📺 Ads", "🎨 Creative", "👔 Strategist", "✍🏾 Social", "🧠 GEO", "🌐 Auditor", "✍️ SEO Blogger", "👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel", "⚙️ Admin"])

if run_btn:
    if not biz_name or not city_in: st.error("❌ Required fields missing.")
    elif user_row['credits'] <= 0: st.error("❌ Out of credits.")
    else:
        with st.spinner("Swarm Launching..."):
            st.session_state.report = run_marketing_swarm({'city': city_in, 'biz_name': biz_name, 'toggles': toggles})
            st.session_state.gen = True
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (st.session_state["username"],))
            conn.execute("INSERT INTO leads (date, user, city, content, team_id) VALUES (?,?,?,?,?)", (datetime.now().strftime("%Y-%m-%d"), st.session_state["username"], city_in, str(st.session_state.report), user_row['team_id']))
            conn.commit(); conn.close(); st.rerun()

# --- 9. RENDER ALL SEATS (Isolated Mapping) ---
def render_seat(idx, title, icon, key):
    with tabs[idx]:
        st.markdown(f"### {icon} {title} Output")
        if st.session_state.get('gen'):
            data = st.session_state.report.get(key, "Data pending isolation...")
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1: st.success(f"Verified {title} Data")
            with c2: st.download_button("📄 Word", create_word_doc(data, user_row['logo_path']), f"{title}.docx", key=f"w_{key}")
            with c3: st.download_button("📕 PDF", create_pdf(data, "Strategy", city_in, user_row['logo_path']), f"{title}.pdf", key=f"p_{key}")
            st.markdown(f'<div class="insight-card">{data}</div>', unsafe_allow_html=True)
        else: st.info(f"Launch swarm to populate {title}.")

render_seat(0, "Market Analyst", "🕵️", "analyst")
render_seat(1, "Ad Tracker", "📺", "ads")
render_seat(2, "Creative Director", "🎨", "creative")
render_seat(3, "Lead Strategist", "👔", "strategist")
render_seat(4, "Social Content", "✍🏾", "social")
render_seat(5, "GEO Specialist", "🧠", "geo")
render_seat(6, "Web Auditor", "🌐", "auditor")
render_seat(7, "SEO Blogger", "✍️", "seo")

with tabs[8]:
    st.subheader("👁️ Vision Inspector")
    v_file = st.file_uploader("Evidence Upload", type=['png', 'jpg', 'jpeg'])
    if v_file: st.image(v_file, use_container_width=True)

with tabs[9]:
    st.subheader("🎬 Veo Cinematic Studio")
    if st.session_state.get('gen'):
        v_prompt = st.text_area("Video Scene Description", value=st.session_state.report.get('creative', '')[:300], height=150)
        if st.button("📽️ GENERATE AD"):
            with st.spinner("Rendering..."):
                v_file = generate_cinematic_ad(v_prompt)
                if v_file: st.video(v_file)
    else: st.warning("Launch swarm first.")

# --- 10. TEAM & ADMIN (ROBUST BACKEND) ---
with tabs[10]:
    st.header("🤝 Team Collaboration hub")
    conn = sqlite3.connect('breatheeasy.db')
    team_df = pd.read_sql_query("SELECT date, user, city, status FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
    st.dataframe(team_df, use_container_width=True); conn.close()

if user_row['role'] == 'admin':
    with tabs[11]:
        st.header("⚙️ Admin Control")
        conn = sqlite3.connect('breatheeasy.db')
        all_u = pd.read_sql_query("SELECT username, email, credits FROM users", conn)
        st.dataframe(all_u, use_container_width=True)
        st.divider()
        u_del = st.text_input("Terminate Username")
        if st.button("❌ Remove User"):
            conn.execute("DELETE FROM users WHERE username=?", (u_del,)); conn.commit(); st.rerun()
        st.divider()
        target = st.selectbox("Refill Credits", all_u['username'])
        amt = st.number_input("Amount", value=50)
        if st.button("💉 Inject Credits"):
            conn.execute("UPDATE users SET credits = credits + ? WHERE username = ?", (amt, target))
            conn.commit(); st.rerun()
        conn.close()
