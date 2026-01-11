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

# --- 3. UI CSS (LOCKED CREAM MAIN / DYNAMIC SIDEBAR WITH CRISP BORDER) ---
sidebar_color = "#3B82F6" if st.session_state.theme == 'dark' else "#2563EB"
bg = "#FDFCF0" # Main Area locked to Champagne Cream
text = "#1E293B" # Darker text for readability
side_bg = "#1E293B" if st.session_state.theme == 'dark' else "#FFFFFF"
side_text = "#F8FAFC" if st.session_state.theme == 'dark' else "#1E293B"
# Stronger border logic for Light Theme to define the box clearly
side_border = "rgba(255,255,255,0.2)" if st.session_state.theme == 'dark' else "rgba(0,0,0,0.18)"

st.markdown(f"""
    <style>
    #MainMenu, footer, header {{visibility: hidden;}}
    .stApp {{ background-color: {bg}; color: {text}; }}
    
    /* SIDEBAR WITH DISTINCT BOX BORDER */
    [data-testid="stSidebar"] {{ 
        background-color: {side_bg} !important; 
        border-right: 2px solid {side_border} !important;
        box-shadow: 4px 0px 15px rgba(0,0,0,0.08);
    }}
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label, [data-testid="stSidebar"] p {{
        color: {side_text} !important;
    }}
    
    .sidebar-brand {{ text-align: center; padding-bottom: 20px; border-bottom: 1px solid {side_border}; margin-bottom: 20px; }}
    
    .price-card {{
        background-color: white; padding: 25px; border-radius: 15px; border: 2px solid {sidebar_color};
        text-align: center; margin-bottom: 20px; color: #1E293B; box-shadow: 0px 4px 10px rgba(0,0,0,0.05);
    }}
    .price-header {{ font-size: 1.5rem; font-weight: 800; color: {sidebar_color}; }}
    .price-value {{ font-size: 2.2rem; font-weight: 900; margin: 10px 0; }}
    
    [data-testid="stMetric"] {{ background-color: {side_bg}; padding: 15px; border-radius: 10px; border: 1.5px solid {side_border}; }}
    .insight-card {{ background-color: white; padding: 25px; border-radius: 15px; border-left: 5px solid {sidebar_color}; margin-top: 15px; line-height: 1.6; white-space: pre-wrap; color: #1E293B; }}
    
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800 !important; width: 100%; transition: 0.3s; height: 3.2em; }}
    div.stButton > button:hover {{ transform: translateY(-2px); box-shadow: 0px 4px 15px {sidebar_color}66; }}
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
        video = st.video_generation(prompt=f"Elite cinematic marketing ad: {prompt}. 4k, professional style.", aspect_ratio="16:9")
        return video
    except Exception as e:
        st.error(f"Veo Error: {e}"); return None

# --- 6. AUTHENTICATION & REGISTRATION (FINAL HARDENED FIX) ---
if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=200)
    auth_tabs = st.tabs(["🔑 Login", "📝 Register & Plans", "🤝 Join Team", "❓ Recovery"])
    with auth_tabs[0]: 
        authenticator.login(location='main')

    with auth_tabs[1]:
        st.markdown("### Select Enterprise Tier")
        p1, p2, p3 = st.columns(3)
        with p1: st.markdown(f'<div class="price-card"><div class="price-header">BASIC</div><div class="price-value">$99</div></div>', unsafe_allow_html=True)
        with p2: st.markdown(f'<div class="price-card"><div class="price-header">PRO</div><div class="price-value">$499</div></div>', unsafe_allow_html=True)
        with p3: st.markdown(f'<div class="price-card"><div class="price-header">ENTERPRISE</div><div class="price-value">$1,999</div></div>', unsafe_allow_html=True)
        plan = st.selectbox("Select Tier", ["Basic", "Pro", "Enterprise"])
        reg_res = authenticator.register_user(location='main')
        if reg_res:
            e, u, n = reg_res
            conn = sqlite3.connect('breatheeasy.db')
            # HARDENED FIX: Pulling password directly from registration state to prevent AttributeError
            new_pw = authenticator.credentials['usernames'][u]['password']
            conn.execute("INSERT INTO users VALUES (?,?,?,?,'member',?,50,'Logo1.jpeg',?)", (u, e, n, new_pw, plan, f"TEAM_{u}"))
            conn.commit(); conn.close(); st.success("Account Created! Please Log In."); st.rerun()
    with auth_tabs[3]: authenticator.forgot_password(location='main')
    st.stop()

# --- 7. DASHBOARD DATA ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()

with st.sidebar:
    st.markdown('<div class="sidebar-brand">', unsafe_allow_html=True)
    st.image(user_row['logo_path'], width=120)
    st.markdown(f'<h2 style="color:{sidebar_color}; margin-top:-10px;">TechInAdvance</h2>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.button("🌓 Toggle Sidebar Theme", on_click=toggle_theme)
    m_col, t_col = st.columns(2)
    with m_col: st.metric("Credits", user_row['credits'])
    with t_col: st.markdown(f"""<div style="background:{side_bg}; padding:10px; border-radius:10px; border:1px solid {side_border}; height:85px; text-align:center;"><small>TEAM ID</small><br><b>{user_row['team_id']}</b></div>""", unsafe_allow_html=True)
    st.divider()
    biz_name = st.text_input("Brand Name")
    c_col1, c_col2 = st.columns(2)
    with c_col1: city_input = st.text_input("City")
    with c_col2: state_input = st.text_input("State")
    full_loc = f"{city_input}, {state_input}"
    ind_cat = st.selectbox("Industry", list(INDUSTRY_LIBRARY.keys()) + ["Custom"])
    svc = st.selectbox("Service", INDUSTRY_LIBRARY[ind_cat]) if ind_cat != "Custom" else st.text_input("Define Service")
    web_url = st.text_input("Audit URL")
    st.divider()
    toggles = {k: st.toggle(v, value=True) for k, v in {"analyst": "🕵️ Analyst", "ads": "📺 Ad Tracker", "builder": "🎨 Creative", "manager": "👔 Strategist", "social": "✍🏾 Social", "geo": "🧠 GEO", "audit": "🌐 Auditor", "seo": "✍️ SEO Blogger"}.items()}
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary")
    authenticator.logout('Sign Out', 'sidebar')

# --- 8. TABS ---
tabs = st.tabs(["🕵️ Analyst", "📺 Ads", "🎨 Creative", "👔 Strategist", "✍🏾 Social", "🧠 GEO", "🌐 Auditor", "✍️ SEO Blogger", "👁️ Vision Inspector", "🎬 Veo Studio", "🤝 Team Intel hub", "⚙️ Admin Control"])

if run_btn:
    if not biz_name or not city_input: st.error("❌ Required fields missing.")
    elif user_row['credits'] <= 0: st.error("❌ Out of credits.")
    else: st.session_state.processing = True

if st.session_state.get('processing'):
    with tabs[0]:
        with st.status("🛠️ Swarm Action...", expanded=True) as status:
            try:
                report = run_marketing_swarm({'city': full_loc, 'industry': ind_cat, 'service': svc, 'biz_name': biz_name, 'url': web_url, 'toggles': toggles})
                st.session_state.report, st.session_state.gen = report, True
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
                conn.execute("INSERT INTO leads (date, user, industry, service, city, content, team_id) VALUES (?,?,?,?,?,?,?)", (datetime.now().strftime("%Y-%m-%d"), user_row['username'], ind_cat, svc, full_loc, str(report), user_row['team_id']))
                conn.commit(); conn.close(); status.update(label="✅ Success!", state="complete")
            except Exception as e: st.error(f"Error: {e}")
            finally: st.session_state.processing = False; st.rerun()

# --- 9. RENDER COMMAND SEATS ---
def render_seat(idx, title, icon, data_key):
    with tabs[idx]:
        st.markdown(f"### {icon} {title} Command Seat")
        if st.session_state.get('gen'):
            data = st.session_state.report.get(data_key, "Agent results pending.")
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1: st.success("Verified")
            with c2: st.download_button("📄 Word", create_word_doc(data, user_row['logo_path']), f"{title}.docx", key=f"w_{data_key}")
            with c3: st.download_button("📕 PDF", create_pdf(data, svc, full_loc, user_row['logo_path']), f"{title}.pdf", key=f"p_{data_key}")
            st.markdown(f'<div class="insight-card">{data}</div>', unsafe_allow_html=True)
        else: st.info("Deploy Swarm to populate.")

seats = [("Analyst", "🕵️", "analyst"), ("Ads", "📺", "ads"), ("Creative", "🎨", "creative"), ("Strategist", "👔", "strategist"), ("Social", "✍🏾", "social"), ("GEO", "🧠", "geo"), ("Auditor", "🌐", "auditor"), ("SEO", "✍️", "seo")]
for i, s in enumerate(seats): render_seat(i, s[0], s[1], s[2])

with tabs[8]:
    st.subheader("👁️ Vision Inspector")
    v_file = st.file_uploader("Evidence Upload", type=['png', 'jpg', 'jpeg'])
    if v_file: st.image(v_file, use_container_width=True)

with tabs[9]:
    st.markdown("### 🎬 Veo Cinematic Studio")
    if st.session_state.get('gen'):
        creative_out = st.session_state.report.get('creative', '')
        vp = creative_out.split("Video Prompt:")[-1] if "Video Prompt:" in creative_out else creative_out[:300]
        v_prompt = st.text_area("Video Scene Description", value=vp, height=150)
        if st.button("📽️ GENERATE AD"):
            with st.spinner("Rendering..."):
                v_file = generate_cinematic_ad(v_prompt)
                if v_file: st.video(v_file)
    else: st.warning("Launch swarm first.")

with tabs[10]:
    st.header("🤝 Team Intel hub")
    conn = sqlite3.connect('breatheeasy.db')
    team_df = pd.read_sql_query("SELECT date, user, service, city FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
    st.dataframe(team_df, use_container_width=True); conn.close()

# --- 10. ADMIN CONTROL (ZERO OMISSIONS) ---
if user_row['role'] == 'admin':
    with tabs[11]:
        st.header("⚙️ Admin Control")
        conn = sqlite3.connect('breatheeasy.db')
        all_users = pd.read_sql_query("SELECT username, email, credits, package FROM users", conn)
        st.dataframe(all_users, use_container_width=True)
        st.divider()
        u_del = st.text_input("Terminate User Username")
        if st.button("❌ Remove User"):
            if u_del != 'admin':
                conn.execute("DELETE FROM users WHERE username=?", (u_del,))
                conn.commit(); st.success(f"Purged {u_del}"); st.rerun()
            else: st.error("Admin protected.")
        st.divider()
        target_u = st.selectbox("Refill User Credits", all_users['username'])
        amount = st.number_input("Refill Amount", value=50)
        if st.button("💉 Inject Credits"):
            conn.execute("UPDATE users SET credits = credits + ? WHERE username = ?", (amount, target_u))
            conn.commit(); st.success("Credits Refilled."); st.rerun()
        conn.close()
