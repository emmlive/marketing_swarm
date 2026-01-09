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
st.set_page_config(page_title="BreatheEasy AI | Enterprise", page_icon="🌬️", layout="wide")

# --- 3. DATABASE INITIALIZATION (Expanded for Packages) ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    # Added 'package' column for Tiered Access
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, package TEXT)''')
    
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        # Admin defaults to 'Unlimited'
        c.execute("INSERT INTO users (username, email, name, password, role, package) VALUES (?, ?, ?, ?, ?, ?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited'))
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
            'package': row.get('package', 'Basic') # Store package in auth dict
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
                    # Logic: New signups start on 'Basic'
                    db_ready_pw = stauth.Hasher.hash(authenticator.credentials['usernames'][username]['password'])
                    if add_user_to_db(username, email, name, db_ready_pw, package='Basic'):
                        st.success('✅ Registered! Login to start your Basic plan.')
                        st.rerun()
        except Exception as e: st.error(e)
    st.stop()

# --- 6. PROTECTED DASHBOARD ---
if st.session_state["authentication_status"]:
    
    # FETCH USER TIER
    # Authenticator puts user info into st.session_state after login
    username = st.session_state["username"]
    user_tier = db_credentials['usernames'][username].get('package', 'Basic')

    # PACKAGE DEFINITIONS
    PACKAGE_CONFIG = {
        "Basic": {"allowed_industries": ["HVAC", "Plumbing"], "blog": False, "max_files": 1},
        "Pro": {"allowed_industries": ["HVAC", "Plumbing", "Restoration", "Roofing"], "blog": True, "max_files": 5},
        "Unlimited": {"allowed_industries": ["HVAC", "Plumbing", "Restoration", "Roofing", "Solar", "Custom"], "blog": True, "max_files": 20}
    }

    # --- SIDEBAR & MULTI-FILE UPLOAD ---
    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state['name']} <span class='tier-badge'>{user_tier}</span>", unsafe_allow_html=True)
        authenticator.logout('Sign Out', 'sidebar')
        st.divider()

        st.subheader("📁 Asset Manager")
        max_f = PACKAGE_CONFIG[user_tier]["max_files"]
        uploaded_media = st.file_uploader(f"Reference Photos/Videos (Max {max_f})", 
                                         accept_multiple_files=True, 
                                         type=['png', 'jpg', 'mp4'])
        
        if len(uploaded_media) > max_f:
            st.error(f"⚠️ Your {user_tier} plan only allows {max_f} files. Please remove some.")
        
        st.divider()
        st.subheader("🎯 Campaign Settings")
        
        # INDUSTRY GATING
        full_map = {
            "HVAC": ["Full System Replacement", "IAQ"],
            "Plumbing": ["Sewer Repair", "Tankless Heaters"],
            "Restoration": ["Water Damage", "Mold Remediation"],
            "Roofing": ["Roof Replacement", "Storm Damage"],
            "Solar": ["Solar Grid Install"],
            "Custom": ["Manual Entry"]
        }
        
        allowed = PACKAGE_CONFIG[user_tier]["allowed_industries"]
        main_cat = st.selectbox("Industry", [i for i in full_map.keys() if i in allowed])
        target_service = st.selectbox("Service", full_map[main_cat]) if main_cat != "Custom" else st.text_input("Custom Service")
        city_input = st.text_input("City", placeholder="e.g. Naperville, IL")

        # FEATURE GATING (Blog)
        if PACKAGE_CONFIG[user_tier]["blog"]:
            include_blog = st.toggle("📝 SEO Blog Content", value=True)
        else:
            st.info("🔒 Upgrade to Pro for SEO Blogs")
            include_blog = False

        run_button = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

    # --- MAIN TABS ---
    t_gen, t_db, t_social, t_brand = st.tabs(["🔥 Launchpad", "📊 Database", "📱 Social", "🎨 Brand Kit"])

    with t_gen:
        if run_button and city_input:
            if len(uploaded_media) <= max_f:
                with st.spinner(f"Agent Swarm active on {user_tier} Tier..."):
                    # Process Swarm
                    run_marketing_swarm({'city': city_input, 'industry': main_cat, 'service': target_service, 'premium': True, 'blog': include_blog})
                    with open("final_marketing_strategy.md", "r", encoding="utf-8") as f: content = f.read()
                    st.session_state['ad_copy'] = content
                    st.session_state['generated'] = True
            else:
                st.error("Too many files uploaded for your plan.")

        if st.session_state.get('generated'):
            st.success(f"✨ {user_tier} Campaign Ready!")
            st.markdown(st.session_state['ad_copy'])

    with t_brand:
        st.header("SaaS Identity")
        if user_tier == "Basic":
            st.warning("Want to add Solar or Custom Industries? [Click here to Upgrade to Pro](https://your-stripe-link.com)")
        st.image(logo_url, width=150)
