import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
from datetime import datetime
from main import run_marketing_swarm 
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from io import BytesIO
from PIL import Image

# --- STRIPE ERROR HANDLING ---
try:
    import stripe
    stripe.api_key = st.secrets.get("STRIPE_API_KEY", "sk_test_placeholder")
except ImportError:
    st.error("Stripe library not found. Please add 'stripe' to requirements.txt")

# --- 1. SYSTEM INITIALIZATION ---
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

if 'auth_tab' not in st.session_state:
    st.session_state.auth_tab = "🔑 Login"

def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

def switch_to_login():
    st.session_state.auth_tab = "🔑 Login"
    st.rerun()

os.environ["OTEL_SDK_DISABLED"] = "true"
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

# TechInAdvance Favicon & Browser Title
st.set_page_config(
    page_title="TechInAdvance AI | Enterprise Command", 
    page_icon="Logo1.jpeg", 
    layout="wide"
)

# SaaS White-Label CSS: Elite UI
if st.session_state.theme == 'dark':
    bg, text, side, card, btn = "#0F172A", "#F8FAFC", "#1E293B", "#334155", "#3B82F6"
else:
    bg, text, side, card, btn = "#F8FAFC", "#0F172A", "#E2E8F0", "#FFFFFF", "#2563EB"

st.markdown(f"""
    <style>
    #MainMenu, footer, header {{visibility: hidden;}}
    .stDeployButton {{display:none;}}
    [data-testid="stSidebar"] {{ background-color: {bg}; color: {text}; border-right: 1px solid #1E293B; }}
    [data-testid="stSidebar"] * {{ color: {text} !important; }}
    .st-emotion-cache-1kyx7g3 {{ background-color: {side} !important; border-radius: 12px; padding: 20px; margin-bottom: 10px; }}
    div.stButton > button {{ background-color: {btn}; color: white; border-radius: 10px; width: 100%; font-weight: 700; border: none; }}
    div.stButton > button:hover {{ transform: translateY(-1px); box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, 
                  package TEXT, credits INTEGER DEFAULT 0, logo_path TEXT, team_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, 
                  service TEXT, city TEXT, content TEXT, team_id TEXT, is_shared INTEGER DEFAULT 0, score INTEGER)''')
    hashed_pw = stauth.Hasher.hash('admin123')
    c.execute("""INSERT OR IGNORE INTO users (username, email, name, password, role, package, credits, logo_path, team_id) 
                 VALUES (?,?,?,?,?,?,?,?,?)""",
              ('admin', 'admin@techinadvance.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited', 9999, 'Logo1.jpeg', 'HQ_001'))
    conn.commit()
    conn.close()

try:
    init_db()
    conn = sqlite3.connect('breatheeasy.db')
    pd.read_sql_query("SELECT team_id FROM users LIMIT 1", conn)
    conn.close()
except:
    if os.path.exists('breatheeasy.db'): os.remove('breatheeasy.db')
    init_db()

# --- 3. STRIPE SUBSCRIPTION ENGINE ---
def create_checkout_session(plan_name, price_id, user_email):
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            success_url=f"https://techinadvance.ai/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url="https://techinadvance.ai/cancel",
            customer_email=user_email,
        )
        return session.url
    except Exception as e: return f"Error: {e}"

# --- 4. EXPORT ENGINE (WHITE-LABEL ENABLED) ---
def create_word_doc(content, logo_path="Logo1.jpeg"):
    doc = Document()
    final_logo = logo_path if logo_path and os.path.exists(logo_path) else "Logo1.jpeg"
    try: doc.add_picture(final_logo, width=Inches(1.5))
    except: pass
    doc.add_heading('TechInAdvance AI Strategy Report', 0)
    doc.add_paragraph(str(content))
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city, logo_path="Logo1.jpeg"):
    pdf = FPDF(); pdf.add_page()
    final_logo = logo_path if logo_path and os.path.exists(logo_path) else "Logo1.jpeg"
    try: pdf.image(final_logo, 10, 8, 33); pdf.ln(20)
    except: pass
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'{service} Strategy - {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=10); pdf.multi_cell(0, 7, txt=str(content).encode('latin-1', 'ignore').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')

def render_breatheeasy_gauge(score, industry):
    color = "#ff4b4b" if score < 4 else "#ffa500" if score < 7 else "#2ecc71"
    st.markdown(f"""
        <div style="text-align: center; border: 2px solid #ddd; padding: 25px; border-radius: 20px; background: #ffffff; color: #1E293B;">
            <h3 style="margin: 0;">{industry} Performance Status</h3>
            <div style="font-size: 64px; font-weight: 800; color: {color};">{score}/10</div>
            <div style="width: 100%; background: #E2E8F0; border-radius: 999px; height: 16px; margin-top: 15px;">
                <div style="width: {score*10}%; background: {color}; height: 16px; border-radius: 999px;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- 5. AUTHENTICATION & STRIPE FLOW ---
def get_db_creds():
    try:
        conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
        df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn); conn.close()
        return {'usernames': {row['username']: {'email':row['email'], 'name':row['name'], 'password':row['password']} for _, row in df.iterrows()}}
    except: return {'usernames': {}}

authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], 30)

if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=200)
    st.title("🌬️ TechInAdvance AI Enterprise Swarm")
    auth_tabs = ["🔑 Login", "📝 Register & Choose Plan", "❓ Forgot Password"]
    active_idx = auth_tabs.index(st.session_state.auth_tab)
    choice = st.radio("Access Control", auth_tabs, index=active_idx, horizontal=True, label_visibility="collapsed")
    
    if choice == "🔑 Login": authenticator.login(location='main')
    elif choice == "📝 Register & Choose Plan":
        st.subheader("🚀 Join the TechInAdvance Swarm")
        plan_options = {
            "Basic ($99/mo - 5 Credits)": {"id": "price_basic", "creds": 5},
            "Pro ($499/mo - 50 Credits)": {"id": "price_pro", "creds": 50},
            "Enterprise ($1999/mo - Unlimited)": {"id": "price_ent", "creds": 9999}
        }
        selected_plan = st.selectbox("Select Subscription Plan", list(plan_options.keys()))
        try:
            reg_result = authenticator.register_user(location='main')
            if reg_result:
                email_reg, username_reg, name_reg = reg_result
                hashed_password = authenticator.credentials['usernames'][username_reg]['password']
                payment_url = create_checkout_session(selected_plan, plan_options[selected_plan]["id"], email_reg)
                st.link_button("💳 Proceed to Secure Payment", payment_url)
                conn = sqlite3.connect('breatheeasy.db')
                conn.execute("INSERT OR IGNORE INTO users (username, email, name, password, role, package, credits, team_id, logo_path) VALUES (?,?,?,?,?,?,?,?,?)",
                             (username_reg, email_reg, name_reg, hashed_password, 'member', selected_plan.split()[0], plan_options[selected_plan]["creds"], f"TEAM_{username_reg}", "Logo1.jpeg"))
                conn.commit(); conn.close()
                st.success("Registration Successful! Proceed to payment.")
                st.session_state.auth_tab = "🔑 Login"
        except Exception: st.info("Please fill the form to join TechInAdvance.")
    st.stop()

# --- 6. DASHBOARD & WHITE-LABEL SIDEBAR ---
conn = sqlite3.connect('breatheeasy.db')
user_row = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(st.session_state["username"],)).iloc[0]
conn.close()

