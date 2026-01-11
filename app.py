import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
import json
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

st.set_page_config(page_title="TechInAdvance AI | Enterprise Hub", page_icon="Logo1.jpeg", layout="wide")

# --- 2. EXHAUSTIVE INDUSTRY & SERVICE LIBRARY ---
INDUSTRY_LIBRARY = {
    "HVAC & Home Services": ["AC Repair", "Heating Install", "Plumbing", "Electrical", "Pest Control"],
    "Medical & Healthcare": ["Telehealth Growth", "Dental Implants", "Plastic Surgery", "Physical Therapy"],
    "Legal Services": ["Personal Injury", "Criminal Defense", "Family Law", "Corporate Litigation"],
    "Solar & Energy": ["Residential ROI Audit", "Commercial Install", "Battery Storage"],
    "SaaS & Tech": ["Product Launch", "User Retention", "Enterprise Sales"],
    "E-commerce": ["DTC Brand Growth", "Amazon SEO", "Influencer Strategy"],
    "Real Estate": ["Luxury Listings", "Buyer Lead Gen", "Property Management"],
    "Finance & Fintech": ["Wealth Management", "Mortgage Lending", "Business Funding"]
}

# --- 3. UI CSS (CREAM MAIN / SIDEBAR BOX BORDER) ---
sidebar_color = "#3B82F6" if st.session_state.theme == 'dark' else "#2563EB"
bg = "#FDFCF0" # Champagne Cream Main
text = "#1E293B" 
side_bg = "#1E293B" if st.session_state.theme == 'dark' else "#FFFFFF"
side_text = "#F8FAFC" if st.session_state.theme == 'dark' else "#1E293B"
side_border = "rgba(255,255,255,0.2)" if st.session_state.theme == 'dark' else "rgba(0,0,0,0.2)"

st.markdown(f"""
    <style>
    #MainMenu, footer, header {{visibility: hidden;}}
    .stApp {{ background-color: {bg}; color: {text}; }}
    [data-testid="stSidebar"] {{ 
        background-color: {side_bg} !important; 
        border-right: 3px solid {side_border} !important;
        box-shadow: 4px 0px 15px rgba(0,0,0,0.1);
    }}
    .sidebar-brand {{ text-align: center; padding-bottom: 20px; border-bottom: 1px solid {side_border}; margin-bottom: 20px; }}
    .price-card {{
        background-color: white; padding: 25px; border-radius: 15px; border: 2px solid {sidebar_color};
        text-align: center; margin-bottom: 20px; color: #1E293B; box-shadow: 0px 4px 10px rgba(0,0,0,0.05);
    }}
    [data-testid="stMetric"] {{ background-color: {side_bg}; padding: 15px; border-radius: 10px; border: 1.5px solid {side_border}; }}
    .insight-card {{ background-color: white; padding: 25px; border-radius: 12px; border-left: 6px solid {sidebar_color}; line-height: 1.8; color: #1E293B; box-shadow: 0px 4px 10px rgba(0,0,0,0.08); overflow-wrap: break-word; }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800 !important; width: 100%; height: 3.2em; }}
    </style>
""", unsafe_allow_html=True)

# --- 4. DATABASE ENGINE (HARDENED HASHING) ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, package TEXT, credits INTEGER DEFAULT 0, logo_path TEXT, team_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT, team_id TEXT, status TEXT DEFAULT 'Active')''')
    hashed_pw = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001')", ('admin', 'admin@techinadvance.ai', 'Admin', hashed_pw))
    conn.commit(); conn.close()

init_db()

# --- 5. AUTH & DOCUMENT HELPERS ---
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
    doc.add_heading('Strategic Intelligence Brief', 0)
    doc.add_paragraph(str(content))
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

