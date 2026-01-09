import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
from datetime import datetime
from openai import OpenAI
from main import run_marketing_swarm 
from docx import Document
from fpdf import FPDF
from io import BytesIO

# SMTP Libraries
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- 1. PRE-IMPORT KEY MAPPING ---
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
if "OPENAI_API_KEY" in st.secrets:
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

# --- 2. PAGE CONFIGURATION ---
st.set_page_config(page_title="BreatheEasy AI", page_icon="🌬️", layout="wide")

# --- 3. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('leads_history.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  date TEXT, user TEXT, industry TEXT, 
                  service TEXT, city TEXT, content TEXT)''')
    conn.commit()
    conn.close()

def save_to_db(user, industry, service, city, content):
    conn = sqlite3.connect('leads_history.db', check_same_thread=False)
    c = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO leads (date, user, industry, service, city, content) VALUES (?, ?, ?, ?, ?, ?)",
              (date_str, user, industry, service, city, content))
    conn.commit()
    conn.close()

init_db()

# --- 4. SaaS WHITE-LABEL UI & SOCIAL MOCKUP CSS ---
logo_url = "https://drive.google.com/uc?export=view&id=1Jw7XreUO4yAQxUgKAZPK4sRi4mzjw_yU"
brand_blue = "#0056b3"
brand_bg = "#F8F9FB" 

st.markdown(f"""
    <style>
    header {{ visibility: hidden !important; }}
    div[data-testid="stStatusWidget"], div[data-testid="stConnectionStatus"],
    .stAppDeployButton, a[href*="streamlit.io"], div[data-testid="stToolbar"], 
    footer, #stDecoration {{ display: none !important; visibility: hidden !important; }}
    .stApp {{ background-color: {brand_bg}; }}
    .stApp::before {{
        content: ""; display: block; margin: 40px auto 0;
        width: 150px; height: 150px;
        background-image: url("{logo_url}");
        background-size: contain; background-repeat: no-repeat;
    }}
    
    /* Social Media Mockup Styling */
    .mockup-container {{
        background: white;
        border: 1px solid #ddd;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 25px;
        max-width: 500px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    .mockup-header {{ display: flex; align-items: center; margin-bottom: 10px; }}
    .profile-pic {{ width: 40px; height: 40px; border-radius: 50%; background: #eee; margin-right: 10px; }}
    .profile-name {{ font-weight: bold; font-size: 14px; }}
    .mockup-text {{ font-size: 14px; line-height: 1.4; color: #1c1e21; margin-bottom: 10px; white-space: pre-wrap; }}
    .mockup-image {{ width: 100%; height: 250px; background: #f0f2f5; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #888; border: 1px dashed #ccc; }}
    
    /* Facebook Specific */
    .fb-btn {{ color: #606770; font-weight: 600; font-size: 13px; margin-top: 10px; border-top: 1px solid #ddd; padding-top: 10px; display: flex; justify-content: space-around; }}
    
    /* Brand Guide Cards */
    .color-card {{ padding: 20px; border-radius: 10px; text-align: center; color: white; font-weight: bold; border: 1px solid #ddd; }}
    </style>
""", unsafe_allow_html=True)

# --- 5. AUTHENTICATION ---
credentials = dict(st.secrets['credentials'])
if 'usernames' in credentials:
    credentials['usernames'] = dict(credentials['usernames'])
    for user in credentials['usernames']:
        credentials['usernames'][user] = dict(credentials['usernames'][user])

authenticator = stauth.Authenticate(
    credentials, st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days']
)
authenticator.login(location='main')

if st.session_state.get("authentication_status") is False:
    st.error('Username/password is incorrect')
elif st.session_state.get("authentication_status") is None:
    st.warning('Welcome to BreatheEasy AI. Please login to continue.')
    st.stop()

# --- 6. PROTECTED DASHBOARD ---
if st.session_state.get("authentication_status"):
    
    # Helper Functions (Word, PDF, SMTP, Welcome Email)
    def create_word_doc(content):
        doc = Document(); doc.add_heading('BreatheEasy AI Report', 0)
        for line in content.split('\n'): doc.add_paragraph(line)
        bio = BytesIO(); doc.save(bio); return bio.getvalue()

    def create_pdf(content, service, city):
        pdf = FPDF(); pdf.add_page()
        try: pdf.image(logo_url, 10, 8, 30)
        except: pass
        pdf.set_font("Arial", 'B', 15); pdf.cell(80); pdf.cell(30, 10, 'BreatheEasy AI Report', 0, 0, 'C'); pdf.ln(20)
        pdf.set_font("Arial", 'I', 10); pdf.cell(0, 10, f'{service} - {city}', 0, 1, 'R'); pdf.ln(10)
        pdf.set_font("Arial", size=11); clean = content.encode('latin-1', 'ignore').decode('latin-1'); pdf.multi_cell(0, 8, txt=clean)
        return pdf.output(dest='S').encode('latin-1')

    def send_email_via_smtp(content, city):
        msg = MIMEMultipart(); msg["From"], msg["To"], msg["Subject"] = st.secrets["EMAIL_SENDER"], st.secrets["TEAM_EMAIL"], f"🚀 AI Report: {city}"
        msg.attach(MIMEText(f"Campaign ready for {city}.", "plain"))
        part = MIMEBase("application", "octet-stream"); part.set_payload(create_word_doc(content)); encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename=Report_{city}.docx"); msg.attach(part)
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"])
                server.sendmail(st.secrets["EMAIL_SENDER"], st.secrets["TEAM_EMAIL"], msg.as_string())
            return True
        except: return False

    # --- SIDEBAR ---
    with st.sidebar:
        st.header(f"Welcome, {st.session_state['name']}!")
        authenticator.logout('Logout', 'sidebar', key='unique_logout_key')
        st.divider()
        
        industry_map = {"HVAC": ["Full System Replacement", "IAQ"], "Plumbing": ["Sewer Replacement"]}
        main_cat = st.selectbox("Industry", list(industry_map.keys()))
        target_service = st.selectbox("Service", industry_map[main_cat])
        city_input = st.text_input("Target City", placeholder="e.g. Chicago, IL")
        
        st.divider()
        high_ticket = st.toggle("High-Ticket Focus", value=True)
        include_blog = st.checkbox("SEO Blog Content", value=True)
        run_button = st.button("🚀 Run AI Swarm")

    st.title("🌬️ BreatheEasy AI Launchpad")
    main_tabs = st.tabs(["🔥 Generate", "📊 History", "📱 Social Preview", "🎨 Brand Kit"])

    with main_tabs[0]:
        if run_button and city_input:
            with st.spinner("Analyzing..."):
                run_marketing_swarm(inputs={'city': city_input, 'industry': main_cat, 'service': target_service, 'premium': high_ticket, 'blog': include_blog})
                with open("final_marketing_strategy.md", "r", encoding="utf-8") as f: content = f.read()
                st.session_state['ad_copy'] = content
                st.session_state['generated'] = True
                save_to_db(st.session_state['name'], main_cat, target_service, city_input, content)

        if st.session_state.get('generated'):
            st.success("✨ Campaign Ready!")
            full_rpt = st.session_state.get('ad_copy', '')
            c1, c2, c3 = st.columns(3)
            with c1: st.download_button("📄 Word", create_word_doc(full_rpt), "Report.docx")
            with c2: st.download_button("📕 PDF", create_pdf(full_rpt, target_service, city_input), "Report.pdf")
            with c3:
                if st.button("📧 Email Team"):
                    if send_email_via_smtp(full_rpt, city_input): st.success("Sent!")
            st.markdown(full_rpt)

    with main_tabs[1]:
        conn = sqlite3.connect('leads_history.db', check_same_thread=False)
        history_df = pd.read_sql_query("SELECT date, city, service FROM leads ORDER BY id DESC", conn)
        st.dataframe(history_df, use_container_width=True)
        conn.close()

    with main_tabs[2]:
        st.header("Social Media Live Preview")
        if not st.session_state.get('generated'):
            st.info("Run a swarm to see previews of your ads.")
        else:
            ad_text = st.session_state.get('ad_copy', "Sample Ad Copy Content")
            
            p_c1, p_c2 = st.columns(2)
            
            with p_c1:
                st.subheader("Facebook Ad Mockup")
                st.markdown(f"""
                <div class="mockup-container">
                    <div class="mockup-header">
                        <img src="{logo_url}" class="profile-pic">
                        <div class="profile-name">BreatheEasy {main_cat} Services</div>
                    </div>
                    <div class="mockup-text">{ad_text[:300]}...</div>
                    <div class="mockup-image">AI Generated Visual Placeholder</div>
                    <div class="fb-btn"><span>👍 Like</span><span>💬 Comment</span><span>🔗 Share</span></div>
                </div>
                """, unsafe_allow_html=True)
            
            with p_c2:
                st.subheader("Instagram Mockup")
                st.markdown(f"""
                <div class="mockup-container" style="max-width: 400px;">
                    <div class="mockup-header">
                        <img src="{logo_url}" class="profile-pic">
                        <div class="profile-name">breatheeasy_ai</div>
                    </div>
                    <div class="mockup-image" style="height: 400px;"></div>
                    <div style="padding: 10px 0; font-size: 20px;">❤️ 💬 ✈️</div>
                    <div class="mockup-text"><b>breatheeasy_ai</b> {ad_text[:150]}... #hvac #premium</div>
                </div>
                """, unsafe_allow_html=True)

    with main_tabs[3]:
        st.header("Brand Assets")
        st.markdown(f'<div class="color-card" style="background-color: {brand_blue};">Trust Blue: {brand_blue}</div>', unsafe_allow_html=True)
        st.image(logo_url, width=200)
