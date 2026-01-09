import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
import urllib.parse
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
    div[data-testid="stStatusWidget"], .stAppDeployButton, footer, #stDecoration {{ display: none !important; }}
    .stApp {{ background-color: {brand_bg}; }}
    .stApp::before {{
        content: ""; display: block; margin: 30px auto 0;
        width: 140px; height: 140px;
        background-image: url("{logo_url}");
        background-size: contain; background-repeat: no-repeat;
    }}
    .block-container {{ padding-top: 1.5rem !important; }}
    
    /* Social Mockup Styles */
    .mockup-container {{ background: white; border: 1px solid #ddd; border-radius: 12px; padding: 15px; margin-bottom: 20px; max-width: 500px; }}
    .mockup-header {{ display: flex; align-items: center; margin-bottom: 10px; }}
    .profile-pic {{ width: 38px; height: 38px; border-radius: 50%; background: #eee; margin-right: 10px; }}
    .profile-name {{ font-weight: bold; font-size: 14px; color: #1c1e21; }}
    .mockup-text {{ font-size: 14px; line-height: 1.4; color: #1c1e21; margin-bottom: 10px; }}
    .mockup-image {{ width: 100%; height: 240px; background: #f0f2f5; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #888; border: 1px dashed #ccc; }}
    .fb-btn-row {{ display: flex; justify-content: space-around; border-top: 1px solid #eee; margin-top: 10px; padding-top: 8px; color: #606770; font-size: 13px; font-weight: 600; }}
    
    /* Brand Cards */
    .color-card {{ padding: 15px; border-radius: 8px; text-align: center; color: white; font-weight: bold; margin-bottom: 5px; }}
    </style>
""", unsafe_allow_html=True)

# --- 5. AUTHENTICATION ---
credentials = dict(st.secrets['credentials'])
authenticator = stauth.Authenticate(
    credentials, st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days']
)
authenticator.login(location='main')

if st.session_state.get("authentication_status") is False:
    st.error('Username/password is incorrect')
elif st.session_state.get("authentication_status") is None:
    st.warning('Please login to access the Launchpad')
    st.stop()

# --- 6. PROTECTED DASHBOARD ---
if st.session_state.get("authentication_status"):
    
    # --- HELPER FUNCTIONS ---
    def create_word_doc(content):
        doc = Document(); doc.add_heading('BreatheEasy AI Report', 0)
        for line in content.split('\n'): doc.add_paragraph(line)
        bio = BytesIO(); doc.save(bio); return bio.getvalue()

    def create_pdf(content, service, city):
        pdf = FPDF(); pdf.add_page()
        try: pdf.image(logo_url, 10, 8, 30)
        except: pass
        pdf.set_font("Arial", 'B', 15); pdf.cell(80); pdf.cell(30, 10, 'BreatheEasy AI Strategy', 0, 0, 'C'); pdf.ln(20)
        pdf.set_font("Arial", 'I', 10); pdf.cell(0, 10, f'{service} in {city}', 0, 1, 'R'); pdf.ln(10)
        pdf.set_font("Arial", size=11); clean = content.encode('latin-1', 'ignore').decode('latin-1'); pdf.multi_cell(0, 8, txt=clean)
        return pdf.output(dest='S').encode('latin-1')

    def send_email_via_smtp(content, city):
        msg = MIMEMultipart(); msg["From"], msg["To"], msg["Subject"] = st.secrets["EMAIL_SENDER"], st.secrets["TEAM_EMAIL"], f"🚀 AI Report: {city}"
        msg.attach(MIMEText(f"Campaign complete for {city}.", "plain"))
        part = MIMEBase("application", "octet-stream"); part.set_payload(create_word_doc(content)); encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename=Report_{city}.docx"); msg.attach(part)
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"]); server.sendmail(st.secrets["EMAIL_SENDER"], st.secrets["TEAM_EMAIL"], msg.as_string())
            return True
        except: return False

    def send_welcome_email(name, email):
        msg = MIMEMultipart("alternative"); msg["Subject"] = "Welcome to BreatheEasy AI"; msg["From"] = st.secrets["EMAIL_SENDER"]; msg["To"] = email
        html = f"<html><body><h2>Welcome {name}!</h2><p>You have been authorized on the BreatheEasy AI portal.</p></body></html>"
        msg.attach(MIMEText(html, "html"))
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"]); server.sendmail(st.secrets["EMAIL_SENDER"], email, msg.as_string())
            return True
        except: return False

    def get_push_links(content):
        encoded_text = urllib.parse.quote(content[:400])
        return {
            "X": f"https://twitter.com/intent/tweet?text={encoded_text}",
            "Buffer": f"https://buffer.com/add?text={encoded_text}",
            "Meta": "https://business.facebook.com/latest/composer"
        }

    # --- SIDEBAR ---
    with st.sidebar:
        st.header(f"Hello, {st.session_state['name']}!")
        authenticator.logout('Logout', 'sidebar')
        st.divider()
        with st.expander("🛠️ Admin: Add Member"):
            n_name = st.text_input("Name"); n_email = st.text_input("Email"); n_pw = st.text_input("Pass", type="password")
            if st.button("Authorize"):
                st.code(stauth.Hasher([n_pw]).generate()[0])
                if send_welcome_email(n_name, n_email): st.success("Email Sent!")
        
        st.divider()
        industry_map = {"HVAC": ["System Replacement", "IAQ"], "Plumbing": ["Sewer Repair", "Water Heaters"]}
        main_cat = st.selectbox("Industry", list(industry_map.keys()))
        target_service = st.selectbox("Service", industry_map[main_cat])
        city_input = st.text_input("City", placeholder="Naperville, IL")
        high_ticket = st.toggle("High-Ticket Focus", value=True)
        include_blog = st.checkbox("Include SEO Blog", value=True)
        run_button = st.button("🚀 Launch Swarm")

    st.title("🌬️ BreatheEasy AI Launchpad")
    tabs = st.tabs(["🔥 Generate", "📊 Database", "📱 Social Preview", "🎨 Brand Kit"])

    with tabs[0]:
        if run_button and city_input:
            with st.spinner("AI Swarm in progress..."):
                run_marketing_swarm({'city': city_input, 'industry': main_cat, 'service': target_service, 'premium': high_ticket, 'blog': include_blog})
                with open("final_marketing_strategy.md", "r", encoding="utf-8") as f: content = f.read()
                st.session_state['ad_copy'] = content
                st.session_state['generated'] = True
                save_to_db(st.session_state['name'], main_cat, target_service, city_input, content)

        if st.session_state.get('generated'):
            st.success("Campaign Ready!")
            copy = st.session_state['ad_copy']
            c1, c2, c3 = st.columns(3)
            with c1: st.download_button("📄 Word", create_word_doc(copy), f"{city_input}.docx")
            with c2: st.download_button("📕 PDF", create_pdf(copy, target_service, city_input), f"{city_input}.pdf")
            with c3: 
                if st.button("📧 Email Team"):
                    if send_email_via_smtp(copy, city_input): st.success("Sent!")
            st.markdown(copy)

    with tabs[1]:
        conn = sqlite3.connect('leads_history.db', check_same_thread=False)
        st.dataframe(pd.read_sql_query("SELECT date, city, service FROM leads ORDER BY id DESC", conn), use_container_width=True)
        conn.close()

    with tabs[2]:
        if st.session_state.get('generated'):
            ad_text = st.session_state['ad_copy']
            links = get_push_links(ad_text)
            
            st.subheader("🚀 One-Click Push")
            l1, l2, l3 = st.columns(3)
            l1.link_button("🔵 Meta Business", links["Meta"], use_container_width=True)
            l2.link_button("🐦 Post to X", links["X"], use_container_width=True)
            l3.link_button("⌛ Buffer", links["Buffer"], use_container_width=True)
            
            st.divider()
            st.subheader("Facebook Preview")
            st.markdown(f"""<div class="mockup-container"><div class="mockup-header"><img src="{logo_url}" class="profile-pic"><div class="profile-name">BreatheEasy {main_cat}</div></div><div class="mockup-text">{ad_text[:350]}...</div><div class="mockup-image">AI Visual Placement</div><div class="fb-btn-row"><span>👍 Like</span><span>💬 Comment</span><span>🔗 Share</span></div></div>""", unsafe_allow_html=True)
        else:
            st.info("Run a swarm to see social previews.")

    with tabs[3]:
        st.header("Brand Guidelines")
        st.markdown(f'<div class="color-card" style="background-color: {brand_blue};">Trust Blue: {brand_blue}</div>', unsafe_allow_html=True)
        st.image(logo_url, width=150)