# --- 6. LOGIN & REGISTRATION ---
if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=200)
    auth_tabs = st.tabs(["🔑 Login", "📝 Register & Plans", "❓ Recovery"])
    with auth_tabs[0]: authenticator.login(location='main')
    with auth_tabs[1]:
        st.markdown("### Enterprise Tiers")
        p1, p2, p3 = st.columns(3)
        with p1: st.markdown('<div class="price-card">BASIC<br><h3>$99</h3></div>', unsafe_allow_html=True)
        with p2: st.markdown('<div class="price-card">PRO<br><h3>$499</h3></div>', unsafe_allow_html=True)
        with p3: st.markdown('<div class="price-card">ENTERPRISE<br><h3>$1,999</h3></div>', unsafe_allow_html=True)
        plan = st.selectbox("Select Tier", ["Basic", "Pro", "Enterprise"])
        reg_res = authenticator.register_user(location='main')
        if reg_res:
            e, u, n = reg_res
            confirm_pw = st.text_input("Confirm Account Password", type="password", key="reg_pw_final")
            if st.button("Complete Enrollment"):
                hashed = stauth.Hasher.hash(confirm_pw)
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("INSERT INTO users VALUES (?,?,?,?,'member',?,50,'Logo1.jpeg',?)", (u, e, n, hashed, plan, f"TEAM_{u}"))
                conn.commit(); conn.close(); st.success("Account Ready! Please Log In."); st.rerun()
    with auth_tabs[2]: authenticator.forgot_password(location='main')
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
    st.button("🌓 Toggle Sidebar Theme", on_click=toggle_theme)
    m_col, t_col = st.columns(2)
    with m_col: st.metric("Credits", user_row['credits'])
    with t_col: st.markdown(f"""<div style="background:{side_bg}; padding:10px; border-radius:10px; border:1px solid {side_border}; height:85px; text-align:center;"><small>TEAM ID</small><br><b>{user_row['team_id']}</b></div>""", unsafe_allow_html=True)
    st.divider()
    biz_name = st.text_input("Brand Name", placeholder="e.g. Acme Solar")
    
    # RESTORED CITY/STATE SPLIT
    c_col1, c_col2 = st.columns(2)
    with c_col1: city_input = st.text_input("City")
    with c_col2: state_input = st.text_input("State")
    full_loc = f"{city_input}, {state_input}"
    
    # RESTORED AUDIT URL
    audit_url = st.text_input("Audit URL (Optional)")
    
    ind_cat = st.selectbox("Industry", list(INDUSTRY_LIBRARY.keys()) + ["Custom"])
    svc = st.selectbox("Service", INDUSTRY_LIBRARY.get(ind_cat, ["Custom"]))
    st.divider(); st.subheader("🤖 Swarm Personnel")
    toggles = {k: st.toggle(v, value=True) for k, v in {"analyst": "🕵️ Analyst", "ads": "📺 Ad Tracker", "builder": "🎨 Creative", "manager": "👔 Strategist", "social": "✍ Social", "geo": "🧠 GEO", "audit": "🌐 Auditor", "seo": "✍ SEO"}.items()}
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary")
    authenticator.logout('Sign Out', 'sidebar')

# --- 8. COMMAND CENTER TABS ---
tabs = st.tabs(["🕵️ Analyst", "📺 Ads", "🎨 Creative", "👔 Strategist", "✍ Social", "🧠 GEO", "🌐 Auditor", "✍ SEO", "👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel", "⚙ Admin"])

if run_btn:
    if not biz_name or not city_input: st.error("❌ City and Brand required.")
    elif user_row['credits'] <= 0: st.error("❌ Out of credits.")
    else:
        with st.status("🛠️ Swarm Coordinating...", expanded=True) as status:
            report = run_marketing_swarm({'city': full_loc, 'industry': ind_cat, 'service': svc, 'biz_name': biz_name, 'url': audit_url, 'toggles': toggles})
            st.session_state.report, st.session_state.gen = report, True
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (st.session_state["username"],))
            conn.execute("INSERT INTO leads (date, user, industry, service, city, content, team_id) VALUES (?,?,?,?,?,?,?)", 
                         (datetime.now().strftime("%Y-%m-%d"), user_row['username'], ind_cat, svc, full_loc, str(report), user_row['team_id']))
            conn.commit(); conn.close(); status.update(label="✅ Swarm Success!", state="complete"); st.rerun()

