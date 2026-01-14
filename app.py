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

# --- 3. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, plan TEXT, credits INTEGER DEFAULT 0, logo_path TEXT, team_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT, team_id TEXT, status TEXT DEFAULT 'Discovery')''')
    c.execute('''CREATE TABLE IF NOT EXISTS system_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, action TEXT, user TEXT, details TEXT)''')
    hashed_pw = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users (username, email, name, password, role, plan, credits, logo_path, team_id) VALUES (?,?,?,?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001')", ('admin', 'admin@techinadvance.ai', 'Admin', hashed_pw))
    conn.commit(); conn.close()

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

# --- 5D. SIDEBAR ---
with st.sidebar:
    st.image(user_row['logo_path'], width=120)
    st.button("🌓 Toggle Theme", on_click=toggle_theme)
    st.metric("Credits Available", user_row['credits'])
    biz_name = st.text_input("Brand Name")
    full_loc = st.text_input("Target Location", placeholder="City, State")
    audit_url = st.text_input("Audit URL (Optional)")
    final_ind = st.selectbox("Industry", ["HVAC", "Medical", "Solar", "Legal", "Custom"])
    svc = st.text_input("Service Type")
    toggles = {k: st.toggle(v, value=True) for k, v in {"analyst": "🕵️ Analyst", "ads": "📺 Ad Tracker", "builder": "🎨 Creative", "manager": "👔 Strategist", "social": "✍ Social", "geo": "🧠 GEO", "audit": "🌐 Auditor", "seo": "✍ SEO"}.items()}
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary")
    authenticator.logout('Sign Out', 'sidebar')

# --- 7. SWARM EXECUTION ENGINE (STABILIZED) ---
if run_btn:
    if not biz_name or not full_loc:
        st.error("❌ Identification required: Please provide Brand Name and Location.")
    elif user_row['credits'] <= 0:
        st.error("❌ Out of credits: Contact your administrator.")
    else:
        with st.status("🛠️ Coordinating Swarm Agents...", expanded=True) as status:
            try:
                # Execute Strategic Logic
                # We wrap this in a try-except to catch the vision_intel AttributeError
                report = run_marketing_swarm({
                    'city': full_loc, 
                    'industry': final_ind, 
                    'service': svc, 
                    'biz_name': biz_name, 
                    'url': audit_url, 
                    'toggles': toggles
                })
                
                # Update Session State
                st.session_state.report, st.session_state.gen = report, True
                
                # Database Transaction
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],))
                conn.execute("""
                    INSERT INTO leads (date, user, industry, service, city, content, team_id, status) 
                    VALUES (?,?,?,?,?,?,?,?)
                """, (datetime.now().strftime("%Y-%m-%d"), user_row['username'], final_ind, svc, full_loc, str(report), user_row['team_id'], 'Discovery'))
                conn.commit()
                conn.close()
                
                status.update(label="✅ Strategy Engine Synced!", state="complete")
                st.toast(f"Swarm for {biz_name} initialized.")
                st.rerun()
            
            except AttributeError as e:
                status.update(label="❌ Backend State Mismatch", state="error")
                st.error(f"The Swarm Engine encountered an attribute error: {e}")
                st.warning("Ensure 'vision_intel' is properly initialized in your main.py State class.")
            except Exception as e:
                status.update(label="❌ Swarm Failed", state="error")
                st.error(f"Critical System Error: {e}")

