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

# --- HELPER FUNCTIONS: VERIFICATION & SYSTEM HEALTH ---

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
    """Sprint 5: Performance optimization for geographic selectors"""
    return {
        "Alabama": ["Birmingham", "Huntsville", "Mobile"],
        "Arizona": ["Phoenix", "Scottsdale", "Tucson"],
        "California": ["Los Angeles", "San Francisco", "San Diego"],
        "Florida": ["Miami", "Orlando", "Tampa"],
        "Illinois": ["Chicago", "Naperville", "Plainfield"],
        "Texas": ["Austin", "Dallas", "Houston"],
    }

# --- 1. SYSTEM INITIALIZATION ---
try:
    import stripe
    stripe.api_key = st.secrets.get("STRIPE_API_KEY", "sk_test_placeholder")
except ImportError:
    stripe = None

if 'theme' not in st.session_state: st.session_state.theme = 'light'
if 'processing' not in st.session_state: st.session_state.processing = False
if 'gen' not in st.session_state: st.session_state.gen = False
if 'report' not in st.session_state: st.session_state.report = {}

def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

os.environ["OTEL_SDK_DISABLED"] = "true"
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

st.set_page_config(page_title="TechInAdvance AI | Enterprise Command", page_icon="Logo1.jpeg", layout="wide")

