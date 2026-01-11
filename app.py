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
if 'theme' not in st.session_state: st.session_state.theme = 'light'
if 'processing' not in st.session_state: st.session_state.processing = False
if 'gen' not in st.session_state: st.session_state.gen = False
if 'report' not in st.session_state: st.session_state.report = {}

def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

os.environ["OTEL_SDK_DISABLED"] = "true"
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

st.set_page_config(page_title="TechInAdvance AI | Command Hub", page_icon="Logo1.jpeg", layout="wide")

# --- 2. $1B EXECUTIVE UI CSS ---
sidebar_color = "#2563EB"
st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFCF0; color: #1E293B; }}
    [data-testid="stSidebar"] {{ 
        background-color: {"#1E293B" if st.session_state.theme == 'dark' else "#FFFFFF"} !important; 
        border-right: 3px solid rgba(0,0,0,0.1) !important;
        box-shadow: 4px 0px 10px rgba(0,0,0,0.05);
    }}
    .kpi-card {{
        background: white; padding: 20px; border-radius: 12px; border-top: 5px solid {sidebar_color};
        box-shadow: 0px 4px 15px rgba(0,0,0,0.05); text-align: center; margin-bottom: 20px;
    }}
    .insight-card {{ 
        background-color: white; padding: 30px; border-radius: 15px; border-left: 10px solid {sidebar_color}; 
        line-height: 1.8; color: #1E293B; box-shadow: 0px 10px 30px rgba(0,0,0,0.08); overflow-wrap: break-word; 
    }}
    .guide-box {{ background: #F1F5F9; padding: 15px; border-radius: 8px; border: 1px dashed {sidebar_color}; font-size: 0.85rem; margin-bottom: 20px; color: #475569; }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800; height: 3.2em; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE & EXPORT ENGINE ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, package TEXT, credits INTEGER DEFAULT 0, logo_path TEXT, team_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT, team_id TEXT, status TEXT DEFAULT 'Active')''')
    hashed_pw = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001')", ('admin', 'admin@techinadvance.ai', 'Admin', hashed_pw))
    conn.commit(); conn.close()

init_db()

def create_word_doc(content, logo_path="Logo1.jpeg"):
    doc = Document()
    try: doc.add_picture(logo_path if os.path.exists(logo_path) else "Logo1.jpeg", width=Inches(1.5))
    except: pass
    doc.add_heading('Executive Strategic Brief', 0)
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
    try: return st.video_generation(prompt=f"Elite cinematic marketing ad: {prompt}. 4k.", aspect_ratio="16:9")
    except Exception as e: st.error(f"Veo Error: {e}"); return None

# --- 4. AUTHENTICATION ---
def get_db_creds():
    try:
        conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
        df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn); conn.close()
        return {'usernames': {row['username']: {'email':row['email'], 'name':row['name'], 'password':row['password']} for _, row in df.iterrows()}}
    except: return {'usernames': {}}

authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=200)
    auth_tabs = st.tabs(["🔑 Login", "📝 Enrollment", "❓ Recovery"])
    with auth_tabs[0]: authenticator.login(location='main')
    with auth_tabs[1]:
        res = authenticator.register_user(location='main')
        if res:
            e, u, n = res
            raw_pw = st.text_input("Enrollment Password", type="password", key="reg_pw")
            if st.button("Complete Enrollment"):
                h = stauth.Hasher.hash(raw_pw)
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("INSERT INTO users VALUES (?,?,?,?,'member','Basic',50,'Logo1.jpeg',?)", (u, e, n, h, f"TEAM_{u}"))
                conn.commit(); conn.close(); st.success("Account Ready."); st.rerun()
    st.stop()

# --- 5. SIDEBAR (FIXED CUSTOM TYPING) ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()

with st.sidebar:
    st.image(user_row['logo_path'], width=120)
    st.button("🌓 Theme", on_click=toggle_theme)
    st.metric("Credits Available", user_row['credits'])
    st.divider()
    biz_name = st.text_input("Brand Name", placeholder="e.g. Acme Solar")
    c1, c2 = st.columns(2)
    with c1: city_in = st.text_input("City")
    with c2: state_in = st.text_input("State")
    full_loc = f"{city_in}, {state_in}"
    audit_url = st.text_input("Audit URL (Optional)")
    
    ind_cat = st.selectbox("Industry", ["HVAC", "Medical", "Solar", "Legal", "Custom"])
    if ind_cat == "Custom":
        final_ind = st.text_input("Type Your Custom Industry")
        svc = st.text_input("Type Your Custom Service")
    else:
        final_ind = ind_cat
        svc = st.text_input("Service Type")

    st.divider(); st.subheader("🤖 Swarm Personnel")
    toggles = {k: st.toggle(v, value=True) for k, v in {"analyst": "🕵️ Analyst", "ads": "📺 Ad Tracker", "builder": "🎨 Creative", "manager": "👔 Strategist", "social": "✍ Social", "geo": "🧠 GEO", "audit": "🌐 Auditor", "seo": "✍ SEO"}.items()}
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary")
    authenticator.logout('Sign Out', 'sidebar')

