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

# --- 1. SYSTEM INITIALIZATION ---
os.environ["OTEL_SDK_DISABLED"] = "true"
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]

st.set_page_config(page_title="BreatheEasy AI | Enterprise", page_icon="🌬️", layout="wide")

# --- 2. DATABASE ARCHITECTURE ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance_mode', 'OFF')")
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, 
                  package TEXT, logo_path TEXT, last_login TEXT, usage_count INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    c.execute("SELECT username FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, email, name, password, role, package, last_login) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited', datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit(); conn.close()

def update_stats(username):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.cursor().execute("UPDATE users SET last_login = ?, usage_count = usage_count + 1 WHERE username = ?", (now, username))
    conn.commit(); conn.close()

init_db()

# --- 3. UI STYLING & WHITELABELING ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stDeployButton {display:none;}
    .tier-badge { padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; background: #0056b3; color: white; }
    .pricing-card { border: 1px solid #ddd; padding: 25px; border-radius: 12px; text-align: center; background: white; height: 100%; box-shadow: 2px 4px 8px rgba(0,0,0,0.05); }
    .mockup-container { background: white; border: 1px solid #ddd; border-radius: 10px; padding: 15px; margin-bottom: 10px; }
    
    /* Forgot Password Button Style */
    a[href*="forgot_password"] { 
        display: inline-block; padding: 0.6rem 1.2rem; background-color: white; 
        color: #31333F !important; border: 1px solid #ddd; border-radius: 0.5rem; 
        text-decoration: none !important; font-size: 14px; margin-top: 10px; font-weight: 500;
    }
    a[href*="forgot_password"]:hover { border-color: #0056b3; background-color: #f9f9f9; }
    </style>
""", unsafe_allow_html=True)

# --- 4. EXPORT GENERATORS ---
def create_word_doc(content, logo_path=None):
    doc = Document()
    if logo_path and os.path.exists(logo_path):
        try: doc.add_picture(logo_path, width=Inches(1.5))
        except: pass
    doc.add_heading('BreatheEasy AI Strategy', 0)
    for line in content.split('\n'): doc.add_paragraph(line)
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city, logo_path=None):
    pdf = FPDF(); pdf.add_page()
    if logo_path and os.path.exists(logo_path):
        try: pdf.image(logo_path, 10, 8, 33); pdf.ln(20)
        except: pass
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f'{service} Strategy - {city}', 0, 1, 'C')
    pdf.set_font("Arial", size=10); clean = content.encode('latin-1', 'ignore').decode('latin-1')
    pdf.multi_cell(0, 7, txt=clean); return pdf.output(dest='S').encode('latin-1')

# --- 5. AUTHENTICATION ---
def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    return {'usernames': {row['username']: {'email': row['email'], 'name': row['name'], 'password': row['password'], 
            'package': row.get('package', 'Basic'), 'logo_path': row.get('logo_path')} for _, row in df.iterrows()}}

authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days'])

# --- 6. LANDING & LOGIN PAGE ---
authenticator.login(location='main')

if st.session_state["authentication_status"] is None:
    st.markdown("<h1 style='text-align: center;'>🌬️ BreatheEasy AI</h1>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        try:
            res_forgot = authenticator.forgot_password(location='main')
            if res_forgot[0]: st.success('Check email for new password.')
        except: pass
    with col2:
        with st.expander("🆕 New User? Register Here"):
            try:
                res_reg = authenticator.register_user(location='main', pre_authorization=False)
                if res_reg:
                    e, u, n = res_reg
                    if e:
                        h_pw = stauth.Hasher.hash(authenticator.credentials['usernames'][u]['password'])
                        conn = sqlite3.connect('breatheeasy.db')
                        conn.cursor().execute("INSERT INTO users (username, email, name, password, role, package, last_login) VALUES (?,?,?,?,?,?,?)",
                                              (u, e, n, h_pw, 'member', 'Basic', datetime.now().strftime("%Y-%m-%d %H:%M")))
                        conn.commit(); conn.close(); st.success('Registered! Please login.')
            except: st.info("Fill the form to join.")
    st.stop()

# --- 7. DASHBOARD (LOGGED IN) ---
if st.session_state["authentication_status"]:
    username = st.session_state["username"]
    user_info = get_db_creds()['usernames'].get(username, {})
    tier = user_info.get('package', 'Basic')
    is_admin = (username == "admin")

    # SAAS GATING CONFIG
    TIER_LIMITS = {
        "Basic": {"industries": ["HVAC", "Plumbing"], "files": 1, "blog": False},
        "Pro": {"industries": ["HVAC", "Plumbing", "Restoration", "Solar"], "files": 5, "blog": True},
        "Unlimited": {"industries": ["HVAC", "Plumbing", "Restoration", "Solar", "Law Firm", "Medical", "Custom"], "files": 20, "blog": True}
    }

    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state['name']} <span class='tier-badge'>{tier}</span>", unsafe_allow_html=True)
        if st.button("🔑 Change Password"):
            if authenticator.reset_password(username, 'Reset password'):
                new_h = stauth.Hasher.hash(authenticator.credentials['usernames'][username]['password'])
                conn = sqlite3.connect('breatheeasy.db')
                conn.cursor().execute("UPDATE users SET password = ? WHERE username = ?", (new_h, username))
                conn.commit(); conn.close(); st.success('Updated!')
        authenticator.logout('Sign Out', 'sidebar')
        st.divider()

        # DYNAMIC SERVICE OPTIONS
        main_cat = st.selectbox("Industry", TIER_LIMITS[tier]["industries"])
        services_data = {
            "HVAC": ["Full System Replacement", "AC Repair", "Duct Cleaning", "IAQ Audit"],
            "Plumbing": ["Whole-Home Repiping", "Tankless Installation", "Sewer Line Repair", "Emergency Plumbing"],
            "Solar": ["Residential Solar Array", "Battery Backup", "EV Charger Install"],
            "Restoration": ["Mold Remediation", "Water Damage", "Fire Restoration"],
            "Law Firm": ["Personal Injury", "Estate Planning", "Corporate Litigation"],
            "Medical": ["Dermatology", "Dental Implants", "Chiropractic"],
            "Custom": ["Type Custom Service Below"]
        }
        
        if main_cat == "Custom":
            target_service = st.text_input("Custom Service Name")
        else:
            target_service = st.selectbox("High-Ticket Service", services_data.get(main_cat, ["General Service"]))

        if TIER_LIMITS[tier]["blog"]: include_blog = st.toggle("📝 Create SEO Blog", value=True)
        else: st.info("🔒 SEO Blog (Upgrade to Pro)"); include_blog = False
        
        max_f = TIER_LIMITS[tier]["files"]
        uploaded = st.file_uploader(f"Assets (Max {max_f})", accept_multiple_files=True)
        city = st.text_input("Target City")
        launch = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

    # Tabs
    tabs = st.tabs(["🔥 Strategy", "📅 7-Day Calendar", "📱 Previews", "💎 Pricing", "🛠️ Admin" if is_admin else "📋 History"])

    with tabs[0]: # STRATEGY & DOWNLOADS
        if launch and city:
            with st.spinner("AI Agents coordinating swarm..."):
                run_marketing_swarm({'city': city, 'industry': main_cat, 'service': target_service, 'blog': include_blog})
                if os.path.exists("final_marketing_strategy.md"):
                    with open("final_marketing_strategy.md", "r") as f: st.session_state['copy'] = f.read()
                    st.session_state['gen'] = True
                    update_stats(username)
        
        if st.session_state.get('gen'):
            copy = st.session_state['copy']
            st.subheader("📥 Download Deliverables")
            col1, col2 = st.columns(2)
            col1.download_button("📄 Word Doc", create_word_doc(copy, user_info.get('logo_path')), f"{city}_Strategy.docx", use_container_width=True)
            col2.download_button("📕 PDF Report", create_pdf(copy, target_service, city, user_info.get('logo_path')), f"{city}_Strategy.pdf", use_container_width=True)
            st.divider()
            st.markdown(copy)

    with tabs[2]: # MOCKUPS
        if st.session_state.get('gen'):
            st.markdown(f"<div class='mockup-container'><div style='color:#1a0dab;font-size:18px;'>#1 {target_service} in {city}</div><p>{st.session_state.get('copy','')[:150]}...</p></div>", unsafe_allow_html=True)
            

    with tabs[3]: # PRICING
        st.subheader("💎 Membership Plans")
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown('<div class="pricing-card"><h3>Basic</h3><h1>$0</h1><p>2 Industries<br>1 File Upload</p></div>', unsafe_allow_html=True)
        with c2: st.markdown('<div class="pricing-card" style="border:2px solid #0056b3"><h3>Pro</h3><h1>$49</h1><p>5 Industries<br>5 File Uploads<br>SEO Blog</p></div>', unsafe_allow_html=True)
        with c3: st.markdown('<div class="pricing-card"><h3>Unlimited</h3><h1>$99</h1><p>All Industries<br>20 File Uploads<br>Custom Niche</p></div>', unsafe_allow_html=True)
        

    if is_admin:
        with tabs[-1]:
            st.subheader("🛠️ User Management")
            conn = sqlite3.connect('breatheeasy.db')
            df_users = pd.read_sql_query("SELECT username, email, package, usage_count FROM users", conn)
            st.dataframe(df_users, use_container_width=True)
            user_to_del = st.selectbox("Select user to remove", df_users['username'])
            if st.button("❌ Delete User") and user_to_del != 'admin':
                conn.cursor().execute("DELETE FROM users WHERE username = ?", (user_to_del,))
                conn.commit(); st.success(f"{user_to_del} removed."); st.rerun()
            conn.close()
