import streamlit as st
import streamlit_authenticator as stauth
import sqlite3
import os

# --- ARCHITECTURE SETUP (Folder 03) ---
# This ensures the app knows its current 'Phase'
if 'app_phase' not in st.session_state:
    st.session_state.app_phase = "AUTH_GATE" # Phases: AUTH_GATE, COMMAND_CENTER

def init_db_v2():
    """Final Master Database Schema"""
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    # Ensure all columns from Sprints 1-5 exist
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, 
                  role TEXT, plan TEXT, credits INTEGER, verified INTEGER DEFAULT 0, team_id TEXT)''')
    conn.commit()
    conn.close()

init_db_v2()

# --- THE PHASE CONTROLLER ---
# This is the 'Project Management' approach: Only show what is ready.
if st.session_state.get("authentication_status") != True:
    # Phase: AUTH_GATE
    # [We will insert the Folder 04: Security logic here next]
    st.title("Enterprise Swarm Command")
    st.info("System Locked: Please authenticate via the Security Protocol.")
    
    # Placeholder for the Login Gate
    st.subheader("Security Gate")
    # (Sign-in logic goes here)
else:
    # Phase: COMMAND_CENTER
    # [We will insert Folder 06: Dev_Operations logic here]
    st.sidebar.success("Authenticated")
    st.write("Welcome to the Command Center")

# --- FOLDER 04: SECURITY PROTOCOLS & AUTHENTICATION WRAPPER ---

def get_db_creds():
    """Fetches user credentials for the authentication engine"""
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
    conn.close()
    return {'usernames': {r['username']: {'email':r['email'], 'name':r['name'], 'password':r['password']} for _,r in df.iterrows()}}

# 1. Initialize Authenticator
if 'authenticator' not in st.session_state:
    st.session_state.authenticator = stauth.Authenticate(
        get_db_creds(), 
        st.secrets['cookie']['name'], 
        st.secrets['cookie']['key'], 
        30
    )

authenticator = st.session_state.authenticator

# 2. The Multi-Tab Security Gate
if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=180)
    auth_tabs = st.tabs(["🔑 Access Login", "📝 Enterprise Sign-Up", "🤝 Team Request", "❓ Recovery"])
    
    with auth_tabs[0]:
        # Login Logic
        authenticator.login(location='main')
        if st.session_state.get("authentication_status"):
            st.rerun() # Force phase shift to Command Center
            
    with auth_tabs[1]:
        st.subheader("Select Enterprise Growth Package")
        c1, c2, c3 = st.columns(3)
        # Tiered Pricing (SaaS Structure)
        with c1: st.markdown('<div class="price-card"><h3>Basic</h3><h2>$99</h2><p>50 Credits/mo</p></div>', unsafe_allow_html=True)
        with c2: st.markdown('<div class="price-card" style="border-color:#7C3AED;"><h3>Pro</h3><h2>$249</h2><p>150 Credits/mo</p></div>', unsafe_allow_html=True)
        with c3: st.markdown('<div class="price-card"><h3>Enterprise</h3><h2>$499</h2><p>Unlimited Agents</p></div>', unsafe_allow_html=True)
        
        # User Registration Flow
        try:
            reg_res = authenticator.register_user(location='main')
            if reg_res:
                email, username, name = reg_res
                conn = sqlite3.connect('breatheeasy.db')
                # SPRINT 2 REQUIREMENT: Set default credits and role
                conn.execute("""
                    INSERT OR REPLACE INTO users (username, email, name, password, role, plan, credits, verified, team_id)
                    SELECT username, email, name, password, 'member', 'Basic', 50, 0, 'TEAM_GEN' 
                    FROM users WHERE username = ?
                """, (username,))
                conn.commit(); conn.close()
                st.success("Account Created! Please proceed to the Login tab.")
        except Exception as e:
            st.error(f"Security Protocol Error: {e}")
            
    with auth_tabs[2]:
        st.info("To join a team, enter the Team ID provided by your administrator.")
        st.text_input("Enter Enterprise Team ID", key="join_team_id")
        if st.button("Request Access"):
            st.warning("Access request queued for administrator review.")
            
    with auth_tabs[3]:
        authenticator.forgot_password(location='main')

    st.stop() # CRITICAL: No code beyond this point executes for unauthenticated users

# --- FOLDER 05: SaaS_Dev_Operations - THE COMMAND CONSOLE ---

# 1. LOAD USER CONTEXT
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()

# 2. PERFORMANCE HELPERS (RESTORED SPRINT 5)
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

# 3. DYNAMIC SIDEBAR ARCHITECTURE
with st.sidebar:
    st.image("Logo1.jpeg", width=120)
    st.subheader(f"Welcome, {user_row['name']}")
    st.metric("Enterprise Credits", user_row['credits'])
    
    st.divider()
    
    # Brand Configuration
    biz_name = st.text_input("🏢 Brand Name", placeholder="Acme Corp")
    
    # Dynamic Geography (Sprint 3 requirement)
    geo_dict = get_geo_data()
    selected_state = st.selectbox("🎯 Target State", sorted(geo_dict.keys()))
    selected_city = st.selectbox("🏙️ Target City", sorted(geo_dict[selected_state]))
    full_loc = f"{selected_city}, {selected_state}"
    
    st.divider()
    
    # Strategic Directives (Sprint 5 requirement)
    agent_info = st.text_area("✍️ Strategic Directives", 
                             placeholder="Injected into all agent prompts...",
                             help="Define specific goals like 'luxury focus' or 'emergency speed'.")
    
    # Swarm Personnel Toggles
    with st.expander("🤖 Swarm Personnel", expanded=False):
        # Global definition of agents to be used across tabs
        agent_map = [
            ("🕵️ Analyst", "analyst"), ("📺 Ads", "ads"), ("🎨 Creative", "creative"), 
            ("👔 Strategist", "strategist"), ("📱 Social", "social"), ("📍 GEO", "geo"), 
            ("🌐 Auditor", "audit"), ("✍ SEO", "seo")
        ]
        toggles = {k: st.toggle(v, value=True, key=f"tg_{k}") for v, k in agent_map}

    st.divider()
    
    # Verification Security Gate (Sprint 2)
    if user_row['verified'] == 1:
        run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
    else:
        st.error("🛡️ Verification Required")
        if st.button("🔓 One-Click Verify"):
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE users SET verified=1 WHERE username=?", (user_row['username'],))
            conn.commit(); conn.close(); st.rerun()
        run_btn = False

    authenticator.logout('🔒 Sign Out', 'sidebar')

# 4. EXECUTION BRIDGE
if run_btn:
    if not biz_name:
        st.error("Error: Brand Name is required for swarm coordination.")
    else:
        with st.status("🛠️ Coordinating Swarm Agents...", expanded=True):
            # Pass directives and location to the backend
            report = run_marketing_swarm({
                'city': full_loc, 
                'biz_name': biz_name, 
                'service': "Omni-Service", 
                'directives': agent_info
            })
            st.session_state.report = report
            st.session_state.gen = True
            
            # Audit Log Entry (Sprint 4)
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
            conn.commit(); conn.close()
            st.rerun()

# --- FOLDER 06: OMNI-SWARM_SPRINTS - THE INTELLIGENCE HUB ---

# 1. DEFINE EXPORT UTILITIES (SPRINT 3)
def export_word(content, title):
    from docx import Document
    doc = Document()
    doc.add_heading(f'Intelligence Brief: {title}', 0)
    doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def export_pdf(content, title):
    from fpdf import FPDF
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f'Intelligence Brief: {title}', 0, 1, 'C')
    pdf.set_font("Arial", size=10)
    clean_text = str(content).encode('latin-1', 'ignore').decode('latin-1')
    pdf.multi_cell(0, 7, txt=clean_text)
    return pdf.output(dest='S').encode('latin-1')

# 2. RENDER COMMAND CENTER TABS
# We define the labels using the agent_map from Folder 05
tab_labels = ["📖 Guide"] + [a[0] for a in agent_map] + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if user_row['role'] == 'admin':
    tab_labels.append("⚙ Admin")

tabs_obj = st.tabs(tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(tab_labels)}

# A. THE GUIDE TAB (SPRINT 1)
with TAB["📖 Guide"]:
    st.header("📖 Agent Intelligence Manual")
    st.markdown("""
    Your Omni-Swarm is an elite unit of 8 specialized AI agents:
    - **Forensics:** Web Auditor & Ad Tracker find competitor weaknesses.
    - **Strategy:** Swarm Strategist builds a 30-Day ROI Roadmap.
    - **Production:** Creative & SEO Architects build your growth assets.
    """)
    if not st.session_state.get('gen'):
        st.info("👈 Configure your brand in the sidebar and Launch the Swarm to begin.")

# B. DYNAMIC AGENT WORKBENCHES (SPRINTS 3 & 4)
DEPLOY_GUIDES = {
    "analyst": "Identify Price-Gaps to undercut rivals.",
    "ads": "Copy platform hooks into Meta/Google Ads.",
    "creative": "Use these prompts for high-fidelity assets.",
    "strategist": "Your 30-day CEO-level execution checklist.",
    "social": "Deploy viral hooks based on the local schedule.",
    "geo": "Update citations for AI search ranking.",
    "audit": "Patch technical leaks to increase speed.",
    "seo": "Publish for Search Generative Experience (SGE)."
}

for title, key in agent_map:
    with TAB[title]:
        st.markdown(f'<div class="deploy-guide"><b>🚀 DEPLOYMENT:</b> {DEPLOY_GUIDES.get(key)}</div>', unsafe_allow_html=True)
        if st.session_state.get('gen'):
            content = st.session_state.report.get(key, "Intelligence generated. Review below.")
            edited = st.text_area(f"Refine {title}", value=str(content), height=400, key=f"ed_{key}")
            
            # Export Buttons
            c1, c2 = st.columns(2)
            with c1: st.download_button("📄 Word Brief", export_word(edited, title), f"{key}.docx", key=f"w_{key}")
            with c2: st.download_button("📕 PDF Report", export_pdf(edited, title), f"{key}.pdf", key=f"p_{key}")
        else:
            st.warning("Swarm intelligence not yet captured for this seat.")

# C. TEAM INTEL KANBAN (SPRINT 4)
with TAB["🤝 Team Intel"]:
    st.header("🤝 Global Team Pipeline")
    conn = sqlite3.connect('breatheeasy.db')
    team_df = pd.read_sql_query("SELECT city, service, status FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
    
    if not team_df.empty:
        stages = ["Discovery", "Execution", "ROI Verified"]
        cols = st.columns(3)
        for i, stage in enumerate(stages):
            with cols[i]:
                st.markdown(f'<div style="text-align:center; font-weight:bold; color:#2563EB;">{stage.upper()}</div>', unsafe_allow_html=True)
                for _, lead in team_df[team_df['status'] == stage].iterrows():
                    st.markdown(f'<div class="kanban-card"><b>{lead["city"]}</b><br>{lead["service"]}</div>', unsafe_allow_html=True)
    else:
        st.info("Pipeline is currently empty. Launch a swarm to generate leads.")
    conn.close()

# D. ADMIN GOD-MODE (SPRINT 4)
if "⚙ Admin" in TAB:
    with TAB["⚙ Admin"]:
        st.header("⚙️ System Forensics")
        conn = sqlite3.connect('breatheeasy.db')
        st.subheader("Global Activity Audit")
        audit_df = pd.read_sql_query("SELECT * FROM master_audit_logs ORDER BY id DESC LIMIT 50", conn)
        st.dataframe(audit_df, use_container_width=True)
        conn.close()
