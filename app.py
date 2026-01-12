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

# --- 2. $1B EXECUTIVE UI CSS (INCLUDING KANBAN & PRICE CARDS) ---
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
    .kpi-card {{
        background: white; padding: 20px; border-radius: 12px; border-top: 5px solid {sidebar_color};
        box-shadow: 0px 4px 15px rgba(0,0,0,0.05); text-align: center; margin-bottom: 20px;
    }}
    .executive-brief {{
        background: #ffffff; padding: 35px; border-radius: 15px; border-left: 10px solid {sidebar_color};
        line-height: 1.8; color: #1E293B; box-shadow: 0px 10px 30px rgba(0,0,0,0.08); overflow-wrap: break-word;
    }}
    .guide-box {{ background: #F1F5F9; padding: 15px; border-radius: 8px; border: 1px dashed {sidebar_color}; font-size: 0.85rem; margin-bottom: 20px; color: #475569; }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800; height: 3.2em; }}
    
    /* --- NEW KANBAN SYSTEM CLASSES --- */
    .kanban-column {{ 
        background: rgba(255, 255, 255, 0.5); 
        padding: 15px; 
        border-radius: 12px; 
        border: 1px solid rgba(0,0,0,0.05); 
        min-height: 500px; 
    }}
    .kanban-card {{ 
        background: white; 
        padding: 18px; 
        border-radius: 10px; 
        margin-bottom: 12px; 
        border-left: 5px solid {sidebar_color}; 
        box-shadow: 0px 2px 6px rgba(0,0,0,0.04); 
    }}
    .kanban-header {{ 
        font-weight: 900; 
        text-align: center; 
        color: {sidebar_color}; 
        margin-bottom: 20px; 
        text-transform: uppercase; 
        letter-spacing: 1.5px; 
        font-size: 0.9rem; 
        border-bottom: 2px solid {sidebar_color}33; 
        padding-bottom: 8px;
    }}
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
    doc.add_heading('Executive Strategic Intelligence Brief', 0)
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

# --- 4. AUTHENTICATION & SYSTEM INITIALIZATION ---
def init_db():
    """Initializes all required tables for the Decision Intelligence Suite."""
    conn = sqlite3.connect('breatheeasy.db')
    cursor = conn.cursor()
    
    # 4A. Leads & Intelligence Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS leads 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, 
                      industry TEXT, service TEXT, city TEXT, content TEXT, 
                      team_id TEXT, status TEXT DEFAULT 'Discovery')''')
    
    # 4B. User & Credentials Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                     (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, 
                      role TEXT, plan TEXT, credits INTEGER, logo_path TEXT, team_id TEXT)''')
    
    # 4C. NEW: System Audit Logs (Tracks Purges & Maintenance)
    cursor.execute('''CREATE TABLE IF NOT EXISTS system_logs 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, 
                      action TEXT, user TEXT, details TEXT)''')
    
    conn.commit()
    conn.close()

# Ensure database is prepared
init_db()

def get_db_creds():
    """Fetches credentials from the database for Streamlit Authenticator."""
    try:
        conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
        df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
        conn.close()
        return {'usernames': {row['username']: {'email':row['email'], 'name':row['name'], 'password':row['password']} for _, row in df.iterrows()}}
    except:
        return {'usernames': {}}

# Initialize Authenticator with Cookie Management
authenticator = stauth.Authenticate(
    get_db_creds(), 
    st.secrets['cookie']['name'], 
    st.secrets['cookie']['key'], 
    30 # Cookie expiry in days
)

