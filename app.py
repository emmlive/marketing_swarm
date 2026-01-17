import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
from datetime import datetime
from io import BytesIO

# --- 0. HELPER FUNCTIONS ---
def toggle_theme():
    if 'theme' not in st.session_state: st.session_state.theme = 'light'
    st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'

# --- 1. SYSTEM INITIALIZATION ---
st.set_page_config(page_title="TechInAdvance AI | Command", page_icon="Logo1.jpeg", layout="wide")

if 'gen' not in st.session_state: st.session_state.gen = False
if 'report' not in st.session_state: st.session_state.report = {}

# --- 2. EXECUTIVE UI CSS (THE LOOK & FEEL) ---
sidebar_color = "#2563EB" # Tech Blue
st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFCF0; color: #1E293B; }}
    [data-testid="stSidebar"] {{ background-color: #FFFFFF !important; border-right: 3px solid rgba(0,0,0,0.1) !important; }}
    .price-card {{ 
        background: white; padding: 25px; border-radius: 15px; border: 2px solid {sidebar_color}; 
        text-align: center; margin-bottom: 15px; box-shadow: 0px 4px 10px rgba(0,0,0,0.05); 
    }}
    .deploy-guide {{ 
        background: rgba(37, 99, 235, 0.08); padding: 18px; border-radius: 12px; 
        border-left: 6px solid {sidebar_color}; margin-bottom: 25px; 
    }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800; height: 3.2em; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    # User Table
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, 
                  role TEXT, plan TEXT, credits INTEGER, logo_path TEXT, 
                  team_id TEXT, verified INTEGER DEFAULT 0)''')
    # Master Audit Log
    c.execute('''CREATE TABLE IF NOT EXISTS master_audit_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, user TEXT, 
                  action_type TEXT, target_biz TEXT, location TEXT, status TEXT)''')
    
    # Root Admin Auto-Creation
    admin_pw = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users VALUES ('admin','admin@tech.ai','Admin',?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001',1)", (admin_pw,))
    conn.commit()
    conn.close()

init_db()

# --- 4. CORE DEFINITIONS (PREVENTS NAME-ERRORS) ---
agent_map = [
    ("🕵️ Analyst", "analyst"), ("📺 Ads", "ads"), ("🎨 Creative", "creative"), 
    ("👔 Strategist", "strategist"), ("📱 Social", "social"), ("📍 GEO", "geo"), 
    ("🌐 Auditor", "audit"), ("✍ SEO", "seo")
]

# --- 5. THE SIDEBAR SKELETON ---
with st.sidebar:
    col_h, col_t = st.columns([2, 1])
    with col_h: st.caption("🟢 **SYSTEM ONLINE**")
    with col_t: 
        if st.button("🌓"): toggle_theme()
    
    st.image("Logo1.jpeg", width=120) # Ensure this file is in your folder
    st.divider()
    
    st.subheader("Configuration")
    biz_name = st.text_input("Brand Name", placeholder="Acme Solar")
    full_loc = st.text_input("Target Location", placeholder="Miami, FL")
    
    st.divider()
    st.info("Log in to unlock Swarm Command.")

# --- 6. MAIN UI TABS (SKELETON) ---
st.title("Enterprise Swarm Command")
tab_labels = ["📖 Guide"] + [a[0] for a in agent_map] + ["🤝 Team Intel"]
tabs = st.tabs(tab_labels)

with tabs[0]:
    st.header("📖 Agent Intelligence Manual")
    st.write("Welcome to your Enterprise SaaS. Please log in to initiate market forensics.")

# ---------------------------------------------------------
# NEXT STEP: Sprint 2 (Authentication & Sign-Up Logic)
# ---------------------------------------------------------

# --- SECTION #2: SPRINT 2 - AUTHENTICATION & SIGN UP TIERS ---

def get_db_creds():
    """Fetches user credentials for the authentication engine"""
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
    conn.close()
    return {'usernames': {r['username']: {'email':r['email'], 'name':r['name'], 'password':r['password']} for _,r in df.iterrows()}}

# Initialize Authenticator in session state to maintain stability
if 'authenticator' not in st.session_state:
    st.session_state.authenticator = stauth.Authenticate(
        get_db_creds(), 
        st.secrets['cookie']['name'], 
        st.secrets['cookie']['key'], 
        30
    )

authenticator = st.session_state.authenticator

# --- THE LOGIN & SIGN UP GATE ---
if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=180)
    
    # Restored Sprints 1 & 2 Tabs: Login, Sign Up, Team, and Recovery
    auth_tabs = st.tabs(["🔑 Login", "📝 Sign Up", "🤝 Join Team", "❓ Forget Password"])
    
    with auth_tabs[0]: 
        authenticator.login(location='main')
        
    with auth_tabs[1]:
        st.subheader("Select Enterprise Growth Package")
        c1, c2, c3 = st.columns(3)
        
        # Sprint 1: CSS Pricing Cards
        with c1: 
            st.markdown('<div class="price-card"><h3>Basic</h3><h2>$99</h2><p>50 Credits/mo</p></div>', unsafe_allow_html=True)
        with c2: 
            st.markdown('<div class="price-card" style="border-color:#7C3AED;"><h3>Pro</h3><h2>$249</h2><p>150 Credits/mo</p></div>', unsafe_allow_html=True)
        with c3: 
            st.markdown('<div class="price-card"><h3>Enterprise</h3><h2>$499</h2><p>Unlimited Agents</p></div>', unsafe_allow_html=True)
        
        # Sprint 2: Registration Logic
        try:
            reg_data = authenticator.register_user(location='main')
            if reg_data:
                email, username, name = reg_data
                conn = sqlite3.connect('breatheeasy.db')
                # Inject default credits and member role into the new record
                conn.execute("""
                    UPDATE users 
                    SET credits = 50, role = 'member', plan = 'Basic', verified = 0 
                    WHERE username = ?
                """, (username,))
                conn.commit()
                conn.close()
                st.success("Sign Up Successful! Please switch to the Login tab.")
        except Exception as e:
            st.error(f"Sign Up Error: {e}")
            
    with auth_tabs[2]:
        st.subheader("🤝 Join an Existing Team")
        team_id_input = st.text_input("Enter Enterprise Team ID", placeholder="e.g. TEAM_admin_123")
        if st.button("Request Team Access", use_container_width=True):
            st.info(f"Access request for {team_id_input} sent to Administrator.")
            
    with auth_tabs[3]:
        st.subheader("❓ Account Recovery")
        try:
            res = authenticator.forgot_password(location='main')
            if res:
                st.success("Password reset request processed. Check your registered email.")
        except Exception as e:
            pass # Handled internally by widget
            
    st.stop() # Prevents main app from loading until logged in

# --- POST-LOGIN CONTEXT ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()
is_admin = (user_row['role'] == 'admin')

# --- SECTION #4: SPRINT 3 - GLOBAL LOGIC & GEOGRAPHY ---

# 1. Agent Logic (Defines the Tabs and Toggles)
agent_map = [
    ("🕵️ Analyst", "analyst"), ("📺 Ads", "ads"), ("🎨 Creative", "creative"), 
    ("👔 Strategist", "strategist"), ("📱 Social", "social"), ("📍 GEO", "geo"), 
    ("🌐 Auditor", "audit"), ("✍ SEO", "seo")
]

# 2. Deployment Guides (The Blue Instruction Boxes)
DEPLOY_GUIDES = {
    "analyst": "Identify Price-Gaps in the competitor table to undercut rivals.",
    "ads": "Copy platform hooks directly into Meta/Google Manager.",
    "creative": "Implement multi-channel copy and cinematic Veo video prompts.",
    "strategist": "This 30-day ROI roadmap is your CEO-level execution checklist.",
    "social": "Deploy viral hooks across LinkedIn/IG based on local schedule.",
    "geo": "Update Google Business Profile metadata based on AI technical factors.",
    "audit": "Forward this brief to your web team to patch conversion leaks.",
    "seo": "Publish this article to secure rankings in AI Search (SGE)."
}

# --- SECTION #5: THE DYNAMIC SIDEBAR ---
with st.sidebar:
    # System Heartbeat & Theme
    health = check_system_health()
    col_h, col_t = st.columns([2, 1])
    with col_h: st.caption(f"{'🟢' if all(health.values()) else '🔴'} **SYSTEM OPERATIONAL**")
    with col_t: 
        if st.button("🌓", key="theme_toggle"): toggle_theme()

    st.image("Logo1.jpeg", width=120)
    st.metric("Credits Available", user_row['credits'])
    st.divider()

    # Dynamic Industry & Service Logic
    biz_name = st.text_input("🏢 Brand Name", placeholder="e.g. Acme Solar")
    
    industry_map = {
        "Residential Services": ["HVAC", "Roofing", "Solar", "Plumbing"],
        "Medical & Health": ["Dental", "Plastic Surgery", "Veterinary"],
        "Legal & Professional": ["Family Law", "Personal Injury", "CPA"],
        "Custom": ["Type Manual Service..."]
    }
    
    selected_ind_cluster = st.selectbox("📂 Industry Cluster", sorted(list(industry_map.keys())))
    
    if selected_ind_cluster == "Custom":
        final_service = st.text_input("Enter Service Name", key="custom_svc_input")
    else:
        service_list = industry_map[selected_ind_cluster]
        final_service = st.selectbox("🛠️ Specific Service", service_list)

    # Dynamic Geography (State -> City)
    geo_dict = get_geo_data()
    selected_state = st.selectbox("🎯 Target State", sorted(geo_dict.keys()))
    city_list = sorted(geo_dict[selected_state]) + ["Other (Manual City)"]
    selected_city = st.selectbox(f"🏙️ Select City", city_list)
    
    if selected_city == "Other (Manual City)":
        custom_city = st.text_input(f"Type City Name", key="m_city_input")
        full_loc = f"{custom_city}, {selected_state}"
    else:
        full_loc = f"{selected_city}, {selected_state}"

    # Strategic Directives (Prompt Box)
    st.divider()
    agent_info = st.text_area("✍️ Strategic Directives", 
                             placeholder="e.g. Focus on high-ticket luxury clients...", 
                             key="agent_directives_box")

    # Swarm Personnel Toggles
    with st.expander("🤖 Swarm Personnel", expanded=False):
        toggles = {k: st.toggle(v, value=True, key=f"tg_{k}") for k, v in dict(agent_map).items()}

    # Launch Button & Security Gate
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

# --- SECTION #6: EXECUTION ENGINE ---
if run_btn:
    if not biz_name or not final_service:
        st.error("Identification required: Brand Name and Service must be populated.")
    else:
        with st.status("🛠️ Coordinating Swarm Agents...", expanded=True) as status:
            try:
                # Call the external backend main.py
                report = run_marketing_swarm({
                    'city': full_loc, 
                    'biz_name': biz_name, 
                    'service': final_service, 
                    'directives': agent_info
                })
                
                st.session_state.report = report
                st.session_state.gen = True
                
                # Deduct Credit & Audit Log
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
                conn.execute("INSERT INTO master_audit_logs (timestamp, user, action_type, target_biz, location, status) VALUES (?,?,?,?,?,?)", 
                             (datetime.now().strftime("%Y-%m-%d %H:%M"), user_row['username'], "SWARM_LAUNCH", biz_name, full_loc, "SUCCESS"))
                conn.commit(); conn.close()
                
                status.update(label="🚀 Intelligence Captured!", state="complete")
                st.rerun()
            except Exception as e:
                st.error(f"Backend Error: {e}")

# --- SECTION #7: THE COMMAND CENTER TABS ---
tab_labels = ["📖 Guide"] + [a[0] for a in agent_map] + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_admin: tab_labels.append("⚙ Admin")

tabs_obj = st.tabs(tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(tab_labels)}

with TAB["📖 Guide"]:
    st.header("📖 Agent Intelligence Manual")
    st.info("The Omni-Swarm engine is ready. Configure your brand in the sidebar and click Launch.")