# --- 6. MULTIMODAL COMMAND CENTER (DEFENSIVE RENDERING) ---
tab_titles = ["📖 Guide", "🕵️ Analyst", "📺 Ads", "🎨 Creative", "👔 Strategist", "✍ Social", "🧠 GEO", "🌐 Auditor", "✍ SEO", "👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
is_admin = user_row['role'] == 'admin'
if is_admin: tab_titles.append("⚙ Admin")

tabs = st.tabs(tab_titles)
TAB = {name: tabs[i] for i, name in enumerate(tab_titles)}

# --- TAB RENDERING ---
with TAB["📖 Guide"]:
    st.header("📖 Agent Intelligence Manual")
    col1, col2 = st.columns(2)
    with col1:
        with st.expander("🕵️ Intelligence Seats", expanded=True):
            st.markdown("- **Analyst**: Market gaps and pricing.\n- **Ad Tracker**: Hook deconstruction and competitor spend.")
    with col2:
        with st.expander("👔 Strategic Seats", expanded=True):
            st.markdown("- **Strategist**: 30-day ROI roadmap.\n- **SEO**: Authority articles and domain dominance.")

def render_agent(tab_key, title, report_key):
    with TAB[tab_key]:
        st.subheader(f"{title} Command Seat")
        if st.session_state.gen:
            # DEFENSIVE FETCH: Prevents AttributeError if backend fails to return a key
            content = st.session_state.report.get(report_key, "Intelligence generation for this agent is pending or unavailable.")
            edited = st.text_area(f"Refine {title}", value=str(content), height=350, key=f"edit_{report_key}")
            
            c1, c2 = st.columns(2)
            with c1: st.download_button("📄 Word", create_word_doc(edited, title), f"{title}.docx", key=f"w_{report_key}")
            with c2: st.download_button("📕 PDF", create_pdf(edited, svc, full_loc), f"{title}.pdf", key=f"p_{report_key}")
        else: 
            st.info(f"Launch swarm to populate the {title} seat.")

# Render Standard Agents
for t, k in [("🕵️ Analyst","analyst"), ("📺 Ads","ads"), ("🎨 Creative","creative"), ("👔 Strategist","strategist"), ("✍ Social","social"), ("🧠 GEO","geo"), ("🌐 Auditor","audit"), ("✍ SEO","seo")]:
    render_agent(t, t.split()[-1], k)

# Render Specialty Tabs
with TAB["👁️ Vision"]:
    st.subheader("👁️ Vision Inspector")
    if st.session_state.gen:
        # Specifically targeting the missing vision_intel field safely
        v_intel = st.session_state.report.get('vision_intel', "Vision analysis data not found in state.")
        st.markdown(f'<div class="executive-brief">{v_intel}</div>', unsafe_allow_html=True)
    
    v_file = st.file_uploader("Upload Evidence for Analysis", type=['png','jpg','jpeg'], key="vis_up_main")
    if v_file: st.image(v_file, use_container_width=True, caption="Target Asset")

with TAB["🎬 Veo Studio"]:
    st.subheader("🎬 Veo Cinematic Studio")
    if st.session_state.gen:
        creative_context = st.session_state.report.get('creative', '')
        v_prompt = st.text_area("Video Scene Description", value=str(creative_context)[:300], height=150, key="veo_prompt_area")
        if st.button("📽️ GENERATE AD", key="veo_gen_btn_main"):
            with st.spinner("Rendering cinematic asset..."):
                v_vid = generate_cinematic_ad(v_prompt)
                if v_vid: st.video(v_vid)
    else: 
        st.warning("Launch swarm first to generate creative context for video.")

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

# --- 9C. GOD-MODE ADMIN (ISOLATED) ---
if is_admin:
    with TAB["⚙ Admin"]:
        st.header("⚙️ God-Mode Admin Control")
        conn = sqlite3.connect('breatheeasy.db')
        all_u = pd.read_sql_query("SELECT username, email, credits FROM users", conn)
        st.dataframe(all_u, use_container_width=True)
        col1, col2 = st.columns(2)
        with col1:
            u_del = st.text_input("User to Purge", placeholder="Username")
            if st.button("❌ Terminate"):
                if u_del != 'admin':
                    conn.execute("DELETE FROM users WHERE username=?", (u_del,))
                    conn.commit(); st.success("Purged."); st.rerun()
        with col2:
            target = st.selectbox("Injection Target", all_u['username'], key="admin_inj_target")
            amt = st.number_input("Credits", value=50, key="admin_inj_amt")
            if st.button("💉 Inject"):
                conn.execute("UPDATE users SET credits = credits + ? WHERE username = ?", (amt, target))
                conn.commit(); st.success("Injected."); st.rerun()
        conn.close()
