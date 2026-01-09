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
st.set_page_config(
    page_title="BreatheEasy AI | Multi-Industry Swarm",
    page_icon="🌬️",
    layout="wide"
)

# --- 3. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT)''')
    
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, email, name, password, role) VALUES (?, ?, ?, ?, ?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin'))
    conn.commit()
    conn.close()

def get_users_from_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    user_dict = {'usernames': {}}
    for _, row in df.iterrows():
        user_dict['usernames'][row['username']] = {
            'email': row['email'], 'name': row['name'], 'password': row['password']
        }
    return user_dict

def add_user_to_db(username, email, name, hashed_password):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, email, name, password, role) VALUES (?, ?, ?, ?, ?)",
                  (username, email, name, hashed_password, 'member'))
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

# --- 4. SaaS PREMIUM UI CUSTOMIZATION ---
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
    .mockup-container {{ background: white; border: 1px solid #ddd; border-radius: 12px; padding: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); max-width: 500px; }}
    .profile-pic {{ width: 42px; height: 42px; border-radius: 50%; background: #f0f2f5; margin-right: 12px; }}
    .profile-name {{ font-weight: 700; font-size: 14px; color: #1c1e21; }}
    .color-card {{ padding: 15px; border-radius: 8px; text-align: center; color: white; font-weight: bold; margin-bottom: 5px; }}
    </style>
""", unsafe_allow_html=True)

# --- 5. AUTHENTICATION ---
db_credentials = get_users_from_db()
authenticator = stauth.Authenticate(
    db_credentials, st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days']
)

authenticator.login(location='main')

if st.session_state["authentication_status"] is False:
    st.error('Invalid Credentials')
    with st.expander("Forgot Password?"):
        authenticator.forgot_password()

elif st.session_state["authentication_status"] is None:
    st.info('🛡️ Welcome. Please authenticate to access the Launchpad.')
    with st.expander("Register Team Account"):
        try:
            res = authenticator.register_user(pre_authorization=False)
            if res:
                email, username, name = res
                if email:
                    temp_pw = authenticator.credentials['usernames'][username]['password']
                    db_ready_pw = stauth.Hasher.hash(temp_pw)
                    if add_user_to_db(username, email, name, db_ready_pw):
                        st.success('✅ Account Created. You may now login.')
                        st.rerun()
        except Exception as e: st.error(f"Registration error: {e}")
    st.stop()

# --- 6. PROTECTED DASHBOARD ---
if st.session_state["authentication_status"]:
    
    # Helper Functions
    def create_word_doc(content):
        doc = Document(); doc.add_heading('BreatheEasy AI Strategy', 0)
        for line in content.split('\n'): doc.add_paragraph(line)
        bio = BytesIO(); doc.save(bio); return bio.getvalue()

    def create_pdf(content, service, city):
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 15)
        pdf.cell(0, 10, 'Marketing Strategy Report', 0, 1, 'C')
        pdf.set_font("Arial", size=11); clean = content.encode('latin-1', 'ignore').decode('latin-1')
        pdf.multi_cell(0, 8, txt=clean); return pdf.output(dest='S').encode('latin-1')

    # --- SIDEBAR: RESTORED INDUSTRY & SERVICE MAPPING ---
    with st.sidebar:
        st.markdown(f"### 👋 Hello, {st.session_state['name']}")
        authenticator.logout('Sign Out', 'sidebar')
        st.divider()
        
        st.subheader("🎯 Campaign Settings")
        
        # RESTORED FULL INDUSTRY MAP
        industry_map = {
            "HVAC": ["Full System Replacement", "IAQ & Filtration", "Heat Pump Upgrade", "Duct Cleaning"],
            "Plumbing": ["Sewer Line Replacement", "Tankless Water Heaters", "Whole-Home Repiping"],
            "Restoration": ["Mold Remediation", "Water Damage Recovery", "Fire & Smoke Restoration"],
            "Roofing": ["Full Roof Replacement", "Storm Damage Repair", "Commercial Coating"],
            "Solar": ["Residential Solar Grid", "Battery Backup Install", "Solar Maintenance"],
            "Custom": ["Manual Entry"]
        }
        
        main_cat = st.selectbox("Select Industry", list(industry_map.keys()))
        
        if main_cat == "Custom":
            target_service = st.text_input("Enter Custom Service", placeholder="e.g. Luxury Landscaping")
        else:
            target_service = st.selectbox("Select Service", industry_map[main_cat])
            
        city_input = st.text_input("Target City", placeholder="e.g. Naperville, IL")
        
        st.divider()
        high_ticket = st.toggle("🚀 High-Ticket Focus", value=True)
        include_blog = st.toggle("📝 SEO Blog Content", value=True)
        
        run_button = st.button("🚀 LAUNCH SWARM", use_container_width=True, type="primary")

    # --- MAIN CONTENT TABS ---
    t_gen, t_db, t_social, t_brand = st.tabs(["🔥 Launchpad", "📊 Lead Database", "📱 Social Preview", "🎨 Brand Kit"])

    with t_gen:
        if run_button and city_input:
            with st.spinner("🤖 Coordinating AI Agents..."):
                run_marketing_swarm({'city': city_input, 'industry': main_cat, 'service': target_service, 'premium': high_ticket, 'blog': include_blog})
                try:
                    with open("final_marketing_strategy.md", "r", encoding="utf-8") as f:
                        content = f.read()
                    st.session_state['ad_copy'] = content
                    st.session_state['generated'] = True
                    save_lead_to_db(st.session_state['name'], main_cat, target_service, city_input, content)
                except:
                    st.error("Error retrieving strategy file.")

        if st.session_state.get('generated'):
            st.success("✨ Strategy Generated Successfully")
            copy = st.session_state['ad_copy']
            
            c1, c2 = st.columns(2)
            with c1: st.download_button("📥 Download Word", create_word_doc(copy), f"{city_input}_Report.docx", use_container_width=True)
            with c2: st.download_button("📕 Download PDF", create_pdf(copy, target_service, city_input), f"{city_input}_Report.pdf", use_container_width=True)
            
            st.divider()
            st.markdown(copy)

    with t_db:
        st.subheader("Historical Lead Intelligence")
        conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
        db_df = pd.read_sql_query("SELECT date, city, industry, service, user FROM leads ORDER BY id DESC", conn)
        st.dataframe(db_df, use_container_width=True, hide_index=True)
        conn.close()

    with t_social:
        if st.session_state.get('generated'):
            ad_text = st.session_state['ad_copy']
            st.link_button("🔵 Meta Business Suite", "https://business.facebook.com/latest/composer", use_container_width=True)
            st.divider()
            st.markdown(f"""
                <div class="mockup-container">
                    <div class="mockup-header">
                        <div class="profile-pic"></div>
                        <div class="profile-name">BreatheEasy {main_cat}</div>
                    </div>
                    <div class="mockup-text">{ad_text[:350]}...</div>
                    <div class="mockup-image">AI Visual Content Rendering</div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.info("💡 Run a campaign to view social media mockups.")

    with t_brand:
        st.header("Brand Assets")
        st.markdown(f'<div class="color-card" style="background-color: {brand_blue};">Trust Blue: {brand_blue}</div>', unsafe_allow_html=True)
        st.image(logo_url, width=150)