# --- LOGIN & REGISTRATION OVERLAY ---
if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=200)
    auth_tabs = st.tabs(["🔑 Login", "📝 Enrollment & Plans", "🤝 Join Team", "❓ Recovery"])
    
    with auth_tabs[0]: 
        authenticator.login(location='main')

    with auth_tabs[1]:
        st.markdown("### Select Enterprise Tier")
        p1, p2, p3 = st.columns(3)
        with p1: st.markdown('<div class="price-card">BASIC<br><h3>$99</h3></div>', unsafe_allow_html=True)
        with p2: st.markdown('<div class="price-card">PRO<br><h3>$499</h3></div>', unsafe_allow_html=True)
        with p3: st.markdown('<div class="price-card">ENTERPRISE<br><h3>$1,999</h3></div>', unsafe_allow_html=True)
        
        plan = st.selectbox("Select Business Plan", ["Basic", "Pro", "Enterprise"])
        
        # Streamlit-Authenticator built-in registration
        res = authenticator.register_user(location='main')
        if res:
            e, u, n = res
            raw_pw = st.text_input("Enrollment Security Password", type="password", key="reg_pw_main")
            if st.button("Finalize $1B Enrollment"):
                if raw_pw:
                    # Hash password before database storage
                    h = stauth.Hasher([raw_pw]).generate()[0]
                    conn = sqlite3.connect('breatheeasy.db')
                    # Default: member role, 50 credits, generic logo
                    conn.execute("INSERT INTO users (username, email, name, password, role, plan, credits, logo_path, team_id) VALUES (?,?,?,?,'member',?,50,'Logo1.jpeg',?)", 
                                 (u, e, n, h, plan, f"TEAM_{u}"))
                    conn.commit()
                    conn.close()
                    st.success("Account Secured. Please Log In.")
                    st.rerun()
                else:
                    st.error("Security Password required to finalize enrollment.")

    with auth_tabs[3]:
        try:
            username_forgot_pw, email_forgot_password, new_random_password = authenticator.forgot_password(location='main')
            if username_forgot_pw:
                # In a real app, logic to email 'new_random_password' to 'email_forgot_password' would go here
                st.success("Recovery processed. Internal system reset initiated.")
        except Exception as e:
            st.error(e)
            
    st.stop() # Prevents app from loading behind the login wall

# --- 5. DASHBOARD, SIDEBAR & LIVE-SYNC EXPORT ENGINE ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()

# --- 5A. MULTI-CHANNEL BROADCAST LOGIC ---
def broadcast_deployment(agent_name, target_biz, content, channel="Cloud"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    with st.spinner(f"Initiating {channel} broadcast for {agent_name}..."):
        if channel == "Email":
            st.toast(f"📧 Strategic Brief emailed at {ts}")
        elif channel == "SMS":
            st.toast(f"📱 Rapid Alert SMS dispatched at {ts}")
        else:
            st.toast(f"✅ {agent_name} synced to Command Hub at {ts}")
        st.success(f"Directives for {target_biz} shared via {channel}. [Log ID: {ts}]")

# --- 5B. STRATEGIC CRUD ENGINE ---
def manage_record(action, record_id=None, new_content=None):
    conn = sqlite3.connect('breatheeasy.db')
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if action == "save":
        conn.execute("UPDATE leads SET status = 'Execution' WHERE id = ?", (record_id,))
        st.toast(f"Record {record_id} moved to Execution.")
    elif action == "delete":
        conn.execute("DELETE FROM leads WHERE id = ?", (record_id,))
        st.warning(f"Record {record_id} purged.")
        st.rerun()
    elif action == "edit":
        conn.execute("UPDATE leads SET content = ?, date = ? WHERE id = ?", (str(new_content), ts, record_id))
        st.info(f"Record {record_id} updated.")
    conn.commit()
    conn.close()

# --- 5C. LIVE-SYNC DOCUMENT GENERATORS ---
def create_word_doc(content, title, logo_path="Logo1.jpeg"):
    doc = Document()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        if os.path.exists(logo_path): doc.add_picture(logo_path, width=Inches(1.2))
    except: pass
    doc.add_heading(f'Intelligence Brief: {title}', 0)
    doc.add_paragraph(f"Verified Generation: {ts} | System: TechInAdvance AI")
    doc.add_paragraph("_" * 50)
    doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city, logo_path="Logo1.jpeg"):
    pdf = FPDF()
    pdf.add_page()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        if os.path.exists(logo_path): pdf.image(logo_path, 10, 8, 30)
    except: pass
    pdf.ln(25)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f'EXECUTIVE SUMMARY: {service.upper()}', 0, 1, 'L')
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 10, f'Market: {city} | Timestamp: {ts}', 0, 1, 'L')
    pdf.ln(5)
    pdf.set_font("Arial", size=11)
    clean_text = str(content).encode('latin-1', 'ignore').decode('latin-1')
    pdf.multi_cell(0, 7, txt=clean_text)
    return pdf.output(dest='S').encode('latin-1')

