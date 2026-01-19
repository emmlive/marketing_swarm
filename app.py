import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import sqlite3
import os
from datetime import datetime
from io import BytesIO
from fpdf import FPDF
from docx import Document
from main import run_marketing_swarm 
from fpdf import FPDF
import streamlit as st
import sqlite3
import pandas as pd
# ... other imports ...

# --- 1. DATABASE SYNC & MIGRATION (Place at Top of app.py) ---
def sync_database_schema():
    """Ensures the DB exists and all SaaS columns are present."""
    conn = sqlite3.connect('breatheeasy.db')
    cursor = conn.cursor()
    
    # Create table if it's a fresh install
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            name TEXT,
            email TEXT,
            password TEXT,
            plan TEXT DEFAULT 'Basic',
            role TEXT DEFAULT 'user',
            credits INTEGER DEFAULT 10,
            verified INTEGER DEFAULT 0,
            team_id TEXT DEFAULT 'HQ_001'
        )
    """)
    
    # MIGRATION: Add columns to existing DB if they are missing
    # This prevents the 'OperationalError' you saw earlier
    migrations = [
        ("plan", "TEXT DEFAULT 'Basic'"),
        ("role", "TEXT DEFAULT 'user'"),
        ("credits", "INTEGER DEFAULT 10"),
        ("team_id", "TEXT DEFAULT 'HQ_001'"),
        ("verified", "INTEGER DEFAULT 0")
    ]
    
    for col_name, col_type in migrations:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass # Column already exists
            
    conn.commit()
    conn.close()

# TRIGGER SYNC
sync_database_schema()

# --- REST OF YOUR APP.PY CODE FOLLOWS ---

# --- SECTION #0: GLOBAL HELPERS ---
# =========================
# PDF SAFETY & DEBUG LAYER
# =========================

import re
import unicodedata
import streamlit as st
from fpdf import FPDF
import fpdf

# ===============================
# 🔥 FPDF INTERNAL ENCODING PATCH
# ===============================

import fpdf.fpdf

_original_putpages = fpdf.fpdf.FPDF._putpages

def _patched_putpages(self):
    # Force-ignore any encoding failures inside FPDF itself
    pages = self.pages
    self.pages = {}
    for k, v in pages.items():
        if isinstance(v, str):
            v = v.encode("latin-1", "ignore").decode("latin-1", "ignore")
        self.pages[k] = v
    _original_putpages(self)

fpdf.fpdf.FPDF._putpages = _patched_putpages

# --------------------------------------------------
# 🔐 NUCLEAR ASCII SANITIZER (NO UNICODE SURVIVES)
# --------------------------------------------------
def nuclear_ascii(text):
    """
    Converts any input into FPDF-safe ASCII.
    NOTHING non-latin-1 survives this function.
    """
    if text is None:
        return ""

    # Force string
    text = str(text)

    # Normalize Unicode
    text = unicodedata.normalize("NFKD", text)

    # Remove zero-width & BOM characters
    text = (
        text.replace("\u200b", "")
            .replace("\u200c", "")
            .replace("\u200d", "")
            .replace("\ufeff", "")
    )

    # Convert to strict ASCII
    text = text.encode("ascii", "ignore").decode("ascii")

    # Remove anything non-printable (except newline)
    text = re.sub(r"[^\x20-\x7E\n]", "", text)

    return text


# --------------------------------------------------
# 🧪 FINAL DEBUG CHECK (REMOVE AFTER STABILIZATION)
# --------------------------------------------------
st.write("🔎 FPDF version:", getattr(fpdf, "__version__", "UNKNOWN"))
st.write("📦 FPDF module path:", fpdf.__file__)

def debug_non_latin1(text, label):
    offenders = []
    for i, ch in enumerate(str(text)):
        try:
            ch.encode("latin-1")
        except UnicodeEncodeError:
            offenders.append((i, repr(ch), hex(ord(ch))))
    if offenders:
        st.write(f"⚠️ Non-Latin-1 chars in {label}:", offenders[:10])


# --------------------------------------------------
# 🛡️ HARDENED PDF EXPORT (WILL NOT CRASH)
# --------------------------------------------------
def export_pdf(content, title):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # ---- Title ----
        pdf.set_font("Arial", "B", 16)
        safe_title = nuclear_ascii(title)
        pdf.cell(
            0, 10,
            f"Intelligence Brief: {safe_title}",
            ln=True,
            align="C"
        )

        # ---- Body ----
        pdf.set_font("Arial", size=10)
        safe_body = nuclear_ascii(content)

        # Normalize line breaks & limit line length
        safe_body = safe_body.replace("\r", "")
        safe_body = "\n".join(
            line[:900] for line in safe_body.split("\n")
        )

        pdf.multi_cell(0, 7, safe_body)

        # Return Streamlit-safe bytes
        return pdf.output(dest="S").encode("latin-1")

    except Exception:
        fallback = FPDF()
        fallback.add_page()
        fallback.set_font("Arial", size=12)
        fallback.multi_cell(
            0, 10,
            "PDF GENERATION FAILED\n\n"
            "All content was sanitized.\n"
            "The error was safely handled."
        )
        return fallback.output(dest="S").encode("latin-1")

def export_word(content, title):
    """Standard Word export engine"""
    doc = Document()
    doc.add_heading(f'Intelligence Brief: {title}', 0)
    doc.add_paragraph(str(content))
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- ARCHITECTURE SETUP (Folder 03) ---

# 1. State Controller: Tracks if we are at the Login Gate or the Command Center
if 'app_phase' not in st.session_state:
    st.session_state.app_phase = "AUTH_GATE" 

def init_db_v2():
    """Forces administrative credentials and initializes ALL required tables"""
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    
    # 1. User Table
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, 
                  role TEXT, plan TEXT, credits INTEGER, verified INTEGER DEFAULT 0, team_id TEXT)''')
    
    # 2. Leads Table (For Kanban)
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, city TEXT, 
                  service TEXT, status TEXT DEFAULT "Discovery", team_id TEXT)''')
    
    # 3. Audit Logs Table (FIXES YOUR DATABASE ERROR)
    c.execute('''CREATE TABLE IF NOT EXISTS master_audit_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, user TEXT, 
                  action_type TEXT, target_biz TEXT, location TEXT, status TEXT)''')
    
    # 4. Inject/Refresh Admin
    admin_pw = stauth.Hasher.hash('admin123')
    c.execute("""INSERT OR REPLACE INTO users 
                 (username, email, name, password, role, plan, credits, verified, team_id) 
                 VALUES ('admin', 'admin@tech.ai', 'System Admin', ?, 'admin', 'Unlimited', 9999, 1, 'HQ_001')""", 
              (admin_pw,))
    
    conn.commit()
    conn.close()

# MANDATORY: Execute initialization before any UI rendering
init_db_v2()

# --- CRITICAL: EXECUTION ORDER ---
# Run this before the Authenticator is initialized
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

# --- FOLDER 04: HARDENED SECURITY & AUTHENTICATION PROTOCOLS ---

def get_db_creds():
    """Fetches fresh credentials from the database"""
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    try:
        df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
        conn.close()
        return {'usernames': {r['username']: {'email':r['email'], 'name':r['name'], 'password':r['password']} for _,r in df.iterrows()}}
    except:
        conn.close()
        return {'usernames': {}}

def init_db_v2():
    """Forces administrative credentials using the v0.4.x static hashing method"""
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    
    # 1. Create User Table
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, 
                  role TEXT, plan TEXT, credits INTEGER, verified INTEGER DEFAULT 0, team_id TEXT)''')
    
    # 2. FIXED HASHING: In v0.4.x+, Hasher is a static utility, not a class to instantiate
    # We call .hash() directly on the class. No brackets, no .generate()
    admin_pw = stauth.Hasher.hash('admin123')
    
    # 3. Inject/Refresh Admin
    c.execute("""INSERT OR REPLACE INTO users 
                 (username, email, name, password, role, plan, credits, verified, team_id) 
                 VALUES ('admin', 'admin@tech.ai', 'System Admin', ?, 'admin', 'Unlimited', 9999, 1, 'HQ_001')""", 
              (admin_pw,))
    
    conn.commit()
    conn.close()

# --- MANDATORY EXECUTION ORDER ---
init_db_v2()

# 1. Initialize the Database and Admin Record
init_db_v2()

# 2. Initialize Authenticator in Session State
# We pass get_db_creds() directly to ensure the authenticator has the LATEST data
if 'authenticator' not in st.session_state:
    st.session_state.authenticator = stauth.Authenticate(
        get_db_creds(), 
        st.secrets['cookie']['name'], 
        st.secrets['cookie']['key'], 
        30
    )

authenticator = st.session_state.authenticator

# 3. THE SECURITY GATE
if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=180)
    auth_tabs = st.tabs(["🔑 Login", "📝 Sign Up", "🤝 Join Team", "❓ Forget Password"])
    
    with auth_tabs[0]:
        authenticator.login(location='main')
        # If login is successful, refresh to enter Command Center
        if st.session_state.get("authentication_status"):
            st.rerun()
            
    with auth_tabs[1]:
        st.subheader("Enterprise Registration")
        # Pricing cards and registration logic go here
        res = authenticator.register_user(location='main')
        if res:
            st.success("Account created! Please log in.")

    with auth_tabs[2]:
        st.subheader("🤝 Request Enterprise Team Access")
        st.markdown("""
        To sync with an existing corporate swarm, enter your **Organization ID** below. 
        Your administrator will receive a notification to verify your seat.
        """)
        
        with st.form("team_request_form"):
            team_id_req = st.text_input("Enterprise Team ID", placeholder="e.g., HQ_NORTH_2026")
            reason = st.text_area("Purpose of Access", placeholder="e.g., Regional Marketing Analyst")
            
            submit_req = st.form_submit_button("Submit Access Request", use_container_width=True)
            
            if submit_req:
                if team_id_req:
                    # Logic: In a live env, this would write to a 'pending_requests' table
                    st.success(f"Request for Team {team_id_req} has been logged. Status: PENDING.")
                else:
                    st.error("Please provide a valid Team ID.")
            
    with auth_tabs[3]:
        authenticator.forgot_password(location='main')

    st.stop() # Prevents any further code from running if not logged in
        

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

# --- 3. DYNAMIC SIDEBAR ARCHITECTURE (Safe Tiered Update) ---
with st.sidebar:
    st.image("Logo1.jpeg", width=120)
    st.subheader(f"Welcome, {user_row['name']}")
    
    # 0. SAFE DATA RETRIEVAL (Prevents KeyErrors)
    # We use .get() so if 'package' is missing but 'plan' exists (or vice versa), it won't crash
    current_tier = user_row.get('plan', user_row.get('package', 'Basic'))
    current_credits = user_row.get('credits', 0)
    is_admin = user_row.get('role') == 'admin'

    st.metric(f"{current_tier} Plan", f"{current_credits} Credits")
    st.divider()

    # --- TIER LIMITS CONFIGURATION ---
    tier_limits = {
        "Basic": 3,      
        "Pro": 5,        
        "Enterprise": 8,
        "Unlimited": 8   # Admin fallback
    }
    
    # Logic: Admin bypasses all limits, others use their plan tier
    agent_limit = 8 if is_admin else tier_limits.get(current_tier, 3)

    # 1. BRAND CONFIGURATION
    biz_name = st.text_input("🏢 Brand Name", placeholder="Acme Corp")
    
    # 2. BRAND LOGO GUARDRAIL (Pro & Enterprise only)
    custom_logo = None
    if current_tier == "Basic" and not is_admin:
        st.info("💡 **Basic Plan:** System branding active. Upgrade to Pro for custom logos.")
    else:
        custom_logo = st.file_uploader("📤 Custom Brand Logo (Pro+)", type=['png', 'jpg', 'jpeg'])
    
    # 3. GEOGRAPHY
    geo_dict = get_geo_data()
    selected_state = st.selectbox("🎯 Target State", sorted(geo_dict.keys()))
    selected_city = st.selectbox("🏙️ Target City", sorted(geo_dict[selected_state]))
    full_loc = f"{selected_city}, {selected_state}"
    
    st.divider()
    
    # 4. STRATEGIC DIRECTIVES
    agent_info = st.text_area("✍️ Strategic Directives", 
                             placeholder="Injected into all agent prompts...",
                             help="Define specific goals like 'luxury focus' or 'emergency speed'.")
    
    # 5. SWARM PERSONNEL TOGGLES (With Limit Logic)
    with st.expander("🤖 Swarm Personnel", expanded=True):
        st.caption(f"Status: {current_tier} | Max: {agent_limit} Agents")
        
        agent_map = [
            ("🕵️ Analyst", "analyst"), ("📺 Ads", "ads"), ("🎨 Creative", "creative"), 
            ("👔 Strategist", "strategist"), ("📱 Social", "social"), ("📍 GEO", "geo"), 
            ("🌐 Auditor", "audit"), ("✍ SEO", "seo")
        ]

        toggles = {}
        active_count = 0
        
        # Determine how many are currently toggled on to calculate limits
        for title, key in agent_map:
            # Check if this specific agent is already in session state
            is_on = st.session_state.get(f"tg_{key}", False)
            if is_on: active_count += 1

        for title, key in agent_map:
            # Logic: Disable toggle if limit reached AND it's not already ON
            is_disabled = False
            if not is_admin and active_count >= agent_limit and not st.session_state.get(f"tg_{key}"):
                is_disabled = True
            
            # Default values for first launch
            default_val = True if key in ['analyst', 'audit', 'seo'] and active_count < 3 else False
            
            toggles[key] = st.toggle(title, value=default_val, disabled=is_disabled, key=f"tg_{key}")
        
        if not is_admin and active_count >= agent_limit:
            st.warning(f"Agent limit reached for {current_tier} plan.")

    st.divider()
    
    # 6. VERIFICATION SECURITY GATE (Simplified)
    if user_row.get('verified') == 1:
        if current_credits > 0:
            run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
        else:
            st.error("💳 Out of Credits")
            run_btn = False
    else:
        st.error("🛡️ Verification Required")
        if st.button("🔓 One-Click Verify"):
            conn = sqlite3.connect('breatheeasy.db')
            conn.execute("UPDATE users SET verified=1 WHERE username=?", (user_row['username'],))
            conn.commit(); conn.close(); st.rerun()
        run_btn = False

    authenticator.logout('🔒 Sign Out', 'sidebar')
    
# --- 4. EXECUTION BRIDGE (Final SDLC Sync) ---
# --- Find this section at the bottom of your sidebar in app.py ---

if run_btn:
    if not biz_name:
        st.error("🚨 Please enter a Brand Name before launching.")
    else:
        # 1. FILTER ACTIVE AGENTS 
        # This converts your toggles into a list of keys: ['analyst', 'seo', etc.]
        active_agents = [k for k, v in toggles.items() if v]

        # 2. SHOW LOADING STATE
        with st.status("🚀 Initializing Swarm Intelligence...", expanded=True) as status:
            st.write(f"📡 Dispatching {len(active_agents)} agents for {biz_name}...")
            
            # 3. THE BRIDGE TO THE ENGINE (Paste your code here)
            # This calls the function in main.py and waits for the dictionary result
            report = run_marketing_swarm({
                'city': full_loc, 
                'biz_name': biz_name, 
                'active_swarm': active_agents,
                'package': current_tier,
                'custom_logo': custom_logo, 
                'directives': agent_info
            })

            # 4. SAVE TO SESSION STATE
            # This makes the data available for the Tabs to display
            st.session_state.report = report
            st.session_state.gen = True
            
            # 5. DEDUCT CREDITS & LOG (SDLC Security)
            # You can add your database update logic here later
            
            status.update(label="✅ Swarm Coordination Complete!", state="complete", expanded=False)

        # 6. REFRESH UI
        # This forces the page to reload so the new data shows up in the Tabs
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

# --- FOLDER 06: AGENT SEATS - FINAL SYNCED RENDERER ---

for i, (title, key) in enumerate(agent_map, 1):
    with tabs_obj[i]:
        # 1. Deployment Guide (Visual UI)
        st.markdown(f'''<div class="deploy-guide">
            <b>🚀 {title.upper()} DEPLOYMENT GUIDE:</b><br>
            {DEPLOY_GUIDES.get(key, "Review the intelligence brief below.")}
        </div>''', unsafe_allow_html=True)

        # 2. Check if the report has been generated
        if st.session_state.get('gen') and st.session_state.get('report'):
            # FORCE FETCH: Get data from the report dictionary
            # We use .get(key) to match the sidebar's toggle key ('analyst', 'ads', etc.)
            agent_content = st.session_state.report.get(key)
            
            if agent_content:
                # INTERACTIVE WORKBENCH
                edited = st.text_area(
                    f"Refine {title} Intelligence", 
                    value=str(agent_content), 
                    height=450, 
                    key=f"editor_{key}"
                )

                # EXPORT ENGINE
                c1, c2 = st.columns(2)
                with c1:
                    st.download_button("📄 Word Brief", export_word(edited, title), f"{biz_name}_{key}.docx", key=f"btn_w_{key}")
                with c2:
                    st.download_button("📕 PDF Report", export_pdf(edited, title), f"{biz_name}_{key}.pdf", key=f"btn_p_{key}")
            else:
                # This triggers if the agent was not selected in the sidebar
                st.warning(f"⚠️ {title} was not selected for this deployment. Toggle it in the sidebar and re-launch.")
        else:
            st.info(f"✨ The {title} seat is ready for deployment. Launch the swarm from the sidebar.")

# --- C. TEAM INTEL KANBAN (SPRINT 4 POWER UPDATE) ---
with TAB["🤝 Team Intel"]:
    st.header("🤝 Global Team Pipeline")
    
    # Use a sidebar-style metric to show team velocity
    conn = sqlite3.connect('breatheeasy.db')
    
    # 1. FETCH TEAM DATA
    try:
        team_df = pd.read_sql_query(
            "SELECT id, city, service, status FROM leads WHERE team_id = ?", 
            conn, params=(user_row['team_id'],)
        )
    except:
        # Fallback if table doesn't exist yet
        st.error("Lead tracking table not initialized. Visit Admin tab to sync schema.")
        team_df = pd.DataFrame()

    # 2. QUICK ADD (Optional: Manually inject a lead)
    with st.expander("➕ Manual Pipeline Entry"):
        with st.form("manual_lead"):
            c1, c2 = st.columns(2)
            l_city = c1.text_input("City/Location")
            l_serv = c2.text_input("Service Category")
            if st.form_submit_button("Inject to Team"):
                conn.execute("INSERT INTO leads (city, service, status, team_id) VALUES (?, ?, 'Discovery', ?)",
                             (l_city, l_serv, user_row['team_id']))
                conn.commit()
                st.rerun()

    # 3. KANBAN RENDERER
    if not team_df.empty:
        stages = ["Discovery", "Execution", "ROI Verified"]
        cols = st.columns(3)
        
        for i, stage in enumerate(stages):
            with cols[i]:
                st.markdown(f'''
                    <div style="background-color:#F3F4F6; padding:10px; border-radius:10px; border-bottom:3px solid #2563EB;">
                        <h4 style="text-align:center; color:#2563EB; margin:0;">{stage.upper()}</h4>
                    </div>
                ''', unsafe_allow_html=True)
                
                # Filter leads for this stage
                stage_leads = team_df[team_df['status'] == stage]
                
                for _, lead in stage_leads.iterrows():
                    with st.container():
                        st.markdown(f'''
                            <div style="background-color:white; border:1px solid #E5E7EB; padding:10px; border-radius:5px; margin-top:10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
                                <small style="color:#6B7280;">LOC:</small> <b>{lead["city"]}</b><br>
                                <small style="color:#6B7280;">SVC:</small> {lead["service"]}
                            </div>
                        ''', unsafe_allow_html=True)
                        
                        # 4. STAGE ADVANCER (Sprint 4 Control)
                        if stage != "ROI Verified":
                            if st.button(f"Move to {stages[i+1]} ➡️", key=f"move_{lead['id']}"):
                                conn.execute("UPDATE leads SET status = ? WHERE id = ?", (stages[i+1], lead['id']))
                                conn.commit()
                                st.rerun()
    else:
        st.info("Pipeline is currently empty. Launch a swarm or use the Manual Entry above.")
    
    conn.close()

# --- D. Admin God-MODE (Sprint 4 Finalized) ---
# --- TAB DEFINITION (Place this before your content blocks) ---

# 1. Define ALL tabs used in your app logic
# This list must include every tab name you reference in your 'with TAB' blocks
main_tabs = [
    "📖 Guide", 
    "📊 Intelligence", 
    "📝 Strategy", 
    "🎨 Creative", 
    "🔍 Audit", 
    "👁️ Vision", 
    "🎬 Veo Studio", 
    "🤝 Team Intel"
]

# 2. Dynamically add Admin tab ONLY for users with the 'admin' role
if user_row.get('role') == 'admin':
    main_tabs.append("⚙ Admin")

# 3. Create the actual Tab objects
tabs_obj = st.tabs(main_tabs)

# 4. Map the names to the objects (The Switchboard)
TAB = {name: tabs_obj[i] for i, name in enumerate(main_tabs)}

# --- 5. FILL CONTENT ---
# Now your existing code like 'with TAB["🤝 Team Intel"]:' will work perfectly.

# 2. Dynamically add Admin tab ONLY for admins
if user_row.get('role') == 'admin':
    main_tabs.append("⚙ Admin")

# 3. Create the Tab objects and map them to the TAB dictionary
tabs = st.tabs(main_tabs)
TAB = dict(zip(main_tabs, tabs))

# --- D. Admin God-MODE (Paste your updated logic here) ---
if "⚙ Admin" in TAB:
    with TAB["⚙ Admin"]:
        st.header("⚙️ System Forensics & User Control")
        
        # All sub-tabs defined at the same level
        admin_sub1, admin_sub2, admin_sub3 = st.tabs(["📊 Activity Logs", "👥 User Manager", "🔐 Security"])

        # --- SUB-TAB 1: ACTIVITY AUDIT ---
        with admin_sub1:
            st.subheader("Global Activity Audit")
            conn = sqlite3.connect('breatheeasy.db')
            try:
                audit_df = pd.read_sql_query("SELECT * FROM master_audit_logs ORDER BY id DESC LIMIT 50", conn)
                st.dataframe(audit_df, use_container_width=True)
            except:
                st.info("No audit logs found yet. Run your first swarm to see data.")
            conn.close()

        # --- SUB-TAB 2: USER MANAGER ---
        with admin_sub2:
            st.subheader("Subscriber Management")
            conn = sqlite3.connect('breatheeasy.db')
            # Using 'plan' to match your schema
            users_df = pd.read_sql("SELECT id, username, name, email, plan, role, credits FROM users", conn)
            st.dataframe(users_df, use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### ➕ Sync User Account")
                with st.form("admin_user_form", clear_on_submit=True):
                    u_name = st.text_input("Username")
                    u_full = st.text_input("Full Name")
                    u_tier = st.selectbox("Plan", ["Basic", "Pro", "Enterprise", "Unlimited"])
                    u_creds = st.number_input("Credits", value=10)
                    if st.form_submit_button("Update/Create"):
                        conn.execute("""
                            INSERT INTO users (username, name, plan, credits, role, verified)
                            VALUES (?, ?, ?, ?, 'user', 1)
                            ON CONFLICT(username) DO UPDATE SET 
                            name=excluded.name, plan=excluded.plan, credits=excluded.credits
                        """, (u_name, u_full, u_tier, u_creds))
                        conn.commit()
                        st.success(f"User {u_name} synced!")
                        st.rerun()

            with col2:
                st.markdown("### 🗑️ Remove User")
                u_del = st.selectbox("Select Account", users_df['username'].tolist(), key="admin_del_sel")
                if st.button("🔴 Permanently Delete User"):
                    if u_del != user_row['username']:
                        conn.execute("DELETE FROM users WHERE username = ?", (u_del,))
                        conn.commit()
                        st.warning(f"Purged: {u_del}")
                        st.rerun()
                    else:
                        st.error("Admin cannot delete themselves.")
            conn.close()

        # --- SUB-TAB 3: SECURITY ---
        with admin_sub3:
            st.subheader("Credential Overrides")
            conn = sqlite3.connect('breatheeasy.db')
            target_p = st.selectbox("Reset Password For:", users_df['username'].tolist(), key="p_mgr")
            new_p = st.text_input("New Secure Password", type="password")
            
            if st.button("🛠️ Reset & Hash Credentials"):
                hashed_p = stauth.Hasher([new_p]).generate()[0]
                conn.execute("UPDATE users SET password = ? WHERE username = ?", (hashed_p, target_p))
                conn.commit()
                st.success(f"Password reset for {target_p}!")
            conn.close()