# --- 2. EXECUTIVE UI CSS ---
sidebar_color = "#2563EB"
st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFCF0; color: #1E293B; }}
    [data-testid="stSidebar"] {{ 
        background-color: {"#1E293B" if st.session_state.theme == 'dark' else "#FFFFFF"} !important; 
        border-right: 3px solid rgba(0,0,0,0.1) !important;
        box-shadow: 4px 0px 10px rgba(0,0,0,0.05);
    }}
    .price-card {{
        background-color: white; padding: 20px; border-radius: 12px; border: 2px solid {sidebar_color};
        text-align: center; margin-bottom: 15px; color: #1E293B; box-shadow: 0px 4px 8px rgba(0,0,0,0.05);
    }}
    .guide-box {{ background: #F1F5F9; padding: 15px; border-radius: 8px; border: 1px dashed {sidebar_color}; font-size: 0.85rem; margin-bottom: 20px; color: #475569; }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800; height: 3.2em; }}
    .kanban-card {{ background: white; padding: 18px; border-radius: 10px; margin-bottom: 12px; border-left: 5px solid {sidebar_color}; box-shadow: 0px 2px 6px rgba(0,0,0,0.04); }}
    .kanban-header {{ font-weight: 900; text-align: center; color: {sidebar_color}; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 1.5px; font-size: 0.9rem; border-bottom: 2px solid {sidebar_color}33; padding-bottom: 8px; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE INITIALIZATION (ENTERPRISE & AUDIT READY) ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    
    # 3A. CORE USER REGISTRY
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, 
                  role TEXT, plan TEXT, credits INTEGER DEFAULT 0, 
                  logo_path TEXT, team_id TEXT)''')
    
    # 3B. STRATEGIC LEADS & KANBAN DATA
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, 
                  industry TEXT, service TEXT, city TEXT, content TEXT, 
                  team_id TEXT, status TEXT DEFAULT 'Discovery')''')
    
    # 3C. MASTER AUDIT LOGS (NEW: SPRINT 4 INFRASTRUCTURE)
    # This tracks every technical forensic and ad generation event for Admin review
    c.execute('''CREATE TABLE IF NOT EXISTS master_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    user TEXT,
                    action_type TEXT,
                    target_biz TEXT,
                    location TEXT,
                    credit_cost INTEGER,
                    status TEXT
                )''')

    # 3D. LEGACY SYSTEM LOGS
    c.execute('''CREATE TABLE IF NOT EXISTS system_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, 
                  action TEXT, user TEXT, details TEXT)''')
    
    # 3E. SAFETY MIGRATION: ADD 'VERIFIED' COLUMN IF MISSING
    try:
        c.execute("ALTER TABLE users ADD COLUMN verified INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        # Column already exists, proceeding safely
        pass
    
    # 3F. INITIALIZE ROOT ADMIN (AUTO-VERIFIED)
    hashed_pw = stauth.Hasher.hash('admin123')
    c.execute("""INSERT OR IGNORE INTO users 
                 (username, email, name, password, role, plan, credits, logo_path, team_id, verified) 
                 VALUES (?,?,?,?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001', 1)""", 
              ('admin', 'admin@techinadvance.ai', 'Admin', hashed_pw))
    
    conn.commit()
    conn.close()

# Execute Initialization
init_db()

# --- 4. AUTHENTICATION ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
    conn.close()
    return {'usernames': {row['username']: {'email':row['email'], 'name':row['name'], 'password':row['password']} for _, row in df.iterrows()}}

authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=200)
    auth_tabs = st.tabs(["🔑 Login", "📝 Enrollment", "🤝 Join Team", "❓ Recovery"])
    with auth_tabs[0]: authenticator.login(location='main')
    with auth_tabs[1]:
        plan = st.selectbox("Select Business Plan", ["Basic", "Pro", "Enterprise"])
        res = authenticator.register_user(location='main')
        if res:
            e, u, n = res
            raw_pw = st.text_input("Security Password", type="password")
            if st.button("Finalize Enrollment"):
                h = stauth.Hasher([raw_pw]).generate()[0]
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("INSERT INTO users VALUES (?,?,?,?,'member',?,50,'Logo1.jpeg',?)", (u, e, n, h, plan, f"TEAM_{u}"))
                conn.commit(); conn.close()
                st.success("Enrolled. Please Log In."); st.rerun()
    st.stop()

# --- 5. LOGGED-IN SESSION ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()

# --- EXPORT HELPERS ---
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

# --- 5D. SIDEBAR COMMAND CONSOLE (S5 PERFORMANCE EDITION) ---
with st.sidebar:
    # 1. SPRINT 5: SYSTEM HEARTBEAT MONITOR
    health = check_system_health()
    is_healthy = all(health.values())
    
    status_emoji = "🟢" if is_healthy else "🔴"
    status_label = "SYSTEM OPERATIONAL" if is_healthy else "SYSTEM MAINTENANCE"
    
    st.caption(f"{status_emoji} **{status_label}**")
    
    if not is_healthy:
        with st.expander("⚠️ Infrastructure Alerts"):
            for svc, state in health.items():
                st.write(f"{svc}: {'✅' if state else '❌'}")
    
    st.divider()

    # 2. BRANDING & METRICS
    st.image(user_row['logo_path'], width=120)
    st.button("🌓 Toggle Theme", on_click=toggle_theme)
    st.metric("Credits Available", user_row['credits'])
    st.divider()
    
    biz_name = st.text_input("Brand Name", placeholder="e.g. Acme Solar")

    # 3. SPRINT 5: CACHED GEOGRAPHIC DATA
    # Call the cached function defined in your Helpers section
    location_data = get_geo_data()

    # RESTORED: DYNAMIC LOCATION LOGIC
    state_list = sorted(list(location_data.keys())) + ["Other (Manual Entry)"]
    selected_state = st.selectbox("🎯 Target State", state_list)

    if selected_state == "Other (Manual Entry)":
        c_col, s_col = st.columns(2)
        with c_col: m_city = st.text_input("City")
        with s_col: m_state = st.text_input("State")
        full_loc = f"{m_city}, {m_state}"
    else:
        # Pulls cities instantly from memory
        city_list = sorted(location_data[selected_state]) + ["City not listed..."]
        selected_city = st.selectbox(f"🏙️ Select City ({selected_state})", city_list)
        
        if selected_city == "City not listed...":
            custom_city = st.text_input(f"Type City in {selected_state}")
            full_loc = f"{custom_city}, {selected_state}"
        else:
            full_loc = f"{selected_city}, {selected_state}"

    st.caption(f"📍 Focus: **{full_loc}**")
    
    # ... (Rest of sidebar: Requirements, Toggles, and Launch Button) ...

    # RESTORED: AGENT CUSTOM REQUIREMENTS BOX
    st.divider()
    with st.expander("🛠️ Custom Agent Requirements", expanded=False):
        user_requirements = st.text_area("Add specific directives", 
                                         placeholder="e.g., 'Focus on high-ticket luxury clients'", 
                                         key="agent_reqs")

    audit_url = st.text_input("Audit URL (Optional)")
    
    ind_cat = st.selectbox("Industry", ["HVAC", "Medical", "Solar", "Legal", "Custom"])
    if ind_cat == "Custom":
        final_ind = st.text_input("Type Your Custom Industry")
        svc = st.text_input("Type Your Custom Service")
    else:
        final_ind = ind_cat
        svc = st.text_input("Service Type")
        
    st.divider(); st.subheader("🤖 Swarm Personnel")
    toggles = {k: st.toggle(v, value=True) for k, v in {
        "analyst": "🕵️ Analyst", "ads": "📺 Ad Tracker", "builder": "🎨 Creative", 
        "manager": "👔 Strategist", "social": "✍ Social", "geo": "🧠 GEO", 
        "audit": "🌐 Auditor", "seo": "✍ SEO"}.items()}
    
    # SPRINT 2: VERIFICATION GATE
    if is_verified(st.session_state["username"]):
        run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
    else:
        trigger_verification(user_row['email'])
        run_btn = False 
    
    st.divider()
    if st.button("🔒 End Demo Session", use_container_width=True):
        st.session_state.show_cleanup_confirm = True

    authenticator.logout('Sign Out', 'sidebar')

# --- 7. SWARM EXECUTION ENGINE (FORCE PERSISTENCE & DATA ANCHOR) ---
if run_btn:
    # 7A. Validation Check
    if not biz_name or not full_loc:
        st.error("❌ Identification required: Please provide Brand Name and Location.")
    elif user_row['credits'] <= 0:
        st.error("❌ Out of credits: Please contact your administrator.")
    else:
        # 1. PRE-RUN HYGIENE: Clear old reports to ensure clean rendering
        st.session_state.report = {} 
        st.session_state.gen = False

        with st.status("🛠️ Coordinating Swarm Agents...", expanded=True) as status:
            try:
                # 2. PROGRESS VISUALIZER
                progress_bar = st.progress(0, text="Initializing Swarm...")
                
                # 3. EXECUTE BACKEND SWARM
                # This calls the run_marketing_swarm function in main.py
                progress_bar.progress(10, text="🕵️ Phase 1: Market Discovery & Forensics...")
                
                report_data = run_marketing_swarm({
                    'city': full_loc, 
                    'industry': final_ind, 
                    'service': svc, 
                    'biz_name': biz_name, 
                    'url': audit_url, 
                    'toggles': toggles,
                    'custom_reqs': user_requirements 
                })

                # 4. DATA ANCHORING: Hard-lock the results into session_state
                # We map the returned dictionary to the UI state immediately
                st.session_state.report = report_data
                st.session_state.gen = True  # This locks the Tabs view to "Visible"

                progress_bar.progress(85, text="👔 Phase 3: Finalizing Strategy & Logging...")

                # 5. ATOMIC DATABASE TRANSACTION
                conn = sqlite3.connect('breatheeasy.db')
                cursor = conn.cursor()
                try:
                    # Deduct Credits
                    cursor.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
                    
                    # Log to Master Audit
                    cursor.execute("""
                        INSERT INTO master_audit_logs 
                        (timestamp, user, action_type, target_biz, location, credit_cost, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        user_row['username'],
                        "OMNI_SWARM_LAUNCH",
                        biz_name,
                        full_loc,
                        1,
                        "SUCCESS"
                    ))
                    conn.commit()
                except Exception as db_e:
                    conn.rollback()
                    raise db_e
                finally:
                    conn.close()

                # 6. FINAL UI SYNC
                progress_bar.progress(100, text="✅ Intelligence Synchronized.")
                status.update(label="🚀 Swarm Complete!", state="complete")
                
                # Small delay to ensure state stability before the UI refresh
                import time
                time.sleep(0.5)
                
                st.rerun()

            except Exception as e:
                status.update(label="❌ Swarm Interrupted", state="error")
                st.error(f"Critical Backend Error: {e}")
                st.session_state.gen = False # Ensure tabs don't show empty on error
                
# --- 6. MULTIMODAL COMMAND CENTER (DEFENSIVE RENDERING) ---

# 1. INITIALIZE TITLES
tab_titles = [
    "📖 Guide", "🕵️ Analyst", "📺 Ads", "🎨 Creative", "👔 Strategist", 
    "✍ Social", "🧠 GEO", "🌐 Auditor", "✍ SEO", "👁️ Vision", 
    "🎬 Veo Studio", "🤝 Team Intel"
]

# 2. RBAC GATE: Check Admin Status
is_admin = user_row.get('role') == 'admin'
if is_admin: 
    tab_titles.append("⚙ Admin")

# 3. VERIFICATION GATE: Check Verification Status
user_is_verified = is_verified(st.session_state["username"])

# 4. INITIALIZE TABS & INTEGRITY CHECK
tabs = st.tabs(tab_titles)
TAB = {name: tabs[i] for i, name in enumerate(tab_titles)}

# --- TAB RENDERING ENGINE ---

with TAB["📖 Guide"]:
    st.header("📖 Agent Intelligence Manual")
    st.info("The Omni-Swarm engine coordinates 8 specialized AI agents to deconstruct markets and engineer high-ticket growth.")
    
    g_col1, g_col2 = st.columns(2)
    with g_col1:
        with st.expander("🕵️ Intelligence & Audit Cluster", expanded=True):
            st.markdown("""
            - **Market Analyst:** Quantifies the 'Market Entry Gap' and competitor pricing arbitrage.
            - **Forensic Vision:** Diagnoses technical defects in field photos and deconstructs rival design psychology.
            - **Ad Tracker:** Performs psychological teardowns of live competitor hooks and spend patterns.
            - **Web Auditor:** Identifies conversion friction and technical 'money leaks' on any URL.
            """)
    with g_col2:
        with st.expander("👔 Production & Strategy Cluster", expanded=True):
            st.markdown("""
            - **Creative Director:** Engineers cross-platform ad copy (Google/Meta) and cinematic Veo video prompts.
            - **SEO Architect:** Crafts technical E-E-A-T articles to dominate AI-Search (SGE) results.
            - **GEO Specialist:** Optimizes local 'Citation Velocity' and AI-Map visibility.
            - **Swarm Strategist:** Synthesizes all intelligence into a 30-Day Phased ROI Roadmap.
            """)

def render_agent(tab_key, title, report_key):
    
    # --- SPRINT 3: IMPLEMENTATION MANUALS ---
    DEPLOYMENT_GUIDES = {
        "analyst": "Identify the 'Price-Gap' in the competitor table. Use this to undercut rivals while maintaining premium positioning in your high-margin services.",
        "ads": "Copy these platform-specific ad sets directly into Google or Meta Ads Manager. The psychological hooks are engineered to disrupt local rival traffic.",
        "creative": "Implement these multi-channel copy sets. Use the cinematic Veo prompts to generate high-fidelity video ads for Meta Reels or YouTube Shorts.",
        "strategist": "This 30-day roadmap is your CEO-level execution checklist. Present the ROI projections to stakeholders to justify marketing spend allocation.",
        "social": "Deploy these viral hooks across LinkedIn, IG, and X using the distribution schedule to hit your audience during peak local engagement hours.",
        "geo": "Update your Google Business Profile keywords and local citation metadata based on these technical AI-search ranking factors.",
        "audit": "Forward this technical brief to your web development team. It contains specific action items to patch 'money leaks' and increase conversion speed.",
        "seo": "Publish this technical article to your domain. It is optimized with E-E-A-T markers to secure high-authority rankings in AI Search Generative Experience (SGE)."
    }

    with TAB[tab_key]:
        st.subheader(f"{title} Command Seat")
        
        # 1. SECURITY & VERIFICATION CHECK
        if not user_is_verified:
            st.error("🛡️ Verification Required: This agent's seat is locked until email verification is complete.")
            return

        # 2. STRATEGIC DEPLOYMENT GUIDE (World-Class SaaS UI)
        guide_text = DEPLOYMENT_GUIDES.get(report_key, "Review this report to align with your growth strategy.")
        st.markdown(f"""
            <div style="background-color:rgba(37, 99, 235, 0.1); padding:15px; border-radius:10px; border-left: 6px solid #2563EB; margin-bottom:25px;">
                <b style="color:#2563EB; font-size: 1.1rem;">🚀 DEPLOYMENT GUIDE:</b><br>
                <span style="color:#1E293B; font-size: 0.95rem;">{guide_text}</span>
            </div>
        """, unsafe_allow_html=True)

       # --- 8. DYNAMIC REPORT RENDERING ---
# This 'if' must be at the far left margin (no spaces before it)
if st.session_state.gen:
    # 1. Define Map
    agent_map = [
        ("🕵️ Analyst", "analyst"), ("🎨 Creative", "creative"), 
        ("👔 Strategist", "strategist"), ("📱 Social", "social"), 
        ("📍 GEO", "geo"), ("🌐 Auditor", "auditor"), ("✍ SEO", "seo")
    ]
    
    # 2. Initialize Tabs
    all_tab_labels = [a[0] for a in agent_map] + ["👁️ Vision", "🎬 Veo Studio", "⚙ Admin"]
    TAB = st.tabs(all_tab_labels)

    # 3. Dynamic Loop for Standard Agents
    for i, (title, report_key) in enumerate(agent_map):
        with TAB[i]:
            st.subheader(f"{title} Intelligence")
            content = st.session_state.report.get(report_key, "Intelligence not available.")
            edited = st.text_area(f"Refine {title}", value=str(content), height=350, key=f"edit_{report_key}")
            
            c1, c2 = st.columns(2)
            with c1: st.download_button("📄 Word Brief", create_word_doc(edited, title), f"{title}.docx", key=f"w_{report_key}")
            with c2: st.download_button("📕 PDF Report", create_pdf(edited, svc, full_loc), f"{title}.pdf", key=f"p_{report_key}")

    # --- 9. SPECIALTY TABS (STILL INSIDE THE 'IF GEN' BLOCK) ---
    with TAB[7]: # Vision
        st.subheader("👁️ Vision Inspector")
        v_intel = st.session_state.report.get('vision', "Vision analysis pending.")
        st.markdown(v_intel)
        
    with TAB[8]: # Veo
        st.subheader("🎬 Veo Cinematic Studio")
        v_prompt = st.text_area("Video Scene Prompt", key="veo_prompt_area")
        
    # --- 9C. GOD-MODE ADMIN (INTEGRATED) ---
    with TAB[9]:
        if is_admin:
            st.header("⚙️ God-Mode Management")
            st.warning("⚡ Root Access: Viewing global system infrastructure.")
            
            conn = sqlite3.connect('breatheeasy.db')
            # (Metrics and Table logic here...)
            st.success("Admin Session Verified.")
            conn.close()
        else:
            # SECURITY GATEKEEPER
            st.error("🚫 Administrative Access Denied.")
            st.info("Your account does not have the permissions required to view system infrastructure.")

# --- FINAL ELSE BLOCK ---
else:
    # This 'else' MUST align perfectly with the 'if st.session_state.gen' at the top
    st.info("👋 Welcome! Configure your Swarm Personnel in the sidebar and click 'Launch' to generate intelligence.")
    
# Render Specialty Tabs
with TAB["👁️ Vision"]:
    st.subheader("👁️ Vision Inspector")
    
    # 1. SECURITY & VERIFICATION CHECK
    if not user_is_verified:
        st.error("🛡️ Verification Required: Vision Intelligence is locked until email verification is complete.")
    else:
        # 2. DEPLOYMENT GUIDE: TECHNICAL FORENSICS
        st.markdown("""
            <div style="background-color:rgba(37, 99, 235, 0.1); padding:15px; border-radius:10px; border-left: 6px solid #2563EB; margin-bottom:25px;">
                <b style="color:#2563EB; font-size: 1.1rem;">🚀 DEPLOYMENT GUIDE:</b><br>
                <span style="color:#1E293B; font-size: 0.95rem;">
                <b>Field Analysis:</b> Use the 'Severity Score' to justify urgent repairs or service calls. 
                Share the 'Evidence of Need' summary directly with customers to build trust via transparency.
                </span>
            </div>
        """, unsafe_allow_html=True)

        if st.session_state.gen:
            v_intel = st.session_state.report.get('vision_intel', "Vision analysis data not found in state.")
            st.markdown(f'<div class="executive-brief">{v_intel}</div>', unsafe_allow_html=True)
        
        # 3. FILE UPLOADER FOR CUSTOMER EVIDENCE
        v_file = st.file_uploader("Upload Evidence for Analysis (Roofing, HVAC, Damage)", type=['png','jpg','jpeg'], key="vis_up_main")
        if v_file: 
            st.image(v_file, use_container_width=True, caption="Target Asset for Forensic Swarm")

with TAB["🎬 Veo Studio"]:
    st.subheader("🎬 Veo Cinematic Studio")
    
    # 1. SECURITY & VERIFICATION CHECK
    if not user_is_verified:
        st.error("🛡️ Verification Required: Cinematic Production is locked until email verification is complete.")
    else:
        # 2. DEPLOYMENT GUIDE: VIDEO MARKETING
        st.markdown("""
            <div style="background-color:rgba(124, 58, 237, 0.1); padding:15px; border-radius:10px; border-left: 6px solid #7C3AED; margin-bottom:25px;">
                <b style="color:#7C3AED; font-size: 1.1rem;">🎬 PRODUCTION GUIDE:</b><br>
                <span style="color:#1E293B; font-size: 0.95rem;">
                Deploy these cinematic assets as <b>Meta Reels, YouTube Shorts, or Website Backgrounds.</b> 
                The prompt is engineered for Google's Veo model to ensure high-fidelity brand storytelling.
                </span>
            </div>
        """, unsafe_allow_html=True)

        if st.session_state.gen:
            creative_context = st.session_state.report.get('creative', '')
            v_prompt = st.text_area("Video Scene Description (Refine for Cinematic Output)", 
                                     value=str(creative_context)[:500], 
                                     height=150, 
                                     key="veo_prompt_area")
            
            if st.button("📽️ GENERATE CINEMATIC AD", key="veo_gen_btn_main", use_container_width=True):
                with st.spinner("Veo Engine Rendering Cinematic Asset..."):
                    v_vid = generate_cinematic_ad(v_prompt)
                    if v_vid: 
                        st.video(v_vid)
                        st.success("Cinematic Asset Rendered Successfully.")
        else: 
            st.warning("Launch the Omni-Swarm first to generate creative context and specific scene descriptions for the Veo Studio.")

# Admin Tab Rendering (Only if it exists in the map)
if "⚙ Admin" in TAB:
    with TAB["⚙ Admin"]:
        # Admin logic remains identical to your previous version
        pass

# --- 9. TEAM INTEL (KANBAN PIPELINE) ---
with TAB["🤝 Team Intel"]:
    st.header("🤝 Global Pipeline Kanban")
    conn = sqlite3.connect('breatheeasy.db')
    team_df = pd.read_sql_query("SELECT * FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
    
    m1, m2, m3 = st.columns(3)
    with m1: st.metric("Total Swarms", len(team_df))
    with m2: st.metric("Active Markets", len(team_df['city'].unique()) if not team_df.empty else 0)
    with m3: st.metric("Team Health", "Operational")

    stages = ["Discovery", "Execution", "ROI Verified"]
    kanban_cols = st.columns(3)
    for i, stage in enumerate(stages):
        with kanban_cols[i]:
            st.markdown(f'<div class="kanban-header">{stage}</div>', unsafe_allow_html=True)
            stage_leads = team_df[team_df['status'] == stage] if not team_df.empty else pd.DataFrame()
            for _, lead in stage_leads.iterrows():
                with st.container():
                    st.markdown(f'<div class="kanban-card"><b>{lead["city"]}</b><br><small>{lead["service"]}</small></div>', unsafe_allow_html=True)
                    new_status = st.selectbox("Move", stages, index=stages.index(stage), key=f"kb_{lead['id']}", label_visibility="collapsed")
                    if new_status != stage:
                        conn.execute("UPDATE leads SET status = ? WHERE id = ?", (new_status, lead['id']))
                        conn.commit(); st.rerun()
    conn.close()

# --- 9C. GOD-MODE ADMIN (TAB 10 / INDEX 9) ---
    with TAB[9]: 
        # THE SECURITY GATE: This 'if' is indented inside 'with TAB[9]'
        if is_admin:
            st.header("⚙️ God-Mode Management")
            st.warning("⚡ Root Access: You are viewing global system infrastructure and audit trails.")
            
            # --- 1. GLOBAL INFRASTRUCTURE METRICS ---
            conn = sqlite3.connect('breatheeasy.db')
            
            try:
                # Fetch real-time data for high-level metrics
                total_swarms = pd.read_sql_query("SELECT COUNT(*) as count FROM master_audit_logs", conn).iloc[0]['count']
                total_users = pd.read_sql_query("SELECT COUNT(*) as count FROM users", conn).iloc[0]['count']
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Global Swarm Count", total_swarms)
                m2.metric("Total Registered Users", total_users)
                m3.metric("System Integrity", "Verified", delta="SSL/DB Active")

                st.divider()

                # --- 2. MASTER AUDIT LOG TABLE ---
                st.subheader("📊 Global Activity Audit Trail")
                audit_df = pd.read_sql_query("""
                    SELECT timestamp, user, action_type, target_biz, location, credit_cost, status 
                    FROM master_audit_logs 
                    ORDER BY id DESC LIMIT 500
                """, conn)

                if not audit_df.empty:
                    st.dataframe(
                        audit_df, 
                        use_container_width=True, 
                        hide_index=True,
                        column_config={
                            "status": st.column_config.SelectboxColumn(
                                "Status", options=["SUCCESS", "FAILED", "PENDING"], width="small"
                            )
                        }
                    )
                    
                    # --- 3. CSV EXPORT ---
                    csv_data = audit_df.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Export Audit Log (CSV)", csv_data, "audit_log.csv", "text/csv")
                
                st.divider()

                # --- 4. RAPID CREDIT INJECTION ---
                st.subheader("👤 User Management")
                u_df = pd.read_sql_query("SELECT username, credits FROM users", conn)
                target_u = st.selectbox("Select User", u_df['username'], key="god_target")
                amt = st.number_input("Credits to Add", value=10, key="god_amt")
                
                if st.button("Inject Credits", type="primary"):
                    conn.execute("UPDATE users SET credits = credits + ? WHERE username = ?", (amt, target_u))
                    conn.commit()
                    st.success(f"Added {amt} credits to {target_u}")
                    st.rerun()

            except Exception as e:
                st.error(f"Admin DB Error: {e}")
            finally:
                conn.close()

        else:
            # THIS 'else' MUST ALIGN VERTICALLY WITH 'if is_admin' ABOVE
            st.error("🚫 Administrative Access Denied.")
            st.info("Your account does not have the permissions required to view system infrastructure.")

        # --- 4. USER MANAGEMENT (CREDITS & TERMINATION) ---
        st.subheader("👤 User Registry Management")
        all_users = pd.read_sql_query("SELECT username, email, credits, plan, verified FROM users", conn)
        st.dataframe(all_users, use_container_width=True, hide_index=True)
        
        # Credit Injection Logic
        st.write("**Credit Injection & User Access**")
        target_u = st.selectbox("Select User", all_users['username'], key="admin_target")
        amt = st.number_input("Credits to Add", value=10, step=10)
        
        if st.button("Inject Credits"):
            conn.execute("UPDATE users SET credits = credits + ? WHERE username = ?", (amt, target_u))
            conn.commit()
            st.success(f"Successfully injected {amt} credits to {target_u}")
            st.rerun()

        conn.close()
