import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
import urllib.parse
from datetime import datetime
from main import run_marketing_swarm 
from docx import Document
from fpdf import FPDF
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- 1. PRE-IMPORT KEY MAPPING ---
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

# --- 2. PAGE CONFIGURATION ---
st.set_page_config(page_title="BreatheEasy AI | Enterprise Swarm", page_icon="🌬️", layout="wide")

# --- 3. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, package TEXT)''')
    
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, email, name, password, role, package) VALUES (?, ?, ?, ?, ?, ?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited'))
    conn.commit()
    conn.close()

def update_user_package(username, new_package):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE users SET package = ? WHERE username = ?", (new_package, username))
    conn.commit()
    conn.close()

def get_users_from_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    user_dict = {'usernames': {}}
    for _, row in df.iterrows():
        user_dict['usernames'][row['username']] = {
            'email': row['email'], 'name': row['name'], 'password': row['password'],
            'package': row.get('package', 'Basic')
        }
    return user_dict

def add_user_to_db(username, email, name, hashed_password, package='Basic'):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, email, name, password, role, package) VALUES (?, ?, ?, ?, ?, ?)",
                  (username, email, name, hashed_password, 'member', package))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def save_lead_to_db(user, industry, service, city, content):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO leads (date, user, industry, service, city, content) VALUES (?, ?, ?, ?, ?, ?)",
              (date_str, user, industry, service, city, content))
    conn.commit()
    conn.close()

init_db()

# --- 4. SaaS UI STYLING ---
logo_url = "https://drive.google.com/uc?export=view&id=1Jw7XreUO4yAQxUgKAZPK4sRi4mzjw_yU"
brand_blue = "#0056b3"
brand_bg = "#F8F9FB" 

st.markdown(f"""
    <style>
    header {{ visibility: hidden !important; }}
    div[data-testid="stStatusWidget"], .stAppDeployButton, footer, #stDecoration {{ display: none !important; }}
    .stApp {{ background-color: {brand_bg}; }}
    .stApp::before {{
        content: ""; display: block; margin: 30px auto 0;
        width: 140px; height: 140px;
        background-image: url("{logo_url}");
        background-size: contain; background-repeat: no-repeat;
    }}
    .block-container {{ padding-top: 1.5rem !important; }}
    .tier-badge {{ padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; background: {brand_blue}; color: white; }}
    .pricing-card {{ border: 1px solid #ddd; padding: 20px; border-radius: 10px; text-align: center; background: white; }}
    </style>
""", unsafe_allow_html=True)

# --- 5. AUTHENTICATION & TIER CHECK ---
db_credentials = get_users_from_db()
authenticator = stauth.Authenticate(
    db_credentials, st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days']
)

authenticator.login(location='main')

if st.session_state["authentication_status"] is None:
    st.warning('Welcome. Please login.')
    with st.expander("New User? Register Here"):
        try:
            res = authenticator.register_user(pre_authorization=False)
            if res:
                email, username, name = res
                if email:
                    db_ready_pw = stauth.Hasher.hash(authenticator.credentials['usernames'][username]['password'])
                    if add_user_to_db(username, email, name, db_ready_pw, package='Basic'):
                        st.success('✅ Registered! Login to start your Basic plan.')
                        st.rerun()
        except Exception as e: st.error(e)
    st.stop()