with st.sidebar:
    st.image("Logo1.jpeg", use_column_width=True)
    st.button("🌓 Switch Theme", on_click=toggle_theme)
    st.markdown(f"### 👋 {st.session_state['name']} (`{user_row['package']}`)")
    st.metric("Credits Available", user_row['credits'])
    
    if user_row['package'] in ["Pro", "Enterprise", "Unlimited"]:
        st.divider(); st.subheader("🎨 Custom White-Labeling")
        custom_logo = st.file_uploader("Upload Company Logo", type=['png', 'jpg', 'jpeg'])
        if custom_logo:
            save_path = f"user_logos/{st.session_state['username']}_logo.png"
            os.makedirs("user_logos", exist_ok=True)
            with open(save_path, "wb") as f: f.write(custom_logo.getbuffer())
            conn = sqlite3.connect('breatheeasy.db'); conn.execute("UPDATE users SET logo_path = ? WHERE username = ?", (save_path, st.session_state['username'])); conn.commit(); conn.close(); st.success("Logo applied!")

    st.divider(); biz_name = st.text_input("Business Name"); biz_usp = st.text_area("Unique Selling Proposition")
    st.divider()
    toggles = {"audit": st.toggle("🌐 Web Auditor", value=True), "advice": st.toggle("👔 Advice Director", value=True), "sem": st.toggle("🔍 SEM Specialist"), "seo": st.toggle("✍️ SEO Creator"), "repurpose": st.toggle("✍🏾 Content Repurposer"), "geo": st.toggle("🧠 GEO Specialist", disabled=(user_row['package']=="Basic")), "analytics": st.toggle("📊 Analytics Specialist")}
    
    web_url = st.text_input("Website URL") if toggles["audit"] else ""
    ind_choice = st.selectbox("Industry", ["HVAC", "Medical", "Law", "Solar", "Real Estate", "Custom"])
    final_ind = st.text_input("Enter Industry Name") if ind_choice == "Custom" else ind_choice
    svc = st.text_input("Service Type"); city = st.text_input("Target City")
    
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary")
    authenticator.logout('Sign Out', 'sidebar')

# --- 7. TABS: FULL PLATFORM ---
hub_display_name = f"🔬 {final_ind} Diagnostic Hub" if final_ind else "🔬 Diagnostic Lab"
tabs = st.tabs(["📝 Ad Copy", "🗓️ User Schedule", "🖼️ Visual Assets", "🚀 Push to Ads", hub_display_name, "⚙️ Admin"])

with tabs[0]:
    if run_btn and city and biz_name:
        with st.status("🐝 Swarm Active...", expanded=True):
            report = run_marketing_swarm({'city': city, 'industry': final_ind, 'service': svc, 'biz_name': biz_name, 'usp': biz_usp, 'url': web_url, 'toggles': toggles})
            st.session_state['report'] = report; st.session_state['gen'] = True
            conn = sqlite3.connect('breatheeasy.db'); conn.execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (user_row['username'],)); conn.execute("INSERT INTO leads (date, user, industry, service, city, content, team_id, is_shared) VALUES (?,?,?,?,?,?,?,?)", (datetime.now().strftime("%Y-%m-%d"), user_row['username'], final_ind, svc, city, str(report), user_row['team_id'], 1)); conn.commit(); conn.close(); st.rerun()

    if st.session_state.get('gen'):
        st.subheader("📥 Export Deliverables")
        c1, c2 = st.columns(2)
        report_logo = user_row['logo_path'] if user_row['package'] != "Basic" else "Logo1.jpeg"
        c1.download_button("📄 Word Document", create_word_doc(st.session_state['report'], report_logo), f"Report_{city}.docx", use_container_width=True)
        c2.download_button("📕 PDF Report", create_pdf(st.session_state['report'], svc, city, report_logo), f"Report_{city}.pdf", use_container_width=True)
        st.markdown(st.session_state['report'])

with tabs[1]:
    st.subheader("🗓️ Your 30-Day Project Roadmap")
    if st.session_state.get('gen'): st.write(st.session_state['report'])

with tabs[4]:
    st.subheader(f"🛡️ {final_ind} Quality & Safety Audit")
    diag_up = st.file_uploader(f"Upload {final_ind} Evidence", type=['png', 'jpg'])
    if diag_up:
        score = 8 if final_ind == "Medical" else 4 if final_ind == "HVAC" else 7
        render_breatheeasy_gauge(score, final_ind)
        if st.button("💾 SAVE SCORE"):
            conn = sqlite3.connect('breatheeasy.db'); conn.execute("UPDATE leads SET score = ? WHERE user = ? ORDER BY id DESC LIMIT 1", (score, st.session_state['username'])); conn.commit(); conn.close(); st.success("Score Saved!")

if user_row['role'] == 'admin':
    with tabs[-1]:
        st.subheader("👥 User & Credit Administration")
        conn = sqlite3.connect('breatheeasy.db')
        all_u = pd.read_sql("SELECT username, email, package, credits FROM users", conn)
        st.dataframe(all_u, use_container_width=True)
        user_to_del = st.text_input("Username to Terminate")
        if st.button("❌ Remove User"):
            conn.execute(f"DELETE FROM users WHERE username='{user_to_del}'")
            conn.commit(); st.rerun()
        conn.close()