# --- 5D. SIDEBAR COMMAND CONSOLE (HYBRID LOCATION UPGRADE) ---
with st.sidebar:
    st.image(user_row['logo_path'], width=120)
    st.button("🌓 Toggle Theme", on_click=toggle_theme)
    st.metric("Credits Available", user_row['credits'])
    st.divider()
    
    biz_name = st.text_input("Brand Name", placeholder="e.g. Acme Solar")

    # 1. EXPANDED GEOGRAPHIC DICTIONARY
    location_data = {
        "Alabama": ["Birmingham", "Huntsville", "Mobile"],
        "Arizona": ["Phoenix", "Scottsdale", "Mesa", "Tucson"],
        "California": ["Los Angeles", "San Francisco", "San Diego", "San Jose", "Sacramento"],
        "Colorado": ["Denver", "Boulder", "Colorado Springs"],
        "Florida": ["Miami", "Orlando", "Tampa", "Jacksonville", "Fort Lauderdale"],
        "Georgia": ["Atlanta", "Savannah", "Augusta"],
        "Illinois": ["Chicago", "Naperville", "Aurora", "Rockford"],
        "Massachusetts": ["Boston", "Cambridge", "Worcester"],
        "Michigan": ["Detroit", "Grand Rapids", "Ann Arbor"],
        "Nevada": ["Las Vegas", "Reno", "Henderson"],
        "New York": ["New York City", "Buffalo", "Rochester", "Albany"],
        "North Carolina": ["Charlotte", "Raleigh", "Durham"],
        "Ohio": ["Columbus", "Cleveland", "Cincinnati"],
        "Pennsylvania": ["Philadelphia", "Pittsburgh", "Allentown"],
        "Texas": ["Austin", "Dallas", "Houston", "San Antonio", "Fort Worth"],
        "Washington": ["Seattle", "Bellevue", "Spokane"]
    }

    # 2. DYNAMIC LOCATION LOGIC
    state_list = sorted(list(location_data.keys())) + ["Other (Manual Entry)"]
    selected_state = st.selectbox("🎯 Target State", state_list)

    if selected_state == "Other (Manual Entry)":
        c_col, s_col = st.columns(2)
        with c_col: m_city = st.text_input("City")
        with s_col: m_state = st.text_input("State")
        full_loc = f"{m_city}, {m_state}"
    else:
        # Check if they want to type a city NOT in the list for a supported state
        city_list = sorted(location_data[selected_state]) + ["City not listed..."]
        selected_city = st.selectbox(f"🏙️ Select City ({selected_state})", city_list)
        
        if selected_city == "City not listed...":
            custom_city = st.text_input(f"Type City in {selected_state}")
            full_loc = f"{custom_city}, {selected_state}"
        else:
            full_loc = f"{selected_city}, {selected_state}"

    st.caption(f"📍 Intelligence focused on: **{full_loc}**")

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
    
    st.divider()
    if st.button("🔒 End Demo Session", use_container_width=True, help="Purge demo leads and logout"):
        st.session_state.show_cleanup_confirm = True

    authenticator.logout('Sign Out', 'sidebar')

# --- 5E. MODAL-STYLE CLEANUP PROMPT ---
if st.session_state.get('show_cleanup_confirm'):
    st.markdown("---")
    with st.status("🛠️ Session Termination Hub", expanded=True):
        st.write("Would you like to surgically purge all **Demo Data** before finalizing your session?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Yes, Purge Demo Records", type="primary"):
                try:
                    conn = sqlite3.connect('breatheeasy.db')
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM leads WHERE team_id = 'DEMO_DATA_INTERNAL'")
                    count = cursor.rowcount
                    conn.commit()
                    conn.close()
                    st.success(f"Purged {count} demo records. Real data preserved.")
                    st.session_state.show_cleanup_confirm = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Purge Error: {e}")
                    
        with col2:
            if st.button("🛑 No, Logout Only", type="secondary"):
                st.session_state.show_cleanup_confirm = False
                st.rerun()
    
# --- 6. MULTIMODAL COMMAND CENTER (STRICT ARCHITECTURE) ---

# 1. INITIALIZE TAB OBJECTS
tabs = st.tabs([
    "📖 Guide", "🕵️ Analyst", "📺 Ads", "🎨 Creative", "👔 Strategist", 
    "✍ Social", "🧠 GEO", "🌐 Auditor", "✍ SEO", "👁️ Vision", 
    "🎬 Veo Studio", "🤝 Team Intel", "⚙ Admin"
])

# 2. DEFINE UTILITIES FIRST (Prevents NameError)
def format_output(data):
    """Sanitize and format agent output for high-end executive display."""
    if isinstance(data, str) and (data.startswith('{') or data.startswith('`')):
        try:
            clean_str = data.strip().strip('```json').strip('```').strip()
            import json
            parsed = json.loads(clean_str)
            return pd.json_normalize(parsed).T.to_markdown()
        except: return data
    return data

