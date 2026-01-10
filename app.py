import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
import urllib.parse
from datetime import datetime, timedelta
from main import run_marketing_swarm 
from docx import Document
from fpdf import FPDF
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- 1. PRE-IMPORT KEY MAPPING ---
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

# --- 2. PAGE CONFIGURATION ---
st.set_page_config(page_title="BreatheEasy AI | Enterprise", page_icon="🌬️", layout="wide")

# --- 3. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, package TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, admin_user TEXT, action TEXT, target_user TEXT, details TEXT)''')
    
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, email, name, password, role, package) VALUES (?, ?, ?, ?, ?, ?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited'))
    conn.commit()
    conn.close()

# --- 4. EMAIL & REPORTING LOGIC ---
def send_admin_alert(subject, body):
    msg = MIMEMultipart()
    msg["From"] = st.secrets["EMAIL_SENDER"]
    msg["To"] = st.secrets["TEAM_EMAIL"]
    msg["Subject"] = f"🔔 BreatheEasy: {subject}"
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"])
            server.sendmail(st.secrets["EMAIL_SENDER"], st.secrets["TEAM_EMAIL"], msg.as_string())
        return True
    except: return False

def generate_monthly_report():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    new_users = pd.read_sql_query("SELECT COUNT(*) as count FROM users WHERE username != 'admin'", conn)['count'][0]
    upgrades = pd.read_sql_query("SELECT details FROM audit_logs WHERE action = 'UPDATE_TIER'", conn)
    pro_count = upgrades[upgrades['details'].str.contains("Pro", na=False)].shape[0]
    unlimited_count = upgrades[upgrades['details'].str.contains("Unlimited", na=False)].shape[0]
    total_rev = (pro_count * 49) + (unlimited_count * 99)
    leads = pd.read_sql_query("SELECT industry, service FROM leads", conn)
    service_summary = leads.groupby(['industry', 'service']).size().reset_index(name='usage_count')
    
    report_body = f"""
    BREATHEEASY AI - MONTHLY PERFORMANCE REPORT
    --------------------------------------------
    📈 USER GROWTH: Total Members: {new_users}
    💰 REVENUE SUMMARY: Pro: {pro_count} | Unlimited: {unlimited_count} | EST. TOTAL: ${total_rev}
    🛠️ TOP SERVICES:
    {service_summary.to_string(index=False)}
    """
    conn.close()
    return send_admin_alert("Monthly Revenue & Usage Report", report_body)

# --- 5. LOGGING & DB UPDATES ---
def log_action(admin_user, action, target_user, details=""):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO audit_logs (timestamp, admin_user, action, target_user, details) VALUES (?, ?, ?, ?, ?)",
              (timestamp, admin_user, action, target_user, details))
    conn.commit(); conn.close()

def update_user_package(username, new_package, admin_name):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT package FROM users WHERE username = ?", (username,))
    old_p = c.fetchone()[0]
    c.execute("UPDATE users SET package = ? WHERE username = ?", (new_package, username))
    conn.commit(); conn.close()
    log_action(admin_name, "UPDATE_TIER", username, f"Changed from {old_p} to {new_package}")
    send_admin_alert("Tier Update", f"User {username} upgraded to {new_package}.")

def get_users_from_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    user_dict = {'usernames': {}}
    for _, row in df.iterrows():
        user_dict['usernames'][row['username']] = {
            'email': row['email'], 'name': row['name'], 'password': row['password'], 'package': row.get('package', 'Basic')
        }
    return user_dict

def save_lead_to_db(user, industry, service, city, content):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO leads (date, user, industry, service, city, content) VALUES (?, ?, ?, ?, ?, ?)",
              (date_str, user, industry, service, city, content))
    conn.commit(); conn.close()

init_db()

# --- 6. UI STYLING ---
logo_url = "https://drive.google.com/uc?export=view&id=1Jw7XreUO4yAQxUgKAZPK4sRi4mzjw_yU"
brand_blue = "#0056b3"
brand_bg = "#F8F9FB" 

