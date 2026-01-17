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

# --- SECTION #0: PERFORMANCE HELPERS & GEO-CACHING ---

@st.cache_data(ttl=3600)
def get_geo_data():
    return {
        "Alabama": ["Birmingham", "Huntsville", "Mobile"],
        "Arizona": ["Phoenix", "Scottsdale", "Tucson"],
        "California": ["Los Angeles", "San Francisco", "San Diego"],
        "Florida": ["Miami", "Orlando", "Tampa"],
        "Illinois": ["Chicago", "Naperville", "Plainfield"],
        "Texas": ["Austin", "Dallas", "Houston"],
    }

def check_system_health():
    health = {
        "Gemini 2.0": os.getenv("GOOGLE_API_KEY") is not None,
        "Serper API": os.getenv("SERPER_API_KEY") is not None,
        "Database": os.path.exists("breatheeasy.db"),
    }
    return health

def is_verified(username):
    conn = sqlite3.connect('breatheeasy.db')
    res = conn.execute("SELECT verified FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return res[0] == 1 if res else False

def toggle_theme():
    if 'theme' not in st.session_state:
        st.session_state.theme = 'light'
    st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'

def update_account_settings(username, new_email, new_name):
    conn = sqlite3.connect('breatheeasy.db')
    conn.execute("UPDATE users SET email = ?, name = ? WHERE username = ?", (new_email, new_name, username))
    conn.commit(); conn.close()
    st.success("Enterprise Profile Updated Successfully!")

# --- EXPORT HELPERS ---
def export_word(content, title):
    doc = Document(); doc.add_heading(title, 0); doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def export_pdf(content, title):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, title, 0, 1, 'C')
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 7, txt=str(content).encode('latin-1','ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

# --- 1. INITIALIZATION & DB ---
st.set_page_config(page_title="TechInAdvance AI | Command", page_icon="Logo1.jpeg", layout="wide")

def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, plan TEXT, credits INTEGER, logo_path TEXT, team_id TEXT, verified INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, city TEXT, service TEXT, status TEXT DEFAULT "Discovery", team_id TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS master_audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, user TEXT, action_type TEXT, target_biz TEXT, location TEXT, credit_cost INTEGER, status TEXT)')
    admin_pw = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users VALUES ('admin','admin@techinadvance.ai','Admin',?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001',1)", (admin_pw,))
    conn.commit(); conn.close()

init_db()

# --- 2. AUTHENTICATION ---
def get_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
    conn.close()
    return {'usernames': {r['username']: {'email':r['email'], 'name':r['name'], 'password':r['password']} for _,r in df.iterrows()}}

if 'authenticator' not in st.session_state:
    st.session_state.authenticator = stauth.Authenticate(get_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

authenticator = st.session_state.authenticator

if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=180)
    auth_tabs = st.tabs(["🔑 Login", "📝 Sign Up", "🤝 Join Team", "❓ Forget Password"])
    with auth_tabs[0]: authenticator.login(location='main')
    with auth_tabs[1]:
        st.subheader("Select Enterprise Package")
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown('<div class="price-card"><h3>Basic</h3><h2>$99</h2><p>50 Credits/mo</p></div>', unsafe_allow_html=True)
        with c2: st.markdown('<div class="price-card" style="border-color:#7C3AED;"><h3>Pro</h3><h2>$249</h2><p>150 Credits/mo</p></div>', unsafe_allow_html=True)
        with c3: st.markdown('<div class="price-card"><h3>Enterprise</h3><h2>$499</h2><p>Unlimited</p></div>', unsafe_allow_html=True)
        if authenticator.register_user(location='main'): st.success("Sign up complete!")
    with auth_tabs[3]: authenticator.forgot_password(location='main')
    st.stop()

# --- 3. SESSION CONTEXT ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()
is_admin = (user_row['role'] == 'admin')

# --- 4. SIDEBAR (DYNAMIC) ---
with st.sidebar:
    health = check_system_health()
    col_h, col_t = st.columns([2, 1])
    with col_h: st.caption(f"{'🟢' if all(health.values()) else '🔴'} **SYSTEM HEARTBEAT**")
    with col_t: 
        if st.button("🌓"): toggle_theme()

    st.image(user_row['logo_path'], width=120)
    st.metric("Credits Available", user_row['credits'])
    st.divider()

    biz_name = st.text_input("🏢 Brand Name", placeholder="Acme Solar")
    industry_map = {
        "Residential Services": ["HVAC", "Roofing", "Solar", "Plumbing"],
        "Medical & Health": ["Dental", "Plastic Surgery", "Veterinary"],
        "Legal & Professional": ["Family Law", "Personal Injury", "CPA"],
        "Other (Manual Entry)": []
    }
    selected_ind_cluster = st.selectbox("📂 Industry Cluster", sorted(list(industry_map.keys())))
    
    if selected_ind_cluster == "Other (Manual Entry)":
        final_ind = st.text_input("Type Industry Name", key="custom_ind")
        final_service = st.text_input("Type Specific Service", key="custom_svc")
    else:
        final_ind = selected_ind_cluster
        service_list = industry_map[selected_ind_cluster]
        final_service = st.selectbox("🛠️ Specific Service", service_list)

    geo_dict = get_geo_data()
    selected_state = st.selectbox("🎯 Target State", sorted(geo_dict.keys()))
    city_list = sorted(geo_dict[selected_state]) + ["Other (Manual City)"]
    selected_city = st.selectbox(f"🏙️ Select City ({selected_state})", city_list)
    
    if selected_city == "Other (Manual City)":
        custom_city = st.text_input(f"Type City in {selected_state}", key="manual_city_in_state")
        full_loc = f"{custom_city}, {selected_state}"
    else:
        full_loc = f"{selected_city}, {selected_state}"

    st.divider()
    # CRITICAL: This defines the variable used in Section 5
    agent_info = st.text_area("✍️ Strategic Directives", placeholder="e.g. Focus on luxury clients...", key="agent_directives_box")

    st.subheader("🤖 Swarm Personnel")
    agent_config = {"analyst": "🕵️ Analyst", "ads": "📺 Ad Tracker", "creative": "🎨 Creative", "strategist": "👔 Strategist", "social": "📱 Social", "geo": "📍 GEO", "audit": "🌐 Auditor", "seo": "✍ SEO"}
    toggles = {k: st.toggle(v, value=True, key=f"tg_{k}") for k, v in agent_config.items()}

    st.divider()
    if is_verified(st.session_state["username"]):
        run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
    else:
        st.error("🛡️ Verification Locked")
        if st.button("🔓 DEMO: Verify Now", use_container_width=True):
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE users SET verified=1 WHERE username=?", (user_row['username'],))
            conn.commit(); conn.close(); st.success("Verified!"); st.rerun()
        run_btn = False

    authenticator.logout('🔒 Sign Out', 'sidebar')

# --- 5. EXECUTION ---
if run_btn:
    with st.status("🛠️ Coordinating Swarm Agents...", expanded=True) as status:
        # Pass all dynamic variables
        report = run_marketing_swarm({'city': full_loc, 'biz_name': biz_name, 'service': final_service, 'directives': agent_info})
        st.session_state.report = report
        st.session_state.gen = True
        conn = sqlite3.connect('breatheeasy.db')
        conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
        conn.execute("INSERT INTO master_audit_logs (timestamp, user, action_type, target_biz, location, status) VALUES (?,?,?,?,?,?)", 
                     (datetime.now().strftime("%Y-%m-%d %H:%M"), user_row['username'], "SWARM", biz_name, full_loc, "SUCCESS"))
        conn.commit(); conn.close(); st.rerun()

# --- 6. COMMAND CENTER TABS ---
# (Rest of UI Tabs logic following the same pattern)
tab_labels = ["📖 Guide", "🕵️ Analyst", "📺 Ads", "🎨 Creative", "👔 Strategist", "📱 Social", "📍 GEO", "🌐 Auditor", "✍ SEO", "👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_admin: tab_labels.append("⚙ Admin")

tabs_obj = st.tabs(tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(tab_labels)}

# ... (Insert your TAB rendering logic here)