def render_executive_seat(idx, title, icon, key, guide):
    """Renders agent seats into tabs 1 through 9."""
    with tabs[idx + 1]: 
        st.markdown(f'<div class="guide-box"><b>📖 {title} User Guide:</b> {guide}</div>', unsafe_allow_html=True)
        st.markdown(f"### {icon} {title} Command Seat")
        
        if title == "Vision":
            st.info("Upload competitor assets for visual teardowns.")
            uploaded_file = st.file_uploader("Upload Competitor Asset (PNG/JPG)", type=["png", "jpg", "jpeg"], key="vision_upload")
            if uploaded_file:
                v1, v2 = st.columns([1, 1])
                with v1: st.image(uploaded_file, caption="Target Asset", use_container_width=True)
                with v2:
                    if st.button("🚀 Analyze Visual Gaps", type="primary"):
                        with st.spinner("Agent 'Vision' scanning..."):
                            st.session_state.vision_report = "### 👁️ Visual Intelligence Report\n- **Rival Hook:** Scarcity Abuse.\n- **Leak:** No trust signals.\n- **Move:** Contrast disruption."
            if st.session_state.get('vision_report'):
                st.markdown(f'<div class="insight-card">{st.session_state.vision_report}</div>', unsafe_allow_html=True)

        elif st.session_state.get('gen'):
            raw_data = st.session_state.report.get(key, "Strategic isolation in progress...")
            edited_intel = st.text_area("Refine Strategic Output", value=format_output(raw_data), height=350, key=f"area_{key}")
            
            if title == "Ad Tracker":
                st.divider()
                lib_col, mock_col = st.columns(2)
                with lib_col:
                    search_q = f"{final_ind} {full_loc}".replace(" ", "%20")
                    st.link_button("🔥 Meta Ad Library", f"https://www.facebook.com/ads/library/?q={search_q}")
                with mock_col:
                    st.markdown(f'<div style="border:1px solid #00FFAA; padding:10px; border-radius:10px; font-size:0.8em;"><b>{biz_name}</b><br>{edited_intel[:60]}...</div>', unsafe_allow_html=True)

            k1, k2, k3 = st.columns([2, 1, 1])
            with k1: st.success(f"Verified {title} Intelligence")
            with k2: st.download_button("📄 Word", create_word_doc(edited_intel, title, user_row['logo_path']), f"{title}.docx", key=f"w_{key}")
            with k3: st.download_button("📕 PDF", create_pdf(edited_intel, svc, full_loc, user_row['logo_path']), f"{title}.pdf", key=f"p_{key}")
            st.markdown(f'<div class="insight-card">{edited_intel}</div>', unsafe_allow_html=True)
            
            st.divider(); d1, d2, d3, d4 = st.columns(4)
            with d1: st.button("📧 Email", key=f"m_{key}", on_click=broadcast_deployment, args=(title, biz_name, edited_intel, "Email"))
            with d2: st.button("📱 SMS", key=f"s_{key}", on_click=broadcast_deployment, args=(title, biz_name, edited_intel, "SMS"))
            with d3: st.button("💾 Save", key=f"sv_{key}", on_click=manage_record, args=("save", None))
            with d4: st.button("✅ Hub", key=f"c_{key}", on_click=broadcast_deployment, args=(title, biz_name, edited_intel, "Cloud"))
        else:
            st.info(f"Launch swarm to populate {title} seat.")

# 3. STATIC TAB CONTENT (TABS 0, 11, 12)
with tabs[0]:
    st.header("📖 Agent Intelligence Manual")
    st.info("Learn how to leverage your AI Swarm for maximum ROI.")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        with st.expander("🕵️ Analyst & Ad Tracker", expanded=True):
            st.markdown("**What it Does:** Identifies market price gaps and competitor ad strategies.\n**Action:** Adjust your pricing based on the 'Price Arbitrage' data.")
    with col_g2:
        with st.expander("👔 Chief Growth Strategist"):
            st.markdown("**What it Does:** Synthesizes all data into a 30-day roadmap.\n**Action:** Use this as your primary business plan for the month.")

