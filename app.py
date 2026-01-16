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

# --- 0. HELPERS & SYSTEM HEALTH ---

def check_system_health():
    """Sprint 5: Verifies critical infrastructure status"""
    health = {
        "Gemini 2.0": os.getenv("GOOGLE_API_KEY") is not None,
        "Serper API": os.getenv("SERPER_API_KEY") is not None,
        "Database": os.path.exists("breatheeasy.db"),
    }
    return health

def is_verified(username):
    """Checks if the user has completed the email verification gate"""
    conn = sqlite3.connect('breatheeasy.db')
    res = conn.execute("SELECT verified FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return res[0] == 1 if res else False

def trigger_verification(email):
    """UI Trigger for unverified accounts"""
    st.warning("⚠️ Account Not Verified")
    st.info(f"Verification link sent to: {email}")
    if st.button("Simulate Email Link Click (Demo Mode)", use_container_width=True):
        conn = sqlite3.connect('breatheeasy.db')
        conn.execute("UPDATE users SET verified = 1 WHERE username = ?", (st.session_state["username"],))
        conn.commit()
        conn.close()
        st.success("Email Verified! Reloading...")
        st.rerun()

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

# --- 1. SYSTEM INITIALIZATION ---
if 'theme' not in st.session_state: st.session_state.theme = 'light'
if 'gen' not in st.session_state: st.session_state.gen = False
if 'report' not in st.session_state: st.session_state.report = {}

st.set_page_config(page_title="TechInAdvance AI | Enterprise Command", page_icon="Logo1.jpeg", layout="wide")

# --- 2. EXECUTIVE UI CSS ---
sidebar_color = "#2563EB"
st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFCF0; color: #1E293B; }}
    .guide-box {{ background: #F1F5F9; padding: 15px; border-radius: 8px; border: 1px dashed {sidebar_color}; font-size: 0.85rem; margin-bottom: 20px; color: #475569; }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800; height: 3.2em; }}
    .kanban-card {{ background: white; padding: 18px; border-radius: 10px; margin-bottom: 12px; border-left: 5px solid {sidebar_color}; box-shadow: 0px 2px 6px rgba(0,0,0,0.04); }}
    .kanban-header {{ font-weight: 900; text-align: center; color: {sidebar_color}; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 1.5px; font-size: 0.9rem; border-bottom: 2px solid {sidebar_color}33; padding-bottom: 8px; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, plan TEXT, credits INTEGER DEFAULT 0, logo_path TEXT, team_id TEXT, verified INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT, team_id TEXT, status TEXT DEFAULT 'Discovery')''')
    c.execute('''CREATE TABLE IF NOT EXISTS master_audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, user TEXT, action_type TEXT, target_biz TEXT, location TEXT, credit_cost INTEGER, status TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- 4. AUTHENTICATION & ENROLLMENT SUITE (STABILIZED) ---
def get_db_creds():
    try:
        conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
        df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
        conn.close()
        # Convert DB rows into the dictionary format required by stauth
        return {
            'usernames': {
                row['username']: {
                    'email': row['email'], 
                    'name': row['name'], 
                    'password': row['password']
                } for _, row in df.iterrows()
            }
        }
    except Exception as e:
        st.error(f"Database Connection Error: {e}")
        return {'usernames': {}}

# Initialize Authenticator with credentials from the DB
db_credentials = get_db_creds()
authenticator = stauth.Authenticate(
    db_credentials, 
    st.secrets['cookie']['name'], 
    st.secrets['cookie']['key'], 
    30
)

# --- THE LOGIN GATE ---
# Check if the user is already logged in via cookie
if st.session_state.get("authentication_status") is None or st.session_state.get("authentication_status") is False:
    st.image("Logo1.jpeg", width=200)
    
    # Create the Login/Register/Recovery Interface
    auth_tabs = st.tabs(["🔑 Login", "📝 Enrollment", "🤝 Join Team", "❓ Recovery"])
    
    with auth_tabs[0]: 
        # This is the actual login form
        name, authentication_status, username = authenticator.login(location='main')
    
    with auth_tabs[1]:
        st.subheader("Select Your Growth Tier")
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown('<div class="price-card"><h3>Basic</h3><h2>$99</h2><p>50 Credits</p></div>', unsafe_allow_html=True)
        with c2: st.markdown('<div class="price-card" style="border-color:#7C3AED;"><h3>Pro</h3><h2>$249</h2><p>150 Credits</p></div>', unsafe_allow_html=True)
        with c3: st.markdown('<div class="price-card"><h3>Enterprise</h3><h2>$499</h2><p>Unlimited*</p></div>', unsafe_allow_html=True)
        
        # Enrollment Logic
        res = authenticator.register_user(location='main')
        if res:
            st.success("Registration successful! Please head to the Login tab.")

    with auth_tabs[2]:
        st.subheader("Team Access")
        st.text_input("Enter Team ID")
        st.button("Request Join")

    with auth_tabs[3]:
        st.subheader("Account Recovery")
        authenticator.forgot_password(location='main')
        authenticator.forgot_username(location='main')

    # IMPORTANT: If not authenticated, stop the script here so 
    # the rest of the app (sidebar/tabs) doesn't try to load.
    if st.session_state.get("authentication_status") is False:
        st.error('Username/password is incorrect')
    elif st.session_state.get("authentication_status") is None:
        st.warning('Please enter your username and password')
    
    st.stop() 

# --- IF WE REACH HERE, THE USER IS LOGGED IN ---

    st.stop() # Prevents rest of app from loading until login is successful
# --- 5. LOGGED-IN DATA FETCH ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()
is_admin = user_row['role'] == 'admin'

# --- 6. EXPORT HELPERS ---
def create_word_doc(content, title):
    doc = Document()
    doc.add_heading(f'Intelligence Brief: {title}', 0)
    doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f'{service} Strategy - {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 7, txt=str(content).encode('latin-1', 'ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

def generate_cinematic_ad(prompt):
    try: return st.video_generation(prompt=f"Elite cinematic marketing ad: {prompt}. 4k.", aspect_ratio="16:9")
    except Exception as e: st.error(f"Veo Error: {e}"); return None

# --- 7. SIDEBAR COMMAND CONSOLE ---
with st.sidebar:
    health = check_system_health()
    st.caption(f"{'🟢' if all(health.values()) else '🔴'} **SYSTEM STATUS**")
    st.image(user_row['logo_path'], width=120)
    st.metric("Credits Available", user_row['credits'])
    
    biz_name = st.text_input("Brand Name", placeholder="Acme Solar")
    location_data = get_geo_data()
    selected_state = st.selectbox("🎯 Target State", sorted(list(location_data.keys())))
    selected_city = st.selectbox(f"🏙️ Select City", sorted(location_data[selected_state]))
    full_loc = f"{selected_city}, {selected_state}"
    
    user_requirements = st.text_area("Custom Directives", key="agent_reqs")
    audit_url = st.text_input("Audit URL (Optional)")
    ind_cat = st.selectbox("Industry", ["HVAC", "Medical", "Solar", "Legal", "Custom"])
    final_ind = ind_cat
    svc = st.text_input("Service Type")
    
    toggles = {k: st.toggle(v, value=True) for k, v in {
        "analyst": "🕵️ Analyst", "ads": "📺 Ad Tracker", "builder": "🎨 Creative", 
        "manager": "👔 Strategist", "social": "✍ Social", "geo": "🧠 GEO", 
        "audit": "🌐 Auditor", "seo": "✍ SEO"}.items()}
    
    if is_verified(st.session_state["username"]):
        run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
    else:
        trigger_verification(user_row['email'])
        run_btn = False 

    authenticator.logout('Sign Out', 'sidebar')

# --- 8. SWARM EXECUTION ENGINE ---
if run_btn:
    if not biz_name or not full_loc:
        st.error("❌ Identification required.")
    elif user_row['credits'] <= 0:
        st.error("❌ Out of credits.")
    else:
        st.session_state.report = {} 
        st.session_state.gen = False
        with st.status("🛠️ Coordinating Swarm Agents...", expanded=True) as status:
            try:
                progress_bar = st.progress(10, text="🕵️ Phase 1: Market Discovery...")
                report_data = run_marketing_swarm({
                    'city': full_loc, 'industry': final_ind, 'service': svc, 
                    'biz_name': biz_name, 'url': audit_url, 'toggles': toggles, 'custom_reqs': user_requirements 
                })
                st.session_state.report = report_data
                st.session_state.gen = True 
                
                # DB Logging
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
                conn.execute("INSERT INTO master_audit_logs (timestamp, user, action_type, target_biz, location, credit_cost, status) VALUES (?,?,?,?,?,?,?)", 
                             (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_row['username'], "OMNI_SWARM_LAUNCH", biz_name, full_loc, 1, "SUCCESS"))
                conn.commit(); conn.close()
                
                progress_bar.progress(100, text="✅ Intelligence Synchronized.")
                status.update(label="🚀 Swarm Complete!", state="complete")
                st.rerun()
            except Exception as e:
                st.error(f"Backend Error: {e}")

# --- 9. MULTIMODAL COMMAND CENTER (TAB RENDERING) ---

# Define the standard agent map for dynamic looping
agent_map = [
    ("🕵️ Analyst", "analyst"), ("🎨 Creative", "creative"), 
    ("👔 Strategist", "strategist"), ("📱 Social", "social"), 
    ("📍 GEO", "geo"), ("🌐 Auditor", "auditor"), ("✍ SEO", "seo")
]

# Construct all tab labels
all_tab_labels = ["📖 Guide"] + [a[0] for a in agent_map] + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_admin: all_tab_labels.append("⚙ Admin")

# Initialize Tabs
tabs_list = st.tabs(all_tab_labels)
TAB = {name: tabs_list[i] for i, name in enumerate(all_tab_labels)}

# A. Guide Tab
with TAB["📖 Guide"]:
    st.header("📖 Agent Intelligence Manual")
    st.info("The Omni-Swarm engine coordinates specialized AI agents to engineer growth.")
    st.markdown("### 🕵️ Intelligence Cluster\n- **Analyst:** Market Entry Gaps.\n- **Ad Tracker:** Competitor Hooks.")

# B. Dynamic Agent Tabs (Filtered by Session State)
for i, (title, report_key) in enumerate(agent_map):
    with TAB[title]:
        st.subheader(f"{title} Command Seat")
        if not st.session_state.gen:
            st.info(f"Launch the Omni-Swarm to populate the {title} seat.")
        else:
            content = st.session_state.report.get(report_key, "Intelligence not available.")
            edited = st.text_area(f"Refine {title} Output", value=str(content), height=350, key=f"edit_{report_key}")
            c1, c2 = st.columns(2)
            with c1: st.download_button("📄 Word Brief", create_word_doc(edited, title), f"{title}_Brief.docx", key=f"w_{report_key}")
            with c2: st.download_button("📕 PDF Report", create_pdf(edited, svc, full_loc), f"{title}_Report.pdf", key=f"p_{report_key}")

# C. Specialty Tabs
with TAB["👁️ Vision"]:
    st.subheader("👁️ Vision Inspector")
    if st.session_state.gen:
        st.markdown(st.session_state.report.get('vision_intel', "No Vision data found."))
    v_file = st.file_uploader("Upload Forensic Evidence", type=['png','jpg','jpeg'])
    if v_file: st.image(v_file, caption="Target Asset")

with TAB["🎬 Veo Studio"]:
    st.subheader("🎬 Veo Cinematic Studio")
    if st.session_state.gen:
        v_prompt = st.text_area("Video Scene Prompt", value=str(st.session_state.report.get('creative', ''))[:500])
        if st.button("📽️ GENERATE CINEMATIC AD"):
            v_vid = generate_cinematic_ad(v_prompt)
            if v_vid: st.video(v_vid)
    else: st.warning("Launch Swarm to generate creative context.")

with TAB["🤝 Team Intel"]:
    st.header("🤝 Global Pipeline Kanban")
    conn = sqlite3.connect('breatheeasy.db')
    team_df = pd.read_sql_query("SELECT * FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
    st.dataframe(team_df, use_container_width=True)
    conn.close()

# D. God-Mode Admin Tab (Stabilized)
if is_admin:
    with TAB["⚙ Admin"]:
        st.header("⚙️ God-Mode Management")
        st.warning("⚡ Root Access: Viewing global system infrastructure.")
        conn = sqlite3.connect('breatheeasy.db')
        
        # Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Global Swarms", pd.read_sql_query("SELECT COUNT(*) FROM master_audit_logs", conn).iloc[0,0])
        m2.metric("Registered Users", pd.read_sql_query("SELECT COUNT(*) FROM users", conn).iloc[0,0])
        m3.metric("Integrity", "Verified")

        # Audit Table
        audit_df = pd.read_sql_query("SELECT timestamp, user, action_type, target_biz, location, status FROM master_audit_logs ORDER BY id DESC LIMIT 100", conn)
        st.dataframe(audit_df, use_container_width=True, hide_index=True, column_config={
            "status": st.column_config.SelectboxColumn("Status", options=["SUCCESS", "FAILED", "PENDING"])
        })
        
        # Credit Injection
        st.subheader("👤 Credit Injection")
        all_u = pd.read_sql_query("SELECT username FROM users", conn)['username'].tolist()
        target_u = st.selectbox("Select User", all_u)
        amt = st.number_input("Amount", value=10)
        if st.button("Inject Credits"):
            conn.execute("UPDATE users SET credits = credits + ? WHERE username = ?", (amt, target_u))
            conn.commit(); st.success("Credits Added."); st.rerun()
        conn.close()