# --- 6. PROTECTED DASHBOARD ---
if st.session_state["authentication_status"]:
    username = st.session_state["username"]
    current_db_data = get_users_from_db()
    user_tier = current_db_data['usernames'][username].get('package', 'Basic')

    PACKAGE_CONFIG = {
        "Basic": {"allowed_industries": ["HVAC", "Plumbing"], "blog": False, "max_files": 1},
        "Pro": {"allowed_industries": ["HVAC", "Plumbing", "Restoration", "Roofing"], "blog": True, "max_files": 5},
        "Unlimited": {"allowed_industries": ["HVAC", "Plumbing", "Restoration", "Roofing", "Solar", "Custom"], "blog": True, "max_files": 20}
    }

    # Helper Functions
    def create_word_doc(content):
        doc = Document(); doc.add_heading('BreatheEasy AI Strategy', 0)
        for line in content.split('\n'): doc.add_paragraph(line)
        bio = BytesIO(); doc.save(bio); return bio.getvalue()

    def create_pdf(content, service, city):
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 15)
        pdf.cell(0, 10, 'BreatheEasy AI Strategy Report', 0, 1, 'C')
        pdf.set_font("Arial", size=11); clean = content.encode('latin-1', 'ignore').decode('latin-1')
        pdf.multi_cell(0, 8, txt=clean); return pdf.output(dest='S').encode('latin-1')

    # --- SIDEBAR & ASSETS ---
    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state['name']} <span class='tier-badge'>{user_tier}</span>", unsafe_allow_html=True)
        authenticator.logout('Sign Out', 'sidebar')
        st.divider()

        if user_tier == "Basic":
            with st.expander("🎟️ Redeem Coupon"):
                coupon_code = st.text_input("Promo Code")
                if st.button("Apply"):
                    if coupon_code == "BreatheFree2026":
                        update_user_package(username, "Pro")
                        st.success("Upgraded to PRO!")
                        st.rerun()
                    else: st.error("Invalid Code")

        st.subheader("📁 Asset Manager")
        max_f = PACKAGE_CONFIG[user_tier]["max_files"]
        uploaded_media = st.file_uploader(f"Max {max_f} assets", accept_multiple_files=True, type=['png', 'jpg', 'mp4'])
        
        st.divider()
        full_map = {
            "HVAC": ["Full System Replacement", "IAQ"], "Plumbing": ["Sewer Repair", "Tankless Heaters"],
            "Restoration": ["Water Damage", "Mold Remediation"], "Roofing": ["Roof Replacement", "Storm Damage"],
            "Solar": ["Solar Grid Install"], "Custom": ["Manual Entry"]
        }
        allowed = PACKAGE_CONFIG[user_tier]["allowed_industries"]
        main_cat = st.selectbox("Industry", [i for i in full_map.keys() if i in allowed])
        target_service = st.selectbox("Service", full_map[main_cat]) if main_cat != "Custom" else st.text_input("Service")
        city_input = st.text_input("City", placeholder="Naperville, IL")

        include_blog = st.toggle("📝 SEO Blog Content", value=True) if PACKAGE_CONFIG[user_tier]["blog"] else False
        if not PACKAGE_CONFIG[user_tier]["blog"]: st.info("🔒 Upgrade for SEO Blogs")

        run_button = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

    # --- MAIN TABS ---
    t_gen, t_db, t_social, t_price = st.tabs(["🔥 Launchpad", "📊 Database", "📱 Social Preview", "💎 Pricing"])

    with t_gen:
        if run_button and city_input:
            if len(uploaded_media) <= max_f:
                with st.spinner(f"Swarm active on {user_tier} Tier..."):
                    run_marketing_swarm({'city': city_input, 'industry': main_cat, 'service': target_service, 'premium': True, 'blog': include_blog})
                    with open("final_marketing_strategy.md", "r", encoding="utf-8") as f: content = f.read()
                    st.session_state['ad_copy'] = content
                    st.session_state['generated'] = True
                    save_lead_to_db(username, main_cat, target_service, city_input, content)
            else: st.error("Too many files.")

        if st.session_state.get('generated'):
            st.success("✨ Strategy Ready!")
            copy = st.session_state['ad_copy']
            c1, c2 = st.columns(2)
            with c1: st.download_button("📄 Word", create_word_doc(copy), f"{city_input}.docx")
            with c2: st.download_button("📕 PDF", create_pdf(copy, target_service, city_input), f"{city_input}.pdf")
            st.markdown(copy)

    with t_db:
        conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
        df = pd.read_sql_query("SELECT date, user, industry, service, city FROM leads ORDER BY id DESC", conn)
        st.dataframe(df, use_container_width=True)
        conn.close()

    with t_price:
        st.title("💎 Plan Comparison")
        p1, p2, p3 = st.columns(3)
        with p1: 
            st.markdown('<div class="pricing-card"><h3>Basic</h3><h1>$0</h1><p>HVAC/Plumb only<br>1 Asset<br>No Blogs</p></div>', unsafe_allow_html=True)
        with p2:
            st.markdown('<div class="pricing-card" style="border: 2px solid #0056b3;"><h3>Pro</h3><h1>$49</h1><p>4 Industries<br>5 Assets<br>SEO Blogs</p></div>', unsafe_allow_html=True)
            st.link_button("Upgrade Now", "https://buy.stripe.com/pro_link", type="primary", use_container_width=True)
        with p3:
            st.markdown('<div class="pricing-card"><h3>Unlimited</h3><h1>$99</h1><p>All Industries<br>20 Assets<br>Custom niches</p></div>', unsafe_allow_html=True)
            st.link_button("Go Unlimited", "https://buy.stripe.com/unlimited_link", use_container_width=True)
