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
    """Ensures the DB exists and all SaaS tables/columns are present."""
    conn = sqlite3.connect('breatheeasy.db')
    cursor = conn.cursor()
    
    # 1. USER TABLE (Existing)
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
    
    # 2. LEADS TABLE (New - For Team Intel Kanban)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT,
            service TEXT,
            status TEXT DEFAULT 'Discovery',
            team_id TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 3. MIGRATIONS (Ensures existing DBs get the new columns without crashing)
    migrations = [
        ("users", "plan", "TEXT DEFAULT 'Basic'"),
        ("users", "role", "TEXT DEFAULT 'user'"),
        ("users", "team_id", "TEXT DEFAULT 'HQ_001'"),
        ("leads", "team_id", "TEXT") # Ensure leads table has team tracking
    ]
    
    for table, col_name, col_type in migrations:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass # Column already exists
            
    conn.commit()
    conn.close()

# Keep this call right under the function definition
sync_database_schema()

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

# =================================================================
# --- 3. THE SECURITY GATE & SaaS PRICING ---
# =================================================================
if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=220)
    st.title("🚀 Marketing Swarm Intelligence")
    st.markdown("---")

    auth_tabs = st.tabs(["🔑 Login", "✨ Pricing & Sign Up", "🤝 Join Team", "❓ Forget Password"])
    
    # --- TAB 0: LOGIN ---
    with auth_tabs[0]:
        authenticator.login(location='main')
        if st.session_state.get("authentication_status"):
            st.rerun()
            
    # --- TAB 1: PRICING & SIGN UP ---
    with auth_tabs[1]:
        st.subheader("Select Your Swarm Package")
        
        # 2026 Industry Standard Pricing Tiers
        p1, p2, p3 = st.columns(3)
        
        with p1:
            st.markdown("""
            <div style="border:1px solid #E5E7EB; padding:20px; border-radius:10px; text-align:center;">
                <h3>🥉 LITE</h3>
                <h2 style="color:#2563EB;">$99<small>/mo</small></h2>
                <p><i>The "Solopreneur" Swarm</i></p>
                <ul style="text-align:left; font-size:14px;">
                    <li>3 Specialized Agents</li>
                    <li>Standard PDF Reports</li>
                    <li>Single User Access</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Choose Lite", key="p_lite", use_container_width=True):
                st.session_state.selected_tier = "lite"

        with p2:
            st.markdown("""
            <div style="border:2px solid #2563EB; padding:20px; border-radius:10px; text-align:center; background-color:#F8FAFC;">
                <span style="background-color:#2563EB; color:white; padding:2px 10px; border-radius:5px; font-size:12px;">MOST POPULAR</span>
                <h3>🥈 PRO</h3>
                <h2 style="color:#2563EB;">$299<small>/mo</small></h2>
                <p><i>The "Growth" Swarm</i></p>
                <ul style="text-align:left; font-size:14px;">
                    <li><b>All 8 AI Agents</b></li>
                    <li>White-label Word/PDF</li>
                    <li>Team Kanban Pipeline</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Choose Pro", key="p_pro", use_container_width=True):
                st.session_state.selected_tier = "pro"

        with p3:
            st.markdown("""
            <div style="border:1px solid #E5E7EB; padding:20px; border-radius:10px; text-align:center;">
                <h3>🥇 ENTERPRISE</h3>
                <h2 style="color:#2563EB;">$999<small>/mo</small></h2>
                <p><i>The "Global" Swarm</i></p>
                <ul style="text-align:left; font-size:14px;">
                    <li>Unlimited Swarms</li>
                    <li>Admin Forensics Hub</li>
                    <li>API & Custom Training</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Choose Enterprise", key="p_ent", use_container_width=True):
                st.session_state.selected_tier = "enterprise"

        # Registration Logic based on selection
        if st.session_state.get('selected_tier'):
            st.info(f"✨ You've selected the **{st.session_state.selected_tier.upper()}** plan. Complete your registration below:")
            try:
                # This creates the user in your 'credentials' dict
                if authenticator.register_user(location='main'):
                    st.success("Account created successfully! Switch to the 'Login' tab to enter.")
            except Exception as e:
                st.error(f"Error during registration: {e}")

    # --- TAB 2: JOIN TEAM ---
    with auth_tabs[2]:
        st.subheader("🤝 Request Enterprise Team Access")
        st.markdown("To sync with an existing corporate swarm, enter your **Organization ID** below.")
        with st.form("team_request_form"):
            team_id_req = st.text_input("Enterprise Team ID", placeholder="e.g., HQ_NORTH_2026")
            reason = st.text_area("Purpose of Access", placeholder="e.g., Regional Marketing Analyst")
            if st.form_submit_button("Submit Access Request", use_container_width=True):
                st.success(f"Request for Team {team_id_req} logged. Status: PENDING.")

    # --- TAB 3: FORGET PASSWORD ---
    with auth_tabs[3]:
        authenticator.forgot_password(location='main')

    st.stop()
        
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

import streamlit as st
import sqlite3
import pandas as pd

# =================================================================
# --- MASTER COMMAND CENTER: CLEAN SYNCED RENDERER (FINAL) ---
# =================================================================

# -----------------------------
# Agent Specs + Tooltips
# -----------------------------
AGENT_SPECS = {
    "analyst": "🕵️ **Market Analyst**: Scans competitors and identifies price-gaps.",
    "ads": "📺 **Ads Architect**: Generates high-converting copy for Meta/Google.",
    "creative": "🎨 **Creative Director**: Provides high-fidelity image prompts.",
    "strategist": "📝 **Swarm Strategist**: Builds a 30-day CEO-level ROI roadmap.",
    "social": "📱 **Social Engineer**: Crafts engagement-driven posts.",
    "geo": "📍 **Geo-Fencer**: Optimizes local map rankings.",
    "audit": "🔍 **Technical Auditor**: Finds site 'leaks' and speed issues.",
    "seo": "📝 **SEO Architect**: Builds content clusters for SGE ranking."
}

DEPLOY_GUIDES = {
    "analyst": "Identify price-gaps to undercut rivals.",
    "ads": "Translate platform hooks into ad headlines and angles.",
    "creative": "Use prompts for Midjourney/Canva conversion assets.",
    "strategist": "30-day CEO roadmap. Start with Phase 1 quick wins.",
    "social": "Deploy viral hooks and community engagement posts.",
    "geo": "Update citations and optimize for 'near me' search intent.",
    "audit": "Patch technical leaks to improve speed and conversions.",
    "seo": "Publish for SGE and optimize for zero-click answers."
}

# -----------------------------
# Safety guards
# -----------------------------
if "agent_map" not in globals() or not agent_map:
    st.error("agent_map is missing or empty. Define agent_map before rendering this dashboard.")
    st.stop()

# user_row is a pandas Series in your app; .get works, but we normalize carefully
role_val = None
try:
    role_val = user_row.get("role")
except Exception:
    role_val = None

current_role = (role_val or st.session_state.get("role") or "user")
current_role = str(current_role).strip().lower()
is_admin = current_role in {"admin", "system admin", "system_admin", "superadmin"}

# -----------------------------
# Build tab labels
# -----------------------------
agent_titles = [a[0] for a in agent_map]
tab_labels = ["📖 Guide"] + agent_titles + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_admin:
    tab_labels.append("⚙ Admin")

# -----------------------------
# Helpers
# -----------------------------
def show_deploy_guide(title: str, key: str):
    st.markdown(
        f"""
        <div style="background-color:#f0f2f6; padding:14px; border-radius:10px;
                    border-left: 5px solid #2563EB; margin-bottom: 14px;">
            <b style="color:#0f172a;">🚀 {title.upper()} DEPLOYMENT GUIDE:</b><br>
            <span style="color:#334155;">{DEPLOY_GUIDES.get(key, "Intelligence Gathering")}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_guide():
    st.header("📖 Agent Intelligence Manual")
    st.info(f"Command Center Active for: {st.session_state.get('biz_name', 'Global Mission')}")

    st.subheader("Agent Specializations")
    for _, desc in AGENT_SPECS.items():
        st.markdown(desc)

    st.markdown("---")
    st.markdown("### 🛡️ Swarm Execution Protocol")
    st.write("1) Launch from the sidebar\n2) Edit inside the Agent Seat\n3) Export using Word/PDF buttons")

def render_agent_seat(title: str, key: str):
    st.subheader(f"🚀 {title} Seat")
    show_deploy_guide(title, key)

    report = st.session_state.get("report") or {}
    if st.session_state.get("gen") and report:
        content = report.get(key)
        if content:
            edited = st.text_area("Refine Intel", value=str(content), height=400, key=f"ed_{key}")
            c1, c2 = st.columns(2)

            with c1:
                st.download_button(
                    "📄 Download Word",
                    export_word(edited, title),
                    file_name=f"{key}.docx",
                    key=f"w_{key}"
                )

            with c2:
                st.download_button(
                    "📕 Download PDF",
                    export_pdf(edited, title),
                    file_name=f"{key}.pdf",
                    key=f"p_{key}"
                )
        else:
            st.warning("Agent not selected for this run.")
    else:
        st.info("System Standby. Launch from sidebar.")

def render_vision():
    st.header("👁️ Visual Intelligence")
    st.write("Visual audits and image analysis results appear here.")

def render_veo():
    st.header("🎬 Veo Video Studio")
    st.write("AI video generation assets appear here.")

def render_team_intel():
    st.header("🤝 Global Team Pipeline")
    try:
        with sqlite3.connect("breatheeasy.db") as conn:
            if is_admin:
                query, params = "SELECT * FROM leads", ()
            else:
                team_id = user_row.get("team_id") if hasattr(user_row, "get") else None
                query, params = "SELECT * FROM leads WHERE team_id = ?", (team_id,)
            team_df = pd.read_sql_query(query, conn, params=params)

        if team_df.empty:
            st.info("Pipeline currently empty.")
        else:
            st.dataframe(team_df, use_container_width=True)

    except Exception as e:
        st.error(f"Team Intel Error: {e}")

def render_admin():
    st.header("⚙️ Admin Forensics")

    admin_sub1, admin_sub2, admin_sub3 = st.tabs(["📊 Logs", "👥 Users", "🔐 Security"])

    with admin_sub1:
        st.subheader("Global Activity Audit")
        try:
            with sqlite3.connect("breatheeasy.db") as conn:
                audit_df = pd.read_sql_query(
                    "SELECT * FROM master_audit_logs ORDER BY id DESC LIMIT 50",
                    conn
                )
            st.dataframe(audit_df, use_container_width=True)
        except Exception as e:
            st.info(f"No audit logs found yet (or table missing). Details: {e}")

    with admin_sub2:
        st.subheader("Subscriber Management")
        try:
            with sqlite3.connect("breatheeasy.db") as conn:
                users_df = pd.read_sql_query(
                    "SELECT id, username, name, email, plan, role, credits FROM users",
                    conn
                )
            st.dataframe(users_df, use_container_width=True)
        except Exception as e:
            st.error(f"User Manager Error: {e}")

    with admin_sub3:
        st.subheader("Credential Overrides")

        try:
            with sqlite3.connect("breatheeasy.db") as conn:
                users_list_df = pd.read_sql_query("SELECT username FROM users", conn)

            if users_list_df.empty:
                st.info("No users available to reset.")
                return

            target_p = st.selectbox("Reset Password For:", users_list_df["username"].tolist(), key="p_mgr")
            new_p = st.text_input("New Secure Password", type="password")

            if st.button("🛠️ Reset & Hash Credentials"):
                if not new_p:
                    st.error("Enter a new password first.")
                else:
                    # ✅ consistent with your earlier usage
                    hashed_p = stauth.Hasher.hash(new_p)
                    with sqlite3.connect("breatheeasy.db") as conn:
                        conn.execute(
                            "UPDATE users SET password = ? WHERE username = ?",
                            (hashed_p, target_p)
                        )
                        conn.commit()
                    st.success(f"Password reset for {target_p}!")

        except Exception as e:
            st.error(f"Security Tab Error: {e}")

# -----------------------------
# Create tabs ONCE and render ONCE (NO DUPLICATION)
# -----------------------------
tabs_obj = st.tabs(tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(tab_labels)}

with TAB["📖 Guide"]:
    render_guide()

for (title, key) in agent_map:
    with TAB[title]:
        render_agent_seat(title, key)

with TAB["👁️ Vision"]:
    render_vision()

with TAB["🎬 Veo Studio"]:
    render_veo()

with TAB["🤝 Team Intel"]:
    render_team_intel()

if "⚙ Admin" in TAB:
    with TAB["⚙ Admin"]:
        if is_admin:
            render_admin()
        else:
            st.error("Not authorized.")