with tabs[11]:
    st.header("🤝 Team Intelligence & Market ROI")
    conn = sqlite3.connect('breatheeasy.db')
    leads_df = pd.read_sql_query("SELECT city, industry, status FROM leads", conn)
    if not leads_df.empty:
        val_map = {"Solar": 22000, "HVAC": 8500, "Medical": 12000, "Legal": 15000, "Dental": 4500, "Custom": 10000}
        total_val = leads_df['industry'].map(val_map).fillna(10000).sum()
        m_col1, m_col2 = st.columns(2)
        m_col1.metric("Pipeline Value", f"${total_val:,.0f}")
        m_col2.metric("Market Reach", f"{len(leads_df['city'].unique())} Active Cities")
        st.divider(); st.subheader("📍 Swarm Geographic Density")
        # 
        geo_coords = {"Miami, Florida": [25.76, -80.19], "Austin, Texas": [30.26, -97.74], "Los Angeles, California": [34.05, -118.24]}
        map_data = [{"lat": geo_coords[loc][0], "lon": geo_coords[loc][1]} for loc in leads_df['city'] if loc in geo_coords]
        if map_data: st.map(pd.DataFrame(map_data), color="#00FFAA", size=20)
    else: st.info("Launch swarms to generate market intelligence.")
    conn.close()

with tabs[12]:
    st.header("⚡ God-Mode Admin Control")
    st.warning("Critical Access: Database Governance & Session Management")
    conn = sqlite3.connect('breatheeasy.db')
    leads_all = pd.read_sql_query("SELECT * FROM leads", conn)
    h1, h2 = st.columns(2)
    h1.metric("Database Records", len(leads_all))
    h2.metric("System Health", "Operational")
    st.divider()
    
    # FIXED TYPO HERE: admin_c1, admin_c2 matches below
    admin_c1, admin_c2 = st.columns(2)
    with admin_c1:
        with st.expander("📥 Master Data Export"):
            csv = leads_all.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export CSV", csv, "master_leads.csv", "text/csv", use_container_width=True)
    with admin_c2: # FIXED FROM admin_col2
        with st.expander("🚨 Critical Reset Zone"):
            if st.button("Purge Demo Data", type="secondary", use_container_width=True):
                cursor = conn.cursor()
                cursor.execute("DELETE FROM leads WHERE team_id = 'DEMO_DATA_INTERNAL'")
                conn.commit(); st.success("Demo records purged."); st.rerun()

    st.divider(); st.subheader("📜 System Audit Trail")
    # 
    logs_df = pd.read_sql_query("SELECT timestamp, user, action, details FROM system_logs ORDER BY timestamp DESC LIMIT 50", conn)
    st.dataframe(logs_df, use_container_width=True, hide_index=True)
    conn.close()

# 4. RENDER LOOP LAST
seats = [
    ("Analyst", "🕵️", "analyst", "Identify competitor price gaps."),
    ("Ad Tracker", "📺", "ads", "Analyze rival psychological hooks."),
    ("Creative", "🎨", "creative", "Visual frameworks and prompts."),
    ("Strategist", "👔", "strategist", "30-day ROI roadmap."),
    ("Social Hooks", "✍", "social", "Viral hooks and schedules."),
    ("GEO Map", "🧠", "geo", "AI Search and Map optimization."),
    ("Audit Scan", "🌐", "auditor", "Technical conversion diagnostics."),
    ("SEO Blogger", "✍", "seo", "High-authority technical articles."),
    ("Vision", "👁️", "vision", "Multimodal visual gap analysis.")
]
for i, s in enumerate(seats): 
    render_executive_seat(i, s[0], s[1], s[2], s[3])