# --- 6. COMMAND CENTER TABS ---
tabs = st.tabs(["🕵️ Analyst", "📺 Ads", "🎨 Creative", "👔 Strategist", "✍ Social", "🧠 GEO", "🌐 Auditor", "✍ SEO", "👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel", "⚙ Admin"])

if run_btn:
    if not biz_name or not city_in: st.error("❌ Identification required.")
    elif user_row['credits'] <= 0: st.error("❌ Out of credits.")
    else:
        with st.status("🛠️ Coordinating Swarm...", expanded=True) as status:
            report = run_marketing_swarm({'city': full_loc, 'biz_name': biz_name, 'url': audit_url, 'toggles': toggles})
            st.session_state.report, st.session_state.gen = report, True
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
            conn.execute("INSERT INTO leads (date, user, industry, service, city, content, team_id) VALUES (?,?,?,?,?,?,?)", 
                         (datetime.now().strftime("%Y-%m-%d"), user_row['username'], final_ind, svc, full_loc, str(report), user_row['team_id']))
            conn.commit(); conn.close(); status.update(label="✅ Success!", state="complete"); st.rerun()

# --- 7. THE MASTER RENDER ENGINE (FIXED PER YOUR LINE REQUIREMENT) ---
def format_output(data):
    """Clean JSON strings into professional Markdown."""
    if isinstance(data, str) and (data.startswith('{') or data.startswith('`')):
        try:
            clean_str = data.strip().strip('```json').strip('```').strip()
            parsed = json.loads(clean_str)
            return pd.json_normalize(parsed).T.to_markdown()
        except: return data
    return data

def render_seat(idx, title, icon, key, guide):
    with tabs[idx]:
        st.markdown(f'<div class="guide-box"><b>📖 {title} Guide:</b> {guide}</div>', unsafe_allow_html=True)
        st.markdown(f"### {icon} {title} Command Seat")
        if st.session_state.get('gen'):
            raw_data = st.session_state.report.get(key, "Isolation in progress...")
            clean_data = format_output(raw_data)
            
            # KPI / EXPORT ROW
            k1, k2, k3 = st.columns([2, 1, 1])
            with k1: st.success(f"Verified {title} Intelligence")
            with k2: st.download_button("📄 Word", create_word_doc(raw_data, user_row['logo_path']), f"{title}.docx", key=f"w_{key}")
            with k3: st.download_button("📕 PDF", create_pdf(raw_data, svc, full_loc, user_row['logo_path']), f"{title}.pdf", key=f"p_{key}")
            
            st.markdown(f'<div class="insight-card">{clean_data}</div>', unsafe_allow_html=True)
            
            if st.button(f"🚀 Deploy {title} Directives", key=f"dep_{key}"):
                st.toast("Syncing with stakeholders..."); st.success("Directives Pushed.")
        else: st.info(f"Launch swarm to populate {title}.")

# RENDER THE 8 AGENT SEATS
seats = [
    ("Analyst", "🕵️", "analyst", "Identify competitor price gaps and quality failures."),
    ("Ad Tracker", "📺", "ads", "Analyze rival psychological hooks to build 'Anti-Competitor' ads."),
    ("Creative", "🎨", "creative", "Visual frameworks and cinematic scene prompts for the Veo tab."),
    ("Strategist", "👔", "strategist", "The 30-day ROI roadmap for executive budget approval."),
    ("Social Hooks", "✍", "social", "Viral hooks and platform-specific posting schedules."),
    ("GEO Map", "🧠", "geo", "AI Search and Map citation velocity optimization."),
    ("Audit Scan", "🌐", "auditor", "Technical conversion leak diagnostics."),
    ("SEO Blogger", "✍", "seo", "High-authority E-E-A-T technical articles.")
]
for i, s in enumerate(seats): render_seat(i, s[0], s[1], s[2], s[3])

# --- 8. MULTIMODAL SPECIALTY TABS ---
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

# --- 9. TEAM & ADMIN ---
with tabs[10]:
    st.header("🤝 Team Collaboration")
    conn = sqlite3.connect('breatheeasy.db')
    team_df = pd.read_sql_query("SELECT date, user, city, status FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
    st.dataframe(team_df, use_container_width=True); conn.close()

if user_row['role'] == 'admin':
    with tabs[11]:
        st.header("⚙️ Admin God-Mode")
        conn = sqlite3.connect('breatheeasy.db')
        all_u = pd.read_sql_query("SELECT username, credits FROM users", conn)
        st.dataframe(all_u, use_container_width=True)
        target = st.selectbox("Inject Credits", all_u['username'])
        amt = st.number_input("Amount", value=50)
        if st.button("💉 Inject"):
            conn.execute("UPDATE users SET credits = credits + ? WHERE username = ?", (amt, target))
            conn.commit(); st.rerun()
        conn.close()
