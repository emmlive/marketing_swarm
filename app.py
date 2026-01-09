import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
from datetime import datetime
from openai import OpenAI
from main import marketing_crew
from docx import Document
from fpdf import FPDF
from io import BytesIO

# SMTP Libraries
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- 1. PRE-IMPORT KEY MAPPING (Fixes KeyErrors) ---
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

# --- 4. SaaS WHITE-LABEL UI ---
logo_url = "https://drive.google.com/uc?export=view&id=1Jw7XreUO4yAQxUgKAZPK4sRi4mzjw_yU"
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
        width: 180px; height: 180px;
        background-image: url("{logo_url}");
        background-size: contain; background-repeat: no-repeat;
    }}
    .block-container {{ padding-top: 1.5rem !important; }}
    #MainMenu {{ visibility: hidden !important; }}
    </style>
""", unsafe_allow_html=True)

# --- 5. AUTHENTICATION CONFIGURATION ---
credentials = dict(st.secrets['credentials'])
if 'usernames' in credentials:
    credentials['usernames'] = dict(credentials['usernames'])
    for user in credentials['usernames']:
        credentials['usernames'][user] = dict(credentials['usernames'][user])

authenticator = stauth.Authenticate(
    credentials, st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days']
)

# --- 6. AUTHENTICATION UI ---
authenticator.login(location='main')

if st.session_state.get("authentication_status") is False:
    st.error('Username/password is incorrect')
elif st.session_state.get("authentication_status") is None:
    st.warning('Welcome to BreatheEasy AI. Please login to continue.')
    st.stop()

# --- 7. PROTECTED DASHBOARD ---
if st.session_state.get("authentication_status"):
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    # --- HELPER FUNCTIONS (Word, PDF, SMTP) ---
    def create_word_doc(content):
        doc = Document()
        doc.add_heading('BreatheEasy AI: Marketing Strategy', 0)
        for line in content.split('\n'):
            doc.add_paragraph(line)
        bio = BytesIO()
        doc.save(bio)
        return bio.getvalue()

    def create_pdf(content, service, city):
        pdf = FPDF()
        pdf.add_page()
        # Add Header branding
        try: pdf.image(logo_url, 10, 8, 30)
        except: pass
        pdf.set_font("Arial", 'B', 15)
        pdf.cell(80)
        pdf.cell(30, 10, 'BreatheEasy AI Strategy Report', 0, 0, 'C')
        pdf.ln(20)
        pdf.set_font("Arial", 'I', 10)
        pdf.cell(0, 10, f'Service: {service} | Location: {city} | Date: {datetime.now().strftime("%Y-%m-%d")}', 0, 1, 'R')
        pdf.ln(10)
        # Content
        pdf.set_font("Arial", size=11)
        clean_text = content.encode('latin-1', 'ignore').decode('latin-1')
        pdf.multi_cell(0, 8, txt=clean_text)
        return pdf.output(dest='S').encode('latin-1')

    def send_email_via_smtp(content, target_city):
        try:
            msg = MIMEMultipart()
            msg["From"], msg["To"], msg["Subject"] = st.secrets["EMAIL_SENDER"], st.secrets["TEAM_EMAIL"], f"🚀 New AI Report: {target_city}"
            msg.attach(MIMEText(f"High-ticket campaign ready for {target_city}. Word doc attached.", "plain"))
            part = MIMEBase("application", "octet-stream")
            part.set_payload(create_word_doc(content))
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename=Report_{target_city}.docx")
            msg.attach(part)
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"])
                server.sendmail(st.secrets["EMAIL_SENDER"], st.secrets["TEAM_EMAIL"], msg.as_string())
            return True
        except Exception as e:
            st.error(f"Email failed: {e}")
            return False

    # --- SIDEBAR ---
    with st.sidebar:
        st.header(f"Welcome, {st.session_state['name']}!")
        authenticator.logout('Logout', 'sidebar', key='unique_logout_key')
        st.divider()
        industry_map = {
            "HVAC": ["Full System Replacement", "IAQ & Filtration", "Heat Pump Upgrade"],
            "Plumbing": ["Sewer Line Replacement", "Water Heater Service"],
            "Custom": ["Manual Entry"]
        }
        main_cat = st.selectbox("Select Industry", list(industry_map.keys()))
        target_service = st.selectbox("Select Service", industry_map[main_cat]) if main_cat != "Custom" else st.text_input("Enter Service")
        city_input = st.text_input("Target City", placeholder="e.g. Naperville, IL")
        st.divider()
        high_ticket = st.toggle("Focus on High-Ticket Leads", value=True)
        include_blog = st.checkbox("Generate SEO Blog Content", value=True)
        run_button = st.button("🚀 Run AI Swarm")

    st.title("🌬️ BreatheEasy AI Launchpad")
    main_tabs = st.tabs(["🔥 Generate Strategy", "📊 Lead Database"])

    with main_tabs[0]:
        if run_button and city_input:
            with st.spinner(f"Coordinating agents for {target_service} in {city_input}..."):
                marketing_crew.kickoff(inputs={'city': city_input, 'industry': main_cat, 'service': target_service, 'premium': high_ticket, 'blog': include_blog})
                with open("final_marketing_strategy.md", "r", encoding="utf-8") as f:
                    report_content = f.read()
                st.session_state['ad_copy'] = report_content
                st.session_state['generated'] = True
                save_to_db(st.session_state['name'], main_cat, target_service, city_input, report_content)

        if st.session_state.get('generated'):
            st.success("✨ Campaign Ready!")
            full_rpt = st.session_state.get('ad_copy', '')
            c1, c2, c3 = st.columns(3)
            with c1: st.download_button("📄 Word Report", create_word_doc(full_rpt), f"{city_input}_Report.docx")
            with c2: st.download_button("📕 Branded PDF", create_pdf(full_rpt, target_service, city_input), f"{city_input}_Report.pdf")
            with c3:
                if st.button("📧 Email Team"):
                    if send_email_via_smtp(full_rpt, city_input): st.success("Sent!")
            st.divider()
            st.markdown(full_rpt)

    with main_tabs[1]:
        st.header("Lead History Database")
        conn = sqlite3.connect('leads_history.db', check_same_thread=False)
        history_df = pd.read_sql_query("SELECT date, user, industry, service, city FROM leads ORDER BY id DESC", conn)
        conn.close()
        if not history_df.empty:
            st.dataframe(history_df, use_container_width=True)
            sel_city = st.selectbox("Reload a city's report:", history_df['city'].unique())
            if st.button("Load History Content"):
                conn = sqlite3.connect('leads_history.db', check_same_thread=False)
                res = pd.read_sql_query(f"SELECT content FROM leads WHERE city='{sel_city}' LIMIT 1", conn)
                conn.close()
                st.info(f"Report for {sel_city}")
                st.markdown(res['content'][0])
        else: st.info("No leads generated yet.")
