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
st.set_page_config(page_title="BreatheEasy AI", page_icon="🌬️", layout="wide")

# --- 3. DATABASE INITIALIZATION (Leads & Users) ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    # Table for Marketing Leads
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    # Table for Users (Automated Auth)
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT)''')
    
    # Check if admin exists
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        # --- VITAL FIX: Correct Hasher Syntax for v0.3.0+ ---
        hasher = stauth.Hasher(['admin123'])
        hashed_pw = hasher.generate()[0]
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

# --- 4. SaaS WHITE-LABEL UI & CSS ---
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
    .mockup-container {{ background: white; border: 1px solid #ddd; border-radius: 12px; padding: 15px; margin-bottom: 20px; max-width: 500px; }}
    .mockup-header {{ display: flex; align-items: center; margin-bottom: 10px; }}
    .profile-pic {{ width: 38px; height: 38px; border-radius: 50%; background: #eee; margin-right: 10px; }}
    .profile-name {{ font-weight: bold; font-size: 14px; color: #1c1e21; }}
    .mockup-text {{ font-size: 14px; line-height: 1.4; color: #1c1e21; margin-bottom: 10px; }}
    .mockup-image {{ width: 100%; height: 220px; background: #f0f2f5; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #888; border: 1px dashed #ccc; }}
    .fb-btn-row {{ display: flex; justify-content: space-around; border-top: 1px solid #eee; margin-top: 10px; padding-top: 8px; color: #606770; font-size: 13px; font-weight: 600; }}
    .color-card {{ padding: 15px; border-radius: 8px; text-align: center; color: white; font-weight: bold; margin-bottom: 5px; }}
    </style>
""", unsafe_allow_html=True)

# --- 5. AUTHENTICATION (Database Driven) ---
db_credentials = get_users_from_db()
authenticator = stauth.Authenticate(
    db_credentials, st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days']
)

authenticator.login(location='main')

if st.session_state["authentication_status"] is False:
    st.error('Username/password is incorrect')
    with st.expander("Forgot Password?"):
        authenticator.forgot_password()

elif st.session_state["authentication_status"] is None:
    st.warning('Please login to access the Launchpad')
    with st.expander("New User? Register Here"):
        try:
            res = authenticator.register_user(pre_authorization=False)
            if res:
                email, username, name = res
                if email:
                    # Capture the hashed password generated by the widget
                    new_pw_hash = authenticator.credentials['usernames'][username]['password']
                    if add_user_to_db(username, email, name, new_pw_hash):
                        st.success('Registered! You can now login.')
                        st.rerun()
        except Exception as e: st.error(e)
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
        pdf.cell(0, 10, 'BreatheEasy AI Strategy Report', 0, 1, 'C')
        pdf.set_font("Arial", size=11); clean = content.encode('latin-1', 'ignore').decode('latin-1')
        pdf.multi_cell(0, 8, txt=clean); return pdf.output(dest='S').encode('latin-1')

    def send_email_via_smtp(content, city):
        msg = MIMEMultipart(); msg["From"], msg["To"], msg["Subject"] = st.secrets["EMAIL_SENDER"], st.secrets["TEAM_EMAIL"], f"🚀 AI Report: {city}"
        msg.attach(MIMEText(f"Campaign ready for {city}.", "plain"))
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
                s.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"]); s.sendmail(st.secrets["EMAIL_SENDER"], st.secrets["TEAM_EMAIL"], msg.as_string())
            return True
        except: return False

    # --- SIDEBAR ---
    with st.sidebar:
        st.header(f"👋 Hello, {st.session_state['name']}!")
        authenticator.logout('Sign Out', 'sidebar')
        st.divider()
        industry_map = {"HVAC": ["System Replacement", "IAQ"], "Plumbing": ["Sewer Repair", "Water Heaters"]}
        main_cat = st.selectbox("Industry", list(industry_map.keys()))
        target_service = st.selectbox("Service", industry_map[main_cat])
        city_input = st.text_input("City", placeholder="Naperville, IL")
        high_ticket = st.toggle("🚀 High-Ticket Focus", value=True)
        include_blog = st.toggle("📝 Include SEO Blog", value=True)
        run_button = st.button("🚀 Launch Swarm", type="primary", use_container_width=True)

    st.title("🌬️ BreatheEasy AI Launchpad")
    tabs = st.tabs(["🔥 Generate Strategy", "📊 Lead Database", "📱 Social Preview", "🎨 Brand Kit"])

    with tabs[0]:
        if run_button and city_input:
            with st.spinner("AI Swarm coordinating agents..."):
                run_marketing_swarm({'city': city_input, 'industry': main_cat, 'service': target_service, 'premium': high_ticket, 'blog': include_blog})
                with open("final_marketing_strategy.md", "r", encoding="utf-8") as f: content = f.read()
                st.session_state['ad_copy'] = content
                st.session_state['generated'] = True
                save_lead_to_db(st.session_state['name'], main_cat, target_service, city_input, content)

        if st.session_state.get('generated'):
            st.success("✨ Strategy Complete!")
            copy = st.session_state['ad_copy']
            c1, c2, c3 = st.columns(3)
            with c1: st.download_button("📄 Download Word", create_word_doc(copy), f"{city_input}_Report.docx", use_container_width=True)
            with c2: st.download_button("📕 Download PDF", create_pdf(copy, target_service, city_input), f"{city_input}_Report.pdf", use_container_width=True)
            with c3: 
                if st.button("📧 Email Team", use_container_width=True):
                    if send_email_via_smtp(copy, city_input): st.success("Sent!")
            st.divider()
            st.markdown(copy)

    with tabs[1]:
        st.subheader("Campaign History Intelligence")
        conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
        st.dataframe(pd.read_sql_query("SELECT date, city, service, user FROM leads ORDER BY id DESC", conn), use_container_width=True, hide_index=True)
        conn.close()

    with tabs[2]:
        if st.session_state.get('generated'):
            ad_text = st.session_state['ad_copy']
            encoded_text = urllib.parse.quote(ad_text[:400])
            st.link_button("🐦 Post to X (Twitter)", f"https://twitter.com/intent/tweet?text={encoded_text}", use_container_width=True)
            st.divider()
            st.markdown(f"""
                <div class="mockup-container">
                    <div class="mockup-header">
                        <img src="{logo_url}" class="profile-pic">
                        <div class="profile-name">BreatheEasy {main_cat}</div>
                    </div>
                    <div class="mockup-text">{ad_text[:350]}...</div>
                    <div class="mockup-image">AI Visual Content Rendering</div>
                    <div class="fb-btn-row"><span>👍 Like</span><span>💬 Comment</span><span>🔗 Share</span></div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Run a campaign in the 'Generate' tab to see previews.")

    with tabs[3]:
        st.header("SaaS Brand Kit")
        st.markdown(f'<div class="color-card" style="background-color: {brand_blue};">Primary Brand Blue: {brand_blue}</div>', unsafe_allow_html=True)
        st.image(logo_url, width=150)