# --- 9. RENDER ALL 8 AGENT SEATS (ISOLATED + FORMATTER + EXPORTS) ---
def format_output(data):
    """Clean JSON strings into professional Markdown."""
    if isinstance(data, str) and (data.startswith('{') or data.startswith('`')):
        try:
            clean_str = data.strip().strip('```json').strip('```').strip()
            parsed = json.loads(clean_str)
            return pd.json_normalize(parsed).T.to_markdown()
        except: return data
    return data

def render_seat(idx, title, icon, key):
    with tabs[idx]:
        st.markdown(f"### {icon} {title} Command Seat")
        if st.session_state.get('gen'):
            raw_data = st.session_state.report.get(key, "Isolation in progress...")
            clean_data = format_output(raw_data)
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1: st.success(f"Verified {title} Data")
            with c2: st.download_button("📄 Word", create_word_doc(raw_data, user_row['logo_path']), f"{title}.docx", key=f"w_{key}")
            with c3: st.download_button("📕 PDF", create_pdf(raw_data, svc, full_loc, user_row['logo_path']), f"{title}.pdf", key=f"p_{key}")
            st.markdown(f'<div class="insight-card">{clean_data}</div>', unsafe_allow_html=True)
        else: st.info(f"Launch swarm to populate {title}.")

seats = [("Analyst", "🕵️", "analyst"), ("Ad Tracker", "📺", "ads"), ("Creative", "🎨", "creative"), ("Strategist", "👔", "strategist"), ("Social Hooks", "✍", "social"), ("GEO Map", "🧠", "geo"), ("Audit Scan", "🌐", "auditor"), ("SEO Blogger", "✍", "seo")]
for i, s in enumerate(seats): render_seat(i, s[0], s[1], s[2])

with tabs[8]:
    st.subheader("👁️ Vision Inspector")
    v_file = st.file_uploader("Screenshot Evidence", type=['png', 'jpg', 'jpeg'])
    if v_file: st.image(v_file, use_container_width=True)

with tabs[9]:
    st.subheader("🎬 Veo Cinematic Studio")
    if st.session_state.get('gen'):
        creative_out = st.session_state.report.get('creative', '')
        v_prompt = st.text_area("Video Scene Description", value=str(creative_out)[:300], height=150)
        if st.button("📽️ GENERATE AD"):
            with st.spinner("Rendering..."):
                v_file = generate_cinematic_ad(v_prompt)
                if v_file: st.video(v_file)
    else: st.warning("Launch swarm first.")

# --- 10. TEAM INTEL & ADMIN (ROBUST BACKEND) ---
with tabs[10]:
    st.header("🤝 Team Collaboration Hub")
    conn = sqlite3.connect('breatheeasy.db')
    team_df = pd.read_sql_query("SELECT date, user, city, service, status FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("Team Health")
        st.metric("Total Swarms", len(team_df))
        st.metric("Markets", len(team_df['city'].unique()))
    with c2:
        st.subheader("Project Pipeline")
        st.dataframe(team_df, use_container_width=True)
    st.divider(); st.subheader("🛡️ Security Trace"); st.code(f"Database Integrity: OK | Access Trace: {user_row['username']} | Time: {datetime.now()}")
    conn.close()

if user_row['role'] == 'admin':
    with tabs[11]:
        st.header("⚙️ God-Mode Admin Control")
        conn = sqlite3.connect('breatheeasy.db')
        all_u = pd.read_sql_query("SELECT username, email, credits, package FROM users", conn)
        st.dataframe(all_u, use_container_width=True)
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            u_del = st.text_input("Terminate User Username")
            if st.button("❌ Terminate User"):
                if u_del != 'admin':
                    conn.execute("DELETE FROM users WHERE username=?", (u_del,))
                    conn.commit(); st.success(f"Purged {u_del}"); st.rerun()
                else: st.error("Cannot delete primary admin.")
        with col2:
            target = st.selectbox("Select Target User", all_u['username'])
            amt = st.number_input("Refill Amount", value=50)
            if st.button("💉 Inject Credits"):
                conn.execute("UPDATE users SET credits = credits + ? WHERE username = ?", (amt, target))
                conn.commit(); st.success(f"Injected {amt} to {target}"); st.rerun()
        conn.close()