st.markdown(f"""
    <style>
    header {{ visibility: hidden !important; }}
    div[data-testid="stStatusWidget"], .stAppDeployButton, footer, #stDecoration {{ display: none !important; }}
    .stApp {{ background-color: {brand_bg}; }}
    .stApp::before {{
        content: ""; display: block; margin: 30px auto 0; width: 140px; height: 140px;
        background-image: url("{logo_url}"); background-size: contain; background-repeat: no-repeat;
    }}
    .tier-badge {{ padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; background: {brand_blue}; color: white; }}
    .feature-card {{ background: white; padding: 25px; border-radius: 12px; border: 1px solid #e0e0e0; text-align: center; height: 100%; }}
    .pricing-card {{ border: 1px solid #ddd; padding: 20px; border-radius: 10px; text-align: center; background: white; height: 100%; }}
    </style>
""", unsafe_allow_html=True)

# --- 7. AUTHENTICATION & LANDING PAGE ---
db_credentials = get_users_from_db()
authenticator = stauth.Authenticate(
    db_credentials, st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days']
)
authenticator.login(location='main')

if st.session_state["authentication_status"] is None:
    st.markdown("<h1 style='text-align: center;'>🌬️ BreatheEasy AI Launchpad</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.2rem;'>High-Ticket Home Service Marketing Swarm</p>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown('<div class="feature-card"><h3>🐝 Swarm</h3><p>5 agents working in sync.</p></div>', unsafe_allow_html=True)
    with c2: st.markdown('<div class="feature-card"><h3>📈 Niches</h3><p>HVAC, Solar, Restoration.</p></div>', unsafe_allow_html=True)
    with c3: st.markdown('<div class="feature-card"><h3>📄 Export</h3><p>Word & PDF delivery.</p></div>', unsafe_allow_html=True)

    with st.expander("New User? Register Here"):
        try:
            res = authenticator.register_user(pre_authorization=False)
            if res:
                email, username, name = res
                if email:
                    db_ready_pw = stauth.Hasher.hash(authenticator.credentials['usernames'][username]['password'])
                    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
                    conn.cursor().execute("INSERT INTO users (username, email, name, password, role, package) VALUES (?, ?, ?, ?, ?, ?)",
                                          (username, email, name, db_ready_pw, 'member', 'Basic'))
                    conn.commit(); conn.close()
                    send_admin_alert("New Registration", f"New user: {name} (@{username})")
                    st.success('✅ Registered! Login above.'); st.rerun()
        except Exception as e: st.error(e)
    st.stop()

# --- 8. PROTECTED DASHBOARD ---
if st.session_state["authentication_status"]:
    username = st.session_state["username"]
    current_db_data = get_users_from_db()
    user_tier = current_db_data['usernames'][username].get('package', 'Basic')

    PACKAGE_CONFIG = {
        "Basic": {"allowed_industries": ["HVAC", "Plumbing"], "blog": False, "max_files": 1},
        "Pro": {"allowed_industries": ["HVAC", "Plumbing", "Restoration", "Roofing"], "blog": True, "max_files": 5},
        "Unlimited": {"allowed_industries": ["HVAC", "Plumbing", "Restoration", "Roofing", "Solar", "Custom"], "blog": True, "max_files": 20}
    }

    # --- RESTORED FILE EXPORT FUNCTIONS ---
    def create_word_doc(content):
        doc = Document()
        doc.add_heading('BreatheEasy AI Strategy Report', 0)
        doc.add_paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d')}")
        for line in content.split('\n'):
            doc.add_paragraph(line)
        bio = BytesIO()
        doc.save(bio)
        return bio.getvalue()

    def create_pdf(content, service, city):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, 'BreatheEasy AI Marketing Strategy', 0, 1, 'C')
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, f"Industry: {service} | Location: {city}", 0, 1, 'C')
        pdf.ln(10)
        pdf.set_font("Arial", size=11)
        # Clean text for PDF encoding
        clean_text = content.encode('latin-1', 'ignore').decode('latin-1')
        pdf.multi_cell(0, 8, txt=clean_text)
        return pdf.output(dest='S').encode('latin-1')

    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state['name']} <span class='tier-badge'>{user_tier}</span>", unsafe_allow_html=True)
        authenticator.logout('Sign Out', 'sidebar')
        st.divider()
        if user_tier == "Basic":
            with st.expander("🎟️ Promo Code"):
                code = st.text_input("Enter Code")
                if st.button("Apply"):
                    if code == "BreatheFree2026": update_user_package(username, "Pro", "SELF_REDEEM"); st.rerun()
        
        st.subheader("🎯 Campaign Settings")
        full_map = {
            "HVAC": ["System Replacement", "IAQ"], "Plumbing": ["Sewer Repair", "Tankless"],
            "Restoration": ["Mold", "Water Damage"], "Roofing": ["Full Roof", "Repair"],
            "Solar": ["Grid Install"], "Custom": ["Manual Entry"]
        }
        allowed = PACKAGE_CONFIG[user_tier]["allowed_industries"]
        main_cat = st.selectbox("Industry", [i for i in full_map.keys() if i in allowed])
        target_service = st.selectbox("Service", full_map[main_cat]) if main_cat != "Custom" else st.text_input("Service")
        city_input = st.text_input("City", placeholder="Naperville, IL")
        include_blog = st.toggle("📝 SEO Blog", value=True) if PACKAGE_CONFIG[user_tier]["blog"] else False
        run_button = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

    tabs = st.tabs(["🔥 Launchpad", "📊 Database", "📱 Social", "💎 Pricing", "🛠️ Admin" if username == "admin" else "ℹ️ Support"])

    with tabs[0]:
        if run_button and city_input:
            with st.spinner("AI Swarm Active..."):
                run_marketing_swarm({'city': city_input, 'industry': main_cat, 'service': target_service, 'premium': True, 'blog': include_blog})
                with open("final_marketing_strategy.md", "r", encoding="utf-8") as f: content = f.read()
                st.session_state['ad_copy'] = content
                st.session_state['generated'] = True
                save_lead_to_db(username, main_cat, target_service, city_input, content)
        
        if st.session_state.get('generated'):
            st.success("✨ Strategy Ready!")
            copy = st.session_state['ad_copy']
            
            # Action Buttons
            col_a, col_b = st.columns(2)
            with col_a:
                st.download_button("📥 Download Word Doc", create_word_doc(copy), f"{city_input}_Report.docx", use_container_width=True)
            with col_b:
                st.download_button("📕 Download PDF", create_pdf(copy, target_service, city_input), f"{city_input}_Report.pdf", use_container_width=True)
            
            st.divider()
            st.markdown(copy)

    with tabs[3]:
        st.title("💎 Plan Comparison")
        p1, p2, p3 = st.columns(3)
        with p1: 
            st.markdown('<div class="pricing-card"><h3>Basic</h3><h1>$0</h1><p>HVAC/Plumb only<br>1 Asset Upload<br>No Blogs</p></div>', unsafe_allow_html=True)
        with p2:
            st.markdown('<div class="pricing-card" style="border: 2px solid #0056b3;"><h3>Pro</h3><h1>$49</h1><p>4 Industries<br>5 Assets<br>SEO Blogs</p></div>', unsafe_allow_html=True)
            st.link_button("Upgrade Now", "https://buy.stripe.com/pro_link", type="primary", use_container_width=True)
        with p3:
            st.markdown('<div class="pricing-card"><h3>Unlimited</h3><h1>$99</h1><p>All Industries<br>20 Assets<br>Custom niches</p></div>', unsafe_allow_html=True)
            st.link_button("Go Unlimited", "https://buy.stripe.com/unlimited_link", use_container_width=True)

    if username == "admin":
        with tabs[-1]:
            a_tabs = st.tabs(["👥 Users", "📜 Logs", "📈 Reports"])
            # [Admin logic here...]