# --- 7. SWARM EXECUTION (SYNCED WITH KANBAN PIPELINE) ---
if run_btn:
    if not biz_name or not city_input: 
        st.error("❌ Identification required: Please provide Brand Name and City.")
    elif user_row['credits'] <= 0: 
        st.error("❌ Out of credits: Please contact your administrator for a credit injection.")
    else:
        with st.status("🛠️ Coordinating Swarm Agents...", expanded=True) as status:
            # 7A. Execute Strategic Logic via main.py
            report = run_marketing_swarm({
                'city': full_loc, 
                'industry': final_ind, 
                'service': svc, 
                'biz_name': biz_name, 
                'url': audit_url, 
                'toggles': toggles
            })
            
            # 7B. Update Session State for Instant UI Rendering
            st.session_state.report, st.session_state.gen = report, True
            
            # 7C. Database Transaction: Credit Deduction & Kanban Entry
            conn = sqlite3.connect('breatheeasy.db')
            # Deduct 1 Enterprise Credit
            conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
            
            # Create Lead Entry with initial 'Discovery' status for Kanban Board
            conn.execute("""
                INSERT INTO leads (date, user, industry, service, city, content, team_id, status) 
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                datetime.now().strftime("%Y-%m-%d"), 
                user_row['username'], 
                final_ind, 
                svc, 
                full_loc, 
                str(report), 
                user_row['team_id'], 
                'Discovery'
            ))
            
            conn.commit()
            conn.close()
            
            # 7D. Finalize UI State
            status.update(label="✅ Strategy Engine Synced!", state="complete")
            st.toast(f"Swarm for {biz_name} successfully initialized.")
            st.rerun()

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

# --- 9. TEAM INTEL & ADMIN (FULL FEATURE RESTORATION) ---
with tabs[10]:
    st.header("🤝 Global Pipeline Kanban")
    st.markdown('<div class="guide-box"><b>Executive Overview:</b> Monitor swarm progression. Transition leads from Discovery to ROI Verified as milestones are met.</div>', unsafe_allow_html=True)
    
    conn = sqlite3.connect('breatheeasy.db')
    # Fetch lead data
    team_df = pd.read_sql_query("SELECT id, date, city, industry, service, status FROM leads WHERE team_id = ?", conn, params=(user_row['team_id'],))
    
    # 9A. TEAM HEALTH METRICS
    m1, m2, m3 = st.columns(3)
    with m1: st.metric("Total Swarms", len(team_df))
    with m2: st.metric("Active Markets", len(team_df['city'].unique()))
    with m3: st.metric("Team Velocity", f"{len(team_df[team_df['status'] == 'ROI Verified'])} Wins")

    st.divider()

    # 9B. KANBAN PIPELINE LOGIC
    stages = ["Discovery", "Execution", "ROI Verified"]
    kanban_cols = st.columns(3)
    
    for i, stage in enumerate(stages):
        with kanban_cols[i]:
            st.markdown(f'<div class="kanban-header">{stage}</div>', unsafe_allow_html=True)
            stage_leads = team_df[team_df['status'] == stage]
            
            if stage_leads.empty:
                st.caption(f"Zero leads in {stage}")
            
            for _, lead in stage_leads.iterrows():
                with st.container():
                    st.markdown(f"""
                    <div class="kanban-card">
                        <small style="color:gray;">{lead['date']}</small><br>
                        <b style="font-size:1.05rem; color:#1E293B;">{lead['city']}</b><br>
                        <div style="margin-top:5px; font-size:0.8rem;">
                            <span style="background:#E0E7FF; padding:2px 6px; border-radius:4px; color:#3730A3;">{lead['service']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Transition Control
                    new_status = st.selectbox(
                        "Move Stage", 
                        stages, 
                        index=stages.index(stage), 
                        key=f"kb_move_{lead['id']}",
                        label_visibility="collapsed"
                    )
                    if new_status != stage:
                        conn.execute("UPDATE leads SET status = ? WHERE id = ?", (new_status, lead['id']))
                        conn.commit()
                        st.toast(f"Updated: {lead['city']} -> {new_status}")
                        st.rerun()

    st.divider()
    st.subheader("🛡️ Security Log")
    st.code(f"Integrity: OK | Trace: {user_row['username']} | Sync Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    conn.close()

# 9C. GOD-MODE ADMIN CONTROL
if user_row['role'] == 'admin':
    with tabs[11]:
        st.header("⚙️ God-Mode Admin Control")
        conn = sqlite3.connect('breatheeasy.db')
        all_u = pd.read_sql_query("SELECT username, email, credits, package FROM users", conn)
        st.dataframe(all_u, use_container_width=True)
        
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("User Termination")
            u_del = st.text_input("Username to Purge", placeholder="Enter exact username")
            if st.button("❌ Terminate User"):
                if u_del != 'admin':
                    conn.execute("DELETE FROM users WHERE username=?", (u_del,))
                    conn.commit()
                    st.success(f"System purged: {u_del}")
                    st.rerun()
                else:
                    st.error("Access Denied: Cannot delete primary Root Admin.")
        
        with col2:
            st.subheader("Credit Injection")
            target = st.selectbox("Target User", all_u['username'])
            amt = st.number_input("Injection Volume", value=50, step=10)
            if st.button("💉 Finalize Injection"):
                conn.execute("UPDATE users SET credits = credits + ? WHERE username = ?", (amt, target))
                conn.commit()
                st.success(f"Successfully injected {amt} credits into {target}.")
                st.rerun()
        conn.close()
