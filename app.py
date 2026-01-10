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

st.set_page_config(page_title="BreatheEasy AI | Enterprise Command", page_icon="🌬️", layout="wide")

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

def update_user_package(username, new_tier):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    conn.cursor().execute("UPDATE users SET package = ? WHERE username = ?", (new_tier, username))
    conn.commit(); conn.close()

init_db()

# --- 3. UI STYLING & GLOBAL CONFIG ---
PACKAGE_CONFIG = {
    "Basic": {
        "allowed_industries": ["HVAC", "Plumbing"], 
        "max_files": 1, 
        "blog": False, 
        "branding": False,
        "desc": "Perfect for solo contractors. Standard industries and basic reports."
    },
    "Pro": {
        "allowed_industries": ["HVAC", "Plumbing", "Restoration", "Solar"], 
        "max_files": 5, 
        "blog": True, 
        "branding": True,
        "desc": "For growing agencies. Includes SEO Blogs, Branding, and High-Ticket industries."
    },
    "Unlimited": {
        "allowed_industries": ["HVAC", "Plumbing", "Restoration", "Solar", "Roofing", "Law Firm", "Medical", "Custom"], 
        "max_files": 20, 
        "blog": True, 
        "branding": True,
        "desc": "Full Enterprise access. Custom niches and priority AI Swarm analysis."
    }
}

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stDeployButton {display:none;}
    .tier-badge { padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; background: #0056b3; color: white; }
    .pricing-card { border: 1px solid #ddd; padding: 25px; border-radius: 12px; text-align: center; background: white; height: 100%; box-shadow: 2px 4px 8px rgba(0,0,0,0.05); }
    a[href*="forgot_password"] { display: inline-block; padding: 0.6rem 1.2rem; background-color: white; color: #31333F !important; border: 1px solid #ddd; border-radius: 0.5rem; text-decoration: none !important; font-size: 14px; margin-top: 10px; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

# --- 4. EXPORT GENERATORS ---
def create_word_doc(content, logo_path=None):
    doc = Document()
    if logo_path and os.path.exists(logo_path):
        try: doc.add_picture(logo_path, width=Inches(1.5))
        except: pass
    doc.add_heading('BreatheEasy AI | Strategy Report', 0)
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

# --- 5. AUTHENTICATION & LANDING ---
@st.dialog("🎓 Strategy Masterclass")
def video_tutorial():
    st.write("### How to close $10k+ clients using these reports.")
    st.video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    if st.button("Close"): st.rerun()

def get_db_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    return {'usernames': {row['username']: {'email': row['email'], 'name': row['name'], 'password': row['password'], 
            'package': row.get('package', 'Basic'), 'logo_path': row.get('logo_path')} for _, row in df.iterrows()}}

authenticator = stauth.Authenticate(get_db_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days'])

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
        with st.expander("🆕 Register New User"):
            try:
                # Explicit location='main' fixes potential TypeErrors
                res_reg = authenticator.register_user(location='main', pre_authorization=False)
                if res_reg:
                    e, u, n = res_reg
                    if e:
                        h_pw = stauth.Hasher.hash(authenticator.credentials['usernames'][u]['password'])
                        conn = sqlite3.connect('breatheeasy.db')
                        conn.cursor().execute("INSERT INTO users (username, email, name, password, role, package, last_login) VALUES (?,?,?,?,?,?,?)",
                                              (u, e, n, h_pw, 'member', 'Basic', datetime.now().strftime("%Y-%m-%d %H:%M")))
                        conn.commit(); conn.close(); st.success('Registration complete! Please login.')
            except Exception as e: st.info("Fill the form to register.")
    st.stop()

# --- 6. PROTECTED DASHBOARD ---
if st.session_state["authentication_status"]:
    username = st.session_state["username"]
    user_info = get_db_creds()['usernames'].get(username, {})
    user_tier = user_info.get('package', 'Basic')
    user_logo = user_info.get('logo_path')

    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state['name']} <span class='tier-badge'>{user_tier}</span>", unsafe_allow_html=True)
        if st.button("🎓 Video Tutorial"): video_tutorial()
        
        if PACKAGE_CONFIG[user_tier]["branding"]:
            with st.expander("🎨 Custom Branding"):
                logo_file = st.file_uploader("Company Logo", type=['png', 'jpg'])
                if logo_file:
                    os.makedirs("logos", exist_ok=True)
                    user_logo = f"logos/{username}.png"
                    with open(user_logo, "wb") as f: f.write(logo_file.getvalue())
                    conn = sqlite3.connect('breatheeasy.db')
                    conn.cursor().execute("UPDATE users SET logo_path = ? WHERE username = ?", (user_logo, username))
                    conn.commit(); conn.close(); st.success("Branding Applied!")
        
        if user_tier == "Basic":
            with st.expander("🎟️ Redeem Coupon"):
                coupon = st.text_input("Promo Code")
                if st.button("Apply"):
                    if coupon == "BreatheFree2026":
                        update_user_package(username, "Pro")
                        st.success("Upgraded to PRO!"); st.rerun()

        authenticator.logout('Sign Out', 'sidebar')
        st.divider()

        # ASSET MANAGER & INPUTS
        st.subheader("📁 Asset Manager")
        max_f = PACKAGE_CONFIG[user_tier]["max_files"]
        st.file_uploader(f"Max {max_f} assets", accept_multiple_files=True)
        
        full_map = {
            "HVAC": ["Full System Replacement", "IAQ Audit", "AC Repair"], 
            "Plumbing": ["Sewer Repair", "Tankless Heaters", "Repiping"],
            "Restoration": ["Water Damage", "Mold Remediation"], 
            "Roofing": ["Roof Replacement", "Storm Damage"],
            "Solar": ["Solar Grid Install"], "Custom": ["Manual Entry"]
        }
        allowed = PACKAGE_CONFIG[user_tier]["allowed_industries"]
        main_cat = st.selectbox("Industry", [i for i in full_map.keys() if i in allowed])
        target_service = st.selectbox("Service", full_map[main_cat]) if main_cat != "Custom" else st.text_input("Service")
        city_input = st.text_input("City", placeholder="Naperville, IL")

        # THE TWO AGENT FEATURES (Blog SEO and Competitor Analyst)
        include_blog = st.toggle("📝 SEO Blog Content Strategist", value=True) if PACKAGE_CONFIG[user_tier]["blog"] else False
        include_comp = st.toggle("🕵️ Competitor Intelligence Analyst", value=True) if user_tier != "Basic" else False
        
        run_button = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

    # --- TABS ---
    tabs = st.tabs(["🔥 Launchpad", "📊 Database", "📱 Social Preview", "💎 Pricing", "🛠️ Admin" if username == "admin" else "📋 History"])

    with tabs[0]: # OUTPUT TAB
        if run_button and city_input:
            with st.spinner("Swarm Coordinating..."):
                run_marketing_swarm({'city': city_input, 'industry': main_cat, 'service': target_service, 'blog': include_blog, 'comp': include_comp})
                if os.path.exists("final_marketing_strategy.md"):
                    with open("final_marketing_strategy.md", "r") as f: st.session_state['copy'] = f.read()
                    st.session_state['gen'] = True
        
        if st.session_state.get('gen'):
            copy = st.session_state['copy']
            
            # THE RESTORED DOWNLOAD SECTION
            st.subheader("📥 Download Deliverables")
            col1, col2 = st.columns(2)
            col1.download_button("📄 Word Doc", create_word_doc(copy, user_logo), f"{city_input}_Strategy.docx", use_container_width=True)
            col2.download_button("📕 PDF Report", create_pdf(copy, target_service, city_input, user_logo), f"{city_input}_Strategy.pdf", use_container_width=True)
            st.divider()
            st.markdown(copy)

    with tabs[3]: # PRICING (GEM Tab)
        st.subheader("💎 Membership Plans")
        c1, c2, c3 = st.columns(3)
        for i, (p_name, p_val) in enumerate(PACKAGE_CONFIG.items()):
            with [c1, c2, c3][i]:
                st.markdown(f"""
                <div class="pricing-card">
                    <h3>{p_name}</h3>
                    <p style='color: #666; font-size: 13px;'>{p_val['desc']}</p>
                    <hr>
                    <ul style="text-align: left; font-size: 12px;">
                        <li>{len(p_val['allowed_industries'])} Industries</li>
                        <li>{p_val['max_files']} File Assets</li>
                        <li>{'✅' if p_val['blog'] else '❌'} SEO Blog AI</li>
                        <li>{'✅' if p_val['branding'] else '❌'} Logo Branding</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)

    if username == "admin":
        with tabs[-1]:
            st.subheader("🛠️ User Management")
            conn = sqlite3.connect('breatheeasy.db')
            df_users = pd.read_sql_query("SELECT username, email, package FROM users", conn)
            st.dataframe(df_users, use_container_width=True)
            user_to_del = st.selectbox("Select user to remove", df_users['username'])
            if st.button("❌ Remove Account") and user_to_del != 'admin':
                conn.cursor().execute("DELETE FROM users WHERE username = ?", (user_to_del,))
                conn.commit(); st.success(f"Removed {user_to_del}"); st.rerun()
            conn.close()
